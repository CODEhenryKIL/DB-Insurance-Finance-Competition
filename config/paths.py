"""
===========================================
M-Model 프로젝트 경로 관리
===========================================

이 파일의 역할:
- 모든 파일 경로를 중앙에서 관리
- 상대 경로 문제 방지 (절대 경로 사용)
- 디렉토리 자동 생성 기능

정의된 경로:
- PROJECT_ROOT: 프로젝트 루트 디렉토리
- DATA_CACHE_DIR: 캐시 저장 디렉토리
- STEP1~5_OUTPUT: 각 단계별 출력 파일 경로
- REPORTS_DIR: 리포트 저장 디렉토리
"""

from pathlib import Path

# ===========================================
# 기본 경로 설정
# ===========================================

# 이 파일의 위치를 기준으로 프로젝트 루트 계산
# config/paths.py → 프로젝트 루트는 한 단계 위
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# 데이터 캐시 디렉토리
# 모든 중간 결과물과 raw 데이터가 여기 저장됨
DATA_CACHE_DIR = PROJECT_ROOT / 'data_cache'

# CACHE_DIR alias (backwards compatibility)
CACHE_DIR = DATA_CACHE_DIR

# SEC/Edgar raw 데이터 캐시
# edgartools나 SEC API에서 받은 원본 JSON 파일 저장
EDGAR_CACHE_DIR = DATA_CACHE_DIR / 'edgar_cache'

# 리포트 저장 디렉토리
# 백테스트 결과 차트 및 PDF 리포트 저장
REPORTS_DIR = PROJECT_ROOT / 'reports'

# 로그 파일 디렉토리
LOGS_DIR = PROJECT_ROOT / 'logs'


# ===========================================
# Step별 출력 파일 경로
# ===========================================

# Step0: 유니버스 빌더 (유효 티커 목록)
# - 필터링된 유효 티커 + CIK 매핑 정보
STEP0_VALID_UNIVERSE_JSON = DATA_CACHE_DIR / 'step0_valid_universe.json'

# Step1: 가격 데이터 수집
# - 월말 조정종가 (수익률 계산용)
STEP1_PRICE_ADJ_CSV = DATA_CACHE_DIR / 'step1_px_adj_m.csv'

# - 월말 종가 ($5 룰 판정용)
STEP1_PRICE_CLOSE_CSV = DATA_CACHE_DIR / 'step1_px_close_m.csv'

# - 메타 정보 (티커 리스트, 섹터 정보 등)
STEP1_META_JSON = DATA_CACHE_DIR / 'step1_meta.json'


# Step2: 재무 데이터 수집
# - 연간 재무제표 패널 데이터
# - Columns: Ticker, FiscalYear, EndDate, Revenue, OI, NetIncome, RD, SGA, Equity
STEP2_FUNDAMENTALS_CSV = DATA_CACHE_DIR / 'step2_fund_annual.csv'


# Step3: Feature Engineering
# - 피처 패널 데이터
# - Columns: Ticker, FiscalYear, EndDate, m1, m2, m3, y
STEP3_FEATURES_CSV = DATA_CACHE_DIR / 'step3_features_annual.csv'


# Step4: 모델 학습 및 예측
# - 예측 결과 (Gap 포함)
# - Columns: Ticker, FiscalYear, y, yhat, Gap
STEP4_PREDICTIONS_CSV = DATA_CACHE_DIR / 'step4_predictions.csv'


# Step5: 백테스트 결과 (4가지 롱 비율)
# - 각 롱 비율별로 별도 파일 저장
STEP5_BACKTEST_5PCT_CSV = DATA_CACHE_DIR / 'step5_backtest_results_5pct.csv'
STEP5_BACKTEST_10PCT_CSV = DATA_CACHE_DIR / 'step5_backtest_results_10pct.csv'
STEP5_BACKTEST_20PCT_CSV = DATA_CACHE_DIR / 'step5_backtest_results_20pct.csv'
STEP5_BACKTEST_30PCT_CSV = DATA_CACHE_DIR / 'step5_backtest_results_30pct.csv'

# 백테스트 결과 딕셔너리 (롱 비율 → 파일 경로)
STEP5_BACKTEST_RESULTS = {
    0.05: STEP5_BACKTEST_5PCT_CSV,
    0.10: STEP5_BACKTEST_10PCT_CSV,
    0.20: STEP5_BACKTEST_20PCT_CSV,
    0.30: STEP5_BACKTEST_30PCT_CSV,
}


# ===========================================
# 리포트 파일 경로
# ===========================================

# 종합 백테스트 리포트 (PDF)
REPORT_PDF = REPORTS_DIR / 'm_model_backtest_report.pdf'

# 누적 수익률 차트
CHART_CUMULATIVE_RETURNS = REPORTS_DIR / 'cumulative_returns.png'

# 연간 수익률 비교 차트
CHART_ANNUAL_RETURNS = REPORTS_DIR / 'annual_returns_comparison.png'

# Gap 분포 히스토그램
CHART_GAP_DISTRIBUTION = REPORTS_DIR / 'gap_distribution.png'

# 성과 지표 테이블
CHART_METRICS_TABLE = REPORTS_DIR / 'metrics_table.png'

# Step 3.5: 유니버스 리포트 (데이터 품질 점검용)
UNIVERSE_REPORT_XLSX = REPORTS_DIR / 'final_universe_report.xlsx'

# Step 5.5: 백테스트 포트폴리오 히스토리 (연도별 선택 티커 리스트)
BACKTEST_PORTFOLIO_HISTORY_XLSX = REPORTS_DIR / 'backtest_portfolio_history.xlsx'


# ===========================================
# 로그 파일 경로
# ===========================================

# 메인 로그 파일
LOG_FILE = LOGS_DIR / 'm_model.log'


# ===========================================
# 디렉토리 자동 생성 함수
# ===========================================

def ensure_all_dirs():
    """
    프로젝트 실행에 필요한 모든 디렉토리를 생성합니다.
    이미 존재하면 아무 작업도 하지 않습니다.
    
    생성 디렉토리:
    - data_cache/
    - data_cache/edgar_cache/
    - reports/
    - logs/
    
    Returns:
        None
        
    사용 시점:
        프로젝트 실행 시작 시 한 번 호출 (main.py에서)
    """
    # 각 디렉토리를 순회하며 생성
    for directory in [DATA_CACHE_DIR, EDGAR_CACHE_DIR, REPORTS_DIR, LOGS_DIR]:
        # exist_ok=True: 이미 존재해도 에러 발생 안함
        # parents=True: 중간 경로도 자동 생성
        directory.mkdir(parents=True, exist_ok=True)
    
    print(f"디렉토리 초기화 완료:")
    print(f"  - 캐시: {DATA_CACHE_DIR}")
    print(f"  - 리포트: {REPORTS_DIR}")
    print(f"  - 로그: {LOGS_DIR}")


def get_step5_path(long_ratio: float) -> Path:
    """
    롱 비율에 해당하는 백테스트 결과 파일 경로를 반환합니다.
    
    Args:
        long_ratio: 롱 비율 (0.05, 0.10, 0.20, 0.30 중 하나)
        
    Returns:
        해당 롱 비율의 백테스트 결과 CSV 파일 경로
        
    Raises:
        ValueError: 지원하지 않는 롱 비율인 경우
        
    사용 예시:
        path = get_step5_path(0.20)
        # → data_cache/step5_backtest_results_20pct.csv
    """
    if long_ratio not in STEP5_BACKTEST_RESULTS:
        raise ValueError(
            f"지원하지 않는 롱 비율: {long_ratio}. "
            f"사용 가능한 비율: {list(STEP5_BACKTEST_RESULTS.keys())}"
        )
    
    return STEP5_BACKTEST_RESULTS[long_ratio]


# ===========================================
# 사용 예시
# ===========================================
if __name__ == '__main__':
    """
    이 파일을 직접 실행하면 모든 경로를 출력하고 디렉토리를 생성합니다.
    개발 중 경로 확인용
    """
    print("=" * 60)
    print("M-Model 프로젝트 경로 설정")
    print("=" * 60)
    
    print(f"\n[프로젝트 루트]")
    print(f"  {PROJECT_ROOT}")
    
    print(f"\n[캐시 디렉토리]")
    print(f"  데이터 캐시: {DATA_CACHE_DIR}")
    print(f"  Edgar 캐시: {EDGAR_CACHE_DIR}")
    
    print(f"\n[Step1 출력]")
    print(f"  조정종가: {STEP1_PRICE_ADJ_CSV}")
    print(f"  종가: {STEP1_PRICE_CLOSE_CSV}")
    print(f"  메타: {STEP1_META_JSON}")
    
    print(f"\n[Step2 출력]")
    print(f"  재무데이터: {STEP2_FUNDAMENTALS_CSV}")
    
    print(f"\n[Step3 출력]")
    print(f"  피처: {STEP3_FEATURES_CSV}")
    
    print(f"\n[Step4 출력]")
    print(f"  예측: {STEP4_PREDICTIONS_CSV}")
    
    print(f"\n[Step5 출력 (4가지 롱 비율)]")
    for ratio, path in STEP5_BACKTEST_RESULTS.items():
        print(f"  {ratio:.0%}: {path}")
    
    print(f"\n[리포트]")
    print(f"  PDF: {REPORT_PDF}")
    print(f"  차트: {REPORTS_DIR}")
    
    print(f"\n[로그]")
    print(f"  {LOG_FILE}")
    
    # 디렉토리 생성
    print("\n" + "=" * 60)
    ensure_all_dirs()
    print("=" * 60)
