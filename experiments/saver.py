"""
===========================================
결과 저장 (Saver)
===========================================

실험 결과를 체계적으로 저장
- CSV 파일
- JSON 설정
- 폴더 구조 자동 생성
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
import json
from typing import Dict, List

from config.constants import BENCHMARK_RETURNS, BENCHMARK_INDICES
from utils.logger import get_logger
from .config import ExperimentConfig
from .runner import ExperimentResults, YearlyResult

logger = get_logger(__name__)

# 기본 실험 폴더
EXPERIMENTS_V2_DIR = project_root / 'experiments_v2'


class ResultSaver:
    """
    결과 저장 클래스
    
    저장 항목:
    1. config.json - 실험 설정
    2. data/weights_history.csv - 연도별 가중치
    3. data/returns_by_year.csv - 연도별 수익률
    4. data/predictions_with_rank.csv - 예측 결과 + 순위
    5. data/portfolio_holdings_normal.csv - 일반 포트폴리오 구성
    6. data/portfolio_holdings_smallcap.csv - 소형주 포트폴리오 구성
    7. metrics/performance_metrics.csv - 성과 지표
    8. metrics/validation_tests.json - 검정 결과
    """
    
    def __init__(self, base_dir: Path = EXPERIMENTS_V2_DIR):
        """
        초기화
        
        Parameters
        ----------
        base_dir : Path
            실험 폴더 기본 경로
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 벤치마크 폴더 생성 (한 번만)
        self._save_benchmark_data()
    
    def _save_benchmark_data(self) -> None:
        """벤치마크 데이터 저장 (공용)"""
        benchmark_dir = self.base_dir / '_benchmark'
        benchmark_dir.mkdir(exist_ok=True)
        
        benchmark_file = benchmark_dir / 'benchmark_returns.csv'
        if not benchmark_file.exists():
            # DataFrame으로 변환
            rows = []
            for year, returns in BENCHMARK_RETURNS.items():
                row = {'Year': year}
                row.update(returns)
                rows.append(row)
            
            df = pd.DataFrame(rows)
            df.to_csv(benchmark_file, index=False)
            logger.info(f"  → 벤치마크 데이터 저장: {benchmark_file}")
    
    def get_exp_dir(self, config: ExperimentConfig) -> Path:
        """실험 폴더 경로"""
        return self.base_dir / config.get_exp_folder_name()
    
    def create_folder_structure(self, config: ExperimentConfig) -> Path:
        """
        실험 폴더 구조 생성
        
        Returns
        -------
        Path
            실험 폴더 경로
        """
        exp_dir = self.get_exp_dir(config)
        
        # 폴더 생성
        exp_dir.mkdir(parents=True, exist_ok=True)
        (exp_dir / 'data').mkdir(exist_ok=True)
        (exp_dir / 'metrics').mkdir(exist_ok=True)
        
        logger.info(f"  → 폴더 구조 생성: {exp_dir}")
        
        return exp_dir
    
    def save(self, results: ExperimentResults) -> Path:
        """
        전체 결과 저장
        
        Parameters
        ----------
        results : ExperimentResults
            실험 결과
        
        Returns
        -------
        Path
            실험 폴더 경로
        """
        logger.info("\n" + "="*60)
        logger.info(f"  결과 저장: {results.config.exp_id}")
        logger.info("="*60)
        
        # 1. 폴더 생성
        exp_dir = self.create_folder_structure(results.config)
        
        # 2. 설정 저장
        self._save_config(exp_dir, results.config)
        
        # 3. 가중치 히스토리
        self._save_weights_history(exp_dir, results)
        
        # 4. 연도별 수익률
        self._save_returns_by_year(exp_dir, results)
        
        # 5. 예측 결과 + 순위
        self._save_predictions_with_rank(exp_dir, results)
        
        # 6. 포트폴리오 구성
        self._save_portfolio_holdings(exp_dir, results)
        
        # 7. 성과 지표
        self._save_performance_metrics(exp_dir, results)
        
        # 8. 검정 결과
        self._save_validation_tests(exp_dir, results)
        
        logger.info(f"\n  ✅ 저장 완료: {exp_dir}")
        
        return exp_dir
    
    def _save_config(self, exp_dir: Path, config: ExperimentConfig) -> None:
        """설정 저장"""
        config_path = exp_dir / 'config.json'
        config.to_json(config_path)
        logger.info(f"  → config.json 저장")
    
    def _save_weights_history(self, exp_dir: Path, results: ExperimentResults) -> None:
        """가중치 히스토리 저장"""
        if results.weights_history is not None:
            path = exp_dir / 'data' / 'weights_history.csv'
            results.weights_history.to_csv(path, index=False)
            logger.info(f"  → weights_history.csv 저장")
    
    def _save_returns_by_year(self, exp_dir: Path, results: ExperimentResults) -> None:
        """연도별 수익률 저장"""
        rows = []
        
        for yr in results.yearly_results:
            row = {
                'Year': yr.year,
                'PortfolioType': yr.portfolio_type,
                'Ratio': yr.ratio,
                'Return': yr.portfolio_return,
                'N_Stocks': yr.n_stocks
            }
            
            # 벤치마크 수익률 추가
            for bench, ret in yr.benchmark_returns.items():
                row[bench] = ret
                row[f'Alpha_vs_{bench}'] = yr.portfolio_return - ret
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        path = exp_dir / 'data' / 'returns_by_year.csv'
        df.to_csv(path, index=False)
        logger.info(f"  → returns_by_year.csv 저장 ({len(df)}행)")
    
    def _save_predictions_with_rank(self, exp_dir: Path, results: ExperimentResults) -> None:
        """예측 결과 + 순위 저장"""
        if results.predictions_with_rank is not None:
            path = exp_dir / 'data' / 'predictions_with_rank.csv'
            results.predictions_with_rank.to_csv(path, index=False)
            logger.info(f"  → predictions_with_rank.csv 저장")
    
    def _save_portfolio_holdings(self, exp_dir: Path, results: ExperimentResults) -> None:
        """포트폴리오 구성 저장 (일반/소형주 분리)"""
        
        for portfolio_type in ["normal", "smallcap"]:
            rows = []
            
            for yr in results.yearly_results:
                if yr.portfolio_type != portfolio_type:
                    continue
                
                for i, ticker in enumerate(yr.tickers):
                    rows.append({
                        'Year': yr.year,
                        'Ratio': yr.ratio,
                        'Ticker': ticker,
                        'Gap': yr.gaps[i] if i < len(yr.gaps) else np.nan,
                        'Weight': yr.weights[i] if i < len(yr.weights) else np.nan,
                        'Return': yr.portfolio_return  # 포트폴리오 전체 수익률
                    })
            
            if rows:
                df = pd.DataFrame(rows)
                path = exp_dir / 'data' / f'portfolio_holdings_{portfolio_type}.csv'
                df.to_csv(path, index=False)
                logger.info(f"  → portfolio_holdings_{portfolio_type}.csv 저장")
    
    def _save_performance_metrics(self, exp_dir: Path, results: ExperimentResults) -> None:
        """성과 지표 저장"""
        if results.performance_metrics:
            df = pd.DataFrame.from_dict(results.performance_metrics, orient='index')
            df.index.name = 'Portfolio'
            
            path = exp_dir / 'metrics' / 'performance_metrics.csv'
            df.to_csv(path)
            logger.info(f"  → performance_metrics.csv 저장")
    
    def _save_validation_tests(self, exp_dir: Path, results: ExperimentResults) -> None:
        """검정 결과 저장"""
        if results.validation_tests:
            path = exp_dir / 'metrics' / 'validation_tests.json'
            
            # numpy 타입 변환 (JSON 직렬화 위해)
            def convert(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, (np.int64, np.int32)):
                    return int(obj)
                if isinstance(obj, (np.float64, np.float32)):
                    return float(obj)
                if isinstance(obj, dict):
                    return {k: convert(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [convert(i) for i in obj]
                return obj
            
            tests = convert(results.validation_tests)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(tests, f, indent=2, ensure_ascii=False)
            logger.info(f"  → validation_tests.json 저장")


# ========================================
# 테스트
# ========================================
if __name__ == '__main__':
    from .config import get_baseline_config
    from .runner import ExperimentRunner, ExperimentResults
    
    # 더미 결과 생성
    config = get_baseline_config()
    
    results = ExperimentResults(config=config)
    results.yearly_results = [
        YearlyResult(
            year=2019, portfolio_type="normal", ratio=0.10,
            portfolio_return=0.15, n_stocks=10,
            tickers=["AAPL", "MSFT"], gaps=[0.5, 0.4], weights=[0.5, 0.5],
            benchmark_returns={'S&P500': 0.10}
        )
    ]
    results.performance_metrics = {
        'normal_10': {'CAGR': 0.12, 'Sharpe': 1.5, 'MDD': -0.15, 'WinRate': 0.7}
    }
    
    # 저장 테스트
    saver = ResultSaver()
    exp_dir = saver.save(results)
    print(f"\n✅ 저장 완료: {exp_dir}")
