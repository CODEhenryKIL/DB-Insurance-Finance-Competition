"""
===========================================
Step3: Feature Engineering (반기별)
===========================================

반기별 리밸런싱을 위한 피처 엔지니어링
- Q2, Q4 데이터만 사용 (6월, 12월 리밸런싱)
- m1, m2, m3, y 피처 계산 (반기 기준)

핵심 차이점 (연간 대비):
- Period: YYYY-H1/H2 형식 (H1=Q2, H2=Q4)
- m2: 과거 2반기 평균 대비
- 6개월 홀딩 기간
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


# 반기용 상각 기간 (반기 단위: 3년 = 6반기)
AMORTIZATION_SEMIANNUALS = AMORTIZATION_YEARS * 2


class SemiannualFeatureBuilder:
    """
    반기별 피처 엔지니어링 클래스
    
    Q2 (6월), Q4 (12월) 데이터만 사용하여 반기별 피처 계산
    """
    
    def __init__(self):
        """초기화"""
        logger.info("SemiannualFeatureBuilder 초기화 완료")
        logger.info(f"  - Epsilon: {EPSILON}")
        logger.info(f"  - m1 범위: [{M1_CLIP_MIN}, {M1_CLIP_MAX}]")
        logger.info(f"  - m2 범위: [{M2_CLIP_MIN}, {M2_CLIP_MAX}]")
        logger.info(f"  - m3 범위: [{M3_CLIP_MIN}, {M3_CLIP_MAX}]")
        logger.info(f"  - 상각 기간: {AMORTIZATION_SEMIANNUALS}반기")
    
    def restate_financials_semiannual(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        반기별 회계 재작성
        
        H1 (Q2), H2 (Q4) 데이터 기반으로 I, A, AdjOI 계산
        """
        df = df.copy()
        
        # 정렬
        df = df.sort_values(['Ticker', 'FiscalYear', 'FiscalQuarter'])
        
        results = []
        
        for ticker, group in df.groupby('Ticker'):
            group = group.copy()
            
            # 반기별 순수 지출 계산
            # H1 (Q2): Q2 누적값
            # H2 (Q4): Q4 - Q2 (하반기 only)
            group['RD_semi'] = group['RD']
            group['SGA_semi'] = group['SGA']
            group['OI_semi'] = group['OI']
            
            for year in group['FiscalYear'].unique():
                year_mask = group['FiscalYear'] == year
                year_data = group[year_mask]
                
                # Q4 (H2)의 경우, Q2 값을 빼서 하반기만 계산
                q4_mask = year_mask & (group['FiscalQuarter'] == 4)
                q2_data = year_data[year_data['FiscalQuarter'] == 2]
                
                if len(q2_data) > 0 and q4_mask.any():
                    q2_row = q2_data.iloc[0]
                    q4_idx = group[q4_mask].index[0]
                    
                    group.loc[q4_idx, 'RD_semi'] = group.loc[q4_idx, 'RD'] - q2_row['RD']
                    group.loc[q4_idx, 'SGA_semi'] = group.loc[q4_idx, 'SGA'] - q2_row['SGA']
                    group.loc[q4_idx, 'OI_semi'] = group.loc[q4_idx, 'OI'] - q2_row['OI']
            
            # Investment = R&D + SGA × weight (반기별)
            group['Investment'] = group['RD_semi'].fillna(0) + group['SGA_semi'].fillna(0) * SGA_WEIGHT
            
            # Amortization (과거 6반기 평균)
            group['Amortization'] = group['Investment'].rolling(
                window=AMORTIZATION_SEMIANNUALS,
                min_periods=1
            ).mean()
            
            # AdjOI = OI + Amortization (반기별)
            group['AdjOI'] = group['OI_semi'] + group['Amortization']
            
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
    
    def calculate_m2_semiannual(self, investment_series: pd.Series) -> pd.Series:
        """
        m2 (투자 가속도) 계산 - 반기 버전
        
        과거 2반기 평균 대비 현재 투자 비율
        """
        past_2h_mean = (investment_series.shift(1) + investment_series.shift(2)) / 2
        past_2h_mean = np.where(past_2h_mean < EPSILON, EPSILON, past_2h_mean)
        m2 = investment_series / past_2h_mean
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
        반기별 피처 엔지니어링 파이프라인
        """
        logger.info("")
        logger.info("="*60)
        logger.info("  Step3 (Semiannual): Feature Engineering 시작")
        logger.info("="*60)
        
        # 1. 분기별 재무 데이터 로드
        logger.info("[1단계] 분기별 재무 데이터 로드")
        quarterly_file = CACHE_DIR.parent / 'data_cache_quarterly' / 'step2_fund_quarterly.csv'
        
        if not quarterly_file.exists():
            logger.error(f"❌ 분기별 데이터 파일 없음: {quarterly_file}")
            raise FileNotFoundError(f"분기별 데이터 파일 없음: {quarterly_file}")
        
        df = pd.read_csv(quarterly_file, index_col=0)
        logger.info(f"  → 원본 데이터: {len(df):,}행, {df['Ticker'].nunique()}개 티커")
        
        # 2. Q2, Q4만 필터링 (반기용)
        logger.info("[2단계] Q2/Q4만 필터링 (반기용)")
        before_filter = len(df)
        df = df[df['FiscalQuarter'].isin([2, 4])]
        after_filter = len(df)
        logger.info(f"  → Q2/Q4 필터: {after_filter:,}행 ({before_filter - after_filter:,}행 제거)")
        
        # 반기 Period 생성
        df['SemiPeriod'] = df.apply(
            lambda r: f"{int(r['FiscalYear'])}-H{'1' if r['FiscalQuarter'] == 2 else '2'}",
            axis=1
        )
        
        # 3. 섹터 필터링
        logger.info("[3단계] 섹터 필터링")
        before_filter = len(df)
        df = df[~df['Sector'].isin(EXCLUDED_SECTORS)]
        after_filter = len(df)
        logger.info(f"  → 제외 섹터: {EXCLUDED_SECTORS}")
        logger.info(f"  → 필터 후: {after_filter:,}행")
        
        # 4. 필수 데이터 검증
        logger.info("[4단계] 필수 데이터 검증")
        df = df.dropna(subset=['SGA', 'Revenue'])
        df['RD'] = df['RD'].fillna(0)
        
        # 5. 회계 재작성
        logger.info("[5단계] 반기별 회계 재작성")
        df = self.restate_financials_semiannual(df)
        logger.info(f"  → Investment, Amortization, AdjOI 계산 완료")
        
        # 6. 가격 데이터 로드 및 MarketCap 계산
        logger.info("[6단계] MarketCap 계산")
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
                
                filing_date_approx = (end_date + pd.DateOffset(months=3)).tz_localize('UTC')
                
                if ticker in px_close_df.columns:
                    price = px_close_df[ticker].asof(filing_date_approx)
                    if pd.notna(price):
                        df.loc[idx, 'Price'] = price
                        df.loc[idx, 'MarketCap'] = price * shares
        
        logger.info(f"  → MarketCap 계산 완료")
        
        # 7. 피처 계산
        logger.info("[7단계] 피처 계산 (m1, m2, m3, y)")
        feature_dfs = []
        
        for ticker, group in df.groupby('Ticker'):
            group = group.sort_values(['FiscalYear', 'FiscalQuarter']).copy()
            
            # m1
            group['m1'] = self.calculate_m1(group['AdjOI'], group['OI_semi'])
            
            # m2 (반기 기준)
            group['m2'] = self.calculate_m2_semiannual(group['Investment'])
            
            # m3
            group['m3'] = self.calculate_m3(group['AdjOI'], group['Equity'])
            
            # y
            group['y'] = self.calculate_y(group['MarketCap'], group['Equity'])
            
            feature_dfs.append(group)
        
        features_df = pd.concat(feature_dfs, ignore_index=True)
        
        # 8. 출력 컬럼
        output_columns = [
            'Ticker', 'FiscalYear', 'FiscalQuarter', 'SemiPeriod',
            'm1', 'm2', 'm3', 'y', 'Sector',
            'Investment', 'Amortization', 'AdjOI', 'OI', 'Equity',
            'Shares', 'Price', 'MarketCap', 'EndDate'
        ]
        features_df = features_df[[c for c in output_columns if c in features_df.columns]]
        
        # 9. 저장
        logger.info("[8단계] 저장")
        output_path = CACHE_DIR / 'step3_features_semiannual.csv'
        features_df.to_csv(output_path)
        logger.info(f"✅ 저장 완료: {output_path}")
        logger.info(f"  → 총 {len(features_df):,}행, {features_df['Ticker'].nunique()}개 티커")
        
        # 반기별 통계
        semi_stats = features_df.groupby(['FiscalYear', 'FiscalQuarter']).size()
        logger.info(f"  → 반기별 평균 기업 수: {semi_stats.mean():.0f}개")
        
        return features_df


# ===========================================
# Main 실행
# ===========================================
if __name__ == '__main__':
    builder = SemiannualFeatureBuilder()
    features = builder.run()
