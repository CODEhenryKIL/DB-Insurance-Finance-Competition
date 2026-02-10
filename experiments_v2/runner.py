"""
===========================================
실험 실행 (Runner)
===========================================

실험 로직 실행 및 결과 수집
- 설정 기반 백테스트 실행
- 일반주/소형주 분리
- 연도별 결과 수집
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from scipy.stats import spearmanr

from config.constants import BENCHMARK_RETURNS, BENCHMARK_INDICES
from config.paths import CACHE_DIR
from backtesting.metrics import (
    calculate_cagr,
    calculate_sharpe_ratio,
    calculate_mdd,
    calculate_alpha_beta,
    calculate_performance_metrics
)
from utils.logger import get_logger
from .config import ExperimentConfig

logger = get_logger(__name__)


@dataclass
class YearlyResult:
    """연도별 결과"""
    year: int
    portfolio_type: str  # "normal" or "smallcap"
    ratio: float  # 0.05, 0.10, 0.20, 0.30
    
    # 수익률
    portfolio_return: float = 0.0
    benchmark_returns: Dict[str, float] = field(default_factory=dict)
    
    # 포트폴리오 정보
    n_stocks: int = 0
    tickers: List[str] = field(default_factory=list)
    gaps: List[float] = field(default_factory=list)
    weights: List[float] = field(default_factory=list)


@dataclass
class ExperimentResults:
    """실험 전체 결과"""
    config: ExperimentConfig
    
    # 연도별 결과
    yearly_results: List[YearlyResult] = field(default_factory=list)
    
    # 모델 가중치 히스토리
    weights_history: pd.DataFrame = None
    
    # 예측 결과 (y, yhat, Gap, Rank)
    predictions_with_rank: pd.DataFrame = None
    
    # 성과 지표
    performance_metrics: Dict = field(default_factory=dict)
    
    # 검정 결과
    validation_tests: Dict = field(default_factory=dict)


class ExperimentRunner:
    """
    실험 실행 클래스
    
    설정 기반으로 백테스트 실행 및 결과 수집
    """
    
    def __init__(self, config: ExperimentConfig):
        """
        초기화
        
        Parameters
        ----------
        config : ExperimentConfig
            실험 설정
        """
        self.config = config
        
        # 데이터 로드
        self.predictions_df = None
        self.features_df = None
        self.price_df = None
        
        logger.info("="*60)
        logger.info(f"  실험 Runner 초기화: {config.exp_id}")
        logger.info("="*60)
    
    def load_data(self) -> None:
        """데이터 로드"""
        logger.info("[데이터 로드]")
        
        # Predictions
        pred_path = CACHE_DIR / self.config.predictions_file
        if not pred_path.exists():
            raise FileNotFoundError(f"Predictions 파일 없음: {pred_path}")
        
        self.predictions_df = pd.read_csv(pred_path, index_col=0)
        logger.info(f"  → Predictions: {len(self.predictions_df)}개")
        
        # Features (MarketCap, Sector 등)
        feat_path = CACHE_DIR / self.config.features_file
        self.features_df = pd.read_csv(feat_path, index_col=0)
        logger.info(f"  → Features: {len(self.features_df)}개")
        
        # MarketCap 병합
        self.predictions_df = self.predictions_df.merge(
            self.features_df[['Ticker', 'FiscalYear', 'MarketCap', 'Sector']],
            on=['Ticker', 'FiscalYear'],
            how='left'
        )
        
        # 가격 데이터
        price_path = CACHE_DIR / 'step1_px_close_m.csv'
        self.price_df = pd.read_csv(price_path, index_col=0, parse_dates=[0])
        self.price_df.index = pd.to_datetime(self.price_df.index, utc=True)
        logger.info(f"  → 가격 데이터: {self.price_df.shape}")
        
        # 가중치 히스토리 (있으면)
        if self.config.model_type == "RankNet":
            weights_path = CACHE_DIR / 'step4_weights_history_ranknet.csv'
        else:
            weights_path = CACHE_DIR / 'step4_weights_history.csv'
        
        if weights_path.exists():
            self.weights_df = pd.read_csv(weights_path)
            logger.info(f"  → 가중치 히스토리: {weights_path.name}")
        else:
            self.weights_df = None
    
    def add_ranks(self) -> None:
        """Gap 기준 연도별 순위 추가"""
        logger.info("[순위 계산]")
        
        # 연도별 Gap 순위 (내림차순, 높을수록 저평가)
        self.predictions_df['Gap_Rank'] = self.predictions_df.groupby('FiscalYear')['Gap'].rank(
            ascending=False, method='min'
        )
        
        # 연도별 Gap 백분위
        self.predictions_df['Gap_Percentile'] = self.predictions_df.groupby('FiscalYear')['Gap'].rank(
            pct=True
        )
        
        # 소형주 플래그 (MarketCap 하위 N%)
        # transform 사용하여 FiscalYear 컬럼 보존
        def get_smallcap_threshold(marketcaps):
            return marketcaps.quantile(self.config.smallcap_percentile)
        
        thresholds = self.predictions_df.groupby('FiscalYear')['MarketCap'].transform(get_smallcap_threshold)
        self.predictions_df['is_smallcap'] = self.predictions_df['MarketCap'] <= thresholds
        
        logger.info(f"  → 순위 계산 완료")
        logger.info(f"  → 소형주 비율: {self.predictions_df['is_smallcap'].mean()*100:.1f}%")
    
    def apply_dollar_five_rule(
        self,
        tickers: List[str],
        year: int
    ) -> List[str]:
        """
        $5 룰 적용
        
        최근 12개월 중 80% 이상이 $5 이하면 제외
        """
        rebalance_date = pd.Timestamp(f"{year}-{self.config.rebalance_month:02d}-01", tz='UTC')
        rebalance_date = rebalance_date + pd.offsets.MonthEnd(0)
        
        start_date = rebalance_date - pd.DateOffset(months=12)
        recent_prices = self.price_df.loc[start_date:rebalance_date]
        
        valid_tickers = []
        for ticker in tickers:
            if ticker not in recent_prices.columns:
                continue
            
            ticker_prices = recent_prices[ticker].dropna()
            if len(ticker_prices) == 0:
                continue
            
            below_threshold_ratio = (ticker_prices <= self.config.price_threshold_dollars).mean()
            if below_threshold_ratio < self.config.price_below_threshold_ratio:
                valid_tickers.append(ticker)
        
        return valid_tickers
    
    def calculate_portfolio_return(
        self,
        tickers: List[str],
        year: int
    ) -> Tuple[float, List[float]]:
        """
        포트폴리오 수익률 계산
        
        Returns
        -------
        portfolio_return : float
            동일가중 평균 수익률
        individual_returns : list
            개별 종목 수익률
        """
        if len(tickers) == 0:
            return 0.0, []
        
        # 매수 시점 (year년 12월 말)
        buy_date = pd.Timestamp(f"{year}-{self.config.rebalance_month:02d}-01", tz='UTC')
        buy_date = buy_date + pd.offsets.MonthEnd(0)
        
        # 매도 시점 (12개월 후)
        sell_date = buy_date + pd.DateOffset(months=self.config.holding_months)
        
        individual_returns = []
        for ticker in tickers:
            if ticker not in self.price_df.columns:
                continue
            
            buy_price = self.price_df[ticker].asof(buy_date)
            sell_price = self.price_df[ticker].asof(sell_date)
            
            if pd.notna(buy_price) and pd.notna(sell_price) and buy_price > 0:
                ret = (sell_price - buy_price) / buy_price
                individual_returns.append(ret)
        
        if len(individual_returns) == 0:
            return 0.0, []
        
        portfolio_return = np.mean(individual_returns)
        return portfolio_return, individual_returns
    
    def get_benchmark_returns(self, year: int) -> Dict[str, float]:
        """벤치마크 수익률 조회 (year+1년 수익률)"""
        return_year = year + 1
        
        if return_year in BENCHMARK_RETURNS:
            return BENCHMARK_RETURNS[return_year]
        else:
            return {idx: np.nan for idx in BENCHMARK_INDICES}
    
    def run_backtest_for_year(
        self,
        year: int,
        portfolio_type: str,  # "normal" or "smallcap"
        ratio: float
    ) -> YearlyResult:
        """
        특정 연도, 포트폴리오 타입, 비율에 대한 백테스트
        """
        result = YearlyResult(
            year=year,
            portfolio_type=portfolio_type,
            ratio=ratio
        )
        
        # 해당 연도 데이터
        year_df = self.predictions_df[self.predictions_df['FiscalYear'] == year].copy()
        
        if len(year_df) == 0:
            return result
        
        # 포트폴리오 타입 필터링
        if portfolio_type == "smallcap":
            year_df = year_df[year_df['is_smallcap'] == True]
        else:
            # normal = 전체 (소형주 포함)
            pass
        
        if len(year_df) == 0:
            return result
        
        # Gap 상위 N% 선택
        n_select = max(1, int(len(year_df) * ratio))
        top_df = year_df.nlargest(n_select, 'Gap')
        
        # $5 룰 적용
        candidate_tickers = top_df['Ticker'].tolist()
        valid_tickers = self.apply_dollar_five_rule(candidate_tickers, year)
        
        if len(valid_tickers) == 0:
            return result
        
        # 최종 선택된 종목 정보
        final_df = top_df[top_df['Ticker'].isin(valid_tickers)]
        
        result.tickers = valid_tickers
        result.gaps = final_df['Gap'].tolist()
        result.n_stocks = len(valid_tickers)
        result.weights = [1.0 / len(valid_tickers)] * len(valid_tickers)
        
        # 수익률 계산
        result.portfolio_return, _ = self.calculate_portfolio_return(valid_tickers, year)
        
        # 벤치마크 수익률
        result.benchmark_returns = self.get_benchmark_returns(year)
        
        return result
    
    def run(self) -> ExperimentResults:
        """
        전체 실험 실행
        
        Returns
        -------
        ExperimentResults
            실험 결과 객체
        """
        logger.info("\n" + "="*60)
        logger.info(f"  실험 시작: {self.config.exp_id} - {self.config.exp_name}")
        logger.info("="*60)
        
        # 데이터 로드
        self.load_data()
        
        # 순위 계산
        self.add_ranks()
        
        # 결과 객체
        results = ExperimentResults(config=self.config)
        results.weights_history = self.weights_df
        results.predictions_with_rank = self.predictions_df.copy()
        
        # 연도 리스트
        years = sorted(self.predictions_df['FiscalYear'].unique())
        
        # 수익률 계산 가능한 연도만 (다음 해 가격 필요)
        valid_years = [y for y in years if y < years[-1]]
        
        logger.info(f"\n[백테스트 실행]")
        logger.info(f"  → 대상 연도: {valid_years}")
        
        # 각 조합별 백테스트
        for year in valid_years:
            for portfolio_type in ["normal", "smallcap"]:
                for ratio in self.config.long_ratios:
                    yearly_result = self.run_backtest_for_year(year, portfolio_type, ratio)
                    results.yearly_results.append(yearly_result)
                    
                    # 로그
                    if yearly_result.n_stocks > 0:
                        logger.debug(
                            f"  FY{year} {portfolio_type} {ratio*100:.0f}%: "
                            f"{yearly_result.n_stocks}종목, "
                            f"수익률 {yearly_result.portfolio_return*100:.1f}%"
                        )
        
        # 성과 지표 계산
        results.performance_metrics = self._calculate_performance_metrics(results)
        
        # 검정 수행
        results.validation_tests = self._run_validation_tests(results)
        
        logger.info("\n" + "="*60)
        logger.info(f"  실험 완료: {self.config.exp_id}")
        logger.info("="*60)
        
        return results
    
    def _calculate_performance_metrics(
        self, 
        results: ExperimentResults
    ) -> Dict:
        """성과 지표 계산"""
        logger.info("\n[성과 지표 계산]")
        
        metrics = {}
        
        for portfolio_type in ["normal", "smallcap"]:
            for ratio in self.config.long_ratios:
                key = f"{portfolio_type}_{int(ratio*100)}"
                
                # 해당 조합의 연도별 수익률
                yearly = [
                    r for r in results.yearly_results 
                    if r.portfolio_type == portfolio_type and r.ratio == ratio
                ]
                
                if not yearly:
                    continue
                
                returns = pd.Series([r.portfolio_return for r in yearly])
                years = [r.year for r in yearly]
                
                # CAGR
                n_years = len(returns)
                cagr = calculate_cagr(returns, n_years) if n_years > 0 else np.nan
                
                # Sharpe
                sharpe = calculate_sharpe_ratio(returns, self.config.risk_free_rate)
                
                # MDD (누적 수익률 기준)
                cumulative = (1 + returns).cumprod()
                mdd = calculate_mdd(cumulative)
                
                # Win Rate
                win_rate = (returns > 0).mean()
                
                # 벤치마크 대비 Alpha, Beta
                alphas = {}
                betas = {}
                for bench in self.config.benchmark_indices:
                    bench_returns = pd.Series([
                        r.benchmark_returns.get(bench, np.nan) for r in yearly
                    ])
                    
                    if bench_returns.notna().sum() >= 2:
                        alpha, beta = calculate_alpha_beta(
                            returns, bench_returns, self.config.risk_free_rate
                        )
                        alphas[f"Alpha_vs_{bench}"] = alpha
                        betas[f"Beta_vs_{bench}"] = beta
                
                metrics[key] = {
                    'portfolio_type': portfolio_type,
                    'ratio': ratio,
                    'n_years': n_years,
                    'mean_return': returns.mean(),
                    'std_return': returns.std(),
                    'CAGR': cagr,
                    'Sharpe': sharpe,
                    'MDD': mdd,
                    'WinRate': win_rate,
                    **alphas,
                    **betas
                }
                
                logger.info(
                    f"  {key}: CAGR={cagr*100:.1f}%, Sharpe={sharpe:.2f}, "
                    f"MDD={mdd*100:.1f}%, WinRate={win_rate*100:.0f}%"
                )
        
        return metrics
    
    def _run_validation_tests(
        self,
        results: ExperimentResults
    ) -> Dict:
        """검정 수행"""
        logger.info("\n[검정 수행]")
        
        tests = {}
        
        # 1. 가중치 적절성 검정 (가중치가 합리적인지)
        if results.weights_history is not None:
            weights = results.weights_history
            tests['weight_stability'] = {
                'm1_std': weights['w1'].std() if 'w1' in weights.columns else np.nan,
                'm2_std': weights['w2'].std() if 'w2' in weights.columns else np.nan,
                'm3_std': weights['w3'].std() if 'w3' in weights.columns else np.nan,
                'comment': '가중치 표준편차가 낮을수록 안정적'
            }
            logger.info(f"  → 가중치 안정성 검정 완료")
        
        # 2. Rank IC 검정 (예측력)
        if results.predictions_with_rank is not None:
            pred_df = results.predictions_with_rank
            rank_ics = []
            
            for year, group in pred_df.groupby('FiscalYear'):
                if len(group) < 10:
                    continue
                ic, _ = spearmanr(group['yhat'], group['y'])
                rank_ics.append({'year': year, 'Rank_IC': ic})
            
            tests['rank_ic'] = {
                'mean_ic': np.mean([r['Rank_IC'] for r in rank_ics]),
                'std_ic': np.std([r['Rank_IC'] for r in rank_ics]),
                'by_year': rank_ics
            }
            logger.info(f"  → Rank IC 검정 완료: 평균 {tests['rank_ic']['mean_ic']:.4f}")
        
        # 3. 포트폴리오 강건성 (연도별 수익률 일관성)
        for portfolio_type in ["normal", "smallcap"]:
            for ratio in self.config.long_ratios:
                key = f"{portfolio_type}_{int(ratio*100)}"
                
                yearly = [
                    r for r in results.yearly_results 
                    if r.portfolio_type == portfolio_type and r.ratio == ratio
                ]
                
                if len(yearly) < 3:
                    continue
                
                returns = [r.portfolio_return for r in yearly]
                tests[f'robustness_{key}'] = {
                    'positive_years': sum(1 for r in returns if r > 0),
                    'negative_years': sum(1 for r in returns if r <= 0),
                    'max_return': max(returns),
                    'min_return': min(returns),
                    'return_range': max(returns) - min(returns)
                }
        
        logger.info(f"  → 강건성 검정 완료")
        
        return tests


# ========================================
# 테스트
# ========================================
if __name__ == '__main__':
    from .config import get_baseline_config
    
    config = get_baseline_config()
    runner = ExperimentRunner(config)
    
    try:
        results = runner.run()
        print(f"\n✅ 실험 완료: {len(results.yearly_results)}개 결과")
    except Exception as e:
        print(f"❌ 실험 실패: {e}")
        import traceback
        traceback.print_exc()
