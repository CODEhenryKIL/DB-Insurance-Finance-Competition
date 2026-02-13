"""
===========================================
Step3: Feature Engineering (분기별)
===========================================

분기별 리밸런싱을 위한 피처 엔지니어링
- 분기별 재무 데이터 사용 (step2_fund_quarterly.csv)
- m1, m2, m3, y 피처 계산 (분기 기준)
- 3/6/9/12월 리밸런싱 대비

핵심 차이점 (연간 대비):
- Period: YYYY-QN 형식 (예: 2020-Q1, 2020-Q2)
- m2: 과거 2분기 평균 대비 (연간: 과거 2년)
- 회계 재작성: 분기별 누적 데이터 사용
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
    PBR_CLIP_MIN, PBR_CLIP_MAX,
    SGA_WEIGHT, AMORTIZATION_YEARS,
    EXCLUDED_SECTORS
)
from config.paths import CACHE_DIR
from utils.logger import get_logger, log_dataframe_info

logger = get_logger(__name__)


# 분기용 상각 기간 (분기 단위: 3년 = 12분기)
AMORTIZATION_QUARTERS = AMORTIZATION_YEARS * 4


class QuarterlyFeatureBuilder:
    """
    분기별 피처 엔지니어링 클래스
    
    분기별 재무 데이터를 사용하여 m1, m2, m3, y 피처 계산
    """
    
    def __init__(self):
        """초기화"""
        logger.info("QuarterlyFeatureBuilder 초기화 완료")
        logger.info(f"  - Epsilon: {EPSILON}")
        logger.info(f"  - m1 범위: [{M1_CLIP_MIN}, {M1_CLIP_MAX}]")
        logger.info(f"  - m2 범위: [{M2_CLIP_MIN}, {M2_CLIP_MAX}]")
        logger.info(f"  - m3 범위: [{M3_CLIP_MIN}, {M3_CLIP_MAX}]")
        logger.info(f"  - 상각 기간: {AMORTIZATION_QUARTERS}분기")
    
    def restate_financials_quarterly(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        분기별 회계 재작성
        
        분기 누적 데이터 기반으로 I, A, AdjOI 계산
        
        Parameters
        ----------
        df : DataFrame
            원본 분기 재무 데이터
            
        Returns
        -------
        DataFrame
            Investment, Amortization, AdjOI 컬럼 추가
        """
        df = df.copy()
        
        # 정렬 (티커별, 연도-분기 순)
        df = df.sort_values(['Ticker', 'FiscalYear', 'FiscalQuarter'])
        
        # 분기별 R&D + SGA 자산화 (분기 단위)
        # 누적 데이터이므로 분기별 차이 계산 필요
        results = []
        
        for ticker, group in df.groupby('Ticker'):
            group = group.copy()
            
            # 분기별 순수 지출 계산 (누적 → 분기별)
            # Q1: 그대로, Q2-Q4: 이전 분기 대비 차
            group['RD_qtr'] = group['RD']
            group['SGA_qtr'] = group['SGA']
            group['OI_qtr'] = group['OI']
            
            # 같은 연도 내에서 분기별 차이 계산
            for year in group['FiscalYear'].unique():
                year_mask = group['FiscalYear'] == year
                year_data = group[year_mask].sort_values('FiscalQuarter')
                
                for i, (idx, row) in enumerate(year_data.iterrows()):
                    if row['FiscalQuarter'] > 1:
                        # 이전 분기 값
                        prev_rows = year_data[year_data['FiscalQuarter'] < row['FiscalQuarter']]
                        if len(prev_rows) > 0:
                            prev_row = prev_rows.iloc[-1]
                            group.loc[idx, 'RD_qtr'] = row['RD'] - prev_row['RD']
                            group.loc[idx, 'SGA_qtr'] = row['SGA'] - prev_row['SGA']
                            group.loc[idx, 'OI_qtr'] = row['OI'] - prev_row['OI']
            
            # Investment = R&D + SGA × weight (분기별)
            group['Investment'] = group['RD_qtr'].fillna(0) + group['SGA_qtr'].fillna(0) * SGA_WEIGHT
            
            # Amortization (과거 12분기 평균)
            group['Amortization'] = group['Investment'].rolling(
                window=AMORTIZATION_QUARTERS, 
                min_periods=1
            ).mean()
            
            # AdjOI = OI + Amortization (분기별)
            group['AdjOI'] = group['OI_qtr'] + group['Amortization']
            
            results.append(group)
        
        return pd.concat(results, ignore_index=True)
    
    def calculate_m1(self, adj_oi: pd.Series, oi: pd.Series) -> pd.Series:
        """m1 (이익 복원력) 계산"""
        denominator = np.maximum(np.abs(oi), EPSILON)
        m1 = adj_oi / denominator
        both_near_zero = (np.abs(oi) < EPSILON) & (np.abs(adj_oi) < EPSILON)
        m1 = np.where(both_near_zero, 0, m1)
        m1 = np.clip(m1, M1_CLIP_MIN, M1_CLIP_MAX)
        return pd.Series(m1, index=adj_oi.index)
    
    def calculate_m2_quarterly(self, investment_series: pd.Series) -> pd.Series:
        """
        m2 (투자 가속도) 계산 - 분기 버전
        
        공식: m2 = I_t / Avg(I_t-1, I_t-2)
        과거 2분기 평균 대비 현재 투자 비율
        """
        past_2q_mean = (investment_series.shift(1) + investment_series.shift(2)) / 2
        past_2q_mean = np.where(past_2q_mean < EPSILON, EPSILON, past_2q_mean)
        m2 = investment_series / past_2q_mean
        m2 = np.clip(m2, M2_CLIP_MIN, M2_CLIP_MAX)
        return pd.Series(m2, index=investment_series.index)
    
    def calculate_m3(self, adj_oi: pd.Series, equity: pd.Series) -> pd.Series:
        """m3 (본업 기초체력) 계산"""
        denominator = np.where(equity <= 0, np.nan, equity)
        m3 = adj_oi / denominator
        m3 = np.clip(m3, M3_CLIP_MIN, M3_CLIP_MAX)
        return pd.Series(m3, index=adj_oi.index)
    
    def calculate_y(self, market_cap: pd.Series, equity: pd.Series) -> pd.Series:
        """y (타겟 변수) 계산: ln(PBR)"""
        pbr = market_cap / np.where(equity <= 0, np.nan, equity)
        pbr = np.clip(pbr, PBR_CLIP_MIN, PBR_CLIP_MAX)
        y = np.log(pbr)
        return pd.Series(y, index=market_cap.index)
    
    def run(self) -> pd.DataFrame:
        """
        분기별 피처 엔지니어링 파이프라인
        
        Returns
        -------
        DataFrame
            분기별 피처 데이터
        """
        logger.info("")
        logger.info("="*60)
        logger.info("  Step3 (Quarterly): Feature Engineering 시작")
        logger.info("="*60)
        
        # 1. 분기별 재무 데이터 로드
        logger.info("[1단계] 분기별 재무 데이터 로드")
        quarterly_file = CACHE_DIR.parent / 'data_cache_quarterly' / 'step2_fund_quarterly.csv'
        
        if not quarterly_file.exists():
            logger.error(f"❌ 분기별 데이터 파일 없음: {quarterly_file}")
            raise FileNotFoundError(f"분기별 데이터 파일 없음: {quarterly_file}")
        
        df = pd.read_csv(quarterly_file, index_col=0)
        logger.info(f"  → 원본 데이터: {len(df):,}행, {df['Ticker'].nunique()}개 티커")
        
        # 2. 섹터 필터링
        logger.info("[2단계] 섹터 필터링")
        before_filter = len(df)
        df = df[~df['Sector'].isin(EXCLUDED_SECTORS)]
        after_filter = len(df)
        logger.info(f"  → 제외 섹터: {EXCLUDED_SECTORS}")
        logger.info(f"  → 필터 후: {after_filter:,}행 ({before_filter - after_filter:,}행 제거)")
        
        # 3. 필수 데이터 검증
        logger.info("[3단계] 필수 데이터 검증")
        before_drop = len(df)
        df = df.dropna(subset=['SGA', 'Revenue'])
        after_drop = len(df)
        logger.info(f"  → SGA/Revenue NaN 제거: {before_drop - after_drop:,}행")
        
        # R&D 결측치 0으로
        df['RD'] = df['RD'].fillna(0)
        
        # 4. 회계 재작성
        logger.info("[4단계] 분기별 회계 재작성")
        df = self.restate_financials_quarterly(df)
        logger.info(f"  → Investment, Amortization, AdjOI 계산 완료")
        
        # 5. 가격 데이터 로드 및 MarketCap 계산
        logger.info("[5단계] MarketCap 계산")
        px_close_df = pd.read_csv(CACHE_DIR / 'step1_px_close_m.csv', index_col=0, parse_dates=[0])
        px_close_df.index = pd.to_datetime(px_close_df.index, utc=True)
        
        df['MarketCap'] = np.nan
        df['Price'] = np.nan
        
        for ticker in df['Ticker'].unique():
            ticker_data = df[df['Ticker'] == ticker]
            
            for idx, row in ticker_data.iterrows():
                end_date = pd.to_datetime(row['EndDate'])
                shares = row['Shares']
                
                if pd.isna(shares):
                    continue
                
                # 3개월 래그 (공시 시점 반영)
                filing_date_approx = (end_date + pd.DateOffset(months=3)).tz_localize('UTC')
                
                if ticker in px_close_df.columns:
                    price = px_close_df[ticker].asof(filing_date_approx)
                    if pd.notna(price):
                        df.loc[idx, 'Price'] = price
                        df.loc[idx, 'MarketCap'] = price * shares
        
        logger.info(f"  → MarketCap 계산 완료")
        
        # 6. 피처 계산
        logger.info("[6단계] 피처 계산 (m1, m2, m3, y)")
        feature_dfs = []
        
        for ticker, group in df.groupby('Ticker'):
            group = group.sort_values(['FiscalYear', 'FiscalQuarter']).copy()
            
            # m1
            group['m1'] = self.calculate_m1(group['AdjOI'], group['OI_qtr'])
            
            # m2 (분기 기준)
            group['m2'] = self.calculate_m2_quarterly(group['Investment'])
            
            # m3
            group['m3'] = self.calculate_m3(group['AdjOI'], group['Equity'])
            
            # y
            group['y'] = self.calculate_y(group['MarketCap'], group['Equity'])
            
            feature_dfs.append(group)
        
        features_df = pd.concat(feature_dfs, ignore_index=True)
        
        # 7. 출력 컬럼
        output_columns = [
            'Ticker', 'FiscalYear', 'FiscalQuarter', 'Period',
            'm1', 'm2', 'm3', 'y', 'Sector',
            'Investment', 'Amortization', 'AdjOI', 'OI', 'Equity',
            'Shares', 'Price', 'MarketCap', 'EndDate'
        ]
        features_df = features_df[[c for c in output_columns if c in features_df.columns]]
        
        # 8. 저장
        logger.info("[7단계] 저장")
        output_path = CACHE_DIR / 'step3_features_quarterly.csv'
        features_df.to_csv(output_path)
        logger.info(f"✅ 저장 완료: {output_path}")
        logger.info(f"  → 총 {len(features_df):,}행, {features_df['Ticker'].nunique()}개 티커")
        
        # 분기별 통계
        quarter_stats = features_df.groupby(['FiscalYear', 'FiscalQuarter']).size()
        logger.info(f"  → 분기별 평균 기업 수: {quarter_stats.mean():.0f}개")
        
        return features_df


# ===========================================
# Main 실행
# ===========================================
if __name__ == '__main__':
    builder = QuarterlyFeatureBuilder()
    features = builder.run()
