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
        
        # ⭐ 포트폴리오 히스토리 저장용 (Step 5.5)
        self.portfolio_history = {}  # {ratio: [{year, tickers, gaps, ...}, ...]}
        
        logger.info("PortfolioBacktester 초기화 완료")
        logger.info(f"  - 롱 비율: {long_ratios}")
        logger.info(f"  - 홀딩 기간: {holding_months}개월")
        logger.info(f"  - 리밸런싱: 매년 {rebalance_month}월")
        logger.info(f"  - 벤치마크: {BENCHMARK_INDICES} (하드코딩 Price Return)")
    
    def get_benchmark_returns(self, year: int) -> dict:
        """
        특정 연도의 벤치마크 수익률 조회 (하드코딩 데이터)
        
        Parameters
        ----------
        year : int
            조회할 연도 (리밸런싱 연도)
        
        Returns
        -------
        dict
            각 벤치마크 지수별 수익률
            {'S&P500': 0.1341, 'Russell1000': 0.1392, ...}
        """
        # 리밸런싱은 year년 12월에 하고, year+1년 수익률을 측정
        return_year = year + 1
        
        if return_year in BENCHMARK_RETURNS:
            return BENCHMARK_RETURNS[return_year]
        else:
            logger.warning(f"  ⚠️ {return_year}년 벤치마크 데이터 없음 (기본값 0% 사용)")
            return {idx: 0.0 for idx in BENCHMARK_INDICES}
    
    # ============================================
    # [DEPRECATED] 동적 다운로드 방식 - 더 이상 사용 안함
    # ============================================
    # def download_benchmark_data(
    #     self,
    #     start_date: str = '2010-01-01',
    #     end_date: str = None
    # ) -> pd.Series:
    #     """
    #     S&P 500 벤치마크 데이터 다운로드
    #     
    #     ⚠️ DEPRECATED: yfinance 동적 다운로드 방식 폐기
    #     - 배당 포함 여부(Total Return vs Price Return) 불명확
    #     - 리밸런싱 시점 매칭 문제
    #     - 데이터 무결성 이슈
    #     
    #     → 대신 BENCHMARK_RETURNS 하드코딩 데이터 사용
    #     """
    #     pass
    
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
        
        1. Step4 predictions 로드 (Gap 컬럼 사용)
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
        logger.info(f"  → Gap 통계: 평균 {predictions_df['Gap'].mean():.4f}, 표준편차 {predictions_df['Gap'].std():.4f}")
        
        # 1.5 Step3 features 로드 (MarketCap 정보)
        logger.info("[1.5단계] Step3 features 로드 (MarketCap)")
        features_df = pd.read_csv(CACHE_DIR / 'step3_features_annual.csv', index_col=0)
        
        # MarketCap 병합
        predictions_df = predictions_df.merge(
            features_df[['Ticker', 'FiscalYear', 'MarketCap']],
            on=['Ticker', 'FiscalYear'],
            how='left'
        )
        logger.info(f"  → MarketCap 병합 완료 (결측: {predictions_df['MarketCap'].isna().sum()}개)")
        
        # 2. Step1 가격 데이터 로드
        logger.info("[2단계] Step1 가격 데이터 로드")
        price_df = pd.read_csv(CACHE_DIR / 'step1_px_close_m.csv', index_col=0, parse_dates=[0])
        price_df.index = pd.to_datetime(price_df.index, utc=True)
        price_df.index = price_df.index.normalize()
        logger.info(f"  → 가격 데이터: {price_df.shape[0]}행 × {price_df.shape[1]}열")
        
        # 2.5. 벤치마크 데이터 (하드코딩 Price Return 사용)
        logger.info("[2.5단계] 벤치마크 데이터 로드 (하드코딩 Price Return)")
        logger.info(f"  → 벤치마크 지수: {BENCHMARK_INDICES}")
        logger.info(f"  → 데이터 연도: {min(BENCHMARK_RETURNS.keys())} ~ {max(BENCHMARK_RETURNS.keys())}")
        
        # 3. 리밸런싱 연도 확인
        rebalance_years = sorted(predictions_df['FiscalYear'].unique())
        logger.info(f"[3단계] 리밸런싱 가능 연도: {len(rebalance_years)}년")
        logger.info(f"  → FY{rebalance_years[0]} ~ FY{rebalance_years[-1]}")
        
        # 4. 각 비율별로 백테스트
        logger.info(f"[4단계] 백테스트 실행 ({len(self.long_ratios)}가지 비율)")
        
        all_results = {}
        self.portfolio_history = {}
        
        for ratio in self.long_ratios:
            logger.info(f"\n  === 롱 비율: {ratio*100:.0f}% ===")
            
            yearly_results = []
            
            for year in rebalance_years:
                # 해당 연도 predictions
                year_df = predictions_df[predictions_df['FiscalYear'] == year].copy()
                
                # Gap 기준 정렬 (내림차순)
                year_df = year_df.sort_values('Gap', ascending=False)
                
                # 리밸런싱 시점
                rebalance_date = pd.Timestamp(f'{year}-12-31').tz_localize('UTC')
                
                # $5 룰 적용
                all_tickers = year_df['Ticker'].tolist()
                valid_tickers = self.apply_dollar_five_rule(all_tickers, rebalance_date, price_df)
                
                # 상위 N% 선택
                n_select = max(1, int(len(valid_tickers) * ratio))
                selected_tickers = [t for t in year_df['Ticker'] if t in valid_tickers][:n_select]
                
                # 선택된 티커의 Gap 정보
                selected_gaps = year_df[year_df['Ticker'].isin(selected_tickers)][['Ticker', 'Gap', 'y', 'yhat']].to_dict('records')
                
                # 수익률 계산
                portfolio_return = self.calculate_portfolio_return(
                    selected_tickers,
                    rebalance_date,
                    price_df
                )
                
                logger.debug(f"    FY{year}: {len(selected_tickers)}개 선택, 수익률 {portfolio_return*100:.2f}%")
                
                yearly_results.append({
                    'Year': year,
                    'N_Candidates': len(year_df),
                    'N_Selected': len(selected_tickers),
                    'Portfolio_Return': portfolio_return,
                    '_selected_tickers': selected_tickers,
                    '_selected_gaps': selected_gaps
                })
            
            # DataFrame 변환
            results_df = pd.DataFrame(yearly_results)
            all_results[f'Gap_{ratio*100:.0f}%'] = results_df
            
            # 포트폴리오 히스토리 저장
            self.portfolio_history[ratio] = [
                {
                    'year': r['Year'],
                    'tickers': r['_selected_tickers'],
                    'gaps': r['_selected_gaps'],
                    'return': r['Portfolio_Return']
                }
                for r in yearly_results
            ]
            
            logger.info(f"  [Gap {ratio*100:.0f}%] 평균 수익률: {results_df['Portfolio_Return'].mean()*100:.2f}%")
        
        # 4.5 소형주 전략 (시가총액 하위 50% 내에서 Gap 상위 N%)
        logger.info(f"\n[4.5단계] 소형주 (SmallCap) 전략 실행")
        
        smallcap_ratios = [0.05, 0.10, 0.20]  # SmallCap 비율
        
        for ratio in smallcap_ratios:
            logger.info(f"\n  === SmallCap 롱 비율: {ratio*100:.0f}% ===")
            
            yearly_results = []
            
            for year in rebalance_years:
                # 해당 연도 predictions (MarketCap 포함)
                year_df = predictions_df[predictions_df['FiscalYear'] == year].copy()
                
                # MarketCap 유효한 기업만
                year_df = year_df.dropna(subset=['MarketCap'])
                
                if len(year_df) == 0:
                    logger.warning(f"    FY{year}: MarketCap 데이터 없음 (스킵)")
                    yearly_results.append({
                        'Year': year,
                        'N_Candidates': 0,
                        'N_Selected': 0,
                        'Portfolio_Return': 0.0,
                        '_selected_tickers': [],
                        '_selected_gaps': []
                    })
                    continue
                
                # 시가총액 중앙값 계산
                median_marketcap = year_df['MarketCap'].median()
                
                # 시가총액 하위 50% (소형주)
                smallcap_df = year_df[year_df['MarketCap'] <= median_marketcap].copy()
                
                # Gap 기준 정렬 (내림차순)
                smallcap_df = smallcap_df.sort_values('Gap', ascending=False)
                
                # 리밸런싱 시점
                rebalance_date = pd.Timestamp(f'{year}-12-31').tz_localize('UTC')
                
                # $5 룰 적용
                all_tickers = smallcap_df['Ticker'].tolist()
                valid_tickers = self.apply_dollar_five_rule(all_tickers, rebalance_date, price_df)
                
                # 상위 N% 선택 (소형주 내에서)
                n_select = max(1, int(len(valid_tickers) * ratio))
                selected_tickers = [t for t in smallcap_df['Ticker'] if t in valid_tickers][:n_select]
                
                # 선택된 티커의 Gap 정보
                selected_gaps = smallcap_df[smallcap_df['Ticker'].isin(selected_tickers)][['Ticker', 'Gap', 'y', 'yhat']].to_dict('records')
                
                # 수익률 계산
                portfolio_return = self.calculate_portfolio_return(
                    selected_tickers,
                    rebalance_date,
                    price_df
                )
                
                logger.debug(f"    FY{year}: 소형주 {len(smallcap_df)}개 중 {len(selected_tickers)}개 선택, 수익률 {portfolio_return*100:.2f}%")
                
                yearly_results.append({
                    'Year': year,
                    'N_Candidates': len(smallcap_df),
                    'N_Selected': len(selected_tickers),
                    'Portfolio_Return': portfolio_return,
                    '_selected_tickers': selected_tickers,
                    '_selected_gaps': selected_gaps
                })
            
            # DataFrame 변환
            results_df = pd.DataFrame(yearly_results)
            all_results[f'SmallCap_{ratio*100:.0f}%'] = results_df
            
            # 포트폴리오 히스토리 저장
            self.portfolio_history[f'SmallCap_{ratio}'] = [
                {
                    'year': r['Year'],
                    'tickers': r['_selected_tickers'],
                    'gaps': r['_selected_gaps'],
                    'return': r['Portfolio_Return']
                }
                for r in yearly_results
            ]
            
            logger.info(f"  [SmallCap {ratio*100:.0f}%] 평균 수익률: {results_df['Portfolio_Return'].mean()*100:.2f}%")
        
        # 5. 벤치마크 수익률 계산 (하드코딩 데이터 사용)
        logger.info(f"\n[5단계] 벤치마크 수익률 계산 (하드코딩 Price Return)")
        
        # 각 벤치마크 지수별 연도별 수익률 저장
        benchmark_returns_by_index = {idx: [] for idx in BENCHMARK_INDICES}
        
        for year in rebalance_years:
            bench_data = self.get_benchmark_returns(year)
            for idx in BENCHMARK_INDICES:
                benchmark_returns_by_index[idx].append(bench_data.get(idx, 0.0))
        
        # S&P 500을 기본 벤치마크로 사용 (성과 지표 계산용)
        benchmark_returns = pd.Series(benchmark_returns_by_index['S&P500'])
        
        logger.info(f"  → 리밸런싱 연도: {rebalance_years}")
        logger.info(f"  → S&P 500 평균: {benchmark_returns.mean()*100:.2f}%")
        logger.info(f"  → Russell 2000 평균: {np.mean(benchmark_returns_by_index['Russell2000'])*100:.2f}%")
        
        # 6. 성과 지표 계산 (5개 벤치마크 대비)
        logger.info(f"\n[6단계] 성과 지표 계산 (5개 벤치마크 대비)")
        
        performance_summary = []
        
        for ratio_key, results_df in all_results.items():
            # S&P 500 기준 메인 지표
            metrics = calculate_performance_metrics(
                results_df['Portfolio_Return'],
                benchmark_returns,
                risk_free_rate=RISK_FREE_RATE
            )
            
            ir = calculate_information_ratio(
                results_df['Portfolio_Return'],
                benchmark_returns,
                periods_per_year=1
            )
            metrics['Information_Ratio'] = ir
            metrics['Long_Ratio'] = ratio_key
            
            # ⭐ 각 벤치마크 대비 Alpha 추가 계산
            portfolio_returns = results_df['Portfolio_Return'].values
            for idx in BENCHMARK_INDICES:
                idx_returns = np.array(benchmark_returns_by_index[idx])
                alpha_vs_idx = np.mean(portfolio_returns - idx_returns)
                metrics[f'Alpha_vs_{idx}'] = alpha_vs_idx
            
            performance_summary.append(metrics)
            
            logger.info(f"\n  [지표 - {ratio_key}]")
            logger.info(f"    CAGR: {metrics['Portfolio_CAGR']*100:.2f}%")
            logger.info(f"    Sharpe: {metrics['Portfolio_Sharpe']:.2f}")
            logger.info(f"    MDD: {metrics['Portfolio_MDD']*100:.2f}%")
            logger.info(f"    Alpha (vs S&P500): {metrics['Alpha_vs_S&P500']*100:.2f}%")
            logger.info(f"    Alpha (vs Russell2000): {metrics['Alpha_vs_Russell2000']*100:.2f}%")
            logger.info(f"    IR: {ir:.2f}")
        
        # 7. 결과 저장 (5개 벤치마크 포함)
        logger.info(f"\n[7단계] 결과 저장 (5개 벤치마크 포함)")
        
        # 성과 지표 저장
        summary_df = pd.DataFrame(performance_summary)
        summary_df.to_csv(CACHE_DIR / 'step5_backtest_metrics.csv', index=False)
        logger.info(f"  ✅ 성과 지표: {CACHE_DIR / 'step5_backtest_metrics.csv'}")
        
        # 연도별 수익률 저장 (5개 벤치마크 모두 포함)
        returns_dict = {'Year': rebalance_years}
        for ratio_key, results_df in all_results.items():
            returns_dict[ratio_key] = results_df['Portfolio_Return'].values
        
        # 5개 벤치마크 모두 추가
        for idx in BENCHMARK_INDICES:
            returns_dict[idx] = benchmark_returns_by_index[idx]
        
        # Alpha 계산 (대표 포트폴리오 기준)
        if 'Gap_10%' in all_results:
            main_portfolio = all_results['Gap_10%']['Portfolio_Return'].values
            returns_dict['Alpha_vs_SP500'] = main_portfolio - np.array(benchmark_returns_by_index['S&P500'])
            returns_dict['Alpha_vs_R2000'] = main_portfolio - np.array(benchmark_returns_by_index['Russell2000'])
        
        returns_df = pd.DataFrame(returns_dict)
        returns_df.to_csv(CACHE_DIR / 'step5_backtest_returns.csv', index=False)
        logger.info(f"  ✅ 연도별 수익률: {CACHE_DIR / 'step5_backtest_returns.csv'}")
        logger.info(f"     → 컬럼: Year, Portfolio Returns, {', '.join(BENCHMARK_INDICES)}, Alpha")
        
        # 포트폴리오 히스토리 저장
        self.save_portfolio_history()
        
        # 8. Survivorship Bias 경고
        logger.warning("")
        logger.warning("="*60)
        logger.warning("⚠️  경고: Survivorship Bias 가능성")
        logger.warning("="*60)
        
        logger.info("")
        logger.info("="*60)
        logger.info("  Step5: 백테스트 완료")
        logger.info("="*60)
        
        return all_results

    def save_portfolio_history(self) -> None:
        """
        Step 5.5: 포트폴리오 히스토리 저장 (Excel)
        
        연도별 선택된 티커 리스트, Gap, 수익률 등을 Excel로 저장
        다른 개발자/분석가가 백테스트 결과를 상세히 확인 가능
        
        출력 파일: reports/backtest_portfolio_history.xlsx
        
        시트 구성:
        1. Summary: 각 비율별 요약 통계
        2. Top_5pct: 상위 5% 포트폴리오 연도별 상세
        3. Top_10pct: 상위 10% 포트폴리오 연도별 상세
        4. Top_20pct: 상위 20% 포트폴리오 연도별 상세
        5. Top_30pct: 상위 30% 포트폴리오 연도별 상세
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils.dataframe import dataframe_to_rows
            
            output_path = REPORTS_DIR / 'backtest_portfolio_history.xlsx'
            
            # 디렉토리 확인
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            
            wb = Workbook()
            
            # ============================================
            # Summary 시트
            # ============================================
            ws_summary = wb.active
            ws_summary.title = "Summary"
            
            # 헤더 스타일
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_align = Alignment(horizontal="center", vertical="center")
            
            # Summary 헤더
            summary_headers = ["Ratio", "Years", "Avg_Tickers", "Avg_Return", "Total_Return", "Best_Year", "Worst_Year"]
            for col, header in enumerate(summary_headers, 1):
                cell = ws_summary.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
            
            # Summary 데이터
            row_idx = 2
            for ratio, history in self.portfolio_history.items():
                if not history:
                    continue
                    
                avg_tickers = np.mean([len(h['tickers']) for h in history])
                avg_return = np.mean([h['return'] for h in history])
                total_return = np.prod([1 + h['return'] for h in history]) - 1
                best_year = max(history, key=lambda x: x['return'])
                worst_year = min(history, key=lambda x: x['return'])
                
                ws_summary.cell(row=row_idx, column=1, value=f"Top {ratio*100:.0f}%")
                ws_summary.cell(row=row_idx, column=2, value=len(history))
                ws_summary.cell(row=row_idx, column=3, value=round(avg_tickers, 1))
                ws_summary.cell(row=row_idx, column=4, value=f"{avg_return*100:.2f}%")
                ws_summary.cell(row=row_idx, column=5, value=f"{total_return*100:.2f}%")
                ws_summary.cell(row=row_idx, column=6, value=f"FY{best_year['year']} ({best_year['return']*100:.2f}%)")
                ws_summary.cell(row=row_idx, column=7, value=f"FY{worst_year['year']} ({worst_year['return']*100:.2f}%)")
                row_idx += 1
            
            # 컬럼 너비 조정
            ws_summary.column_dimensions['A'].width = 12
            ws_summary.column_dimensions['B'].width = 8
            ws_summary.column_dimensions['C'].width = 12
            ws_summary.column_dimensions['D'].width = 12
            ws_summary.column_dimensions['E'].width = 14
            ws_summary.column_dimensions['F'].width = 22
            ws_summary.column_dimensions['G'].width = 22
            
            # ============================================
            # 각 비율별 상세 시트
            # ============================================
            ratio_to_name = {
                0.05: "Top_5pct",
                0.10: "Top_10pct",
                0.20: "Top_20pct",
                0.30: "Top_30pct"
            }
            
            for ratio, history in self.portfolio_history.items():
                if not history:
                    continue
                
                sheet_name = ratio_to_name.get(ratio, f"Top_{ratio*100:.0f}pct")
                ws = wb.create_sheet(title=sheet_name)
                
                # 헤더
                headers = ["Year", "N_Tickers", "Return", "Ticker", "Gap", "y_actual", "yhat_pred", "Rank"]
                for col, header in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=col, value=header)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_align
                
                # 데이터
                row_idx = 2
                for year_data in history:
                    year = year_data['year']
                    tickers = year_data['tickers']
                    gaps = year_data['gaps']
                    ret = year_data['return']
                    
                    # 각 티커별로 한 줄씩
                    for rank, gap_info in enumerate(gaps, 1):
                        ws.cell(row=row_idx, column=1, value=f"FY{year}")
                        ws.cell(row=row_idx, column=2, value=len(tickers))
                        ws.cell(row=row_idx, column=3, value=f"{ret*100:.2f}%")
                        ws.cell(row=row_idx, column=4, value=gap_info['Ticker'])
                        ws.cell(row=row_idx, column=5, value=round(gap_info['Gap'], 4) if gap_info.get('Gap') else None)
                        ws.cell(row=row_idx, column=6, value=round(gap_info['y'], 4) if gap_info.get('y') else None)
                        ws.cell(row=row_idx, column=7, value=round(gap_info['yhat'], 4) if gap_info.get('yhat') else None)
                        ws.cell(row=row_idx, column=8, value=rank)
                        row_idx += 1
                    
                    # 연도 구분선 (빈 행 추가)
                    row_idx += 1
                
                # 컬럼 너비 조정
                ws.column_dimensions['A'].width = 10
                ws.column_dimensions['B'].width = 12
                ws.column_dimensions['C'].width = 10
                ws.column_dimensions['D'].width = 10
                ws.column_dimensions['E'].width = 10
                ws.column_dimensions['F'].width = 12
                ws.column_dimensions['G'].width = 12
                ws.column_dimensions['H'].width = 8
            
            # 저장
            wb.save(output_path)
            logger.info(f"  → 포트폴리오 히스토리: {output_path}")
            logger.info(f"     - Summary 시트: 각 비율별 요약 통계")
            logger.info(f"     - Top_5pct/10pct/20pct/30pct: 연도별 선택 티커 상세")
            
        except ImportError:
            logger.warning("  ⚠️ openpyxl 패키지 없음 - 포트폴리오 히스토리 Excel 저장 스킵")
            logger.warning("     pip install openpyxl 로 설치 후 재실행")
        except Exception as e:
            logger.error(f"  ❌ 포트폴리오 히스토리 저장 실패: {e}")

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
