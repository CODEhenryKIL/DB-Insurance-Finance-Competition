"""
===========================================
M-Model 통합 설정 파일
===========================================

모든 프로젝트 설정을 한 곳에서 관리:
1. 경로 설정 (Paths)
2. 데이터 수집 설정 (Data)
3. 회계 재작성 파라미터 (Restatement)
4. 모델 학습 설정 (Model)
5. 백테스트 설정 (Backtest)
6. 방어 로직 파라미터 (Defense)
"""

from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict

# ===========================================
# 경로 설정
# ===========================================

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATA_CACHE_DIR = PROJECT_ROOT / 'data_cache'
DATA_CACHE_QUARTERLY_DIR = PROJECT_ROOT / 'data_cache_quarterly'
REPORTS_DIR = PROJECT_ROOT / 'reports'
LOGS_DIR = PROJECT_ROOT / 'logs'
EDGAR_CACHE_DIR = DATA_CACHE_DIR / 'edgar_cache'

# 캐시 디렉토리 alias (하위 호환성)
CACHE_DIR = DATA_CACHE_DIR


@dataclass
class StepPaths:
    """각 Step별 출력 파일 경로"""
    # Step 0
    valid_universe: Path = DATA_CACHE_DIR / 'step0_valid_universe.json'
    
    # Step 1
    price_adj: Path = DATA_CACHE_DIR / 'step1_px_adj_m.csv'
    price_close: Path = DATA_CACHE_DIR / 'step1_px_close_m.csv'
    meta: Path = DATA_CACHE_DIR / 'step1_meta.json'
    
    # Step 2
    fundamentals: Path = DATA_CACHE_DIR / 'step2_fund_annual.csv'
    fundamentals_sp500: Path = DATA_CACHE_DIR / 'step2_fund_annual_sp500.csv'
    lost_tickers: Path = DATA_CACHE_DIR / 'step2_lost_tickers.csv'
    
    # Step 3
    features: Path = DATA_CACHE_DIR / 'step3_features_annual.csv'
    
    # Step 4
    predictions: Path = DATA_CACHE_DIR / 'step4_predictions.csv'
    predictions_ranknet: Path = DATA_CACHE_DIR / 'step4_predictions_ranknet.csv'
    weights_history: Path = DATA_CACHE_DIR / 'step4_weights_history.csv'
    weights_history_ranknet: Path = DATA_CACHE_DIR / 'step4_weights_history_ranknet.csv'
    
    # Step 5
    backtest_returns: Path = DATA_CACHE_DIR / 'step5_backtest_returns.csv'
    backtest_metrics: Path = DATA_CACHE_DIR / 'step5_backtest_metrics.csv'


@dataclass
class QuarterlyPaths:
    """분기별 데이터 경로"""
    price_adj: Path = DATA_CACHE_QUARTERLY_DIR / 'step1_px_adj_m.csv'
    price_close: Path = DATA_CACHE_QUARTERLY_DIR / 'step1_px_close_m.csv'
    meta: Path = DATA_CACHE_QUARTERLY_DIR / 'step1_meta.json'
    fundamentals: Path = DATA_CACHE_QUARTERLY_DIR / 'step2_fund_quarterly.csv'


PATHS = StepPaths()
QUARTERLY_PATHS = QuarterlyPaths()


# ===========================================
# 데이터 수집 설정
# ===========================================

@dataclass
class DataConfig:
    """데이터 수집 관련 설정"""
    # 테스트 모드
    test_mode: bool = False
    test_tickers: List[str] = field(default_factory=lambda: [
        'BIIB', 'EW', 'RF', 'EXPD', 'IQV', 'MO', 'DD', 'ABT', 'COST',
        'AMZN', 'ANET', 'XYZ', 'AIZ', 'PYPL', 'TROW', 'HPQ', 'STE'
    ])
    
    # 시장 모드: 'SP500' or 'FULL'
    market_mode: str = 'SP500'
    
    # 데이터 기간
    start_year: int = 2012
    current_year: int = datetime.now().year
    
    # 배치 처리
    batch_size: int = 100
    checkpoint_enabled: bool = True
    
    # 제외 섹터
    excluded_sectors: List[str] = field(default_factory=lambda: [
        'Financials', 'Utilities', 'Energy', 'Materials', 'Real Estate', 'Unknown'
    ])
    
    # API 설정
    api_sleep_seconds: float = 0.15
    sec_headers: Dict[str, str] = field(default_factory=lambda: {
        'User-Agent': 'M-Model Research contact@example.com',
        'Accept-Encoding': 'gzip, deflate'
    })


# ===========================================
# 회계 재작성 설정
# ===========================================

@dataclass
class RestatementConfig:
    """회계 재작성 파라미터"""
    sga_weight: float = 0.3           # SG&A 자산화 비율 (30%)
    amortization_years: int = 3        # 무형자산 상각 기간


# ===========================================
# 모델 학습 설정
# ===========================================

@dataclass
class ModelConfig:
    """모델 학습 관련 설정"""
    # 공통
    input_dim: int = 3
    output_dim: int = 1
    random_seed: int = 42
    train_window_years: int = 5
    
    # Y 타겟 모드: 'raw' or 'sector'
    y_target_mode: str = 'sector'
    
    # MSE 모델
    learning_rate: float = 0.01
    epochs: int = 100
    weight_decay: float = 0.01
    early_stopping_patience: int = 10
    
    # RankNet 모델
    ranknet_learning_rate: float = 0.005
    ranknet_epochs: int = 300
    ranknet_batch_size: int = 128
    ranknet_sigma: float = 1.0
    ranknet_weight_decay: float = 0.001
    ranknet_patience: int = 30


# ===========================================
# 백테스트 설정
# ===========================================

@dataclass
class BacktestConfig:
    """백테스트 전략 파라미터"""
    start_year: int = 2015
    long_ratios: List[float] = field(default_factory=lambda: [0.05, 0.10, 0.20, 0.30])
    holding_period_months: int = 12
    rebalance_month: int = 12
    
    # $5 룰
    price_check_months: int = 12
    price_threshold: float = 5.0
    price_below_ratio: float = 0.80
    
    # 무위험 수익률
    risk_free_rate: float = 0.02


# ===========================================
# 방어 로직 설정
# ===========================================

@dataclass
class DefenseConfig:
    """방어 로직 파라미터"""
    epsilon: float = 1e-6
    
    # m1 클리핑
    m1_clip_min: float = -5.0
    m1_clip_max: float = 5.0
    
    # m2 클리핑
    m2_clip_min: float = 0.0
    m2_clip_max: float = 10.0
    
    # m3 클리핑
    m3_clip_min: float = -5.0
    m3_clip_max: float = 5.0
    
    # PBR 클리핑
    pbr_clip_min: float = 0.01
    pbr_clip_max: float = 100.0
    
    # 데이터 품질
    max_missing_ratio: float = 0.30
    min_data_points: int = 3


# ===========================================
# 벤치마크 데이터 (하드코딩)
# ===========================================

BENCHMARK_INDICES = ['S&P500', 'Russell1000', 'Russell2000', 'Russell3000', 'Wilshire5000']

BENCHMARK_RETURNS = {
    2012: {'S&P500': 0.1341, 'Russell1000': 0.1392, 'Russell2000': 0.1463, 'Russell3000': 0.1398, 'Wilshire5000': 0.1369},
    2013: {'S&P500': 0.2960, 'Russell1000': 0.3044, 'Russell2000': 0.3700, 'Russell3000': 0.3095, 'Wilshire5000': 0.3142},
    2014: {'S&P500': 0.1139, 'Russell1000': 0.1107, 'Russell2000': 0.0353, 'Russell3000': 0.1045, 'Wilshire5000': 0.0997},
    2015: {'S&P500': -0.0073, 'Russell1000': -0.0109, 'Russell2000': -0.0571, 'Russell3000': -0.0147, 'Wilshire5000': -0.0232},
    2016: {'S&P500': 0.0954, 'Russell1000': 0.0970, 'Russell2000': 0.1948, 'Russell3000': 0.1042, 'Wilshire5000': 0.1067},
    2017: {'S&P500': 0.1942, 'Russell1000': 0.1934, 'Russell2000': 0.1314, 'Russell3000': 0.1885, 'Wilshire5000': 0.1865},
    2018: {'S&P500': -0.0624, 'Russell1000': -0.0658, 'Russell2000': -0.1218, 'Russell3000': -0.0699, 'Wilshire5000': -0.0736},
    2019: {'S&P500': 0.2888, 'Russell1000': 0.2889, 'Russell2000': 0.2372, 'Russell3000': 0.2854, 'Wilshire5000': 0.2772},
    2020: {'S&P500': 0.1626, 'Russell1000': 0.1887, 'Russell2000': 0.1836, 'Russell3000': 0.1882, 'Wilshire5000': 0.1998},
    2021: {'S&P500': 0.2689, 'Russell1000': 0.2476, 'Russell2000': 0.1369, 'Russell3000': 0.2400, 'Wilshire5000': 0.2282},
    2022: {'S&P500': -0.1944, 'Russell1000': -0.2041, 'Russell2000': -0.2156, 'Russell3000': -0.2048, 'Wilshire5000': -0.2143},
    2023: {'S&P500': 0.2423, 'Russell1000': 0.2451, 'Russell2000': 0.1509, 'Russell3000': 0.2395, 'Wilshire5000': 0.2429},
    2024: {'S&P500': 0.2331, 'Russell1000': 0.2284, 'Russell2000': 0.1002, 'Russell3000': 0.2215, 'Wilshire5000': 0.2257},
}


# ===========================================
# 전역 설정 인스턴스
# ===========================================

DATA = DataConfig()
RESTATEMENT = RestatementConfig()
MODEL = ModelConfig()
BACKTEST = BacktestConfig()
DEFENSE = DefenseConfig()


# ===========================================
# 유틸리티 함수
# ===========================================

def ensure_dirs():
    """필요한 디렉토리 생성"""
    for directory in [DATA_CACHE_DIR, DATA_CACHE_QUARTERLY_DIR, REPORTS_DIR, LOGS_DIR, EDGAR_CACHE_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def print_config():
    """현재 설정 출력"""
    print("=" * 60)
    print("M-Model 설정")
    print("=" * 60)
    print(f"\n[데이터]")
    print(f"  Market Mode: {DATA.market_mode}")
    print(f"  Start Year: {DATA.start_year}")
    print(f"  Test Mode: {DATA.test_mode}")
    print(f"\n[모델]")
    print(f"  Y Target Mode: {MODEL.y_target_mode}")
    print(f"  Train Window: {MODEL.train_window_years}년")
    print(f"\n[백테스트]")
    print(f"  Start Year: {BACKTEST.start_year}")
    print(f"  Long Ratios: {BACKTEST.long_ratios}")
    print("=" * 60)


# 하위 호환성을 위한 개별 변수 export
# (기존 코드에서 from config.constants import X 형태로 사용)
TEST_MODE = DATA.test_mode
TEST_TICKERS = DATA.test_tickers
MARKET_MODE = DATA.market_mode
START_YEAR = DATA.start_year
CURRENT_YEAR = DATA.current_year
BATCH_SIZE = DATA.batch_size
EXCLUDED_SECTORS = DATA.excluded_sectors
API_SLEEP_SECONDS = DATA.api_sleep_seconds
SEC_HEADERS = DATA.sec_headers

SGA_WEIGHT = RESTATEMENT.sga_weight
AMORTIZATION_YEARS = RESTATEMENT.amortization_years

INPUT_DIM = MODEL.input_dim
OUTPUT_DIM = MODEL.output_dim
RANDOM_SEED = MODEL.random_seed
LEARNING_RATE = MODEL.learning_rate
EPOCHS = MODEL.epochs
WEIGHT_DECAY = MODEL.weight_decay
EARLY_STOPPING_PATIENCE = MODEL.early_stopping_patience
TRAIN_WINDOW_YEARS = MODEL.train_window_years
Y_TARGET_MODE = MODEL.y_target_mode

BACKTEST_START_YEAR = BACKTEST.start_year
LONG_RATIOS = BACKTEST.long_ratios
HOLDING_PERIOD_MONTHS = BACKTEST.holding_period_months
REBALANCE_MONTH = BACKTEST.rebalance_month
PRICE_CHECK_MONTHS = BACKTEST.price_check_months
PRICE_THRESHOLD_DOLLARS = BACKTEST.price_threshold
PRICE_BELOW_THRESHOLD_RATIO = BACKTEST.price_below_ratio
RISK_FREE_RATE = BACKTEST.risk_free_rate

EPSILON = DEFENSE.epsilon
M1_CLIP_MIN = DEFENSE.m1_clip_min
M1_CLIP_MAX = DEFENSE.m1_clip_max
M2_CLIP_MIN = DEFENSE.m2_clip_min
M2_CLIP_MAX = DEFENSE.m2_clip_max
M3_CLIP_MIN = DEFENSE.m3_clip_min
M3_CLIP_MAX = DEFENSE.m3_clip_max


if __name__ == '__main__':
    print_config()
