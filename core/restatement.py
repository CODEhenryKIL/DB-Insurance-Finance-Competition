"""
===========================================
회계 재작성 로직 (K-IFRS 방식)
===========================================

US GAAP → K-IFRS 방식 재작성:
- R&D와 SG&A의 일부를 자산화
- 3년 정액 상각

핵심 공식:
1. I = RD + 0.3 × SGA          (자산화 투자액)
2. A = rolling_mean(I, 3년)     (상각비)
3. AdjOI = OI + I - A           (조정 영업이익)
"""

import pandas as pd
import numpy as np
from typing import Union

# 새로운 config 구조 사용
try:
    from config.settings import RESTATEMENT
    SGA_WEIGHT = RESTATEMENT.sga_weight
    AMORTIZATION_YEARS = RESTATEMENT.amortization_years
except ImportError:
    # Fallback
    SGA_WEIGHT = 0.3
    AMORTIZATION_YEARS = 3


def calculate_investment(
    rd: Union[float, pd.Series], 
    sga: Union[float, pd.Series],
    sga_weight: float = SGA_WEIGHT
) -> Union[float, pd.Series]:
    """
    자산화 투자액(I) 계산
    
    I = RD + sga_weight × SGA
    
    Parameters
    ----------
    rd : float or Series
        R&D 비용
    sga : float or Series
        SG&A 비용
    sga_weight : float
        SG&A 자산화 비율 (기본값: 0.3)
    
    Returns
    -------
    float or Series
        자산화 투자액
    """
    return rd + sga_weight * sga


def calculate_amortization(
    investment_series: pd.Series, 
    years: int = AMORTIZATION_YEARS
) -> pd.Series:
    """
    무형자산 상각비(A) 계산 (정액법)
    
    A_t = rolling_mean(I, years년)
    
    Parameters
    ----------
    investment_series : Series
        연도별 자산화 투자액
    years : int
        상각 기간 (기본값: 3년)
    
    Returns
    -------
    Series
        연도별 상각비 (처음 years-1개는 NaN)
    """
    return investment_series.rolling(window=years, min_periods=years).mean()


def calculate_adjusted_oi(
    oi: Union[float, pd.Series],
    investment: Union[float, pd.Series],
    amortization: Union[float, pd.Series]
) -> Union[float, pd.Series]:
    """
    조정 영업이익(AdjOI) 계산
    
    AdjOI = OI + I - A
    
    Parameters
    ----------
    oi : float or Series
        영업이익
    investment : float or Series
        당해 자산화 투자액
    amortization : float or Series
        당해 상각비
    
    Returns
    -------
    float or Series
        조정 영업이익
    """
    return oi + investment - amortization


def restate_financials(fund_df: pd.DataFrame) -> pd.DataFrame:
    """
    전체 재무 데이터 회계 재작성
    
    티커별로 그룹화하여 I, A, AdjOI 계산
    
    Parameters
    ----------
    fund_df : DataFrame
        Step2 출력 재무 데이터
        필수 컬럼: ['Ticker', 'FiscalYear', 'OI', 'RD', 'SGA']
    
    Returns
    -------
    DataFrame
        추가 컬럼: ['Investment', 'Amortization', 'AdjOI']
    """
    result_dfs = []
    
    for ticker, group in fund_df.groupby('Ticker'):
        group = group.sort_values('FiscalYear').copy()
        
        # 1. I (Investment)
        group['Investment'] = calculate_investment(group['RD'], group['SGA'])
        
        # 2. A (Amortization)
        group['Amortization'] = calculate_amortization(
            group.set_index('FiscalYear')['Investment']
        ).values
        
        # 3. AdjOI
        group['AdjOI'] = calculate_adjusted_oi(
            group['OI'],
            group['Investment'],
            group['Amortization']
        )
        
        result_dfs.append(group)
    
    return pd.concat(result_dfs, ignore_index=True)


if __name__ == '__main__':
    """테스트"""
    print("=" * 60)
    print("회계 재작성 테스트")
    print("=" * 60)
    
    # 예시 데이터 (Apple)
    test_data = pd.DataFrame({
        'Ticker': ['AAPL'] * 5,
        'FiscalYear': [2020, 2021, 2022, 2023, 2024],
        'OI': [66288, 108949, 119437, 114301, 123216],
        'RD': [18752, 21914, 26251, 29915, 31370],
        'SGA': [19916, 21973, 25094, 24932, 26097]
    })
    
    print("\n[원본 데이터]")
    print(test_data[['FiscalYear', 'OI', 'RD', 'SGA']].to_string())
    
    result = restate_financials(test_data)
    
    print("\n[재작성 결과]")
    print(result[['FiscalYear', 'OI', 'Investment', 'Amortization', 'AdjOI']].to_string())
    
    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
