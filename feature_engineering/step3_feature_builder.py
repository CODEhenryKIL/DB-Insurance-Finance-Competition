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
        
        # 0. MARKET_MODE 확인
        from config.constants import MARKET_MODE
        logger.info(f"[0단계] MARKET_MODE: {MARKET_MODE}")
        
        # 1. Step2 재무 데이터 로드 (MARKET_MODE에 따라 다른 파일)
        logger.info("[1단계] Step2 재무 데이터 로드")
        
        if MARKET_MODE == 'SP500':
            # S&P 500 전용 데이터 (연도별 Historical Constituents 적용됨)
            sp500_file = CACHE_DIR / 'step2_fund_annual_sp500.csv'
            if sp500_file.exists():
                restated_df = pd.read_csv(sp500_file, index_col=0)
                logger.info(f"  → S&P 500 전용 데이터 로드: {sp500_file.name}")
                logger.info(f"  → 데이터: {len(restated_df):,}행, {restated_df['Ticker'].nunique()}개 티커")
            else:
                logger.error(f"  ❌ S&P 500 데이터 파일 없음: {sp500_file}")
                logger.error(f"     먼저 실행: python scripts/build_sp500_historical.py")
                raise FileNotFoundError(f"S&P 500 데이터 파일 없음: {sp500_file}")
        else:
            # FULL 모드: 기존 전체 데이터
            restated_df = pd.read_csv(STEP2_FUNDAMENTALS_CSV, index_col=0)
            logger.info(f"  → 전체 시장 데이터 로드: {STEP2_FUNDAMENTALS_CSV.name}")
        
        logger.info(f"  → 원본 데이터: {len(restated_df):,}행")
        
        # ⭐ [수정] 2단계: 섹터 필터링 (가장 먼저!)
        logger.info("[1.5단계] 섹터 필터링")
        from config.constants import EXCLUDED_SECTORS
        before_filter = len(restated_df)
        restated_df = restated_df[~restated_df['Sector'].isin(EXCLUDED_SECTORS)]
        after_filter = len(restated_df)
        logger.info(f"  → 제외 섹터: {EXCLUDED_SECTORS}")
        logger.info(f"  → 필터 후: {after_filter:,}행 ({before_filter - after_filter:,}행 제거)")
        
        # ⭐ [수정] 3단계: 필수 데이터 검증 (SGA, Revenue NaN → Drop)
        logger.info("[1.6단계] 필수 데이터 검증 (SGA/Revenue)")
        before_drop = len(restated_df)
        restated_df = restated_df.dropna(subset=['SGA', 'Revenue'])
        after_drop = len(restated_df)
        logger.info(f"  → SGA/Revenue NaN 제거: {before_drop - after_drop:,}행 제거")
        logger.info(f"  → 유효 데이터: {after_drop:,}행")
        
        # ⭐ [수정] 4단계: R&D만 fillna(0) (R&D 안 하는 기업 존재)
        logger.info("[1.7단계] R&D 결측치 처리")
        rd_missing_before = restated_df['RD'].isna().sum()
        restated_df['RD'] = restated_df['RD'].fillna(0)
        logger.info(f"  → R&D 결측 {rd_missing_before:,}행 → 0으로 대체")
        
        log_dataframe_info(logger, restated_df, "필터링 후 재무 데이터")
        
        # 2. 회계 재작성
        logger.info("[2단계] 회계 재작성 (I, A, AdjOI)")
        restated_df = restate_financials(restated_df)
        logger.info(f"  → Investment 컬럼 추가")
        logger.info(f"  → Amortization 컬럼 추가 (처음 2년은 NaN)")
        logger.info(f"  → AdjOI 컬럼 추가")
        
        # 3. Step1 가격 데이터 로드 및 MarketCap 계산
        logger.info("[3단계] MarketCap 및 PBR 계산")
        px_close_df = pd.read_csv(CACHE_DIR / 'step1_px_close_m.csv', index_col=0, parse_dates=[0])
       # ⭐ 인덱스 타입 변환 보장 (UTC로 통일)
        px_close_df.index = pd.to_datetime(px_close_df.index, utc=True)
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
                filing_date_approx = (end_date + pd.DateOffset(months=3)).tz_localize('UTC')  # ⭐ UTC 타임존 추가
                
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
        output_columns = ['Ticker', 'FiscalYear', 'm1', 'm2', 'm3', 'y', 'Sector',
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
        
        # ⭐ Step 3.5: 유니버스 리포트 생성
        logger.info("")
        logger.info("="*60)
        logger.info("  Step 3.5: 유니버스 리포트 생성")
        logger.info("="*60)
        self.generate_universe_report(features_df)
        
        logger.info("")
        logger.info("="*60)
        logger.info("  Step3: Feature Engineering 완료")
        logger.info("="*60)
        
        return features_df
    
    def generate_universe_report(self, features_df: pd.DataFrame) -> None:
        """
        Step 3.5: 유니버스 리포트 생성 (Excel)
        
        모델 학습 전 데이터 품질 점검용 리포트
        
        Parameters
        ----------
        features_df : DataFrame
            Step3 피처 데이터
        """
        from config.paths import UNIVERSE_REPORT_XLSX, REPORTS_DIR
        
        # 리포트 디렉토리 생성
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info("유니버스 리포트 생성 중...")
        
        # 1. Details Sheet: 티커별 데이터 상태
        details_data = []
        
        for ticker, group in features_df.groupby('Ticker'):
            group = group.sort_values('FiscalYear')
            
            start_year = group['FiscalYear'].min()
            end_year = group['FiscalYear'].max()
            count_rows = len(group)
            
            # R&D 데이터 유무 확인
            # Investment 컬럼이 있고 0이 아닌 값이 있으면 R&D 존재
            has_rd = False
            if 'Investment' in group.columns:
                has_rd = (group['Investment'] > 0).any()
            
            # m1, m2, m3, y 유효 데이터 수
            valid_m1 = group['m1'].notna().sum()
            valid_m2 = group['m2'].notna().sum()
            valid_m3 = group['m3'].notna().sum()
            valid_y = group['y'].notna().sum()
            
            # 상태 판정
            # 최소 3년 데이터 + m2 2개 이상 필요
            if count_rows >= 3 and valid_m2 >= 2 and valid_y >= 2:
                status = 'Ready'
            else:
                status = 'Insufficient Data'
            
            sector = group['Sector'].iloc[0] if 'Sector' in group.columns else 'Unknown'
            
            details_data.append({
                'Ticker': ticker,
                'Sector': sector,
                'Start_Year': int(start_year),
                'End_Year': int(end_year),
                'Count_Rows': count_rows,
                'Missing_R&D': not has_rd,
                'Valid_m1': valid_m1,
                'Valid_m2': valid_m2,
                'Valid_m3': valid_m3,
                'Valid_y': valid_y,
                'Status': status
            })
        
        details_df = pd.DataFrame(details_data)
        
        # 2. Missing Years Sheet: 기업별 누락 연도 상세
        logger.info("  기업별 누락 연도 분석 중...")
        missing_years_data = []
        
        # 전체 연도 범위 (2012 ~ 최신)
        all_years = set(range(2012, features_df['FiscalYear'].max() + 1))
        
        for ticker, group in features_df.groupby('Ticker'):
            group = group.sort_values('FiscalYear')
            existing_years = set(group['FiscalYear'].unique())
            
            start_year = group['FiscalYear'].min()
            end_year = group['FiscalYear'].max()
            
            # 해당 기업의 예상 연도 범위 내 누락
            expected_years = set(range(int(start_year), int(end_year) + 1))
            missing_in_range = sorted(expected_years - existing_years)
            
            # 각 피처별 누락 연도
            m1_missing = sorted(group[group['m1'].isna()]['FiscalYear'].tolist())
            m2_missing = sorted(group[group['m2'].isna()]['FiscalYear'].tolist())
            m3_missing = sorted(group[group['m3'].isna()]['FiscalYear'].tolist())
            y_missing = sorted(group[group['y'].isna()]['FiscalYear'].tolist())
            
            sector = group['Sector'].iloc[0] if 'Sector' in group.columns else 'Unknown'
            
            # 누락이 있는 경우만 기록 (또는 모든 기업 기록)
            if missing_in_range or m1_missing or m2_missing or m3_missing or y_missing:
                missing_years_data.append({
                    'Ticker': ticker,
                    'Sector': sector,
                    'Data_Years': f"{int(start_year)}-{int(end_year)}",
                    'Total_Rows': len(group),
                    'Missing_Years_in_Range': ', '.join(map(str, missing_in_range)) if missing_in_range else '-',
                    'm1_NaN_Years': ', '.join(map(str, [int(y) for y in m1_missing])) if m1_missing else '-',
                    'm2_NaN_Years': ', '.join(map(str, [int(y) for y in m2_missing])) if m2_missing else '-',
                    'm3_NaN_Years': ', '.join(map(str, [int(y) for y in m3_missing])) if m3_missing else '-',
                    'y_NaN_Years': ', '.join(map(str, [int(y) for y in y_missing])) if y_missing else '-',
                    'Total_NaN_Count': len(m1_missing) + len(m2_missing) + len(m3_missing) + len(y_missing)
                })
        
        missing_years_df = pd.DataFrame(missing_years_data)
        if len(missing_years_df) > 0:
            missing_years_df = missing_years_df.sort_values('Total_NaN_Count', ascending=False)
        
        # 3. Summary Sheet: 전체 통계
        total_tickers = len(details_df)
        ready_tickers = (details_df['Status'] == 'Ready').sum()
        insufficient_tickers = (details_df['Status'] == 'Insufficient Data').sum()
        
        # 섹터별 통계
        sector_summary = details_df.groupby('Sector').agg({
            'Ticker': 'count',
            'Status': lambda x: (x == 'Ready').sum()
        }).rename(columns={'Ticker': 'Total', 'Status': 'Ready'})
        sector_summary['Ready_Pct'] = (sector_summary['Ready'] / sector_summary['Total'] * 100).round(1)
        
        summary_data = {
            'Metric': [
                'Total Tickers',
                'Ready for Training',
                'Insufficient Data',
                'Ready Rate (%)',
                'Avg Years per Ticker',
                'Total Data Points',
                'Missing R&D Rate (%)',
                'Tickers with Missing Data',
                'Data Period'
            ],
            'Value': [
                total_tickers,
                ready_tickers,
                insufficient_tickers,
                round(ready_tickers / total_tickers * 100, 1) if total_tickers > 0 else 0,
                round(details_df['Count_Rows'].mean(), 1),
                details_df['Count_Rows'].sum(),
                round(details_df['Missing_R&D'].sum() / total_tickers * 100, 1) if total_tickers > 0 else 0,
                len(missing_years_df),
                f"2012-{features_df['FiscalYear'].max()}"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        
        # 4. Excel 저장 (openpyxl 사용)
        try:
            with pd.ExcelWriter(UNIVERSE_REPORT_XLSX, engine='openpyxl') as writer:
                # Summary 시트
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Sector Summary 시트
                sector_summary.to_excel(writer, sheet_name='Sector_Summary')
                
                # Details 시트 (전체 기업)
                details_df.to_excel(writer, sheet_name='Ticker_Details', index=False)
                
                # Missing Years 시트 (누락 상세)
                if len(missing_years_df) > 0:
                    missing_years_df.to_excel(writer, sheet_name='Missing_Years_Detail', index=False)
            
            logger.info(f"✅ 유니버스 리포트 저장 완료")
            logger.info(f"  - 파일: {UNIVERSE_REPORT_XLSX}")
            logger.info(f"  - 총 티커: {total_tickers}개")
            logger.info(f"  - Ready: {ready_tickers}개 ({ready_tickers/total_tickers*100:.1f}%)")
            logger.info(f"  - Insufficient: {insufficient_tickers}개")
            
            # 섹터별 요약 출력
            logger.info("")
            logger.info("  [섹터별 분포]")
            for sector in sector_summary.index:
                row = sector_summary.loc[sector]
                logger.info(f"    {sector:25s}: {int(row['Total']):4d}개 (Ready: {int(row['Ready'])}개, {row['Ready_Pct']:.1f}%)")
                
        except Exception as e:
            logger.error(f"❌ 리포트 저장 실패: {e}")
            logger.warning("openpyxl이 설치되어 있는지 확인하세요: pip install openpyxl")


# ===========================================
# Main 실행 (모듈로 실행 시)
# ===========================================
if __name__ == '__main__':
    """
    콘솔에서 직접 실행 시
    """
    builder = FeatureBuilder()
    features = builder.run()
