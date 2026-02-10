"""
config 패키지 초기화

사용법:
    # 기존 방식 (하위 호환)
    from config.constants import TEST_MODE, MARKET_MODE
    from config.paths import PATHS
    
    # 새로운 방식 (권장)
    from config.settings import DATA, MODEL, BACKTEST, PATHS
"""

# 하위 호환성을 위해 기존 모듈 export
from .constants import *
from .paths import *

# 새로운 통합 설정
from .settings import (
    # 경로
    PROJECT_ROOT,
    DATA_CACHE_DIR,
    REPORTS_DIR,
    LOGS_DIR,
    PATHS,
    QUARTERLY_PATHS,
    
    # 설정 클래스
    DATA,
    RESTATEMENT,
    MODEL,
    BACKTEST,
    DEFENSE,
    
    # 벤치마크
    BENCHMARK_RETURNS,
    BENCHMARK_INDICES,
    
    # 유틸리티
    ensure_dirs,
    print_config,
)

__all__ = [
    'PROJECT_ROOT',
    'DATA_CACHE_DIR',
    'REPORTS_DIR',
    'LOGS_DIR',
    'PATHS',
    'QUARTERLY_PATHS',
    'DATA',
    'RESTATEMENT',
    'MODEL',
    'BACKTEST',
    'DEFENSE',
    'BENCHMARK_RETURNS',
    'BENCHMARK_INDICES',
    'ensure_dirs',
    'print_config',
]
