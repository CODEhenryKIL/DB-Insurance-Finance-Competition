"""
===========================================
Step5: 백테스트 및 성과 평가
===========================================

이 파일의 역할:
- Gap 기반 롱 전략 백테스트
- 동적 유니버스 ($5 룰, 섹터 필터)
- 연간 리밸런싱
- 4가지 비율 동시 실행 (5%, 10%, 20%, 30%)

핵심 로직:
1. 매년 12월 말 리밸런싱
2. Gap 상위 N% 티커 선택
3. 동일 가중 포트폴리오
4. 12개월 홀딩
5. 성과 지표 계산

$5 룰:
- 최근 12개월 중 80% 이상이 $5 이하면 제외
- 유동성 부족 종목 필터링
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import datetime

from config.constants import (
    LONG_RATIOS,
    HOLDING_PERIOD_MONTHS,
    REBALANCE_MONTH,
    PRICE_THRESHOLD_DOLLARS,
    PRICE_BELOW_THRESHOLD_RATIO,
    PRICE_CHECK_MONTHS,
    BENCHMARK_TICKER,
    RISK_FREE_RATE,
    EXCLUDED_SECTORS
)
from config.paths import CACHE_DIR
from utils.logger import get_logger
from backtesting.metrics import (
    calculate_performance_metrics,
    calculate_information_ratio,
    calculate_cagr,
    calculate_sharpe_ratio,
    calculate_mdd
)

logger = get_logger(__name__)


class PortfolioBacktester:
    """
    Gap 기반 롱 전략 백테스터
    
    매년:
    1. 동적 유니버스 생성 ($5 룰)
    2. Gap 상위 N% 선택
    3. 동일 가중 포트폴리오
    4. 12개월 홀딩
    5. 수익률 계산
    """
    
    def __init__(
        self,
        long_ratios: List[float] = LONG_RATIOS,
        holding_months: int = HOLDING_PERIOD_MONTHS,
        rebalance_month: int = REBALANCE_MONTH
    ):
        """
        초기화
        
        Parameters
        ----------
        long_ratios : list
            롱 포트폴리오 비율 (Gap 상위 N%)
        holding_months : int
            홀딩 기간 (개월)
        rebalance_month : int
            리밸런싱 월 (12 = 12월)
        """
        self.long_ratios = long_ratios
        self.holding_months = holding_months
        self.rebalance_month = rebalance_month
        
        logger.info("PortfolioBacktester 초기화 완료")
        logger.info(f"  - 롱 비율: {long_ratios}")
        logger.info(f"  - 홀딩 기간: {holding_months}개월")
        logger.info(f"  - 리밸런싱: 매년 {rebalance_month}월")
    
    def download_benchmark_data(
        self,
        start_date: str = '2010-01-01',
        end_date: str = None
    ) -> pd.Series:
        """
        S&P 500 벤치마크 데이터 다운로드
        """
        logger.info(f"[벤치마크] S&P 500 ({BENCHMARK_TICKER}) 다운로드 시작")
        
        try:
            import yfinance as yf
            
            # yfinance 다운로드 (period='max'로 충분한 데이터 확보)
            benchmark_data = yf.download(
                BENCHMARK_TICKER, 
                period="max", 
                progress=False,
                auto_adjust=False
            )
            
            if benchmark_data.empty:
                logger.error(f"[벤치마크] 데이터 다운로드 실패 (Empty DataFrame)")
                return pd.Series(dtype=float)
            
            # 가격 컬럼 추출 (Adj Close 우선)
            price_col = None
            
            # MultiIndex 처리 (최신 yfinance)
            if isinstance(benchmark_data.columns, pd.MultiIndex):
                if 'Adj Close' in benchmark_data.columns.get_level_values(0):
                    price_col = benchmark_data['Adj Close']
                elif 'Close' in benchmark_data.columns.get_level_values(0):
                    price_col = benchmark_data['Close']
            else:
                if 'Adj Close' in benchmark_data.columns:
                    price_col = benchmark_data['Adj Close']
                elif 'Close' in benchmark_data.columns:
                    price_col = benchmark_data['Close']
            
            # 여전히 못 찾았으면 첫 번째 컬럼 사용
            if price_col is None:
                price_col = benchmark_data.iloc[:, 0]
                
            # Series인지 DataFrame인지 확인 (DataFrame이면 squeeze)
            if isinstance(price_col, pd.DataFrame):
                price_col = price_col.iloc[:, 0]

            # 월말 종가로 리샘플링 (pandas 최신 버전: 'M' -> 'ME')
            price_col = price_col.sort_index()
            benchmark_monthly_prices = price_col.resample('ME').last()
            
            logger.info(f"[벤치마크] 다운로드 완료: {len(benchmark_monthly_prices)}개월 데이터")
            return benchmark_monthly_prices
            
        except Exception as e:
            logger.error(f"[벤치마크] 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.Series(dtype=float)
    
    def apply_dollar_five_rule(
        self,
        tickers: List[str],
        rebalance_date: pd.Timestamp,
        price_df: pd.DataFrame
    ) -> List[str]:
        """
        $5 룰 적용
        
        최근 12개월 중 80% 이상이 $5 이하면 제외
        
        Parameters
        ----------
        tickers : list
            대상 티커 리스트
        rebalance_date : Timestamp
            리밸런싱 시점
        price_df : DataFrame
            가격 데이터 (월말)
        
        Returns
        -------
        list
            필터링된 티커 리스트
        """
        # 최근 12개월 가격
        start_date = rebalance_date - pd.DateOffset(months=PRICE_CHECK_MONTHS)
        recent_prices = price_df.loc[start_date:rebalance_date]
        
        valid_tickers = []
        
        for ticker in tickers:
            if ticker not in recent_prices.columns:
                logger.warning(f"  {ticker}: 가격 데이터 없음 (제외)")
                continue
            
            ticker_prices = recent_prices[ticker].dropna()
            
            if len(ticker_prices) == 0:
                logger.warning(f"  {ticker}: 최근 가격 없음 (제외)")
                continue
            
            # $5 이하 비율
            below_threshold_ratio = (ticker_prices <= PRICE_THRESHOLD_DOLLARS).mean()
            
            if below_threshold_ratio >= PRICE_BELOW_THRESHOLD_RATIO:
                logger.debug(f"  {ticker}: $5 룰 위반 ({below_threshold_ratio*100:.1f}% 이하) (제외)")
                continue
            
            valid_tickers.append(ticker)
        
        return valid_tickers
    
    def calculate_portfolio_return(
        self,
        selected_tickers: List[str],
        rebalance_date: pd.Timestamp,
        price_df: pd.DataFrame
    ) -> float:
        """
        포트폴리오 12개월 수익률 계산
        
        동일 가중 포트폴리오
        
        Parameters
        ----------
        selected_tickers : list
            선택된 티커 리스트
        rebalance_date : Timestamp
            리밸런싱 시점 (매수 시점)
        price_df : DataFrame
            가격 데이터
        
        Returns
        -------
        float
            포트폴리오 수익률 (12개월)
        """
        if len(selected_tickers) == 0:
            logger.warning("  포트폴리오 비어있음 → 수익률 0%")
            return 0.0
        
        # 매수 시점
        buy_date = rebalance_date
        
        # 매도 시점 (12개월 후)
        sell_date = buy_date + pd.DateOffset(months=self.holding_months)
        
        # 가격 추출
        buy_prices = price_df.loc[buy_date, selected_tickers] if buy_date in price_df.index else None
        sell_prices = price_df.loc[sell_date, selected_tickers] if sell_date in price_df.index else None
        
        if buy_prices is None or sell_prices is None:
            logger.warning(f"  가격 데이터 없음 (Buy: {buy_date}, Sell: {sell_date}) → 수익률 0%")
            return 0.0
        
        # 개별 티커 수익률
        ticker_returns = (sell_prices - buy_prices) / buy_prices
        ticker_returns = ticker_returns.dropna()
        
        if len(ticker_returns) == 0:
            logger.warning("  유효한 수익률 없음 → 수익률 0%")
            return 0.0
        
        # 동일 가중 평균
        portfolio_return = ticker_returns.mean()
        
        return portfolio_return
    
    def run(self) -> Dict[str, pd.DataFrame]:
        """
        전체 백테스트 파이프라인
        
        1. Step4 predictions 로드
        2. Step1 가격 데이터 로드
        3. 각 연도별로:
           a. Gap 기준 정렬
           b. $5 룰 적용
           c. 상위 N% 선택 (4가지 비율)
           d. 12개월 수익률 계산
        4. 성과 지표 계산
        5. 결과 저장
        
        Returns
        -------
        dict
            {ratio: results_df} 형태
        """
        logger.info("")
        logger.info("="*60)
        logger.info("  Step5: 백테스트 및 성과 평가 시작")
        logger.info("="*60)
        
        # 1. Step4 predictions 로드
        logger.info("[1단계] Step4 predictions 로드")
        predictions_df = pd.read_csv(CACHE_DIR / 'step4_predictions.csv', index_col=0)
        logger.info(f"  → Predictions: {len(predictions_df)}개")
        
        # 2. Step1 가격 데이터 로드
        logger.info("[2단계] Step1 가격 데이터 로드")
        price_df = pd.read_csv(CACHE_DIR / 'step1_px_close_m.csv', index_col=0, parse_dates=True)
        logger.info(f"  → 가격 데이터: {price_df.shape[0]}행 × {price_df.shape[1]}열")
        
        # 2.5. ⭐ 벤치마크 데이터 다운로드
        logger.info("[2.5단계] 벤치마크 (S&P 500) 다운로드")
        benchmark_prices = self.download_benchmark_data()
        
        # 벤치마크 데이터 검증
        if len(benchmark_prices) == 0:
            logger.error("  ❌ 벤치마크 데이터 다운로드 실패")
            logger.error("  → Alpha/Beta 계산 불가, 더미 벤치마크 사용")
            benchmark_prices = None
        else:
            logger.info(f"  ✅ 벤치마크 데이터 로드 완료: {len(benchmark_prices)}개월")
            logger.info(f"  → 기간: {benchmark_prices.index[0].strftime('%Y-%m')} ~ {benchmark_prices.index[-1].strftime('%Y-%m')}")
        
        # 3. 리밸런싱 연도 확인
        rebalance_years = sorted(predictions_df['FiscalYear'].unique())
        logger.info(f"[3단계] 리밸런싱 가능 연도: {len(rebalance_years)}년")
        logger.info(f"  → FY{rebalance_years[0]} ~ FY{rebalance_years[-1]}")
        
        # 4. 각 비율별로 백테스트
        logger.info(f"[4단계] 백테스트 실행 ({len(self.long_ratios)}가지 비율)")
        
        all_results = {}
        
        for ratio in self.long_ratios:
            logger.info(f"\n  === 롱 비율: {ratio*100:.0f}% ===")
            
            yearly_results = []
            
            for year in rebalance_years:
                logger.info(f"\n    FY{year} 리밸런싱:")
                
                # 해당 연도 predictions
                year_df = predictions_df[predictions_df['FiscalYear'] == year].copy()
                
                # Gap 기준 정렬 (내림차순)
                year_df = year_df.sort_values('Gap', ascending=False)
                
                logger.info(f"      후보 개수: {len(year_df)}")
                
                # 리밸런싱 시점 (FY 종료 = 12월 말 근처)
                # 간소화: FY{year} 12월 말로 가정
                rebalance_date = pd.Timestamp(f'{year}-12-31')
                
                # $5 룰 적용
                all_tickers = year_df['Ticker'].tolist()
                valid_tickers = self.apply_dollar_five_rule(all_tickers, rebalance_date, price_df)
                
                logger.info(f"      $5 룰 통과: {len(valid_tickers)}/{len(all_tickers)}")
                
                # 상위 N% 선택
                n_select = max(1, int(len(valid_tickers) * ratio))
                selected_tickers = [t for t in year_df['Ticker'] if t in valid_tickers][:n_select]
                
                logger.info(f"      선택: {len(selected_tickers)}개 티커")
                logger.info(f"      티커: {', '.join(selected_tickers)}")
                
                # 수익률 계산
                portfolio_return = self.calculate_portfolio_return(
                    selected_tickers,
                    rebalance_date,
                    price_df
                )
                
                logger.info(f"      수익률: {portfolio_return*100:.2f}%")
                
                yearly_results.append({
                    'Year': year,
                    'N_Candidates': len(year_df),
                    'N_Valid': len(valid_tickers),
                    'N_Selected': len(selected_tickers),
                    'Portfolio_Return': portfolio_return
                })
            
            # DataFrame으로 변환
            results_df = pd.DataFrame(yearly_results)
            all_results[ratio] = results_df
            
            # 요약 통계
            logger.info(f"\n  [요약 - {ratio*100:.0f}%]")
            logger.info(f"    평균 수익률: {results_df['Portfolio_Return'].mean()*100:.2f}%")
            logger.info(f"    표준편차: {results_df['Portfolio_Return'].std()*100:.2f}%")
            logger.info(f"    최고: {results_df['Portfolio_Return'].max()*100:.2f}%")
            logger.info(f"    최저: {results_df['Portfolio_Return'].min()*100:.2f}%")
        
        # 5. ⭐ 벤치마크 수익률 계산
        logger.info(f"\n[5단계] 벤치마크 수익률 계산")
        
        benchmark_annual_returns = []
        universe_annual_returns = []  # ⭐ 개선 3: Equal-Weighted
        
        if benchmark_prices is not None:
            for year in rebalance_years:
                buy_date = pd.Timestamp(f'{year}-12-31')
                sell_date = buy_date + pd.DateOffset(months=12)
                
                # S&P 500 벤치마크 (날짜 매칭 개선)
                try:
                    # 정확한 날짜 매칭 시도
                    if buy_date in benchmark_prices.index and sell_date in benchmark_prices.index:
                        buy_price = benchmark_prices.loc[buy_date]
                        sell_price = benchmark_prices.loc[sell_date]
                    else:
                        # Nearest date 사용 (asof)
                        buy_price = benchmark_prices.asof(buy_date)
                        sell_price = benchmark_prices.asof(sell_date)
                        
                        if pd.isna(buy_price) or pd.isna(sell_price):
                            raise ValueError(f"No benchmark data for FY{year}")
                    
                    bench_return = (sell_price - buy_price) / buy_price
                    benchmark_annual_returns.append(bench_return)
                    
                except Exception as e:
                    logger.warning(f"  FY{year} 벤치마크 수익률 계산 실패: {e}")
                    logger.warning(f"  → 해당 연도는 10% 사용")
                    benchmark_annual_returns.append(0.10)
                
                # ⭐ Equal-Weighted 유니버스 벤치마크
                universe_tickers = predictions_df[predictions_df['FiscalYear'] == year]['Ticker'].unique()
                
                if len(universe_tickers) > 0 and buy_date in price_df.index and sell_date in price_df.index:
                    returns_list = []
                    for ticker in universe_tickers:
                        if ticker in price_df.columns:
                            buy_px = price_df.loc[buy_date, ticker]
                            sell_px = price_df.loc[sell_date, ticker]
                            if pd.notna(buy_px) and pd.notna(sell_px) and buy_px > 0:
                                ret = (sell_px - buy_px) / buy_px
                                returns_list.append(ret)
                    
                    if len(returns_list) > 0:
                        universe_return = np.mean(returns_list)
                        universe_annual_returns.append(universe_return)
                        logger.debug(f"  FY{year} Equal-Weighted: {len(returns_list)}개 종목, {universe_return*100:.2f}%")
                    else:
                        universe_annual_returns.append(0.10)
                else:
                    universe_annual_returns.append(0.10)
            
            benchmark_returns = pd.Series(benchmark_annual_returns)
            universe_returns = pd.Series(universe_annual_returns)
            logger.info(f"  → S&P 500 벤치마크 수익률 계산 완료: {len(benchmark_returns)}개")
            logger.info(f"  → Equal-Weighted 유니버스 수익률 계산 완료: {len(universe_returns)}개")
        else:
            # 더미 벤치마크 (10%)
            benchmark_returns = pd.Series([0.10] * len(rebalance_years))
            universe_returns = pd.Series([0.10] * len(rebalance_years))
            logger.warning("  → 더미 벤치마크 사용 (10%)")
        
        # 6. 성과 지표 계산
        logger.info(f"\n[6단계] 성과 지표 계산")
        
        performance_summary = []
        
        for ratio, results_df in all_results.items():
            metrics = calculate_performance_metrics(
                results_df['Portfolio_Return'],
                benchmark_returns,
                risk_free_rate=RISK_FREE_RATE
            )
            
            # ⭐ Information Ratio 추가
            ir = calculate_information_ratio(
                results_df['Portfolio_Return'],
                benchmark_returns,
                periods_per_year=1  # 연간 데이터
            )
            metrics['Information_Ratio'] = ir
            
            metrics['Long_Ratio'] = ratio
            performance_summary.append(metrics)
            
            logger.info(f"\n  [지표 - {ratio*100:.0f}%]")
            logger.info(f"    CAGR: {metrics['Portfolio_CAGR']*100:.2f}%")
            logger.info(f"    Sharpe: {metrics['Portfolio_Sharpe']:.2f}")
            logger.info(f"    MDD: {metrics['Portfolio_MDD']*100:.2f}%")
            logger.info(f"    Benchmark CAGR: {metrics['Benchmark_CAGR']*100:.2f}%")
            logger.info(f"    Alpha: {metrics['Alpha']*100:.2f}%")
            logger.info(f"    IR: {ir:.2f}")
        
        # ⭐ 벤치마크 성과 지표 계산 (전략과 동일한 방식)
        years = len(benchmark_returns)
        benchmark_cagr = calculate_cagr(benchmark_returns, years)
        benchmark_sharpe = calculate_sharpe_ratio(benchmark_returns)
        
        # MDD는 cumulative returns 필요
        benchmark_cumulative = (1 + benchmark_returns).cumprod()
        benchmark_mdd = calculate_mdd(benchmark_cumulative)
        
        # ⭐ 30% 전략에 대해 벤치마크 비교 테이블 출력
        ratio_30_metrics = [m for m in performance_summary if m['Long_Ratio'] == 0.30]
        if ratio_30_metrics:
            m = ratio_30_metrics[0]
            
            # Win Rate 계산
            portfolio_ret = all_results[0.30]['Portfolio_Return']
            wins = (portfolio_ret > benchmark_returns).sum()
            win_rate = wins / len(portfolio_ret) if len(portfolio_ret) > 0 else 0.0
            
            logger.info(f"\n{'='*60}")
            logger.info(f"  📊 STRATEGY vs S&P 500 BENCHMARK COMPARISON")
            logger.info(f"{'='*60}")
            logger.info(f"")
            logger.info(f"  Metric              Strategy      S&P 500       Performance")
            logger.info(f"  {'-'*58}")
            
            # CAGR
            cagr_diff = (m['Portfolio_CAGR'] - benchmark_cagr) * 100
            cagr_emoji = "✅" if cagr_diff > 0 else "❌"
            logger.info(f"  CAGR                {m['Portfolio_CAGR']*100:6.2f}%       {benchmark_cagr*100:6.2f}%       {cagr_emoji} {cagr_diff:+.2f}%p")
            
            # Sharpe
            sharpe_diff = m['Portfolio_Sharpe'] - benchmark_sharpe
            sharpe_emoji = "✅" if sharpe_diff > 0 else "❌"
            sharpe_label = "Efficient" if sharpe_diff > 0 else "Inefficient"
            logger.info(f"  Sharpe Ratio        {m['Portfolio_Sharpe']:6.2f}        {benchmark_sharpe:6.2f}        {sharpe_emoji} {sharpe_label}")
            
            # MDD (더 작은 절댓값이 좋음)
            mdd_diff = (m['Portfolio_MDD'] - benchmark_mdd) * 100
            mdd_emoji = "✅" if mdd_diff > 0 else "❌"  # MDD가 덜 마이너스면 좋음
            mdd_label = "Defensive" if mdd_diff > 0 else "Aggressive"
            logger.info(f"  MDD                 {m['Portfolio_MDD']*100:6.2f}%       {benchmark_mdd*100:6.2f}%       {mdd_emoji} {mdd_label}")
            
            # Alpha
            alpha_display = f"{m['Alpha']*100:6.2f}%" if not np.isnan(m['Alpha']) else "  nan%"
            logger.info(f"  Alpha               {alpha_display}        0.00%        -")
            
            # Win Rate
            logger.info(f"  Win Rate            {win_rate*100:6.1f}%        -             -")
            
            logger.info(f"  {'-'*58}")
            logger.info(f"")
            logger.info(f"  ✅ = Outperformed | ❌ = Underperformed")
            logger.info(f"{'='*60}")
        
        performance_df = pd.DataFrame(performance_summary)
        
        # 7. 저장
        logger.info(f"\n[7단계] 결과 저장")
        
        # 연도별 수익률 (모든 비율)
        combined_returns = pd.DataFrame({'Year': results_df['Year']})
        for ratio, results_df in all_results.items():
            combined_returns[f'Return_{int(ratio*100)}pct'] = results_df['Portfolio_Return'].values
        
        # 벤치마크 추가
        combined_returns['Benchmark_SP500'] = benchmark_returns.values
        combined_returns['Benchmark_EqualWeight'] = universe_returns.values
        
        output_path_returns = CACHE_DIR / 'step5_backtest_returns.csv'
        combined_returns.to_csv(output_path_returns, index=False)
        logger.info(f"  → 연도별 수익률: {output_path_returns}")
        
        # 성과 지표
        output_path_metrics = CACHE_DIR / 'step5_backtest_metrics.csv'
        performance_df.to_csv(output_path_metrics, index=False)
        logger.info(f"  → 성과 지표: {output_path_metrics}")
        
        # 8. ⭐ 그래프 그리기
        self.plot_performance(combined_returns)
        
        # 8. ⚠️ 생존 편향 경고
        logger.warning("")
        logger.warning("="*60)
        logger.warning("  ⚠️  SURVIVORSHIP BIAS WARNING  ⚠️")
        logger.warning("="*60)
        logger.warning("본 백테스트는 생존 편향(Survivorship Bias)에 노출되어 있습니다.")
        logger.warning("")
        logger.warning("문제점:")
        logger.warning("  - 데이터 소스: yfinance (무료 버전)")
        logger.warning("  - 상장폐지/파산 종목 데이터 미포함 (테스트 결과: SIVB, TWTR 없음)")
        logger.warning("  - 현재 데이터셋: 450개 티커 모두 2026년까지 생존")
        logger.warning("")
        logger.warning("영향:")
        logger.warning("  - 실제 수익률은 보고된 값보다 20-40% 낮을 수 있습니다.")
        logger.warning("  - 보수적 추정: CAGR × 0.6 ~ 0.8")
        logger.warning("")
        logger.warning("권장 조치:")
        logger.warning("  1. S&P 500 Historical Constituents 데이터 확보")
        logger.warning("  2. Bloomberg/FactSet 등 유료 데이터 활용")
        logger.warning("  3. 리포트에 이 한계 명시")
        logger.warning("="*60)
        logger.warning("")
        
        logger.info("")
        logger.info("="*60)
        logger.info("  Step5: 백테스트 완료")
        logger.info("="*60)
        
        return all_results

    def plot_performance(self, df: pd.DataFrame):
        """
        백테스트 성과 시각화
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.ticker as mtick
            
            plt.figure(figsize=(12, 6))
            
            # 누적 수익률 계산
            years = df['Year']
            
            # 벤치마크
            cum_sp500 = (1 + df['Benchmark_SP500']).cumprod() - 1
            cum_ew = (1 + df['Benchmark_EqualWeight']).cumprod() - 1
            
            plt.plot(years, cum_sp500 * 100, 'k--', label='S&P 500', linewidth=2, alpha=0.7)
            plt.plot(years, cum_ew * 100, 'g-.', label='Equal-Weighted', linewidth=2, alpha=0.7)
            
            # 포트폴리오 (Best & Worst case or selected ones)
            # 여기서는 30% 비율을 메인으로 표시 (M-Model)
            if 'Return_30pct' in df.columns:
                cum_port = (1 + df['Return_30pct']).cumprod() - 1
                plt.plot(years, cum_port * 100, 'r-', label='M-Model (Top 30%)', linewidth=3)
            
            if 'Return_10pct' in df.columns:
                cum_10 = (1 + df['Return_10pct']).cumprod() - 1
                plt.plot(years, cum_10 * 100, 'b-', label='Top 10%', linewidth=1, alpha=0.5)

            plt.title('M-Model Backtest Performance vs Benchmarks (S&P 500)', fontsize=14)
            plt.xlabel('Year')
            plt.ylabel('Cumulative Return (%)')
            plt.grid(True, linestyle='--', alpha=0.5)
            plt.legend()
            
            # Y축 % 포맷
            plt.gca().yaxis.set_major_formatter(mtick.PercentFormatter())
            
            output_path = CACHE_DIR / 'step5_performance_plot.png'
            plt.savefig(output_path)
            logger.info(f"  → 성과 그래프: {output_path}")
            plt.close()
            
        except Exception as e:
            logger.warning(f"그래프 그리기 실패: {e}")


# ===========================================
# Main 실행
# ===========================================
if __name__ == '__main__':
    """
    콘솔에서 직접 실행 시
    """
    backtester = PortfolioBacktester()
    results = backtester.run()
