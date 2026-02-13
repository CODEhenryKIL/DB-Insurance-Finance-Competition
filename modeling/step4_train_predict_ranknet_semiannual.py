"""
===========================================
Step4 RankNet Semiannual: 반기별 Ranking 기반 모델 학습
===========================================

이 파일의 역할:
- RankNet Loss로 순위 학습 (연간/분기 RankNet과 동일)
- 반기별 Rolling Window (6반기 = 3년)
- Cross-sectional 배치: 동일 (FiscalYear, FiscalQuarter) 쌍으로 배치 구성

핵심 개념:
1. RankNet Loss: 순위 학습, Outlier에 덜 민감
2. Cross-sectional 배치: 같은 반기 종목끼리만 비교
3. SemiannualIdx = FiscalYear * 2 + (1 if Q2, 2 if Q4)
4. Rolling Window: 6반기 학습 → 1반기 예측
5. 반기 데이터: FiscalQuarter in [2, 4] (H1=Q2, H2=Q4)

입력: data_cache_quarterly/step3_features_semiannual.csv
출력: data_cache_quarterly/step4_predictions_ranknet_semiannual.csv
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from typing import Dict, Tuple, Optional, List
from tqdm import tqdm

from config.constants import (
    RANDOM_SEED,
    INPUT_DIM, OUTPUT_DIM,
    BACKTEST_START_YEAR,
    Y_TARGET_MODE,
    # RankNet 전용 상수
    RANKNET_LEARNING_RATE,
    RANKNET_EPOCHS,
    RANKNET_BATCH_SIZE,
    RANKNET_SIGMA,
    RANKNET_WEIGHT_DECAY,
    RANKNET_PATIENCE,
    RANKNET_TARGET_IC
)
from config.paths import CACHE_DIR
from utils.logger import get_logger, log_dataframe_info
from modeling.model_ranknet import (
    LinearRankNetModel,
    RankNetLoss,
    compute_rank_ic,
    compute_ndcg
)

logger = get_logger(__name__)

# Random seed 설정
torch.manual_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# 반기별 설정
DEFAULT_TRAIN_WINDOW_SEMIANNUALS = 6  # 3년 = 6반기 (기본값)
SEMIANNUAL_CACHE_DIR = CACHE_DIR  # 반기 데이터는 data_cache 디렉토리 사용


# ===========================================
# Cross-sectional Dataset (Semiannual)
# ===========================================
class SemiannualCrossSectionalDataset(Dataset):
    """
    Cross-sectional 방식의 Semiannual Dataset
    
    동일 (FiscalYear, FiscalQuarter) 쌍의 모든 종목을 하나의 샘플로 반환
    → 반기별로 순회하며 배치 구성
    
    ⚠️ __getitem__가 반기별 전체 종목을 반환
       → DataLoader에서 batch_size=1로 설정
       → 내부에서 미니배치로 분할
    
    Parameters
    ----------
    df : DataFrame
        피처 데이터 (Ticker, FiscalYear, FiscalQuarter, SemiannualIdx, m1, m2, m3, y 포함)
    period_indices : List[int]
        학습에 사용할 SemiannualIdx 리스트
    """
    
    def __init__(self, df: pd.DataFrame, period_indices: List[int]):
        self.df = df
        self.period_indices = sorted(period_indices)
        
        # 반기별 데이터 인덱싱
        self.period_data = {}
        for period_idx in self.period_indices:
            period_df = df[df['SemiannualIdx'] == period_idx].copy()
            if len(period_df) > 0:
                X = period_df[['m1', 'm2', 'm3']].values.astype(np.float32)
                y = period_df['y'].values.astype(np.float32).reshape(-1, 1)
                tickers = period_df['Ticker'].values
                self.period_data[period_idx] = {'X': X, 'y': y, 'tickers': tickers}
        
        # 유효 반기만 유지
        self.valid_periods = [p for p in self.period_indices if p in self.period_data]
    
    def __len__(self) -> int:
        return len(self.valid_periods)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, int]:
        """
        반기별 전체 종목 반환
        
        Returns
        -------
        X : Tensor
            피처 (n_stocks, 3)
        y : Tensor
            타겟 (n_stocks, 1)
        period_idx : int
            해당 반기 인덱스
        """
        period_idx = self.valid_periods[idx]
        data = self.period_data[period_idx]
        
        X = torch.from_numpy(data['X'])
        y = torch.from_numpy(data['y'])
        
        return X, y, period_idx


def collate_semiannual_cross_sectional(batch):
    """
    Semiannual Cross-sectional 배치 collate 함수
    
    각 배치는 하나의 반기 데이터만 포함
    (DataLoader batch_size=1로 사용)
    """
    X, y, period_idx = batch[0]  # batch_size=1
    return X, y, period_idx


# ===========================================
# Semiannual RankNet Rolling Trainer
# ===========================================
class SemiannualRankNetRollingTrainer:
    """
    반기별 RankNet Rolling Window 학습
    
    연간/분기 RankNetRollingTrainer와 동일한 인터페이스
    + SemiannualIdx 기반 반기 인덱싱
    
    주요 특징:
    1. 손실함수: RankNet Loss
    2. 배치 구성: (FiscalYear, FiscalQuarter)별 Cross-sectional
    3. 평가 지표: Rank IC, NDCG
    4. Rolling Window: 6반기 (3년)
    5. 반기 데이터: FiscalQuarter in [2, 4] (H1=Q2, H2=Q4)
    """
    
    def __init__(
        self,
        train_window_semiannuals: int = DEFAULT_TRAIN_WINDOW_SEMIANNUALS,
        learning_rate: float = RANKNET_LEARNING_RATE,
        epochs: int = RANKNET_EPOCHS,
        batch_size: int = RANKNET_BATCH_SIZE,
        sigma: float = RANKNET_SIGMA
    ):
        """
        초기화
        
        Parameters
        ----------
        train_window_semiannuals : int
            학습 윈도우 크기 (반기, 기본 6 = 3년)
        learning_rate : float
            Adam optimizer learning rate
        epochs : int
            학습 epoch 수
        batch_size : int
            Cross-sectional 미니배치 크기 (메모리 고려)
        sigma : float
            RankNet 스케일링 파라미터
        """
        self.train_window_semiannuals = train_window_semiannuals
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.sigma = sigma
        
        logger.info("Semiannual RankNet Rolling Trainer 초기화 완료")
        logger.info(f"  - Train window: {train_window_semiannuals}반기 ({train_window_semiannuals // 2}년)")
        logger.info(f"  - Learning rate: {learning_rate}")
        logger.info(f"  - Epochs: {epochs}")
        logger.info(f"  - Batch size: {batch_size} (N×N 메모리 고려)")
        logger.info(f"  - RankNet sigma: {sigma}")
    
    def create_period_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        반기 인덱스 생성 (YYYY-HN → 정수)
        
        SemiannualIdx = FiscalYear * 2 + (1 if Q2, 2 if Q4)
        예: 2020-H1 (Q2) = 2020*2 + 1 = 4041
            2020-H2 (Q4) = 2020*2 + 2 = 4042
        """
        df = df.copy()
        # Q2 → 1 (H1), Q4 → 2 (H2)
        df['SemiannualIdx'] = df['FiscalYear'] * 2 + (df['FiscalQuarter'] // 4 + 1)
        return df
    
    def idx_to_year_half(self, period_idx: int) -> Tuple[int, int]:
        """SemiannualIdx → (FiscalYear, Half) 변환"""
        year = period_idx // 2
        half = period_idx % 2
        if half == 0:
            half = 2
            year -= 1
        return year, half
    
    def prepare_data(
        self,
        features_df: pd.DataFrame,
        train_start_idx: int,
        train_end_idx: int,
        test_idx: int,
        val_ratio: float = 0.2
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Train/Val/Test 데이터 준비 (반기 버전)
        
        Cross-sectional 학습을 위해 DataFrame 단위로 반환
        
        Parameters
        ----------
        features_df : DataFrame
            전체 피처 데이터 (SemiannualIdx 포함)
        train_start_idx : int
            학습 시작 SemiannualIdx
        train_end_idx : int
            학습 종료 SemiannualIdx (포함)
        test_idx : int
            테스트 SemiannualIdx
        val_ratio : float
            Validation 비율 (반기 단위)
        
        Returns
        -------
        train_df, val_df, test_df : DataFrames
        """
        # 학습 기간 데이터 (SemiannualIdx 범위)
        train_period_indices = list(range(train_start_idx, train_end_idx + 1))
        
        # Val은 마지막 반기들로 분리 (Cross-sectional 유지)
        n_val_periods = max(1, int(len(train_period_indices) * val_ratio))
        if len(train_period_indices) > n_val_periods:
            val_period_indices = train_period_indices[-n_val_periods:]
            train_period_indices = train_period_indices[:-n_val_periods]
        else:
            val_period_indices = train_period_indices
        
        train_df = features_df[
            features_df['SemiannualIdx'].isin(train_period_indices)
        ].copy()
        
        val_df = features_df[
            features_df['SemiannualIdx'].isin(val_period_indices)
        ].copy()
        
        test_df = features_df[
            features_df['SemiannualIdx'] == test_idx
        ].copy()
        
        # 결측 제거
        train_df = train_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        val_df = val_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        test_df = test_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        
        return train_df, val_df, test_df
    
    def standardize_features(
        self, 
        train_df: pd.DataFrame, 
        val_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        피처 표준화 (Train 기준)
        
        Returns
        -------
        Standardized train_df, val_df, test_df
        """
        feature_cols = ['m1', 'm2', 'm3']
        
        # Train 기준 mean/std
        X_mean = train_df[feature_cols].mean()
        X_std = train_df[feature_cols].std() + 1e-8
        
        # 표준화 적용
        train_df = train_df.copy()
        val_df = val_df.copy()
        test_df = test_df.copy()
        
        for col in feature_cols:
            train_df[col] = (train_df[col] - X_mean[col]) / X_std[col]
            val_df[col] = (val_df[col] - X_mean[col]) / X_std[col]
            test_df[col] = (test_df[col] - X_mean[col]) / X_std[col]
        
        return train_df, val_df, test_df
    
    def train_epoch(
        self,
        model: LinearRankNetModel,
        criterion: RankNetLoss,
        optimizer: optim.Optimizer,
        train_df: pd.DataFrame
    ) -> float:
        """
        한 Epoch 학습 (Cross-sectional 방식)
        
        ⚠️ 동일 (FiscalYear, FiscalQuarter) 종목끼리만 배치 구성
        ⚠️ 반기 순서는 셔플 가능 (Cross-sectional 내부만 유지)
        
        Returns
        -------
        float
            평균 손실
        """
        model.train()
        total_loss = 0.0
        n_batches = 0
        
        # 반기(SemiannualIdx) 리스트 (셔플 가능)
        period_indices = train_df['SemiannualIdx'].unique().tolist()
        np.random.shuffle(period_indices)
        
        for period_idx in period_indices:
            # 해당 반기 데이터
            period_df = train_df[train_df['SemiannualIdx'] == period_idx]
            
            if len(period_df) < 2:  # 최소 2개 종목 필요 (비교용)
                continue
            
            X = torch.from_numpy(
                period_df[['m1', 'm2', 'm3']].values.astype(np.float32)
            )
            y = torch.from_numpy(
                period_df['y'].values.astype(np.float32).reshape(-1, 1)
            )
            
            # ⚠️ Cross-sectional 내 미니배치 분할
            # 종목 수가 많으면 메모리 이슈 → 미니배치로 분할
            n_stocks = len(period_df)
            
            if n_stocks <= self.batch_size:
                # 배치 사이즈 이하면 전체 사용
                mini_batches = [(X, y)]
            else:
                # 랜덤 샘플링으로 미니배치 구성
                # ⚠️ 같은 반기 내에서만 셔플
                indices = np.arange(n_stocks)
                np.random.shuffle(indices)
                
                mini_batches = []
                for start in range(0, n_stocks, self.batch_size):
                    end = min(start + self.batch_size, n_stocks)
                    batch_idx = indices[start:end]
                    mini_batches.append((X[batch_idx], y[batch_idx]))
            
            # 미니배치별 학습
            for X_batch, y_batch in mini_batches:
                if len(X_batch) < 2:
                    continue
                
                optimizer.zero_grad()
                
                scores = model(X_batch)
                loss = criterion(scores, y_batch)
                
                if loss.requires_grad:
                    loss.backward()
                    optimizer.step()
                
                total_loss += loss.item()
                n_batches += 1
        
        return total_loss / max(n_batches, 1)
    
    def evaluate(
        self,
        model: LinearRankNetModel,
        val_df: pd.DataFrame
    ) -> Dict:
        """
        모델 평가 (반기별 Rank IC 계산)
        
        Returns
        -------
        dict
            {'avg_rank_ic': float, 'avg_ndcg': float, 'loss': float}
        """
        model.eval()
        
        rank_ics = []
        ndcgs = []
        losses = []
        
        criterion = RankNetLoss(sigma=self.sigma)
        
        period_indices = val_df['SemiannualIdx'].unique()
        
        with torch.no_grad():
            for period_idx in period_indices:
                period_df = val_df[val_df['SemiannualIdx'] == period_idx]
                
                if len(period_df) < 2:
                    continue
                
                X = torch.from_numpy(
                    period_df[['m1', 'm2', 'm3']].values.astype(np.float32)
                )
                y = torch.from_numpy(
                    period_df['y'].values.astype(np.float32).reshape(-1, 1)
                )
                
                scores = model(X)
                
                # Loss
                loss = criterion(scores, y)
                losses.append(loss.item())
                
                # Rank IC
                pred_np = scores.numpy().flatten()
                actual_np = y.numpy().flatten()
                
                rank_ic = compute_rank_ic(pred_np, actual_np)
                rank_ics.append(rank_ic)
                
                # NDCG@10%
                k = max(1, len(period_df) // 10)
                ndcg = compute_ndcg(pred_np, actual_np, k=k)
                ndcgs.append(ndcg)
        
        return {
            'avg_rank_ic': np.mean(rank_ics) if rank_ics else 0.0,
            'avg_ndcg': np.mean(ndcgs) if ndcgs else 0.0,
            'loss': np.mean(losses) if losses else 0.0
        }
    
    def train_model(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame | None = None,
        verbose: bool = False
    ) -> Tuple[LinearRankNetModel, Dict]:
        """
        모델 학습 (Early Stopping + Rank IC 모니터링)
        
        Parameters
        ----------
        train_df : DataFrame
            학습 데이터 (표준화 완료)
        val_df : DataFrame, optional
            검증 데이터 (표준화 완료)
        verbose : bool
            로그 출력 여부
        
        Returns
        -------
        model : LinearRankNetModel
            학습된 모델
        history : dict
            학습 히스토리 {'train_loss': [], 'val_rank_ic': [], ...}
        """
        model = LinearRankNetModel(input_dim=INPUT_DIM, output_dim=OUTPUT_DIM)
        criterion = RankNetLoss(sigma=self.sigma)
        optimizer = optim.Adam(
            model.parameters(), 
            lr=self.learning_rate, 
            weight_decay=RANKNET_WEIGHT_DECAY
        )
        
        # 학습 히스토리
        history = {
            'train_loss': [],
            'val_loss': [],
            'val_rank_ic': [],
            'val_ndcg': []
        }
        
        # Early stopping
        best_rank_ic = -1.0
        best_model_state = None
        patience_counter = 0
        stopped_epoch = self.epochs
        
        for epoch in range(self.epochs):
            # Train
            train_loss = self.train_epoch(model, criterion, optimizer, train_df)
            history['train_loss'].append(train_loss)
            
            # Validation
            if val_df is not None and len(val_df) > 0:
                val_metrics = self.evaluate(model, val_df)
                history['val_loss'].append(val_metrics['loss'])
                history['val_rank_ic'].append(val_metrics['avg_rank_ic'])
                history['val_ndcg'].append(val_metrics['avg_ndcg'])
                
                # Early stopping on Rank IC
                if val_metrics['avg_rank_ic'] > best_rank_ic:
                    best_rank_ic = val_metrics['avg_rank_ic']
                    best_model_state = model.state_dict().copy()
                    patience_counter = 0
                else:
                    patience_counter += 1
                
                if patience_counter >= RANKNET_PATIENCE:
                    stopped_epoch = epoch + 1
                    if verbose:
                        logger.debug(f"    Early stopping at epoch {stopped_epoch}")
                    break
                
                # 로그 (매 50 epoch)
                if verbose and (epoch + 1) % 50 == 0:
                    logger.debug(
                        f"    Epoch {epoch+1}/{self.epochs}, "
                        f"Loss: {train_loss:.4f}, "
                        f"Val RankIC: {val_metrics['avg_rank_ic']:.4f}"
                    )
        
        # Best model 복원
        if best_model_state is not None:
            model.load_state_dict(best_model_state)
        
        return model, history
    
    def run(self, window_years: int = 3) -> pd.DataFrame:
        """
        전체 Semiannual RankNet Rolling window 파이프라인
        
        Parameters
        ----------
        window_years : int
            학습 윈도우 (년 단위), 3 또는 5
        
        Returns
        -------
        DataFrame
            predictions 데이터 (Ticker, FiscalYear, FiscalQuarter, SemiannualIdx, score, y, Gap)
        """
        # 파일명 접미사 (호환성: 3년은 접미사 없음, 5년은 _5y)
        suffix = '' if window_years == 3 else f'_{window_years}y'
        
        logger.info("")
        logger.info("="*60)
        logger.info(f"  Step4 RankNet Semiannual: 반기별 Ranking 학습 시작 ({window_years}년 윈도우)")
        logger.info("="*60)
        logger.info(f"  ⭐ Loss Function: RankNet (Pairwise Ranking)")
        logger.info(f"  ⭐ Y_TARGET_MODE: {Y_TARGET_MODE}")
        logger.info(f"  ⭐ Train Window: {self.train_window_semiannuals}반기 ({window_years}년)")
        
        # 1. Step3 반기별 피처 로드
        logger.info("[1단계] Step3 반기별 피처 로드")
        features_path = SEMIANNUAL_CACHE_DIR / 'step3_features_semiannual.csv'
        
        if not features_path.exists():
            logger.error(f"❌ 반기별 피처 파일 없음: {features_path}")
            logger.error("먼저 실행: python feature_engineering/step3_feature_builder_semiannual.py")
            raise FileNotFoundError(f"반기별 피처 파일 없음: {features_path}")
        
        features_df = pd.read_csv(features_path, index_col=0)
        logger.info(f"  → Features: {len(features_df)}개")
        
        # 반기 데이터 필터링 (H1=Q2, H2=Q4만)
        features_df = features_df[features_df['FiscalQuarter'].isin([2, 4])].copy()
        logger.info(f"  → 반기 필터링 (Q2/Q4): {len(features_df)}개")
        
        # Period Index 생성
        features_df = self.create_period_index(features_df)
        
        # Y_TARGET_MODE에 따른 y 전처리
        logger.info(f"\n[1.5단계] Y 타겟 전처리 (mode={Y_TARGET_MODE})")
        
        if Y_TARGET_MODE == 'sector':
            logger.info("  → 섹터 상대 ln(PBR) 적용")
            
            sector_medians = features_df.groupby(['FiscalYear', 'FiscalQuarter', 'Sector'])['y'].median()
            sector_medians.name = 'Sector_Median'
            
            features_df = features_df.merge(
                sector_medians,
                left_on=['FiscalYear', 'FiscalQuarter', 'Sector'],
                right_index=True,
                how='left'
            )
            
            global_median = features_df.groupby(['FiscalYear', 'FiscalQuarter'])['y'].median()
            
            for idx, row in features_df.iterrows():
                if pd.isna(row['Sector_Median']) or row['Sector'] == 'Unknown':
                    key = (row['FiscalYear'], row['FiscalQuarter'])
                    if key in global_median:
                        features_df.loc[idx, 'Sector_Median'] = global_median[key]
            
            features_df['y_original'] = features_df['y']
            features_df['y'] = features_df['y_original'] - features_df['Sector_Median']
            
            logger.info(f"  → y (섹터 상대) 통계: 평균 {features_df['y'].mean():.3f}")
        else:
            logger.info("  → 단순 ln(PBR) 사용")
        
        # 2. 데이터 필터링
        valid_df = features_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        logger.info(f"  → 유효 샘플: {len(valid_df)}/{len(features_df)}")
        
        min_idx = valid_df['SemiannualIdx'].min()
        max_idx = valid_df['SemiannualIdx'].max()
        
        # 첫 테스트 시점: 최소 train_window_semiannuals 이후
        first_test_idx = min_idx + self.train_window_semiannuals
        
        # BACKTEST_START_YEAR 기준 (예: 2015년 H1 = 2015*2+1 = 4031)
        backtest_start_idx = BACKTEST_START_YEAR * 2 + 1
        first_test_idx = max(first_test_idx, backtest_start_idx)
        
        min_year, min_half = self.idx_to_year_half(min_idx)
        max_year, max_half = self.idx_to_year_half(max_idx)
        first_test_year, first_test_half = self.idx_to_year_half(first_test_idx)
        
        logger.info(f"[2단계] Rolling window 설정")
        logger.info(f"  → 데이터 범위: {min_year}H{min_half} ~ {max_year}H{max_half}")
        logger.info(f"  → 백테스트 시작: {first_test_year}H{first_test_half}")
        
        # 3. 각 반기별 학습 및 예측
        logger.info(f"[3단계] RankNet Semiannual Rolling window 학습")
        
        all_predictions = []
        metrics_history = []
        weights_history = []
        
        # 테스트할 반기 인덱스들
        test_indices = sorted(valid_df[valid_df['SemiannualIdx'] >= first_test_idx]['SemiannualIdx'].unique())
        
        for test_idx in tqdm(test_indices, desc="반기별 RankNet 예측"):
            train_start_idx = test_idx - self.train_window_semiannuals
            train_end_idx = test_idx - 1
            
            test_year, test_half = self.idx_to_year_half(test_idx)
            
            try:
                # 데이터 준비
                train_df, val_df, test_df = self.prepare_data(
                    valid_df, train_start_idx, train_end_idx, test_idx
                )
                
                if len(test_df) == 0:
                    logger.warning(f"    ⚠️ {test_year}H{test_half}: Test set 없음")
                    continue
                
                if len(train_df) < 10:
                    logger.warning(f"    ⚠️ {test_year}H{test_half}: Train set 불충분 ({len(train_df)}개)")
                    continue
                
                # 표준화
                train_df, val_df, test_df = self.standardize_features(
                    train_df, val_df, test_df
                )
                
                # 모델 학습
                model, history = self.train_model(train_df, val_df, verbose=False)
                
                # 가중치 추출
                weights = model.get_weights()
                
                # FiscalQuarter는 H1=2, H2=4
                test_quarter = 2 if test_half == 1 else 4
                
                weights_history.append({
                    'FiscalYear': test_year,
                    'FiscalQuarter': test_quarter,
                    'Half': test_half,
                    'SemiannualIdx': test_idx,
                    **weights,
                    'train_samples': len(train_df)
                })
                
                # Test set 예측
                model.eval()
                with torch.no_grad():
                    X_test = torch.from_numpy(
                        test_df[['m1', 'm2', 'm3']].values.astype(np.float32)
                    )
                    scores = model(X_test).numpy().flatten()
                
                # Rank IC 계산
                y_actual = test_df['y'].values
                rank_ic = compute_rank_ic(scores, y_actual)
                
                # Gap 계산 (score - y)
                gap = scores - y_actual
                
                # 결과 저장
                for idx, (_, row) in enumerate(test_df.iterrows()):
                    all_predictions.append({
                        'Ticker': row['Ticker'],
                        'FiscalYear': test_year,
                        'FiscalQuarter': row['FiscalQuarter'],
                        'Half': test_half,
                        'SemiannualIdx': test_idx,
                        'y': y_actual[idx],
                        'yhat': scores[idx],  # RankNet에서는 score
                        'Gap': gap[idx]
                    })
                
                # 메트릭 저장
                metrics_history.append({
                    'FiscalYear': test_year,
                    'FiscalQuarter': test_quarter,
                    'Half': test_half,
                    'SemiannualIdx': test_idx,
                    'train_samples': len(train_df),
                    'test_samples': len(test_df),
                    'rank_ic': rank_ic,
                    'final_train_loss': history['train_loss'][-1] if history['train_loss'] else None,
                    'best_val_rank_ic': max(history['val_rank_ic']) if history['val_rank_ic'] else None
                })
                
            except Exception as e:
                logger.error(f"    ❌ {test_year}H{test_half} 예측 실패: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # 4. 결과 정리
        predictions_df = pd.DataFrame(all_predictions)
        
        logger.info(f"\n[4단계] 예측 결과 요약")
        logger.info(f"  → 예측 개수: {len(predictions_df)}")
        
        # Rank IC 통계
        if metrics_history:
            avg_rank_ic = np.mean([m['rank_ic'] for m in metrics_history])
            logger.info(f"  → 평균 Rank IC: {avg_rank_ic:.4f}")
            
            if avg_rank_ic >= RANKNET_TARGET_IC:
                logger.info(f"  ✅ Rank IC 목표 달성 (>= {RANKNET_TARGET_IC})")
            else:
                logger.warning(f"  ⚠️ Rank IC 목표 미달 (< {RANKNET_TARGET_IC})")
        
        # 5. 저장
        logger.info(f"[5단계] 캐시 저장 중...")
        
        # 출력 디렉토리 생성
        SEMIANNUAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # 예측 결과 저장 (RankNet Semiannual 버전)
        output_path = SEMIANNUAL_CACHE_DIR / f'step4_predictions_ranknet_semiannual{suffix}.csv'
        predictions_df.to_csv(output_path)
        logger.info(f"  ✅ 예측 결과: {output_path}")
        
        # 가중치 히스토리
        if weights_history:
            weights_df = pd.DataFrame(weights_history)
            weights_path = SEMIANNUAL_CACHE_DIR / f'step4_weights_history_ranknet_semiannual{suffix}.csv'
            weights_df.to_csv(weights_path, index=False)
            logger.info(f"  ✅ 가중치 히스토리: {weights_path}")
        
        # 메트릭 히스토리
        if metrics_history:
            metrics_df = pd.DataFrame(metrics_history)
            metrics_path = SEMIANNUAL_CACHE_DIR / f'step4_metrics_ranknet_semiannual{suffix}.csv'
            metrics_df.to_csv(metrics_path, index=False)
            logger.info(f"  ✅ 메트릭 히스토리: {metrics_path}")
        
        logger.info("")
        logger.info("="*60)
        logger.info(f"  Step4 RankNet Semiannual 완료")
        logger.info("="*60)
        
        return predictions_df


# ===========================================
# Main 실행
# ===========================================
if __name__ == '__main__':
    """
    콘솔에서 직접 실행 시
    
    실행:
    python modeling/step4_train_predict_ranknet_semiannual.py          # 3년 윈도우 (기본)
    python modeling/step4_train_predict_ranknet_semiannual.py --window 5  # 5년 윈도우
    
    출력 파일:
    - 3년: step4_predictions_ranknet_semiannual.csv (기존 호환)
    - 5년: step4_predictions_ranknet_semiannual_5y.csv
    """
    parser = argparse.ArgumentParser(description='RankNet Semiannual Training')
    parser.add_argument('--window', '-w', type=int, default=3, choices=[3, 5],
                        help='Training window in years (default: 3)')
    args = parser.parse_args()
    
    # 윈도우를 반기 수로 변환
    train_window_semiannuals = args.window * 2  # 3년=6반기, 5년=10반기
    
    trainer = SemiannualRankNetRollingTrainer(train_window_semiannuals=train_window_semiannuals)
    predictions = trainer.run(window_years=args.window)
