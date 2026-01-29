"""
===========================================
Step4: 모델 학습 및 예측 (Rolling Window)
===========================================

이 파일의 역할:
- Step3 피처 데이터로 매년 모델 학습 및 예측
- Rolling window 방식: 과거 5년 학습 → 다음 1년 예측
- Standardization (rolling mean/std)
- Gap 계산: Gap = yhat - y

핵심 개념:
1. Rolling Window
   - Train: 과거 5년 (2010-2014)
   - Test: 다음 1년 (2015)
   - 매년 1년씩 shift

2. Standardization
   - Train set mean/std로 X 표준화
   - Test set도 동일한 mean/std 사용 (data leakage 방지)

3. Gap
   - Gap > 0: 모델이 과대평가 (롱 대상)
   - Gap < 0: 모델이 과소평가
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
from typing import Dict, Tuple, Optional
from tqdm import tqdm

from config.constants import (
    RANDOM_SEED,
    INPUT_DIM, OUTPUT_DIM,
    LEARNING_RATE, EPOCHS,
    TRAIN_WINDOW_YEARS,
    BACKTEST_START_YEAR
)
from config.paths import CACHE_DIR
from utils.logger import get_logger, log_dataframe_info
from modeling.model import LinearPBRModel

logger = get_logger(__name__)

# Random seed 설정
torch.manual_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


class RollingTrainer:
    """
    Rolling window 방식 모델 학습 및 예측
    
    매년:
    1. 과거 N년 데이터로 학습
    2. 다음 해 yhat 예측
    3. Gap = yhat - y 계산
    """
    
    def __init__(
        self,
        train_window_years: int = TRAIN_WINDOW_YEARS,
        learning_rate: float = LEARNING_RATE,
        epochs: int = EPOCHS
    ):
        """
        초기화
        
        Parameters
        ----------
        train_window_years : int
            학습 윈도우 크기 (년)
        learning_rate : float
            Adam optimizer learning rate
        epochs : int
            학습 epoch 수
        """
        self.train_window_years = train_window_years
        self.learning_rate = learning_rate
        self.epochs = epochs
        
        logger.info("Rolling Trainer 초기화 완료")
        logger.info(f"  - Train window: {train_window_years}년")
        logger.info(f"  - Learning rate: {learning_rate}")
        logger.info(f"  - Epochs: {epochs}")
    
    def prepare_data(
        self,
        features_df: pd.DataFrame,
        train_year_start: int,
        train_year_end: int,
        test_year: int
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, pd.DataFrame, pd.DataFrame]:
        """
        Train/Test 데이터 준비
        
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
        
        Returns
        -------
        X_train, y_train, X_test, y_test, train_df, test_df
        """
        # Train set
        train_df = features_df[
            (features_df['FiscalYear'] >= train_year_start) &
            (features_df['FiscalYear'] <= train_year_end)
        ].copy()
        
        # Test set
        test_df = features_df[features_df['FiscalYear'] == test_year].copy()
        
        # 결측 제거
        train_df = train_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        test_df = test_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        
        if len(train_df) == 0:
            raise ValueError(f"Train set이 비어있습니다 ({train_year_start}-{train_year_end})")
        
        if len(test_df) == 0:
            logger.warning(f"Test set이 비어있습니다 (FY{test_year})")
            return None, None, None, None, train_df, test_df
        
        # X, y 분리
        X_train = train_df[['m1', 'm2', 'm3']].values.astype(np.float32)
        y_train = train_df['y'].values.astype(np.float32).reshape(-1, 1)
        
        X_test = test_df[['m1', 'm2', 'm3']].values.astype(np.float32)
        y_test = test_df['y'].values.astype(np.float32).reshape(-1, 1)
        
        # Standardization (Train 기준)
        X_mean = X_train.mean(axis=0)
        X_std = X_train.std(axis=0) + 1e-8  # 0 방지
        
        X_train_norm = (X_train - X_mean) / X_std
        X_test_norm = (X_test - X_mean) / X_std
        
        # Tensor 변환
        X_train_tensor = torch.from_numpy(X_train_norm)
        y_train_tensor = torch.from_numpy(y_train)
        X_test_tensor = torch.from_numpy(X_test_norm)
        y_test_tensor = torch.from_numpy(y_test)
        
        return X_train_tensor, y_train_tensor, X_test_tensor, y_test_tensor, train_df, test_df
    
    def train_model(
        self,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        verbose: bool = False
    ) -> LinearPBRModel:
        """
        모델 학습
        
        Parameters
        ----------
        X_train : Tensor
            학습 입력 (N, 3)
        y_train : Tensor
            학습 타겟 (N, 1)
        verbose : bool
            학습 로그 출력 여부
        
        Returns
        -------
        LinearPBRModel
            학습된 모델
        """
        model = LinearPBRModel(input_dim=INPUT_DIM, output_dim=OUTPUT_DIM)
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=self.learning_rate)
        
        model.train()
        
        for epoch in range(self.epochs):
            # Forward pass
            y_pred = model(X_train)
            loss = criterion(y_pred, y_train)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # 로그 (매 100 epoch)
            if verbose and (epoch + 1) % 100 == 0:
                logger.debug(f"    Epoch {epoch+1}/{self.epochs}, Loss: {loss.item():.4f}")
        
        return model
    
    def run(self) -> pd.DataFrame:
        """
        전체 Rolling window 학습 및 예측 파이프라인
        
        1. Step3 피처 로드
        2. 각 연도별로 rolling window 학습
        3. 예측 및 Gap 계산
        4. 결과 저장
        
        Returns
        -------
        DataFrame
            predictions 데이터
        """
        logger.info("")
        logger.info("="*60)
        logger.info("  Step4: 모델 학습 및 예측 시작")
        logger.info("="*60)
        
        # 1. Step3 피처 로드
        logger.info("[1단계] Step3 피처 로드")
        features_df = pd.read_csv(CACHE_DIR / 'step3_features_annual.csv', index_col=0)
        logger.info(f"  → Features: {len(features_df)}개")
        log_dataframe_info(logger, features_df, "Features")
        
        # ⭐ 개선 2: 섹터 상대 PBR 전처리
        logger.info("\n[1.5단계] 섹터 상대 PBR 변환")
        logger.info("  y = ln(PBR) → y_relative = ln(PBR) - Sector_Median")
        
        # (1) 전체 유니버스 median (fallback용)
        global_median_by_year = features_df.groupby('FiscalYear')['y'].median()
        logger.info(f"  → 전체 유니버스 연도별 Median 계산 완료")
        
        # (2) 섹터별 median 계산
        sector_medians = features_df.groupby(['FiscalYear', 'Sector'])['y'].median()
        sector_medians.name = 'Sector_Median'
        
        # (3) 원본 df에 merge
        features_df = features_df.merge(
            sector_medians,
            left_on=['FiscalYear', 'Sector'],
            right_index=True,
            how='left'
        )
        
        # (4) Unknown 또는 결측 시 Global median 사용
        for idx, row in features_df.iterrows():
            if pd.isna(row['Sector_Median']) or row['Sector'] == 'Unknown':
                year = row['FiscalYear']
                features_df.loc[idx, 'Sector_Median'] = global_median_by_year[year]
        
        # (5) 상대 PBR 계산
        features_df['y_original'] = features_df['y']  # 백업
        features_df['y'] = features_df['y_original'] - features_df['Sector_Median']
        
        logger.info(f"  → 섹터 상대 PBR 변환 완료")
        logger.info(f"    y 평균: {features_df['y'].mean():.3f} (0에 가까워야 정상)")
        logger.info(f"    y 표준편차: {features_df['y'].std():.3f}")
        
        # 2. 데이터 필터링
        # 유효한 샘플 (m1, m2, m3, y 모두 있음)
        valid_df = features_df.dropna(subset=['m1', 'm2', 'm3', 'y'])
        logger.info(f"  → 유효 샘플: {len(valid_df)}/{len(features_df)} ({len(valid_df)/len(features_df)*100:.1f}%)")
        
        # 2. 예측 가능한 연도 확인
        min_year = valid_df['FiscalYear'].min()
        max_year = valid_df['FiscalYear'].max()
        
        # 백테스트 시작 연도 (2015년 고정 - XBRL 안정화 및 m1 데이터 충분)
        first_test_year = max(BACKTEST_START_YEAR, min_year + self.train_window_years)
        
        logger.info(f"[2단계] Rolling window 설정")
        logger.info(f"  → 데이터 범위: FY{min_year} ~ FY{max_year}")
        logger.info(f"  → 백테스트 시작: FY{first_test_year} (고정: {BACKTEST_START_YEAR})")
        logger.info(f"  → 첫 번째 Test: FY{first_test_year} (Train: FY{first_test_year - self.train_window_years}-FY{first_test_year-1})")
        logger.info(f"  → 마지막 Test: FY{max_year}")
        
        # 3. 각 연도별 학습 및 예측
        logger.info(f"[3단계] Rolling window 학습 및 예측")
        
        all_predictions = []
        weights_history = []  # ⭐ 가중치 히스토리 추가
        
        for test_year in range(first_test_year, max_year + 1):
            train_year_start = test_year - self.train_window_years
            train_year_end = test_year - 1
            
            logger.info(f"\n  FY{test_year} 예측:")
            logger.info(f"    Train: FY{train_year_start}-FY{train_year_end}")
            
            try:
                # 데이터 준비
                result = self.prepare_data(
                    valid_df,
                    train_year_start,
                    train_year_end,
                    test_year
                )
                
                if result[0] is None:
                    logger.warning(f"    ⚠️  FY{test_year}: Test set 없음 (스킵)")
                    continue
                
                X_train, y_train, X_test, y_test, train_df, test_df = result
                
                logger.info(f"    Train: {len(train_df)}개, Test: {len(test_df)}개")
                
                # 모델 학습
                model = self.train_model(X_train, y_train, verbose=False)
                
                # ⭐ 가중치 추출 및 기록
                weights = model.linear.weight.detach().numpy().flatten()
                bias = model.linear.bias.detach().numpy().item()
                weights_history.append({
                    'FiscalYear': test_year,
                    'w_m1': weights[0],
                    'w_m2': weights[1],
                    'w_m3': weights[2],
                    'bias': bias,
                    'train_samples': len(train_df)
                })
                logger.info(f"    가중치: m1={weights[0]:.3f}, m2={weights[1]:.3f}, m3={weights[2]:.3f}")
                
                # 예측
                model.eval()
                with torch.no_grad():
                    yhat_test = model(X_test).numpy().flatten()
                
                # Gap 계산
                y_actual = y_test.numpy().flatten()
                gap = yhat_test - y_actual
                
                # 결과 저장
                for idx, (_, row) in enumerate(test_df.iterrows()):
                    all_predictions.append({
                        'Ticker': row['Ticker'],
                        'FiscalYear': test_year,
                        'y': y_actual[idx],
                        'yhat': yhat_test[idx],
                        'Gap': gap[idx]
                    })
                
                logger.info(f"    ✅ 예측 완료: {len(test_df)}개")
                logger.info(f"    Gap 평균: {gap.mean():.4f}, Gap 표준편차: {gap.std():.4f}")
                
            except Exception as e:
                logger.error(f"    ❌ FY{test_year} 예측 실패: {e}")
                continue
        
        # 4. 결과 정리
        predictions_df = pd.DataFrame(all_predictions)
        
        logger.info(f"\n[4단계] 예측 결과 요약")
        logger.info(f"  → 예측 개수: {len(predictions_df)}")
        logger.info(f"  → 연도 범위: FY{predictions_df['FiscalYear'].min()}-FY{predictions_df['FiscalYear'].max()}")
        logger.info(f"  → Gap 통계:")
        logger.info(f"      평균: {predictions_df['Gap'].mean():.4f}")
        logger.info(f"      중위: {predictions_df['Gap'].median():.4f}")
        logger.info(f"      표준편차: {predictions_df['Gap'].std():.4f}")
        
        # 5. 저장
        logger.info(f"[5단계] 캐시 저장 중...")
        
        # 예측 결과 저장
        output_path = CACHE_DIR / 'step4_predictions.csv'
        predictions_df.to_csv(output_path)
        logger.info(f"✅ 예측 결과 저장 완료")
        logger.info(f"  - 파일: {output_path}")
        
        # ⭐ 가중치 히스토리 저장
        if weights_history:
            weights_df = pd.DataFrame(weights_history)
            weights_path = CACHE_DIR / 'step4_weights_history.csv'
            weights_df.to_csv(weights_path, index=False)
            logger.info(f"✅ 가중치 히스토리 저장 완료")
            logger.info(f"  - 파일: {weights_path}")
            logger.info(f"  - 연도별 가중치 변화 추적 가능")
        
        logger.info("")
        logger.info("="*60)
        logger.info("  Step4: 모델 학습 및 예측 완료")
        logger.info("="*60)
        
        return predictions_df


# ===========================================#
# Main 실행
# ===========================================
if __name__ == '__main__':
    """
    콘솔에서 직접 실행 시
    """
    trainer = RollingTrainer()
    predictions = trainer.run()
