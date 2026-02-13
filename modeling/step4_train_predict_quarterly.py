"""
===========================================
Step4: 모델 학습 및 예측 (분기별 Rolling Window)
===========================================

분기별 리밸런싱을 위한 모델 학습 및 예측
- 분기별 데이터 사용 (step3_features_quarterly.csv)
- Rolling window: 12분기 (3년) 학습 → 1분기 예측
- Gap 계산: Gap = yhat - y

핵심 차이점 (연간 대비):
- window: 분기 단위 (12분기 = 3년)
- 예측 주기: 매 분기 (1/4/7/10월)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import Dict, Tuple, Optional
from tqdm import tqdm

from config.constants import (
    RANDOM_SEED,
    INPUT_DIM, OUTPUT_DIM,
    LEARNING_RATE, EPOCHS,
    WEIGHT_DECAY,
    EARLY_STOPPING_PATIENCE,
    Y_TARGET_MODE,
    BACKTEST_START_YEAR
)
from config.paths import CACHE_DIR
from utils.logger import get_logger, log_dataframe_info
from modeling.model import LinearPBRModel

logger = get_logger(__name__)

torch.manual_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# 분기용 설정
TRAIN_WINDOW_QUARTERS = 12  # 3년 = 12분기


class QuarterlyRollingTrainer:
    """
    분기별 Rolling window 모델 학습 및 예측
    """
    
    def __init__(
        self,
        train_window_quarters: int = TRAIN_WINDOW_QUARTERS,
        learning_rate: float = LEARNING_RATE,
        epochs: int = EPOCHS
    ):
        self.train_window_quarters = train_window_quarters
        self.learning_rate = learning_rate
        self.epochs = epochs
        
        logger.info("Quarterly Rolling Trainer 초기화 완료")
        logger.info(f"  - Train window: {train_window_quarters}분기")
        logger.info(f"  - Learning rate: {learning_rate}")
        logger.info(f"  - Epochs: {epochs}")
    
    def create_period_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """분기 인덱스 생성 (YYYY-QN → 정수)"""
        df = df.copy()
        df['PeriodIdx'] = df['FiscalYear'] * 4 + df['FiscalQuarter']
        return df
    
    def prepare_data(
        self,
        features_df: pd.DataFrame,
        train_start_idx: int,
        train_end_idx: int,
        test_idx: int,
        val_ratio: float = 0.2
    ) -> Tuple:
        """
        Train/Val/Test 데이터 준비 (분기 버전)
        """
        # 학습 기간 데이터
        pool_df = features_df[
            (features_df['PeriodIdx'] >= train_start_idx) &
            (features_df['PeriodIdx'] <= train_end_idx)
        ].copy()
        
        # Test set
        test_df = features_df[features_df['PeriodIdx'] == test_idx].copy()
        
        # 결측 제거
        pool_df = pool_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        test_df = test_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        
        if len(pool_df) == 0:
            raise ValueError(f"Train pool이 비어있습니다")
        
        if len(test_df) == 0:
            return None, None, None, None, None, None, pool_df, test_df
        
        # 섹터별 층화 추출
        ticker_sector = pool_df.groupby('Ticker')['Sector'].last().to_dict()
        
        sector_tickers = {}
        for ticker, sector in ticker_sector.items():
            if sector not in sector_tickers:
                sector_tickers[sector] = []
            sector_tickers[sector].append(ticker)
        
        np.random.seed(RANDOM_SEED)
        train_tickers = set()
        val_tickers = set()
        
        for sector, tickers in sector_tickers.items():
            tickers = np.array(tickers)
            np.random.shuffle(tickers)
            n_val = max(1, int(len(tickers) * val_ratio))
            val_tickers.update(tickers[:n_val])
            train_tickers.update(tickers[n_val:])
        
        train_df = pool_df[pool_df['Ticker'].isin(train_tickers)].copy()
        val_df = pool_df[pool_df['Ticker'].isin(val_tickers)].copy()
        
        # X, y 분리
        X_train = train_df[['m1', 'm2', 'm3']].values.astype(np.float32)
        y_train = train_df['y'].values.astype(np.float32).reshape(-1, 1)
        
        X_val = val_df[['m1', 'm2', 'm3']].values.astype(np.float32)
        y_val = val_df['y'].values.astype(np.float32).reshape(-1, 1)
        
        X_test = test_df[['m1', 'm2', 'm3']].values.astype(np.float32)
        y_test = test_df['y'].values.astype(np.float32).reshape(-1, 1)
        
        # Standardization
        X_mean = X_train.mean(axis=0)
        X_std = X_train.std(axis=0) + 1e-8
        
        X_train_norm = (X_train - X_mean) / X_std
        X_val_norm = (X_val - X_mean) / X_std
        X_test_norm = (X_test - X_mean) / X_std
        
        return (
            torch.from_numpy(X_train_norm),
            torch.from_numpy(y_train),
            torch.from_numpy(X_val_norm),
            torch.from_numpy(y_val),
            torch.from_numpy(X_test_norm),
            torch.from_numpy(y_test),
            train_df,
            test_df
        )
    
    def train_model(
        self,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_val: torch.Tensor = None,
        y_val: torch.Tensor = None,
        verbose: bool = False
    ) -> LinearPBRModel:
        """모델 학습"""
        model = LinearPBRModel(input_dim=INPUT_DIM, output_dim=OUTPUT_DIM)
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=self.learning_rate, weight_decay=WEIGHT_DECAY)
        
        model.train()
        
        best_val_loss = float('inf')
        best_model_state = None
        patience_counter = 0
        
        for epoch in range(self.epochs):
            y_pred = model(X_train)
            loss = criterion(y_pred, y_train)
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            if X_val is not None and y_val is not None:
                model.eval()
                with torch.no_grad():
                    val_pred = model(X_val)
                    val_loss = criterion(val_pred, y_val).item()
                model.train()
                
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    best_model_state = model.state_dict().copy()
                    patience_counter = 0
                else:
                    patience_counter += 1
                
                if patience_counter >= EARLY_STOPPING_PATIENCE:
                    break
        
        if best_model_state is not None:
            model.load_state_dict(best_model_state)
        
        return model
    
    def run(self) -> pd.DataFrame:
        """
        분기별 Rolling window 학습 및 예측 파이프라인
        """
        logger.info("")
        logger.info("="*60)
        logger.info("  Step4 (Quarterly): 모델 학습 및 예측 시작")
        logger.info("="*60)
        logger.info(f"  ⭐ Y_TARGET_MODE: {Y_TARGET_MODE}")
        
        # 1. 분기별 피처 로드
        logger.info("[1단계] Step3 분기별 피처 로드")
        features_path = CACHE_DIR / 'step3_features_quarterly.csv'
        
        if not features_path.exists():
            logger.error(f"❌ 분기별 피처 파일 없음: {features_path}")
            logger.error("먼저 실행: python feature_engineering/step3_feature_builder_quarterly.py")
            raise FileNotFoundError(f"분기별 피처 파일 없음: {features_path}")
        
        features_df = pd.read_csv(features_path, index_col=0)
        logger.info(f"  → Features: {len(features_df)}개")
        
        # Period Index 생성
        features_df = self.create_period_index(features_df)
        
        # Y_TARGET_MODE 처리
        if Y_TARGET_MODE == 'sector':
            logger.info("[1.5단계] 섹터 상대 y 계산")
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
        
        # 2. 유효 데이터 필터링
        valid_df = features_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        logger.info(f"  → 유효 샘플: {len(valid_df)}/{len(features_df)}")
        
        # 분기 범위
        min_idx = valid_df['PeriodIdx'].min()
        max_idx = valid_df['PeriodIdx'].max()
        
        first_test_idx = min_idx + self.train_window_quarters
        # BACKTEST_START_YEAR 기준 (예: 2015년 Q1 = 2015*4+1 = 8061)
        backtest_start_idx = BACKTEST_START_YEAR * 4 + 1
        first_test_idx = max(first_test_idx, backtest_start_idx)
        
        logger.info(f"[2단계] Rolling window 설정")
        logger.info(f"  → 분기 범위: {min_idx} ~ {max_idx}")
        logger.info(f"  → 첫 테스트: {first_test_idx}")
        
        # 3. 각 분기별 학습 및 예측
        logger.info(f"[3단계] Rolling window 학습 및 예측")
        
        all_predictions = []
        weights_history = []
        
        test_indices = sorted(valid_df[valid_df['PeriodIdx'] >= first_test_idx]['PeriodIdx'].unique())
        
        for test_idx in tqdm(test_indices, desc="분기별 예측"):
            train_start_idx = test_idx - self.train_window_quarters
            train_end_idx = test_idx - 1
            
            try:
                result = self.prepare_data(
                    valid_df,
                    train_start_idx,
                    train_end_idx,
                    test_idx
                )
                
                if result[0] is None:
                    continue
                
                X_train, y_train, X_val, y_val, X_test, y_test, train_df, test_df = result
                
                # 모델 학습
                model = self.train_model(X_train, y_train, X_val, y_val, verbose=False)
                
                # 가중치 추출
                weights = model.linear.weight.detach().numpy().flatten()
                bias = model.linear.bias.detach().numpy().item()
                
                test_year = test_idx // 4
                test_quarter = test_idx % 4
                if test_quarter == 0:
                    test_quarter = 4
                    test_year -= 1
                
                weights_history.append({
                    'FiscalYear': test_year,
                    'FiscalQuarter': test_quarter,
                    'PeriodIdx': test_idx,
                    'w_m1': weights[0],
                    'w_m2': weights[1],
                    'w_m3': weights[2],
                    'bias': bias,
                    'train_samples': len(train_df)
                })
                
                # 예측
                model.eval()
                with torch.no_grad():
                    yhat_test = model(X_test).numpy().flatten()
                
                y_actual = y_test.numpy().flatten()
                gap = yhat_test - y_actual
                
                for i, (_, row) in enumerate(test_df.iterrows()):
                    all_predictions.append({
                        'Ticker': row['Ticker'],
                        'FiscalYear': row['FiscalYear'],
                        'FiscalQuarter': row['FiscalQuarter'],
                        'PeriodIdx': test_idx,
                        'y': y_actual[i],
                        'yhat': yhat_test[i],
                        'Gap': gap[i]
                    })
                
            except Exception as e:
                logger.warning(f"  ⚠️ Period {test_idx} 예측 실패: {e}")
                continue
        
        # 4. 결과 정리
        predictions_df = pd.DataFrame(all_predictions)
        
        logger.info(f"\n[4단계] 예측 결과 요약")
        logger.info(f"  → 예측 개수: {len(predictions_df)}")
        if len(predictions_df) > 0:
            logger.info(f"  → Gap 통계: 평균 {predictions_df['Gap'].mean():.4f}, 표준편차 {predictions_df['Gap'].std():.4f}")
        
        # 5. 저장
        logger.info(f"[5단계] 저장")
        output_path = CACHE_DIR / 'step4_predictions_quarterly.csv'
        predictions_df.to_csv(output_path)
        logger.info(f"✅ 예측 결과 저장: {output_path}")
        
        if weights_history:
            weights_df = pd.DataFrame(weights_history)
            weights_path = CACHE_DIR / 'step4_weights_history_quarterly.csv'
            weights_df.to_csv(weights_path, index=False)
            logger.info(f"✅ 가중치 히스토리 저장: {weights_path}")
        
        logger.info("")
        logger.info("="*60)
        logger.info("  Step4 (Quarterly) 완료")
        logger.info("="*60)
        
        return predictions_df


if __name__ == '__main__':
    trainer = QuarterlyRollingTrainer()
    predictions = trainer.run()
