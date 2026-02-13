"""
===========================================
Experiments V2: 실험 프레임워크
===========================================

새로운 실험 관리 시스템:
- 체계적인 폴더 구조
- 재현 가능한 설정 관리
- 자동 보고서 생성
- 이전 실험과 비교

폴더 구조:
experiments_v2/
├── _benchmark/
│   └── benchmark_returns.csv
├── exp_001_xxx/
│   ├── config.json
│   ├── data/
│   │   ├── weights_history.csv
│   │   ├── returns_by_year.csv
│   │   ├── predictions_with_rank.csv
│   │   ├── portfolio_holdings_normal.csv
│   │   └── portfolio_holdings_smallcap.csv
│   ├── metrics/
│   │   ├── performance_metrics.csv
│   │   └── validation_tests.csv
│   └── REPORT.md
"""

from .src.config import ExperimentConfig
from .src.runner import ExperimentRunner
from .src.saver import ResultSaver
from .src.reporter import ReportGenerator

__all__ = [
    'ExperimentConfig',
    'ExperimentRunner', 
    'ResultSaver',
    'ReportGenerator'
]
