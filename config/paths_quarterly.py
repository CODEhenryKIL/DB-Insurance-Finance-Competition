"""
===========================================
M-Model 분기별 데이터 경로 관리
===========================================

이 파일의 역할:
- 분기별 데이터(Q1~Q4) 파일 경로를 중앙에서 관리
- 기존 연간 데이터(data_cache/)와 분리된 새 폴더 사용
- data_cache_quarterly/ 폴더에 모든 분기별 데이터 저장

출력 경로:
- data_cache_quarterly/step1_px_adj_m.csv (월말 조정종가)
- data_cache_quarterly/step1_px_close_m.csv (월말 종가)
- data_cache_quarterly/step1_meta.json (메타 정보)
- data_cache_quarterly/step2_fund_quarterly.csv (분기별 재무 데이터)
"""

from pathlib import Path

# ===========================================
# 기본 경로 설정
# ===========================================

# 프로젝트 루트 (config/paths_quarterly.py → 한 단계 위)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# ⭐ 분기별 데이터 캐시 디렉토리 (기존 data_cache와 분리)
DATA_CACHE_QUARTERLY_DIR = PROJECT_ROOT / 'data_cache_quarterly'

# SEC companyfacts 캐시 (기존 폴더 재사용 - raw 데이터는 동일)
SEC_CACHE_DIR = PROJECT_ROOT / 'data_cache' / 'sec_companyfacts'


# ===========================================
# Step별 출력 파일 경로 (분기별)
# ===========================================

# Step0: 유니버스 (기존 파일 재사용)
STEP0_VALID_UNIVERSE_JSON = PROJECT_ROOT / 'data_cache' / 'step0_valid_universe.json'

# Step1: 가격 데이터 (분기별 폴더에 저장)
STEP1_PRICE_ADJ_CSV_Q = DATA_CACHE_QUARTERLY_DIR / 'step1_px_adj_m.csv'
STEP1_PRICE_CLOSE_CSV_Q = DATA_CACHE_QUARTERLY_DIR / 'step1_px_close_m.csv'
STEP1_META_JSON_Q = DATA_CACHE_QUARTERLY_DIR / 'step1_meta.json'

# Step2: 재무 데이터 (⭐ 분기별 - 핵심 변경점)
STEP2_FUNDAMENTALS_QUARTERLY_CSV = DATA_CACHE_QUARTERLY_DIR / 'step2_fund_quarterly.csv'

# Step3: Feature Engineering (분기별)
STEP3_FEATURES_QUARTERLY_CSV = DATA_CACHE_QUARTERLY_DIR / 'step3_features_quarterly.csv'

# Step4: 모델 예측 (분기별)
STEP4_PREDICTIONS_QUARTERLY_CSV = DATA_CACHE_QUARTERLY_DIR / 'step4_predictions_quarterly.csv'

# Step5: 백테스트 (분기별)
STEP5_BACKTEST_QUARTERLY_CSV = DATA_CACHE_QUARTERLY_DIR / 'step5_backtest_quarterly.csv'


# ===========================================
# 디렉토리 자동 생성
# ===========================================

def ensure_quarterly_dirs():
    """분기별 데이터 저장 디렉토리 생성"""
    DATA_CACHE_QUARTERLY_DIR.mkdir(parents=True, exist_ok=True)


# 모듈 로드 시 자동 생성
ensure_quarterly_dirs()
