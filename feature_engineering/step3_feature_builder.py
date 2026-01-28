"""
===========================================
Step3: Feature Engineering
===========================================

이 파일의 역할:
- Step2 재무 데이터를 기반으로 m1, m2, m3, y 피처 계산
- 회계 재작성 결과 활용
- 방어 로직으로 극단값 및 결측 처리

핵심 피처:
- m1 (이익 복원력): AdjOI / max(abs(OI), epsilon)
- m2 (투자 가속도): I_t / Avg(I_t-1, I_t-2)
- m3 (본업 기초체력): AdjOI / Equity  
- y (타겟): ln(PBR)

방어 로직 ⭐ 중요:
- 분모 0/음수 방어
- 극단값 클리핑
- 결측치 처리
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from typing import Tuple, Optional

from config.constants import (
    EPSILON,
    M1_CLIP_MIN, M1_CLIP_MAX,
    M2_CLIP_MIN, M2_CLIP_MAX,
    M3_CLIP_MIN, M3_CLIP_MAX,
    PBR_CLIP_MIN, PBR_CLIP_MAX
)
from config.paths import (
    CACHE_DIR,
    STEP3_FEATURES_CSV,
    STEP2_FUNDAMENTALS_CSV  # ⭐ 추가
)
from utils.logger import get_logger, log_dataframe_info
from utils.helpers import load_cache, save_cache
from feature_engineering.restatement import restate_financials

logger = get_logger(__name__)


class FeatureBuilder:
    """
    피처 엔지니어링 메인 클래스
    
    Step2 재무 데이터와 Step1 가격 데이터를 결합하여
    m1, m2, m3, y 피처를 계산합니다.
    """
    
    def __init__(self):
        """초기화"""
        logger.info("FeatureBuilder 초기화 완료")
        logger.info(f"  - Epsilon: {EPSILON}")
        logger.info(f"  - m1 범위: [{M1_CLIP_MIN}, {M1_CLIP_MAX}]")
        logger.info(f"  - m2 범위: [{M2_CLIP_MIN}, {M2_CLIP_MAX}]")
        logger.info(f"  - m3 범위: [{M3_CLIP_MIN}, {M3_CLIP_MAX}]")
    
    def calculate_m1(self, adj_oi: pd.Series, oi: pd.Series) -> pd.Series:
        """
        m1 (이익 복원력) 계산
        
        공식: m1 = AdjOI / max(abs(OI), epsilon)
        
        의미:
        - 회계 재작성으로 얼마나 이익이 복원되는가?
        - abs(OI) < epsilon이면 결측 처리 (분모 폭발 방어)
        - OI, AdjOI 모두 0에 가까우면 m1=0 (의미 없는 비율 방지)
        - clip: [-5, +5]
        
        Parameters
        ----------
        adj_oi : Series
            조정 영업이익
        oi : Series
            원래 영업이익
        
        Returns
        -------
        Series
            m1 피처
        """
        # 분모: max(abs(OI), epsilon)
        denominator = np.maximum(np.abs(oi), EPSILON)
        
        # m1 계산
        m1 = adj_oi / denominator
        
        # ⭐ AUDIT FIX: OI와 AdjOI 모두 거의 0이면 m1=0
        both_near_zero = (np.abs(oi) < EPSILON) & (np.abs(adj_oi) < EPSILON)
        m1 = np.where(both_near_zero, 0, m1)
        
        # 클리핑
        m1 = np.clip(m1, M1_CLIP_MIN, M1_CLIP_MAX)
        
        return pd.Series(m1, index=adj_oi.index)
    
    def calculate_m2(self, investment_series: pd.Series) -> pd.Series:
        """
        m2 (투자 가속도) 계산
        
        공식: m2 = I_t / Avg(I_t-1, I_t-2)
        
        의미:
        - 투자가 가속되고 있는가? (성장 모멘텀)
        - 과거 2년 평균 대비 현재 투자 비율
        - clip: [0, 10]
        
        Parameters
        ----------
        investment_series : Series
            연도별 자산화 투자액 (I)
            인덱스는 FiscalYear
        
        Returns
        -------
        Series
            m2 피처 (처음 2년은 NaN)
        """
        # 과거 2년 평균 (shift(1) + shift(2)) / 2
        past_2y_mean = (investment_series.shift(1) + investment_series.shift(2)) / 2
        
        # 분모가 너무 작으면 EPSILON 사용
        past_2y_mean = np.where(past_2y_mean < EPSILON, EPSILON, past_2y_mean)
        
        # m2 계산
        m2 = investment_series / past_2y_mean
        
        # 클리핑
        m2 = np.clip(m2, M2_CLIP_MIN, M2_CLIP_MAX)
        
        return pd.Series(m2, index=investment_series.index)
    
    def calculate_m3(self, adj_oi: pd.Series, equity: pd.Series) -> pd.Series:
        """
        m3 (본업 기초체력) 계산
        
        공식: m3 = AdjOI / Equity
        
        의미:
        - 본업에서 자본 대비 얼마나 이익을 창출하는가? (ROE 유사)
        - Equity ≤ 0이면 결측 처리
        - clip: [-5, +5]
        
        Parameters
        ----------
        adj_oi : Series
            조정 영업이익
        equity : Series
            자본 (Stockholders' Equity)
        
        Returns
        -------
        Series
            m3 피처
        """
        # 분모: Equity가 0 이하면 NaN
        denominator = np.where(equity <= 0, np.nan, equity)
        
        # m3 계산
        m3 = adj_oi / denominator
        
        # 클리핑
        m3 = np.clip(m3, M3_CLIP_MIN, M3_CLIP_MAX)
        
        return pd.Series(m3, index=adj_oi.index)
    
    def calculate_y(self, market_cap: pd.Series, equity: pd.Series) -> pd.Series:
        """
        y (타겟 변수) 계산
        
        공식: y = ln(PBR) = ln(MarketCap / Equity)
        
        의미:
        - PBR의 로그값 (회귀 모델의 타겟)
        - PBR < 0.01 또는 > 100이면 clip
        - Equity ≤ 0이면 결측 처리
        
        Parameters
        ----------
        market_cap : Series
            시가총액 (가격 × 발행주식수)
        equity : Series
            자본 (장부가치, Book Value)
        
        Returns
        -------
        Series
            y 피처
        """
        # PBR 계산
        pbr = market_cap / np.where(equity <= 0, np.nan, equity)
        
        # PBR 클리핑
        pbr = np.clip(pbr, PBR_CLIP_MIN, PBR_CLIP_MAX)
        
        # 로그 변환
        y = np.log(pbr)
        
        return pd.Series(y, index=market_cap.index)
    
    def run(self) -> pd.DataFrame:
        """
        전체 파이프라인 실행
        
        1. Step2 재무 데이터 로드
        2. 회계 재작성 (I, A, AdjOI)
        3. Step1 가격 데이터와 병합하여 MarketCap 계산
        4. 피처 계산 (m1, m2, m3, y)
        5. 결과 저장
        
        Returns
        -------
        DataFrame
            features_annual 데이터
        """
        logger.info("")
        logger.info("="*60)
        logger.info("  Step3: Feature Engineering 시작")
        logger.info("="*60)
        
        # 1. Step2 재무 데이터 로드
        logger.info("[1단계] Step2 재무 데이터 로드")
        restated_df = pd.read_csv(STEP2_FUNDAMENTALS_CSV, index_col=0)
        
        # ⭐ AUDIT FIX #1: RD/SGA fillna(0) - 결측치를 "데이터 없음"으로 간주
        # R&D가 없는 기업(예: 제조업)은 0으로 처리
        restated_df['RD'] = restated_df['RD'].fillna(0)
        restated_df['SGA'] = restated_df['SGA'].fillna(0)
        
        log_dataframe_info(logger, restated_df, "재무 데이터")
        
        # 2. 회계 재작성
        logger.info("[2단계] 회계 재작성 (I, A, AdjOI)")
        restated_df = restate_financials(restated_df)
        logger.info(f"  → Investment 컬럼 추가")
        logger.info(f"  → Amortization 컬럼 추가 (처음 2년은 NaN)")
        logger.info(f"  → AdjOI 컬럼 추가")
        
        # 3. Step1 가격 데이터 로드 및 MarketCap 계산
        logger.info("[3단계] MarketCap 및 PBR 계산")
        px_close_df = pd.read_csv(CACHE_DIR / 'step1_px_close_m.csv', index_col=0, parse_dates=True)
        logger.info(f"  → 가격 데이터: {px_close_df.shape[0]}행 × {px_close_df.shape[1]}열")
        
        # 4. FiscalYear EndDate에 가장 가까운 가격 매칭
        logger.info("[4단계] EndDate 기준 가격 매칭 (3개월 래그 적용)")
        
        # MarketCap 계산 준비
        restated_df['MarketCap'] = np.nan
        restated_df['Price'] = np.nan
        
        for ticker in restated_df['Ticker'].unique():
            ticker_data = restated_df[restated_df['Ticker'] == ticker]
            
            for idx, row in ticker_data.iterrows():
                end_date = pd.to_datetime(row['EndDate'])
                shares = row['Shares']
                
                if pd.isna(shares):
                    logger.warning(f"  {ticker} FY{row['FiscalYear']}: Shares 없음 (MarketCap 계산 불가)")
                    continue
                
                # ⭐ AUDIT FIX #2: Look-ahead Bias 방지
                # 재무제표는 FiscalYear 종료 후 약 3개월 뒤 공시됨
                # 3개월 래그 추가하여 공시 시점 근사
                filing_date_approx = end_date + pd.DateOffset(months=3)
                
                # asof() 사용: filing_date_approx 이전 가장 가까운 날짜
                price = px_close_df[ticker].asof(filing_date_approx)
                
                if pd.notna(price) and pd.notna(shares):
                    market_cap = price * shares
                    restated_df.loc[idx, 'Price'] = price
                    restated_df.loc[idx, 'MarketCap'] = market_cap
        
        logger.info(f"  → MarketCap 계산 완료")
        
        # 5. 피처 계산 (티커별)
        logger.info("[5단계] 피처 계산 (m1, m2, m3, y)")
        feature_dfs = []
        
        for ticker, group in restated_df.groupby('Ticker'):
            group = group.sort_values('FiscalYear').copy()
            
            # m1 (이익 복원력)
            group['m1'] = self.calculate_m1(group['AdjOI'], group['OI'])
            
            # m2 (투자 가속도)
            investment_series = group.set_index('FiscalYear')['Investment']
            group['m2'] = self.calculate_m2(investment_series).values
            
            # m3 (본업 기초체력)
            group['m3'] = self.calculate_m3(group['AdjOI'], group['Equity'])
            
            # y = ln(PBR)
            group['y'] = self.calculate_y(group['MarketCap'], group['Equity'])
            
            feature_dfs.append(group)
        
        features_df = pd.concat(feature_dfs, ignore_index=True)
        
        features_df = pd.concat(feature_dfs, ignore_index=True)
        
        # 6. 최종 컬럼 선택
        output_columns = ['Ticker', 'FiscalYear', 'm1', 'm2', 'm3', 'y', 
                         'Investment', 'Amortization', 'AdjOI', 'OI', 'Equity', 
                         'Shares', 'Price', 'MarketCap']
        features_df = features_df[output_columns]
        
        # 7. 결과 정보
        logger.info("피처 데이터 정보:")
        logger.info(f"  - 행 개수: {len(features_df)}")
        logger.info(f"  - 열 개수: {len(features_df.columns)}")
        logger.info(f"  - 컬럼: {features_df.columns.tolist()}")
        logger.info(f"  - 총 결측치: {features_df.isnull().sum().sum()}")
        
        missing_cols = features_df.isnull().sum()
        missing_cols = missing_cols[missing_cols > 0].sort_values(ascending=False)
        if len(missing_cols) > 0:
            logger.warning("  - 결측 많은 컬럼:")
            for col, count in missing_cols.items():
                pct = count / len(features_df) * 100
                logger.warning(f"      {col}: {count} ({pct:.1f}%)")
        
        # 7. 저장
        logger.info("캐시 저장 중...")
        output_path = CACHE_DIR / 'step3_features_annual.csv'
        features_df.to_csv(output_path)
        logger.info(f"✅ 캐시 저장 완료")
        logger.info(f"  - 파일: {output_path}")
        
        logger.info("")
        logger.info("="*60)
        logger.info("  Step3: Feature Engineering 완료")
        logger.info("="*60)
        
        return features_df


# ===========================================
# Main 실행 (모듈로 실행 시)
# ===========================================
if __name__ == '__main__':
    """
    콘솔에서 직접 실행 시
    """
    builder = FeatureBuilder()
    features = builder.run()
