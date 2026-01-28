"""
===========================================
회계 재작성 로직 (K-IFRS 방식)
===========================================

이 파일의 역할:
- US GAAP 재무제표를 K-IFRS 방식으로 재작성
- R&D와 SG&A의 일부를 자산화하여 무형자산으로 처리
- 3년 정액 상각으로 비용 인식

핵심 공식:
1. I (Investment, 자산화 투자액) = RD + 0.3 × SGA
2. A (Amortization, 상각비) = (I_t + I_t-1 + I_t-2) / 3
3. AdjOI (Adjusted Operating Income) = OI + I - A

왜 이렇게 하는가?
- US GAAP: R&D, SG&A를 즉시 비용 처리 → 기술주/바이오 기업의 이익 과소평가
- K-IFRS: 개발비(Development)를 자산화 가능 → 기술 투자 가치 인정
- M-Model: 이를 통해 기술주의 진짜 수익성을 복원
"""

import pandas as pd
import numpy as np
from typing import Union

# config에서 상수 가져오기
from config.constants import SGA_WEIGHT, AMORTIZATION_YEARS


def calculate_investment(rd: Union[float, pd.Series], 
                        sga: Union[float, pd.Series]) -> Union[float, pd.Series]:
    """
    자산화 투자액(I) 계산
    
    공식: I = RD + 0.3 × SGA
    
    Parameters
    ----------
    rd : float or Series
        R&D 비용 (Research & Development Expense)
    sga : float or Series
        SG&A 비용 (Selling, General & Administrative Expense)
    
    Returns
    -------
    float or Series
        자산화 투자액 (Investment)
    
    Examples
    --------
    >>> calculate_investment(100, 200)
    160.0
    
    >>> df = pd.DataFrame({'RD': [100, 200], 'SGA': [200, 400]})
    >>> calculate_investment(df['RD'], df['SGA'])
    0    160.0
    1    260.0
    dtype: float64
    """
    return rd + SGA_WEIGHT * sga


def calculate_amortization(investment_series: pd.Series, 
                          years: int = AMORTIZATION_YEARS) -> pd.Series:
    """
    무형자산 상각비(A) 계산 (정액법)
    
    공식: A_t = (I_t + I_t-1 + I_t-2) / 3
    
    Parameters
    ----------
    investment_series : Series
        연도별 자산화 투자액 시계열 (I)
        인덱스는 연도(FiscalYear)여야 함
    years : int, default=3
        상각 기간 (년)
    
    Returns
    -------
    Series
        연도별 상각비 (Amortization)
        처음 (years-1)개 연도는 NaN
    
    Notes
    -----
    - 최소 3년치 데이터가 필요 (years=3일 때)
    - 연도가 연속적이지 않으면 경고
    
    Examples
    --------
    >>> inv = pd.Series([100, 120, 150, 180], index=[2020, 2021, 2022, 2023])
    >>> calculate_amortization(inv)
    2020       NaN
    2021       NaN
    2022    123.33
    2023    150.00
    dtype: float64
    """
    # Rolling mean으로 계산 (과거 N년 평균)
    amortization = investment_series.rolling(window=years, min_periods=years).mean()
    
    return amortization


def calculate_adjusted_oi(oi: Union[float, pd.Series],
                         investment: Union[float, pd.Series],
                         amortization: Union[float, pd.Series]) -> Union[float, pd.Series]:
    """
    조정 영업이익(AdjOI) 계산
    
    공식: AdjOI = OI + I - A
    
    논리:
    - OI: 원래 영업이익 (R&D, SG&A를 모두 비용 처리)
    - +I: R&D, SG&A 중 자산화할 부분을 비용에서 제거 (이익 증가)
    - -A: 과거 자산화한 투자액의 상각비를 비용으로 추가 (이익 감소)
    
    Parameters
    ----------
    oi : float or Series
        영업이익 (Operating Income)
    investment : float or Series
        당해 자산화 투자액 (I)
    amortization : float or Series
        당해 상각비 (A)
    
    Returns
    -------
    float or Series
        조정 영업이익 (Adjusted Operating Income)
    
    Examples
    --------
    >>> calculate_adjusted_oi(100, 50, 40)
    110.0
    """
    return oi + investment - amortization


def restate_financials(fund_df: pd.DataFrame) -> pd.DataFrame:
    """
    전체 재무 데이터를 회계 재작성
    
    티커별로 그룹화하여 회계 재작성 수행
    
    Parameters
    ----------
    fund_df : DataFrame
        Step2 출력 재무 데이터
        필수 컬럼: ['Ticker', 'FiscalYear', 'OI', 'RD', 'SGA']
    
    Returns
    -------
    DataFrame
        회계 재작성 결과
        추가 컬럼: ['Investment', 'Amortization', 'AdjOI']
    
    Notes
    -----
    - 티커별로 FiscalYear 정렬 필수
    - 최소 3년치 데이터가 없으면 상각비(A) 계산 불가 → AdjOI도 NaN
    """
    result_dfs = []
    
    for ticker, group in fund_df.groupby('Ticker'):
        # FiscalYear 정렬
        group = group.sort_values('FiscalYear').copy()
        
        # 1. I (Investment) 계산
        group['Investment'] = calculate_investment(group['RD'], group['SGA'])
        
        # 2. A (Amortization) 계산 (3년 rolling mean)
        group['Amortization'] = calculate_amortization(
            group.set_index('FiscalYear')['Investment']
        ).values
        
        # 3. AdjOI (Adjusted OI) 계산
        group['AdjOI'] = calculate_adjusted_oi(
            group['OI'],
            group['Investment'],
            group['Amortization']
        )
        
        result_dfs.append(group)
    
    return pd.concat(result_dfs, ignore_index=True)


# ===========================================
# 사용 예시 및 테스트
# ===========================================
if __name__ == '__main__':
    """
    회계 재작성 로직 단위 테스트
    """
    print("="*60)
    print("회계 재작성 로직 테스트")
    print("="*60)
    
    # 예시 데이터
    test_data = pd.DataFrame({
        'Ticker': ['AAPL'] * 5,
        'FiscalYear': [2020, 2021, 2022, 2023, 2024],
        'OI': [66288, 108949, 119437, 114301, 123216],  # 단위: 백만 달러
        'RD': [18752, 21914, 26251, 29915, 31370],
        'SGA': [19916, 21973, 25094, 24932, 26097]
    })
    
    print("\n[원본 데이터]")
    print(test_data[['FiscalYear', 'OI', 'RD', 'SGA']])
    
    # 회계 재작성
    result = restate_financials(test_data)
    
    print("\n[회계 재작성 결과]")
    print(result[['FiscalYear', 'OI', 'Investment', 'Amortization', 'AdjOI']])
    
    print("\n[계산 상세]")
    for _, row in result.iterrows():
        fy = row['FiscalYear']
        oi = row['OI']
        i = row['Investment']
        a = row['Amortization']
        adj_oi = row['AdjOI']
        
        if pd.notna(adj_oi):
            print(f"FY{fy}: OI={oi:,.0f} + I={i:,.0f} - A={a:,.0f} = AdjOI={adj_oi:,.0f}")
        else:
            print(f"FY{fy}: I={i:,.0f}, A=NaN (상각비 계산 불가)")
    
    print("\n" + "="*60)
    print("✅ 테스트 완료")
    print("="*60)
