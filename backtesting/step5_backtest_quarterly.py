"""
===========================================
Step5: 백테스트 및 성과 평가 (분기별)
===========================================

분기별 리밸런싱 백테스트
- Gap 기반 롱 전략
- 3/6/9/12월 리밸런싱
- 3개월 홀딩

핵심 차이점 (연간 대비):
- 리밸런싱 주기: 분기 (3, 6, 9, 12월 말)
- 홀딩 기간: 3개월
- 연간 4회 리밸런싱
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import datetime
from tqdm import tqdm

from config.constants import (
    LONG_RATIOS,
    PRICE_THRESHOLD_DOLLARS,
    PRICE_BELOW_THRESHOLD_RATIO,
    PRICE_CHECK_MONTHS,
    BENCHMARK_RETURNS,
    BENCHMARK_INDICES,
    RISK_FREE_RATE,
    EXCLUDED_SECTORS
)
from config.paths import CACHE_DIR, REPORTS_DIR
from utils.logger import get_logger
from backtesting.metrics import (
    calculate_performance_metrics,
    calculate_information_ratio,
    calculate_cagr,
    calculate_sharpe_ratio,
    calculate_mdd
)

logger = get_logger(__name__)

# 분기용 상수
HOLDING_PERIOD_MONTHS_QUARTERLY = 3
REBALANCE_MONTHS_QUARTERLY = [3, 6, 9, 12]  # 분기 말

# ⭐ Safe Lag: 공시 지연을 고려한 리밸런싱 시점 지연
# 10-Q 공시는 분기 말 후 약 45일 (1.5개월) 뒤
# 안전을 위해 2~3개월 지연 권장
SAFE_LAG_MONTHS = 3


class QuarterlyPortfolioBacktester:
    """
    분기별 Gap 기반 롱 전략 백테스터
    """
    
    def __init__(
        self,
        long_ratios: List[float] = LONG_RATIOS,
        holding_months: int = HOLDING_PERIOD_MONTHS_QUARTERLY,
        rebalance_months: List[int] = REBALANCE_MONTHS_QUARTERLY
    ):
        self.long_ratios = long_ratios
        self.holding_months = holding_months
        self.rebalance_months = rebalance_months
        
        self.portfolio_history = {}
        
        logger.info("Quarterly PortfolioBacktester 초기화 완료")
        logger.info(f"  - 롱 비율: {long_ratios}")
        logger.info(f"  - 홀딩 기간: {holding_months}개월")
        logger.info(f"  - 리밸런싱: {rebalance_months}월")
    
    def apply_dollar_five_rule(
        self,
        tickers: List[str],
        rebalance_date: pd.Timestamp,
        price_df: pd.DataFrame
    ) -> List[str]:
        """$5 룰 적용"""
        start_date = rebalance_date - pd.DateOffset(months=PRICE_CHECK_MONTHS)
        recent_prices = price_df.loc[start_date:rebalance_date]
        
        valid_tickers = []
        
        for ticker in tickers:
            if ticker not in recent_prices.columns:
                continue
            
            ticker_prices = recent_prices[ticker].dropna()
            
            if len(ticker_prices) == 0:
                continue
            
            below_threshold_ratio = (ticker_prices <= PRICE_THRESHOLD_DOLLARS).mean()
            
            if below_threshold_ratio >= PRICE_BELOW_THRESHOLD_RATIO:
                continue
            
            valid_tickers.append(ticker)
        
        return valid_tickers
    
    def calculate_portfolio_return(
        self,
        selected_tickers: List[str],
        rebalance_date: pd.Timestamp,
        price_df: pd.DataFrame
    ) -> float:
        """포트폴리오 수익률 계산 (3개월 홀딩)"""
        if len(selected_tickers) == 0:
            return 0.0
        
        buy_date = rebalance_date
        sell_date = buy_date + pd.DateOffset(months=self.holding_months)
        
        # 가격 추출
        if buy_date not in price_df.index:
            # 가장 가까운 날짜 찾기
            buy_date = price_df.index[price_df.index <= buy_date].max() if len(price_df.index[price_df.index <= buy_date]) > 0 else None
        
        if sell_date not in price_df.index:
            sell_date = price_df.index[price_df.index >= sell_date].min() if len(price_df.index[price_df.index >= sell_date]) > 0 else None
        
        if buy_date is None or sell_date is None:
            return 0.0
        
        buy_prices = price_df.loc[buy_date, selected_tickers]
        sell_prices = price_df.loc[sell_date, selected_tickers]
        
        ticker_returns = (sell_prices - buy_prices) / buy_prices
        ticker_returns = ticker_returns.dropna()
        
        if len(ticker_returns) == 0:
            return 0.0
        
        return ticker_returns.mean()
    
    def run(self) -> Dict[str, pd.DataFrame]:
        """
        분기별 백테스트 파이프라인
        """
        logger.info("")
        logger.info("="*60)
        logger.info("  Step5 (Quarterly): 백테스트 시작")
        logger.info("="*60)
        
        # 1. 분기별 predictions 로드
        logger.info("[1단계] 분기별 predictions 로드")
        predictions_path = CACHE_DIR / 'step4_predictions_quarterly.csv'
        
        if not predictions_path.exists():
            logger.error(f"❌ 분기별 predictions 없음: {predictions_path}")
            logger.error("먼저 실행: python modeling/step4_train_predict_quarterly.py")
            raise FileNotFoundError(f"분기별 predictions 없음: {predictions_path}")
        
        predictions_df = pd.read_csv(predictions_path, index_col=0)
        logger.info(f"  → Predictions: {len(predictions_df)}개")
        
        # 1.5 Features 로드 (MarketCap)
        features_path = CACHE_DIR / 'step3_features_quarterly.csv'
        if features_path.exists():
            features_df = pd.read_csv(features_path, index_col=0)
            predictions_df = predictions_df.merge(
                features_df[['Ticker', 'FiscalYear', 'FiscalQuarter', 'MarketCap']],
                on=['Ticker', 'FiscalYear', 'FiscalQuarter'],
                how='left'
            )
        
        # 2. 가격 데이터 로드
        logger.info("[2단계] 가격 데이터 로드")
        price_df = pd.read_csv(CACHE_DIR / 'step1_px_close_m.csv', index_col=0, parse_dates=[0])
        price_df.index = pd.to_datetime(price_df.index, utc=True)
        price_df.index = price_df.index.normalize()
        logger.info(f"  → 가격 데이터: {price_df.shape[0]}행 × {price_df.shape[1]}열")
        
        # 3. 리밸런싱 시점 확인
        rebalance_periods = predictions_df.groupby(['FiscalYear', 'FiscalQuarter']).size().reset_index()
        rebalance_periods = rebalance_periods.sort_values(['FiscalYear', 'FiscalQuarter'])
        logger.info(f"[3단계] 리밸런싱 기간: {len(rebalance_periods)}분기")
        
        # 4. 각 비율별로 백테스트
        logger.info(f"[4단계] 백테스트 실행 ({len(self.long_ratios)}가지 비율)")
        
        all_results = {}
        self.portfolio_history = {}
        
        for ratio in self.long_ratios:
            logger.info(f"\n  === 롱 비율: {ratio*100:.0f}% ===")
            
            quarterly_results = []
            
            for _, period_row in tqdm(rebalance_periods.iterrows(), total=len(rebalance_periods), desc=f"Gap {ratio*100:.0f}%"):
                year = int(period_row['FiscalYear'])
                quarter = int(period_row['FiscalQuarter'])
                
                # 해당 분기 predictions
                period_df = predictions_df[
                    (predictions_df['FiscalYear'] == year) &
                    (predictions_df['FiscalQuarter'] == quarter)
                ].copy()
                
                if len(period_df) == 0:
                    continue
                
                # Gap 기준 정렬
                period_df = period_df.sort_values('Gap', ascending=False)
                
                # ⭐ 리밸런싱 시점 (분기 마지막 날 + Safe Lag)
                # Safe Lag: 공시 지연을 고려하여 실제 투자 시점 지연
                # Q1(3월) 실적 + 3개월 Lag → 6월 말 리밸런싱
                fiscal_month = self.rebalance_months[quarter - 1] if quarter <= len(self.rebalance_months) else 12
                fiscal_end = pd.Timestamp(year=year, month=fiscal_month, day=28).tz_localize('UTC')
                fiscal_end = fiscal_end + pd.offsets.MonthEnd(0)
                
                # Safe Lag 적용 (공시 지연 고려)
                rebalance_date = fiscal_end + pd.DateOffset(months=SAFE_LAG_MONTHS)
                rebalance_date = rebalance_date + pd.offsets.MonthEnd(0)  # 월말로 조정
                
                # $5 룰 적용
                all_tickers = period_df['Ticker'].tolist()
                valid_tickers = self.apply_dollar_five_rule(all_tickers, rebalance_date, price_df)
                
                # 상위 N% 선택
                n_select = max(1, int(len(valid_tickers) * ratio))
                selected_tickers = [t for t in period_df['Ticker'] if t in valid_tickers][:n_select]
                
                # 수익률 계산
                portfolio_return = self.calculate_portfolio_return(
                    selected_tickers,
                    rebalance_date,
                    price_df
                )
                
                quarterly_results.append({
                    'Year': year,
                    'Quarter': quarter,
                    'Period': f"{year}-Q{quarter}",
                    'N_Candidates': len(period_df),
                    'N_Selected': len(selected_tickers),
                    'Portfolio_Return': portfolio_return,
                    '_selected_tickers': selected_tickers
                })
            
            results_df = pd.DataFrame(quarterly_results)
            all_results[f'Gap_{ratio*100:.0f}%'] = results_df
            
            avg_return = results_df['Portfolio_Return'].mean() if len(results_df) > 0 else 0
            logger.info(f"  [Gap {ratio*100:.0f}%] 평균 분기 수익률: {avg_return*100:.2f}%")
            
            # 연환산 수익률 (분기 수익률 × 4)
            annualized = (1 + avg_return) ** 4 - 1
            logger.info(f"  [Gap {ratio*100:.0f}%] 연환산: {annualized*100:.2f}%")
        
        # 5. 성과 지표 계산
        logger.info(f"\n[5단계] 성과 지표 계산")
        
        performance_summary = []
        
        for ratio_key, results_df in all_results.items():
            if len(results_df) == 0:
                continue
            
            returns = results_df['Portfolio_Return'].values
            
            # 분기별 통계
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            total_return = np.prod(1 + returns) - 1
            annualized_return = (1 + mean_return) ** 4 - 1
            sharpe = (annualized_return - RISK_FREE_RATE) / (std_return * 2) if std_return > 0 else 0
            
            # MDD 계산 (누적 수익률 기준)
            cumulative = np.cumprod(1 + returns)
            peak = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - peak) / peak
            mdd = drawdown.min()
            
            metrics = {
                'Long_Ratio': ratio_key,
                'N_Quarters': len(returns),
                'Mean_Quarterly_Return': mean_return,
                'Annualized_Return': annualized_return,
                'Total_Return': total_return,
                'Sharpe': sharpe,
                'MDD': mdd,
                'Std_Return': std_return
            }
            
            performance_summary.append(metrics)
            
            logger.info(f"\n  [{ratio_key}]")
            logger.info(f"    분기 평균: {mean_return*100:.2f}%")
            logger.info(f"    연환산: {annualized_return*100:.2f}%")
            logger.info(f"    MDD: {mdd*100:.2f}%")
        
        # 6. 결과 저장
        logger.info(f"\n[6단계] 결과 저장")
        
        summary_df = pd.DataFrame(performance_summary)
        summary_df.to_csv(CACHE_DIR / 'step5_backtest_metrics_quarterly.csv', index=False)
        logger.info(f"  ✅ 성과 지표: step5_backtest_metrics_quarterly.csv")
        
        # 분기별 수익률 저장
        returns_list = []
        for ratio_key, results_df in all_results.items():
            for _, row in results_df.iterrows():
                returns_list.append({
                    'Year': row['Year'],
                    'Quarter': row['Quarter'],
                    'Period': row['Period'],
                    'Ratio': ratio_key,
                    'Return': row['Portfolio_Return']
                })
        
        returns_df = pd.DataFrame(returns_list)
        returns_df.to_csv(CACHE_DIR / 'step5_backtest_returns_quarterly.csv', index=False)
        logger.info(f"  ✅ 분기별 수익률: step5_backtest_returns_quarterly.csv")
        
        logger.info("")
        logger.info("="*60)
        logger.info("  Step5 (Quarterly) 완료")
        logger.info("="*60)
        
        return all_results


if __name__ == '__main__':
    backtester = QuarterlyPortfolioBacktester()
    results = backtester.run()
