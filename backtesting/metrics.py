"""
===========================================
성과 지표 계산 모듈
===========================================

이 파일의 역할:
- 백테스트 결과를 바탕으로 성과 지표 계산
- CAGR, Sharpe Ratio, MDD, Alpha, Beta 등

주요 함수:
- calculate_cagr(): 연평균 복리수익률
- calculate_sharpe_ratio(): 샤프 비율
- calculate_mdd(): 최대 낙폭
- calculate_alpha_beta(): 알파, 베타
"""

import numpy as np
import pandas as pd
from typing import Tuple


def calculate_cagr(returns: pd.Series, years: float) -> float:
    """
    CAGR (연평균 복리수익률) 계산
    
    공식: CAGR = (최종가치 / 초기가치)^(1/년수) - 1
    
    Parameters
    ----------
    returns : Series
        일별/월별 수익률 (1 + r)
    years : float
        투자 기간 (년)
    
    Returns
    -------
    float
        CAGR (연율)
    """
    if len(returns) == 0 or years <= 0:
        return np.nan
    
    # 누적 수익률
    cumulative_return = (1 + returns).prod()
    
    # CAGR 계산
    cagr = (cumulative_return ** (1 / years)) - 1
    
    return cagr


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.02
) -> float:
    """
    Sharpe Ratio 계산
    
    공식: Sharpe = (평균 수익률 - 무위험 수익률) / 수익률 표준편차
    
    Parameters
    ----------
    returns : Series
        연간 수익률
    risk_free_rate : float
        무위험 수익률 (연율)
    
    Returns
    -------
    float
        Sharpe Ratio
    """
    if len(returns) == 0:
        return np.nan
    
    # 연간 초과 수익률
    excess_returns = returns - risk_free_rate
    
    # Sharpe Ratio
    if excess_returns.std() == 0:
        return np.nan
    
    sharpe = excess_returns.mean() / excess_returns.std()
    
    return sharpe


def calculate_mdd(cumulative_returns: pd.Series) -> float:
    """
    MDD (최대 낙폭) 계산
    
    공식: MDD = min((현재 - 최고점) / 최고점)
    
    Parameters
    ----------
    cumulative_returns : Series
        누적 수익률 (1 + r)
    
    Returns
    -------
    float
        MDD (음수, 예: -0.30 = 30% 낙폭)
    """
    if len(cumulative_returns) == 0:
        return np.nan
    
    # Running maximum
    running_max = cumulative_returns.cummax()
    
    # Drawdown
    drawdown = (cumulative_returns - running_max) / running_max
    
    # MDD
    mdd = drawdown.min()
    
    return mdd


def calculate_alpha_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.02
) -> Tuple[float, float]:
    """
    Alpha, Beta 계산
    
    Beta: 포트폴리오 민감도 (벤치마크 대비)
    Alpha: 초과 수익률 (벤치마크 대비)
    
    Parameters
    ----------
    portfolio_returns : Series
        포트폴리오 연간 수익률
    benchmark_returns : Series
        벤치마크 연간 수익률
    risk_free_rate : float
        무위험 수익률
    
    Returns
    -------
    alpha, beta : float
    """
    # 데이터 정렬
    common_index = portfolio_returns.index.intersection(benchmark_returns.index)
    
    if len(common_index) < 2:
        return np.nan, np.nan
    
    port_ret = portfolio_returns.loc[common_index]
    bench_ret = benchmark_returns.loc[common_index]
    
    # 초과 수익률
    port_excess = port_ret - risk_free_rate
    bench_excess = bench_ret - risk_free_rate
    
    # Beta 계산
    covariance = np.cov(port_excess, bench_excess)[0, 1]
    benchmark_variance = bench_excess.var()
    
    if benchmark_variance == 0:
        return np.nan, np.nan
    
    beta = covariance / benchmark_variance
    
    # Alpha 계산 (Jensen's Alpha)
    # Alpha = E[R_p - R_f] - Beta * E[R_b - R_f]
    alpha = port_excess.mean() - beta * bench_excess.mean()
    
    return alpha, beta


def calculate_performance_metrics(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.02
) -> dict:
    """
    전체 성과 지표 계산
    
    Parameters
    ----------
    portfolio_returns : Series
        포트폴리오 연간 수익률
    benchmark_returns : Series
        벤치마크 연간 수익률
    risk_free_rate : float
        무위험 수익률
    
    Returns
    -------
    dict
        성과 지표 딕셔너리
    """
    # 기간 계산 (년)
    years = len(portfolio_returns)
    
    # CAGR
    port_cagr = calculate_cagr(portfolio_returns, years)
    bench_cagr = calculate_cagr(benchmark_returns, years)
    
    # Sharpe Ratio
    port_sharpe = calculate_sharpe_ratio(portfolio_returns, risk_free_rate)
    bench_sharpe = calculate_sharpe_ratio(benchmark_returns, risk_free_rate)
    
    # MDD
    port_cumulative = (1 + portfolio_returns).cumprod()
    bench_cumulative = (1 + benchmark_returns).cumprod()
    
    port_mdd = calculate_mdd(port_cumulative)
    bench_mdd = calculate_mdd(bench_cumulative)
    
    # Alpha, Beta
    alpha, beta = calculate_alpha_beta(portfolio_returns, benchmark_returns, risk_free_rate)
    
    # 승률 (벤치마크 초과 연도 비율)
    win_rate = (portfolio_returns > benchmark_returns).mean()
    
    return {
        # 포트폴리오
        'Portfolio_CAGR': port_cagr,
        'Portfolio_Sharpe': port_sharpe,
        'Portfolio_MDD': port_mdd,
        
        # 벤치마크
        'Benchmark_CAGR': bench_cagr,
        'Benchmark_Sharpe': bench_sharpe,
        'Benchmark_MDD': bench_mdd,
        
        # 상대 지표
        'Alpha': alpha,
        'Beta': beta,
        'Win_Rate': win_rate,
        
        # 기타
        'Years': years,
        'Total_Return_Portfolio': (1 + portfolio_returns).prod() - 1,
        'Total_Return_Benchmark': (1 + benchmark_returns).prod() - 1,
    }


# ===========================================
# 테스트
# ===========================================
if __name__ == '__main__':
    """
    성과 지표 계산 테스트
    """
    print("="*60)
    print("Performance Metrics 테스트")
    print("="*60)
    
    # 더미 데이터
    np.random.seed(42)
    years = 10
    
    # 포트폴리오: 평균 12%, 표준편차 20%
    port_returns = pd.Series(np.random.normal(0.12, 0.20, years))
    
    # 벤치마크: 평균 10%, 표준편차 15%
    bench_returns = pd.Series(np.random.normal(0.10, 0.15, years))
    
    # 성과 지표 계산
    metrics = calculate_performance_metrics(port_returns, bench_returns, risk_free_rate=0.02)
    
    print("\n[성과 지표]")
    for key, val in metrics.items():
        if isinstance(val, float):
            print(f"  {key:30s}: {val:8.4f}")
        else:
            print(f"  {key:30s}: {val}")
    
    print("\n" + "="*60)
    print("✅ 테스트 완료")
    print("="*60)
