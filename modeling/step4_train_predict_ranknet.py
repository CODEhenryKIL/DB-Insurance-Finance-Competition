"""
===========================================
Step4 RankNet: Ranking 기반 모델 학습
===========================================

이 파일의 역할:
- MSE 대신 RankNet Loss로 순위 학습
- Cross-sectional 배치: 동일 날짜 종목만으로 배치 구성
- Rank IC (Information Coefficient) 지표 추가

⚠️ 기존 step4_train_predict.py는 수정하지 않음
   → MSE와 RankNet 비교 시 코드 재수정 방지

핵심 개념:
1. RankNet Loss
   - "누가 누구보다 더 좋은가?"를 학습
   - 극단값(Outlier)에 덜 민감
   - 상위 20~30% 구간 예측 정확도 향상

2. Cross-sectional 배치 ⭐ 중요
   - 동일 시점(FiscalYear) 종목끼리만 비교
   - 서로 다른 연도 종목 비교는 무의미
   - shuffle=True 절대 금지 (연도 단위 셔플만)

3. 메모리 주의
   - 배치 사이즈 N → N×N 매트릭스 생성
   - 권장 배치 사이즈: 64~128

4. 수렴 속도
   - Ranking 학습은 Regression보다 느림
   - Learning Rate 낮추고, Epoch 증가
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

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
    TRAIN_WINDOW_YEARS,
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
    calculate_rank_ic,
    calculate_ndcg
)

logger = get_logger(__name__)

# Random seed 설정
torch.manual_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


# ===========================================
# Cross-sectional Dataset
# ===========================================
class CrossSectionalDataset(Dataset):
    """
    Cross-sectional 방식의 Dataset
    
    동일 FiscalYear의 모든 종목을 하나의 샘플로 반환
    → 연도별로 순회하며 배치 구성
    
    ⚠️ __getitem__이 연도별 전체 종목을 반환
       → DataLoader에서 batch_size=1로 설정
       → 내부에서 미니배치로 분할
    
    Parameters
    ----------
    df : DataFrame
        피처 데이터 (Ticker, FiscalYear, m1, m2, m3, y 포함)
    years : List[int]
        학습에 사용할 연도 리스트
    """
    
    def __init__(self, df: pd.DataFrame, years: List[int]):
        self.df = df
        self.years = sorted(years)
        
        # 연도별 데이터 인덱싱
        self.year_data = {}
        for year in self.years:
            year_df = df[df['FiscalYear'] == year].copy()
            if len(year_df) > 0:
                X = year_df[['m1', 'm2', 'm3']].values.astype(np.float32)
                y = year_df['y'].values.astype(np.float32).reshape(-1, 1)
                tickers = year_df['Ticker'].values
                self.year_data[year] = {'X': X, 'y': y, 'tickers': tickers}
        
        # 유효 연도만 유지
        self.valid_years = [y for y in self.years if y in self.year_data]
    
    def __len__(self) -> int:
        return len(self.valid_years)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, int]:
        """
        연도별 전체 종목 반환
        
        Returns
        -------
        X : Tensor
            피처 (n_stocks, 3)
        y : Tensor
            타겟 (n_stocks, 1)
        year : int
            해당 연도
        """
        year = self.valid_years[idx]
        data = self.year_data[year]
        
        X = torch.from_numpy(data['X'])
        y = torch.from_numpy(data['y'])
        
        return X, y, year


def collate_cross_sectional(batch):
    """
    Cross-sectional 배치 collate 함수
    
    각 배치는 하나의 연도 데이터만 포함
    (DataLoader batch_size=1로 사용)
    """
    X, y, year = batch[0]  # batch_size=1
    return X, y, year


# ===========================================
# RankNet Rolling Trainer
# ===========================================
class RankNetRollingTrainer:
    """
    RankNet 기반 Rolling Window 학습
    
    MSE RollingTrainer와 동일한 인터페이스 유지
    → 결과 비교 용이
    
    주요 차이점:
    1. 손실함수: MSE → RankNet Loss
    2. 배치 구성: 랜덤 셔플 → 연도별 Cross-sectional
    3. 평가 지표: R² → Rank IC, NDCG
    4. 학습 속도: Epoch 증가, LR 감소
    """
    
    def __init__(
        self,
        train_window_years: int = TRAIN_WINDOW_YEARS,
        learning_rate: float = RANKNET_LEARNING_RATE,
        epochs: int = RANKNET_EPOCHS,
        batch_size: int = RANKNET_BATCH_SIZE,
        sigma: float = RANKNET_SIGMA
    ):
        """
        초기화
        
        Parameters
        ----------
        train_window_years : int
            학습 윈도우 크기 (년)
        learning_rate : float
            Adam optimizer learning rate (MSE보다 낮게)
        epochs : int
            학습 epoch 수 (MSE보다 높게)
        batch_size : int
            Cross-sectional 미니배치 크기 (메모리 고려)
        sigma : float
            RankNet 스케일링 파라미터
        """
        self.train_window_years = train_window_years
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.sigma = sigma
        
        logger.info("RankNet Rolling Trainer 초기화 완료")
        logger.info(f"  - Train window: {train_window_years}년")
        logger.info(f"  - Learning rate: {learning_rate} (MSE보다 낮음)")
        logger.info(f"  - Epochs: {epochs} (MSE보다 높음)")
        logger.info(f"  - Batch size: {batch_size} (N×N 메모리 고려)")
        logger.info(f"  - RankNet sigma: {sigma}")
    
    def prepare_data(
        self,
        features_df: pd.DataFrame,
        train_year_start: int,
        train_year_end: int,
        test_year: int,
        val_ratio: float = 0.2
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Train/Val/Test 데이터 준비
        
        Cross-sectional 학습을 위해 DataFrame 단위로 반환
        (Tensor가 아님)
        
        Parameters
        ----------
        features_df : DataFrame
            전체 피처 데이터
        train_year_start : int
            학습 시작 연도
        train_year_end : int
            학습 종료 연도 (포함)
        test_year : int
            테스트 연도
        val_ratio : float
            Validation 비율 (연도 단위)
        
        Returns
        -------
        train_df, val_df, test_df : DataFrames
        """
        # 학습 기간 데이터
        train_years = list(range(train_year_start, train_year_end + 1))
        
        # Val은 마지막 연도로 분리 (Cross-sectional 유지)
        if len(train_years) > 1:
            val_years = [train_years[-1]]
            train_years = train_years[:-1]
        else:
            val_years = train_years
        
        pool_df = features_df[
            features_df['FiscalYear'].isin(train_years)
        ].copy()
        
        val_df = features_df[
            features_df['FiscalYear'].isin(val_years)
        ].copy()
        
        test_df = features_df[
            features_df['FiscalYear'] == test_year
        ].copy()
        
        # 결측 제거
        pool_df = pool_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        val_df = val_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        test_df = test_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        
        return pool_df, val_df, test_df
    
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
        
        ⚠️ 동일 FiscalYear 종목끼리만 배치 구성
        ⚠️ 연도 순서는 셔플 가능 (Cross-sectional 내부만 유지)
        
        Returns
        -------
        float
            평균 손실
        """
        model.train()
        total_loss = 0.0
        n_batches = 0
        
        # 연도 리스트 (셔플 가능)
        years = train_df['FiscalYear'].unique().tolist()
        np.random.shuffle(years)
        
        for year in years:
            # 해당 연도 데이터
            year_df = train_df[train_df['FiscalYear'] == year]
            
            if len(year_df) < 2:  # 최소 2개 종목 필요 (비교용)
                continue
            
            X = torch.from_numpy(
                year_df[['m1', 'm2', 'm3']].values.astype(np.float32)
            )
            y = torch.from_numpy(
                year_df['y'].values.astype(np.float32).reshape(-1, 1)
            )
            
            # ⚠️ Cross-sectional 내 미니배치 분할
            # 종목 수가 많으면 메모리 이슈 → 미니배치로 분할
            n_stocks = len(year_df)
            
            if n_stocks <= self.batch_size:
                # 배치 사이즈 이하면 전체 사용
                mini_batches = [(X, y)]
            else:
                # 랜덤 샘플링으로 미니배치 구성
                # ⚠️ 같은 연도 내에서만 셔플
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
        모델 평가 (연도별 Rank IC 계산)
        
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
        
        years = val_df['FiscalYear'].unique()
        
        with torch.no_grad():
            for year in years:
                year_df = val_df[val_df['FiscalYear'] == year]
                
                if len(year_df) < 2:
                    continue
                
                X = torch.from_numpy(
                    year_df[['m1', 'm2', 'm3']].values.astype(np.float32)
                )
                y = torch.from_numpy(
                    year_df['y'].values.astype(np.float32).reshape(-1, 1)
                )
                
                scores = model(X)
                
                # Loss
                loss = criterion(scores, y)
                losses.append(loss.item())
                
                # Rank IC
                pred_np = scores.numpy().flatten()
                actual_np = y.numpy().flatten()
                
                rank_ic = calculate_rank_ic(pred_np, actual_np)
                rank_ics.append(rank_ic)
                
                # NDCG@10%
                k = max(1, len(year_df) // 10)
                ndcg = calculate_ndcg(pred_np, actual_np, k=k)
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
    
    def run(self) -> pd.DataFrame:
        """
        전체 RankNet Rolling window 파이프라인
        
        Returns
        -------
        DataFrame
            predictions 데이터 (Ticker, FiscalYear, score, y, Gap)
        """
        logger.info("")
        logger.info("="*60)
        logger.info("  Step4 RankNet: Ranking 기반 학습 시작")
        logger.info("="*60)
        logger.info(f"  ⭐ Loss Function: RankNet (Pairwise Ranking)")
        logger.info(f"  ⭐ Y_TARGET_MODE: {Y_TARGET_MODE}")
        
        # 1. Step3 피처 로드
        logger.info("[1단계] Step3 피처 로드")
        features_df = pd.read_csv(CACHE_DIR / 'step3_features_annual.csv', index_col=0)
        logger.info(f"  → Features: {len(features_df)}개")
        
        # Y_TARGET_MODE에 따른 y 전처리 (기존 로직 동일)
        logger.info(f"\n[1.5단계] Y 타겟 전처리 (mode={Y_TARGET_MODE})")
        
        if Y_TARGET_MODE == 'sector':
            logger.info("  → 섹터 상대 ln(PBR) 적용")
            
            sector_medians = features_df.groupby(['FiscalYear', 'Sector'])['y'].median()
            sector_medians.name = 'Sector_Median'
            
            features_df = features_df.merge(
                sector_medians,
                left_on=['FiscalYear', 'Sector'],
                right_index=True,
                how='left'
            )
            
            global_median_by_year = features_df.groupby('FiscalYear')['y'].median()
            
            for idx, row in features_df.iterrows():
                if pd.isna(row['Sector_Median']) or row['Sector'] == 'Unknown':
                    year = row['FiscalYear']
                    features_df.loc[idx, 'Sector_Median'] = global_median_by_year[year]
            
            features_df['y_original'] = features_df['y']
            features_df['y'] = features_df['y_original'] - features_df['Sector_Median']
            
            logger.info(f"  → y (섹터 상대) 통계: 평균 {features_df['y'].mean():.3f}")
        else:
            logger.info("  → 단순 ln(PBR) 사용")
        
        # 2. 데이터 필터링
        valid_df = features_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        logger.info(f"  → 유효 샘플: {len(valid_df)}/{len(features_df)}")
        
        min_year = valid_df['FiscalYear'].min()
        max_year = valid_df['FiscalYear'].max()
        first_test_year = max(BACKTEST_START_YEAR, min_year + self.train_window_years)
        
        logger.info(f"[2단계] Rolling window 설정")
        logger.info(f"  → 데이터 범위: FY{min_year} ~ FY{max_year}")
        logger.info(f"  → 백테스트 시작: FY{first_test_year}")
        
        # 3. 각 연도별 학습 및 예측
        logger.info(f"[3단계] RankNet Rolling window 학습")
        
        all_predictions = []
        metrics_history = []
        weights_history = []
        
        for test_year in range(first_test_year, max_year + 1):
            train_year_start = test_year - self.train_window_years
            train_year_end = test_year - 1
            
            logger.info(f"\n  FY{test_year} 예측:")
            logger.info(f"    Train: FY{train_year_start}-FY{train_year_end}")
            
            try:
                # 데이터 준비
                train_df, val_df, test_df = self.prepare_data(
                    valid_df, train_year_start, train_year_end, test_year
                )
                
                if len(test_df) == 0:
                    logger.warning(f"    ⚠️  FY{test_year}: Test set 없음")
                    continue
                
                # 표준화
                train_df, val_df, test_df = self.standardize_features(
                    train_df, val_df, test_df
                )
                
                logger.info(f"    Train: {len(train_df)}개 (연도: {train_df['FiscalYear'].nunique()})")
                
                # 모델 학습
                model, history = self.train_model(train_df, val_df, verbose=False)
                
                # 가중치 추출
                weights = model.get_weights()
                weights_history.append({
                    'FiscalYear': test_year,
                    **weights,
                    'train_samples': len(train_df)
                })
                logger.info(f"    가중치: m1={weights['w1']:.3f}, m2={weights['w2']:.3f}, m3={weights['w3']:.3f}")
                
                # Test set 예측
                model.eval()
                with torch.no_grad():
                    X_test = torch.from_numpy(
                        test_df[['m1', 'm2', 'm3']].values.astype(np.float32)
                    )
                    scores = model(X_test).numpy().flatten()
                
                # Rank IC 계산
                y_actual = test_df['y'].values
                rank_ic = calculate_rank_ic(scores, y_actual)
                
                # Gap 계산 (score - y)
                # RankNet에서 score는 상대적 순위 점수이므로
                # Gap = score - y 로 유지 (해석 일관성)
                gap = scores - y_actual
                
                # 결과 저장
                for idx, (_, row) in enumerate(test_df.iterrows()):
                    all_predictions.append({
                        'Ticker': row['Ticker'],
                        'FiscalYear': test_year,
                        'y': y_actual[idx],
                        'yhat': scores[idx],  # RankNet에서는 score
                        'Gap': gap[idx]
                    })
                
                # 메트릭 저장
                metrics_history.append({
                    'FiscalYear': test_year,
                    'train_samples': len(train_df),
                    'test_samples': len(test_df),
                    'rank_ic': rank_ic,
                    'final_train_loss': history['train_loss'][-1] if history['train_loss'] else None,
                    'best_val_rank_ic': max(history['val_rank_ic']) if history['val_rank_ic'] else None
                })
                
                logger.info(f"    ✅ 예측 완료: {len(test_df)}개")
                logger.info(f"    📊 Rank IC: {rank_ic:.4f} " + 
                           ("✅" if rank_ic >= 0.03 else "⚠️ (목표: 0.03+)"))
                
            except Exception as e:
                logger.error(f"    ❌ FY{test_year} 예측 실패: {e}")
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
            
            if avg_rank_ic >= 0.03:
                logger.info("  ✅ Rank IC 목표 달성 (>= 0.03)")
            else:
                logger.warning("  ⚠️ Rank IC 목표 미달 (< 0.03)")
        
        # 5. 저장
        logger.info(f"[5단계] 캐시 저장 중...")
        
        # 예측 결과 저장 (RankNet 버전)
        output_path = CACHE_DIR / 'step4_predictions_ranknet.csv'
        predictions_df.to_csv(output_path)
        logger.info(f"  ✅ 예측 결과: {output_path}")
        
        # 가중치 히스토리
        if weights_history:
            weights_df = pd.DataFrame(weights_history)
            weights_path = CACHE_DIR / 'step4_weights_history_ranknet.csv'
            weights_df.to_csv(weights_path, index=False)
            logger.info(f"  ✅ 가중치 히스토리: {weights_path}")
        
        # 메트릭 히스토리
        if metrics_history:
            metrics_df = pd.DataFrame(metrics_history)
            metrics_path = CACHE_DIR / 'step4_metrics_ranknet.csv'
            metrics_df.to_csv(metrics_path, index=False)
            logger.info(f"  ✅ 메트릭 히스토리: {metrics_path}")
        
        logger.info("")
        logger.info("="*60)
        logger.info(f"  Step4 RankNet 완료")
        logger.info("="*60)
        
        return predictions_df


# ===========================================
# Main 실행
# ===========================================
if __name__ == '__main__':
    """
    콘솔에서 직접 실행 시
    
    실행:
    python modeling/step4_train_predict_ranknet.py
    
    출력 파일:
    - data_cache/step4_predictions_ranknet.csv
    - data_cache/step4_weights_history_ranknet.csv
    - data_cache/step4_metrics_ranknet.csv
    """
    trainer = RankNetRollingTrainer()
    predictions = trainer.run()
