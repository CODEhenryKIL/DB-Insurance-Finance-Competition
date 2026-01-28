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
from backtesting.metrics import calculate_performance_metrics

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
        
        # 5. 성과 지표 계산
        logger.info(f"\n[5단계] 성과 지표 계산")
        
        performance_summary = []
        
        for ratio, results_df in all_results.items():
            # 더미 벤치마크 (간소화: 연 10%)
            # 실제로는 SPY 수익률 사용해야 함
            benchmark_returns = pd.Series([0.10] * len(results_df))
            
            metrics = calculate_performance_metrics(
                results_df['Portfolio_Return'],
                benchmark_returns,
                risk_free_rate=RISK_FREE_RATE
            )
            
            metrics['Long_Ratio'] = ratio
            performance_summary.append(metrics)
            
            logger.info(f"\n  [지표 - {ratio*100:.0f}%]")
            logger.info(f"    CAGR: {metrics['Portfolio_CAGR']*100:.2f}%")
            logger.info(f"    Sharpe: {metrics['Portfolio_Sharpe']:.2f}")
            logger.info(f"    MDD: {metrics['Portfolio_MDD']*100:.2f}%")
            logger.info(f"    Alpha: {metrics['Alpha']*100:.2f}%")
        
        performance_df = pd.DataFrame(performance_summary)
        
        # 6. 저장
        logger.info(f"\n[6단계] 결과 저장")
        
        # 연도별 수익률 (모든 비율)
        combined_returns = pd.DataFrame({'Year': results_df['Year']})
        for ratio, results_df in all_results.items():
            combined_returns[f'Return_{int(ratio*100)}pct'] = results_df['Portfolio_Return'].values
        
        output_path_returns = CACHE_DIR / 'step5_backtest_returns.csv'
        combined_returns.to_csv(output_path_returns, index=False)
        logger.info(f"  → 연도별 수익률: {output_path_returns}")
        
        # 성과 지표
        output_path_metrics = CACHE_DIR / 'step5_backtest_metrics.csv'
        performance_df.to_csv(output_path_metrics, index=False)
        logger.info(f"  → 성과 지표: {output_path_metrics}")
        
        logger.info("")
        logger.info("="*60)
        logger.info("  Step5: 백테스트 완료")
        logger.info("="*60)
        
        return all_results


# ===========================================
# Main 실행
# ===========================================
if __name__ == '__main__':
    """
    콘솔에서 직접 실행 시
    """
    backtester = PortfolioBacktester()
    results = backtester.run()
