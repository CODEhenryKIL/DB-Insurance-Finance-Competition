"""
===========================================
M-Model 프로젝트 전역 상수 정의
===========================================

이 파일의 역할:
- 프로젝트 전체에서 사용되는 모든 상수를 중앙에서 관리
- 하드코딩 방지 및 유지보수성 향상
- 한 곳에서 파라미터 수정 가능

주요 상수 그룹:
1. DATA_CONFIG: 데이터 수집 설정 (기간, 섹터 등)
2. RESTATEMENT_CONFIG: 회계 재작성 파라미터 (SGA 가중치, 상각 기간)
3. MODEL_CONFIG: 모델 학습 설정 (learning rate, epochs 등)
4. BACKTEST_CONFIG: 백테스트 전략 파라미터 (롱 비율, 홀딩 기간)
5. DEFENSE_CONFIG: 방어 로직 파라미터 (epsilon, clip 범위 등)
"""

from datetime import datetime

# ===========================================
# 1. 데이터 수집 설정
# ===========================================

# ⭐ 테스트 모드 (17개 티커로 빠른 검증)
TEST_MODE = False  # False로 변경하면 전체 S&P 500 실행

# 테스트용 17개 티커 (다양한 섹터 포함)
TEST_TICKERS = [
    'BIIB', 'EW', 'RF', 'EXPD', 'IQV', 'MO', 'DD', 'ABT', 'COST',
    'AMZN', 'ANET', 'XYZ', 'AIZ', 'PYPL', 'TROW', 'HPQ', 'STE'
]

# ⭐ 시장 모드
# 'FULL': 전체 미국 시장 (~3,640개, 현재 수집된 데이터)
# 'SP500': S&P 500 구성종목만 (연도별 Historical Constituents 적용)
MARKET_MODE = 'FULL'  # 'SP500' or 'FULL'

# ⭐ S&P 500 티커 파일 경로
SP500_TICKERS_FILE = 'sp500_tickers.txt'

# ⭐ 배치 처리 설정 (FULL 모드 전용)
BATCH_SIZE = 100  # 100개 단위로 저장
CHECKPOINT_ENABLED = True  # 체크포인트 저장 여부

# 데이터 수집 시작 연도
# 2012년부터 수집 (m1 계산용 3년 R&D 누적 데이터 확보용)
START_YEAR = 2012

# 백테스트 시작 연도
# 2015년부터 백테스트 시작 (XBRL 안정화 시점, m1 계산 데이터 충분)
BACKTEST_START_YEAR = 2015

# 현재 연도 (자동 계산)
CURRENT_YEAR = datetime.now().year

# 제외할 섹터 리스트
# 영구 제외 섹터 (GICS 코드)
# 회계 기준이 다르거나 M-Model 전략에 부적합한 섹터
# 
# Source Research:
# - Financial (40): 회계 기준 상이 (GAAP vs 금융업 특화 기준)
# - Utilities (55): 규제 산업 (가격 통제, ROE 제한)
# - Energy (10): 원자재 가격 의존 (유가 변동성 지배적)
# - Materials (15): 광업/소재 (선택적 제외, 원자재 가격 영향 큼)
EXCLUDED_SECTORS = [
    'Financials',       # GICS 40
    'Utilities',        # GICS 55
    'Energy',           # GICS 10 (추가)
    'Materials',        # GICS 15 (추가)
    'Real Estate',      # GICS 60 (추가)
    'Unknown'           # 섹터 정보 없는 기업 제외 (v2.1.2)
]

# SEC API 요청 헤더 (필수)
# SEC는 User-Agent가 없으면 요청 거부
SEC_HEADERS = {
    'User-Agent': 'M-Model Research contact@example.com',
    'Accept-Encoding': 'gzip, deflate'
}

# API 요청 간 대기 시간 (초)
# SEC API 과부하 방지
API_SLEEP_SECONDS = 0.15


# ===========================================
# 2. 회계 재작성 파라미터
# ===========================================

# SG&A 중 자산화할 비율
# K-IFRS에서는 SG&A 중 일부를 개발 관련으로 간주하여 자산화
# 일반적으로 20~40% 사용, 여기서는 30% 적용
SGA_WEIGHT = 0.3

# 무형자산 상각 기간 (년)
# K-IFRS 기준 보통 3~5년, 여기서는 3년 정액 상각
AMORTIZATION_YEARS = 3


# ===========================================
# 3. 모델 학습 설정
# ===========================================

# ⭐ Y 타겟 모드 (중요!)
# 'raw': 단순 ln(PBR) - 절대적 저평가 학습
# 'sector': 섹터 상대 ln(PBR) = ln(PBR) - Sector_Median - 섹터 내 상대 저평가 학습
Y_TARGET_MODE = 'sector'  # 'raw' or 'sector' (권장: sector)

# PyTorch 모델 입력 차원 (m1, m2, m3)
INPUT_DIM = 3

# PyTorch 모델 출력 차원 (yhat = ln(PBR))
OUTPUT_DIM = 1

# Adam optimizer learning rate
LEARNING_RATE = 5e-3  # 0.01 → 0.005로 하향 (안정적 학습)

# 학습 epoch 수 (Early stopping과 함께 사용)
EPOCHS = 100  # 500 → 100으로 축소 (early stopping 적용)

# Early stopping patience (val loss 개선 없으면 중단)
EARLY_STOPPING_PATIENCE = 10

# L2 규제 (weight decay)
WEIGHT_DECAY = 1e-2  # 1e-4 → 1e-2로 강화 (강한 규제)

# Rolling window 학습 기간 (년)
# 매 리밸런스 시점에서 과거 N년 데이터로 학습
# 5년 -> 3년으로 단축 (기술주 트렌드 반영)
TRAIN_WINDOW_YEARS = 5

# Random seed (재현성을 위해)
RANDOM_SEED = 42


# ===========================================
# 3.5. RankNet 모델 설정 (Ranking Loss)
# ===========================================
# 
# RankNet은 MSE 대신 Pairwise Ranking Loss를 사용
# "누가 누구보다 더 좋은가?"를 학습
# 
# 장점:
# - 극단값(Outlier)에 덜 민감
# - 상위 20~30% 구간 예측 정확도 향상
# - 포트폴리오 안정성 확보

# RankNet Learning Rate (MSE보다 낮게)
RANKNET_LEARNING_RATE = 5e-3

# RankNet Epochs (MSE보다 높게 - 수렴 느림)
RANKNET_EPOCHS = 300

# RankNet 배치 사이즈 (N×N 메모리 고려)
# 배치 사이즈 N이면 내부적으로 N×N 매트릭스 생성
RANKNET_BATCH_SIZE = 128

# RankNet 스케일링 파라미터 (sigma)
RANKNET_SIGMA = 1.0

# RankNet L2 규제
RANKNET_WEIGHT_DECAY = 1e-3

# RankNet Early Stopping Patience (증가)
RANKNET_PATIENCE = 30

# Rank IC 목표값 (Information Coefficient)
# 예측 점수와 실제 수익률의 스피어만 상관계수
RANKNET_TARGET_IC = 0.03


# ===========================================
# 4. 백테스트 전략 파라미터
# ===========================================

# 롱 포트폴리오 비율 (Gap 상위 N%)
# 4가지 버전 동시 실행: 5%, 10%, 20%, 30%
LONG_RATIOS = [0.05, 0.10, 0.20, 0.30]

# 홀딩 기간 (개월)
# 매년 리밸런싱하므로 12개월
HOLDING_PERIOD_MONTHS = 12

# 리밸런싱 월 (12월)
# 매년 12월 말에 리밸런싱
REBALANCE_MONTH = 12

# $5 룰 파라미터
# 리밸런스 시점 기준 최근 N개월 가격 확인
PRICE_CHECK_MONTHS = 12

# $5 이하 비율 임계값
# 12개월 중 80% 이상이 $5 이하면 제외
PRICE_THRESHOLD_DOLLARS = 5.0
PRICE_BELOW_THRESHOLD_RATIO = 0.80

# ⭐ 벤치마크 연도별 수익률 (Price Return 기준, 하드코딩)
# 출처: 표준 연도별 수익률 데이터 (Price Return 기준)
# yfinance 동적 다운로드 방식 폐기 → 데이터 무결성 확보
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
    2025: {'S&P500': 0.0458, 'Russell1000': 0.0421, 'Russell2000': 0.0268, 'Russell3000': 0.0408, 'Wilshire5000': 0.0395}  # 2025년 1월 YTD (근사)
}

# 벤치마크 지수 리스트 (비교용)
BENCHMARK_INDICES = ['S&P500', 'Russell1000', 'Russell2000', 'Russell3000', 'Wilshire5000']

# [DEPRECATED] 벤치마크 티커 (동적 다운로드용 - 더 이상 사용 안함)
# BENCHMARK_TICKER = 'SPY'  # S&P500 ETF

# 무위험 수익률 (연율)
# Sharpe Ratio 계산 시 사용
RISK_FREE_RATE = 0.02  # 2%


# ===========================================
# 5. 방어 로직 파라미터 (⭐ 중요)
# ===========================================

# Epsilon: 0으로 나누기 방지를 위한 최소값
# 분모가 이 값보다 작으면 이 값으로 대체
EPSILON = 1e-6

# m1 클리핑 범위
# m1 = AdjOI / max(abs(OI), epsilon)
# 극단값을 [-5, +5] 범위로 제한
M1_CLIP_MIN = -5.0
M1_CLIP_MAX = 5.0

# m2 클리핑 범위
# m2 = Intensity_t / Avg(Intensity_t-1, Intensity_t-2)
# 투자 가속도가 너무 크면 비정상적이므로 제한
M2_CLIP_MIN = 0.0
M2_CLIP_MAX = 10.0

# m3 클리핑 범위
# m3 = PIM_t / Avg(PIM_t-1, PIM_t-2)
# 본업 마진 비율 제한
M3_CLIP_MIN = -5.0
M3_CLIP_MAX = 5.0

# PBR 클리핑 범위 (로그 취하기 전)
# 너무 극단적인 PBR은 제외 (예: PBR < 0.01 또는 > 100)
PBR_CLIP_MIN = 0.01
PBR_CLIP_MAX = 100.0


# ===========================================
# 6. 데이터 품질 기준
# ===========================================

# 피처 결측치 허용 비율 (전체 데이터 대비)
# 30% 이상 결측이면 경고
MAX_MISSING_RATIO = 0.30

# 각 티커별 최소 데이터 포인트 수
# 최소 3년치 데이터는 있어야 m2, m3 계산 가능
MIN_DATA_POINTS_PER_TICKER = 3


# ===========================================
# 7. 캐시 및 출력 설정
# ===========================================

# 캐시 저장 형식
CACHE_FORMAT = 'csv'  # 'csv' 또는 'parquet'

# 로그 레벨
# DEBUG: 모든 상세 로그
# INFO: 중요한 정보만
# WARNING: 경고 및 에러만
LOG_LEVEL = 'INFO'

# 차트 저장 형식
CHART_FORMAT = 'png'  # 'png', 'pdf', 'svg'

# 차트 DPI (해상도)
CHART_DPI = 300


# ===========================================
# 사용 예시
# ===========================================
if __name__ == '__main__':
    """
    이 파일을 직접 실행하면 모든 상수를 출력합니다.
    개발 중 상수 값 확인용
    """
    print("=" * 50)
    print("M-Model 프로젝트 전역 상수")
    print("=" * 50)
    
    print("\n[데이터 수집]")
    print(f"  수집 기간: {START_YEAR} ~ {CURRENT_YEAR}")
    print(f"  제외 섹터: {EXCLUDED_SECTORS}")
    
    print("\n[회계 재작성]")
    print(f"  SG&A 자산화 비율: {SGA_WEIGHT:.1%}")
    print(f"  상각 기간: {AMORTIZATION_YEARS}년")
    
    print("\n[모델 학습]")
    print(f"  입력 차원: {INPUT_DIM} (m1, m2, m3)")
    print(f"  Learning Rate: {LEARNING_RATE}")
    print(f"  Epochs: {EPOCHS}")
    print(f"  Train Window: {TRAIN_WINDOW_YEARS}년")
    
    print("\n[백테스트]")
    print(f"  롱 비율: {[f'{r:.0%}' for r in LONG_RATIOS]}")
    print(f"  홀딩 기간: {HOLDING_PERIOD_MONTHS}개월")
    print(f"  리밸런싱: 매년 {REBALANCE_MONTH}월 말")
    
    print("\n[방어 로직]")
    print(f"  Epsilon: {EPSILON}")
    print(f"  m1 범위: [{M1_CLIP_MIN}, {M1_CLIP_MAX}]")
    print(f"  m2 범위: [{M2_CLIP_MIN}, {M2_CLIP_MAX}]")
    print(f"  m3 범위: [{M3_CLIP_MIN}, {M3_CLIP_MAX}]")
    
    print("\n" + "=" * 50)


# ===========================================
# 7. Tier 기반 XBRL 태그 매핑 (⭐ 중요)
# ===========================================
# 
# SEC CompanyFacts API에서 데이터 수집 시 사용하는 XBRL 태그 리스트
# 
# 설계 원칙:
# 1. 계층적 조회 (Tiered Lookup): Tier1부터 조회, 없으면 Tier2, Tier3 순서
# 2. 문맥 확인 (Context Check): Balance Sheet(instant) vs Income Statement(duration)
# 3. 스케일링 오류 방지: EntityCommonStockSharesOutstanding 단위 오류 대응
# 
# 출처:
# - Source 761, 764, 478: 단일 태그 사용 시 누락 문제
# - Source 864: Shares 태그 스케일링 오류 보고

XBRL_TAGS_TIERED = {
    # [Target 1] 발행주식수 (PBR 계산용)
    "Shares": {
        "Tier1": [
            "EntityCommonStockSharesOutstanding",
            "CommonStockSharesOutstanding",
            "CommonStockSharesIssued"
        ],
        "Tier2_Fallback": [
            "WeightedAverageNumberOfSharesOutstandingBasic",
            "WeightedAverageNumberOfDilutedSharesOutstanding"
        ],
        "IFRS": [
            "NumberOfSharesOutstanding",
            "NumberOfOrdinarySharesOutstanding"
        ]
    },
    
    # [Target 2] R&D 비용
    "RD": {
        "Tier1": [
            "ResearchAndDevelopmentExpense",
            "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"
        ],
        "Tier2": [
            "ResearchAndDevelopmentExpenseSoftwareExcludingAmortization"
        ]
    },
    
   # [Target 3] SG&A 비용
    "SGA": {
        "Tier1": [
            "SellingGeneralAndAdministrativeExpense"
        ],
        "Tier2": [
            "SellingAndMarketingExpense",
            "GeneralAndAdministrativeExpense"
        ]
    },
    
    # [Target 4] 영업이익
    "OI": {
        "Tier1": [
            "OperatingIncomeLoss"
        ],
        "Tier2": [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"
        ]
    },
    
    # [Target 5] 매출액
    "Revenue": {
        "Tier1": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",  # ASC 606 (2018+)
            "RevenueFromContractWithCustomerIncludingAssessedTax",  # ASC 606 세금 포함
            "Revenues",
            "SalesRevenueNet"
        ],
        "Tier2": [
            "RevenuesNetOfInterestExpense",
            "SalesRevenueGoodsNet",
            "SalesRevenueServicesNet"
        ]
    },
    
    # [Target 6] 자본총계
    "Equity": {
        "Tier1": [
            "StockholdersEquity"
        ],
        "Tier2": [
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
        ]
    },
    
    # [Target 7] 순이익
    "NetIncome": {
        "Tier1": [
            "NetIncomeLoss"
        ],
        "Tier2": [
            "ProfitLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic"
        ]
    }
}


# ===========================================
# GICS 섹터 정규화 매핑 (개선 2)
# ===========================================
# yfinance의 sector 필드를 GICS 11개 대분류로 표준화

GICS_SECTOR_MAPPING = {
    # Technology
    'Information Technology': 'Technology',
    'Tech': 'Technology',
    'Technology': 'Technology',
    'Software': 'Technology',
    'Hardware': 'Technology',
    'Semiconductors': 'Technology',
    
    # Healthcare
    'Healthcare': 'Healthcare',
    'Health Care': 'Healthcare',
    'Pharmaceuticals': 'Healthcare',
    'Biotechnology': 'Healthcare',
    'Medical Devices': 'Healthcare',
    
    # Financials (이미 제외됨)
    'Financials': 'Financials',
    'Financial Services': 'Financials',
    'Financial': 'Financials',
    'Banks': 'Financials',
    'Insurance': 'Financials',
    
    # Consumer Discretionary
    'Consumer Discretionary': 'Consumer Discretionary',
    'Consumer Cyclical': 'Consumer Discretionary',
    'Retail': 'Consumer Discretionary',
    'Automobiles': 'Consumer Discretionary',
    
    # Consumer Staples
    'Consumer Staples': 'Consumer Staples',
    'Consumer Defensive': 'Consumer Staples',
    'Food & Beverage': 'Consumer Staples',
    
    # Industrials
    'Industrials': 'Industrials',
    'Industrial': 'Industrials',
    'Aerospace & Defense': 'Industrials',
    'Transportation': 'Industrials',
    
    # Energy (이미 제외됨)
    'Energy': 'Energy',
    'Oil & Gas': 'Energy',
    
    # Materials (이미 제외됨)
    'Materials': 'Materials',
    'Basic Materials': 'Materials',
    'Chemicals': 'Materials',
    
    # Communication Services
    'Communication Services': 'Communication',
    'Telecommunication Services': 'Communication',
    'Media': 'Communication',
    'Entertainment': 'Communication',
    
    # Utilities (이미 제외됨)
    'Utilities': 'Utilities',
    'Utility': 'Utilities',
    
    # Real Estate
    'Real Estate': 'Real Estate',
    'REITs': 'Real Estate',
}

# GICS 11개 표준 섹터
GICS_STANDARD_SECTORS = [
    'Technology',
    'Healthcare',
    'Financials',
    'Consumer Discretionary',
    'Consumer Staples',
    'Industrials',
    'Energy',
    'Materials',
    'Communication',
    'Utilities',
    'Real Estate'
]

# 섹터 중앙값 계산 시 최소 샘플 수
MIN_SECTOR_SAMPLE_SIZE = 5

