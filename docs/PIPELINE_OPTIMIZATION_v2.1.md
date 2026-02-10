# 🚀 M-Model 파이프라인 최적화 v2.1 - 변경 사항 문서

> **작성일**: 2026-01-30  
> **버전**: 2.1.3 (Step 1 데이터 검증 완료)  
> **작성자**: GitHub Copilot  
> **목적**: 다른 코드 에이전트가 변경사항을 즉시 파악할 수 있도록 상세 문서화

---

## 📌 핵심 변경 요약 (TL;DR)

**기존 방식**: "일단 다 수집하고 나중에 거르기"  
**새로운 방식**: "**Step 0에서 유효 기업 확정** → 그들만 수집하기"

### 주요 변경점
1. **Step 0 신설**: 유니버스 빌더 (API 호출 전 필터링)
2. **Step 1/2 수정**: Step 0 JSON 우선 사용
3. **Step 3.5 신설**: 유니버스 리포트 (Excel) 자동 생성
4. **Step 5.5 신설**: 백테스트 포트폴리오 히스토리 (Excel) 자동 저장
5. **v2.1.2**: Unknown 섹터 제외 + Step 1 배치 처리 개선
6. **v2.1.3**: Step 1 데이터 무결성 검증 완료 (3,640개 티커 확정)

---

## 📊 현재 파이프라인 상태 (v2.1.3)

| Step | 상태 | 설명 | 티커 수 |
|------|------|------|--------|
| Step 0 | ✅ 완료 | 유니버스 빌더 | 8,410 → 3,640 |
| Step 1 | ✅ 완료 | 가격 데이터 수집 | 3,640 |
| Step 2 | ⏳ 진행 중 | 재무 데이터 수집 (SEC EDGAR) | - |
| Step 3 | 대기 | 피처 엔지니어링 | - |
| Step 4 | 대기 | 모델 학습/예측 | - |
| Step 5 | 대기 | 백테스트 | - |

---

## 📁 파일 변경 목록

### 🆕 새로 생성된 파일

| 파일 경로 | 용도 | 라인 수 |
|-----------|------|---------|
| `data_collection/step0_universe_filter.py` | Step 0 유니버스 빌더 | ~320줄 |

### ✏️ 수정된 파일

| 파일 경로 | 변경 유형 | 변경 라인 |
|-----------|----------|-----------|
| `config/paths.py` | 경로 추가 | +10줄 |
| `config/constants.py` | Unknown 섹터 추가 (v2.1.2) | +1줄 |
| `data_collection/__init__.py` | export 추가 | +7줄 |
| `data_collection/step1_price_collector.py` | 배치 처리 로직 추가 (v2.1.2) | ~80줄 수정 |
| `data_collection/step2_fundamental_collector.py` | 로직 변경 | ~80줄 수정 |
| `feature_engineering/step3_feature_builder.py` | 함수 추가 | +120줄 |
| `backtesting/step5_backtest.py` | 함수 추가 | +150줄 |

---

## 🔧 상세 변경 내역

### 0. `config/constants.py` 변경 (v2.1.2)

#### Unknown 섹터 제외 추가

```python
# 변경 전
EXCLUDED_SECTORS = [
    'Financials',       # GICS 40
    'Utilities',        # GICS 55
    'Energy',           # GICS 10
    'Materials',        # GICS 15
    'Real Estate'       # GICS 60
]

# 변경 후 (v2.1.2)
EXCLUDED_SECTORS = [
    'Financials',       # GICS 40
    'Utilities',        # GICS 55
    'Energy',           # GICS 10
    'Materials',        # GICS 15
    'Real Estate',      # GICS 60
    'Unknown'           # 섹터 정보 없는 기업 제외 (v2.1.2)
]
```

#### 변경 이유
- 섹터 정보가 없는 기업(`Unknown`)은 데이터 품질이 낮을 가능성이 높음
- 분석 정확도 향상을 위해 Step 0 ~ Step 3에서 일관되게 제외

---

### 0.5 `data_collection/step1_price_collector.py` 변경 (v2.1.2)

#### 배치 처리 로직 추가 (대규모 티커 지원)

**문제점**: 4,000개 이상 티커를 `yf.download(threads=True)`로 다운로드 시 스레드 한계 오류 발생
- `RuntimeError: can't start new thread`

**해결책**: 500개 단위 배치 처리 + 스레드 수 제한

```python
# 변경 전
data = yf.download(
    tickers=tickers,
    start=self.start_date,
    end=self.end_date,
    group_by='ticker',
    auto_adjust=False,
    threads=True,  # 무제한 스레드 → 대규모 티커 시 오류
    progress=True
)

# 변경 후 (v2.1.2)
BATCH_SIZE = 500

if len(tickers) > BATCH_SIZE:
    logger.info(f"  - 배치 처리: {BATCH_SIZE}개씩 나눠서 다운로드")
    all_adj_close = []
    all_close = []
    
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(tickers) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(f"  → 배치 {batch_num}/{total_batches}: {len(batch)}개 티커")
        
        data = yf.download(
            tickers=batch,
            threads=8,  # 스레드 수 제한
            ...
        )
        # 배치별 결과 병합
        all_adj_close.append(batch_adj)
        all_close.append(batch_close)
    
    adj_close_df = pd.concat(all_adj_close, axis=1)
    close_df = pd.concat(all_close, axis=1)
```

#### 적용 효과
- 4,333개 티커 → 9개 배치 (500개 × 8 + 333개 × 1)
- 배치당 약 35초, 전체 약 5분
- 스레드 제한(8개)으로 시스템 안정성 확보

---

### 1. `config/paths.py` 변경

#### 추가된 경로 상수

```python
# Step0: 유니버스 빌더 (유효 티커 목록)
# - 필터링된 유효 티커 + CIK 매핑 정보
STEP0_VALID_UNIVERSE_JSON = DATA_CACHE_DIR / 'step0_valid_universe.json'

# Step 3.5: 유니버스 리포트 (데이터 품질 점검용)
UNIVERSE_REPORT_XLSX = REPORTS_DIR / 'final_universe_report.xlsx'

# Step 5.5: 백테스트 포트폴리오 히스토리 (연도별 선택 티커 리스트)
BACKTEST_PORTFOLIO_HISTORY_XLSX = REPORTS_DIR / 'backtest_portfolio_history.xlsx'
```

#### 변경 위치
- **Line 48-52**: `STEP0_VALID_UNIVERSE_JSON` 추가 (Step1 경로 정의 앞)
- **Line 112-113**: `UNIVERSE_REPORT_XLSX` 추가 (CHART_METRICS_TABLE 뒤)
- **Line 116-117**: `BACKTEST_PORTFOLIO_HISTORY_XLSX` 추가

---

### 2. `data_collection/__init__.py` 변경

#### 변경 전
```python
"""data_collection 패키지 초기화"""

from .step1_price_collector import PriceCollector
from .step2_fundamental_collector import FundamentalCollector
```

#### 변경 후
```python
"""data_collection 패키지 초기화"""

from .step0_universe_filter import (
    UniverseBuilder,
    load_valid_universe,
    get_ticker_cik_mapping,
    get_valid_tickers
)
from .step1_price_collector import PriceCollector
from .step2_fundamental_collector import FundamentalCollector
```

#### 새로 export되는 함수들
- `UniverseBuilder`: 유니버스 빌더 클래스
- `load_valid_universe()`: JSON에서 유니버스 로드
- `get_ticker_cik_mapping()`: ticker → CIK 딕셔너리 반환
- `get_valid_tickers()`: 유효 티커 리스트만 반환

---

### 3. `data_collection/step0_universe_filter.py` (🆕 신규 파일)

#### 파일 구조

```
step0_universe_filter.py
├── UniverseBuilder 클래스
│   ├── __init__()
│   ├── get_raw_ticker_list()      # 원본 티커 수집
│   ├── _fetch_sp500_tickers()     # Wikipedia S&P500 파싱
│   ├── load_cik_mapping()         # SEC CIK 매핑 로드
│   ├── normalize_sector()         # GICS 섹터 표준화
│   ├── check_ticker_validity()    # 개별 티커 유효성 검사
│   ├── build_universe()           # 전체 유니버스 빌드
│   ├── save_universe()            # JSON 저장
│   └── run()                      # 메인 파이프라인
│
└── 유틸리티 함수들
    ├── load_valid_universe()      # 저장된 유니버스 로드
    ├── get_ticker_cik_mapping()   # ticker→CIK 딕셔너리
    └── get_valid_tickers()        # 티커 리스트만
```

#### 핵심 로직: `check_ticker_validity()`

```python
def check_ticker_validity(self, ticker: str) -> Tuple[bool, Optional[Dict]]:
    """
    개별 티커 유효성 검사
    
    Filter 1: quoteType이 EQUITY인지 (ETF, SPAC, Fund 제외)
    Filter 2: 섹터가 제외 대상인지 (Financials, Utilities, Energy, Materials, Real Estate)
    Filter 3: CIK 매핑 존재 여부
    
    Returns:
        (is_valid, metadata_dict)
        - metadata_dict: {'ticker', 'cik', 'sector', 'industry', 'name'}
    """
```

#### 출력 파일 형식: `step0_valid_universe.json`

```json
[
  {
    "ticker": "AAPL",
    "cik": "0000320193",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "name": "Apple Inc."
  },
  {
    "ticker": "MSFT",
    "cik": "0000789019",
    "sector": "Technology",
    "industry": "Software - Infrastructure",
    "name": "Microsoft Corporation"
  }
]
```

---

### 4. `data_collection/step1_price_collector.py` 변경

#### 4.1 Import 변경

```python
# 변경 전
from config.paths import (
    STEP1_PRICE_ADJ_CSV,
    STEP1_PRICE_CLOSE_CSV,
    STEP1_META_JSON
)

# 변경 후
from config.paths import (
    STEP1_PRICE_ADJ_CSV,
    STEP1_PRICE_CLOSE_CSV,
    STEP1_META_JSON,
    STEP0_VALID_UNIVERSE_JSON  # ⭐ 추가
)
```

#### 4.2 `get_sp500_tickers()` 메소드 변경

**변경 전 로직**:
1. TEST_MODE 확인
2. MARKET_MODE에 따라 S&P500 또는 전체 시장 티커 수집

**변경 후 로직**:
1. **⭐ Step 0 유니버스 JSON 존재 확인 (우선)**
2. JSON 있으면 → 티커 + 섹터맵 로드, 바로 반환
3. JSON 없으면 → 기존 레거시 로직 실행

```python
def get_sp500_tickers(self) -> List[str]:
    # ⭐ Step 0 유니버스 JSON이 있으면 우선 사용
    if STEP0_VALID_UNIVERSE_JSON.exists():
        logger.info("📜 Step 0 유니버스 JSON에서 티커 로드")
        with open(STEP0_VALID_UNIVERSE_JSON, 'r', encoding='utf-8') as f:
            universe = json.load(f)
        
        tickers = [item['ticker'] for item in universe]
        
        # 섹터 정보도 미리 저장 (나중에 사용)
        self._universe_sector_map = {item['ticker']: item['sector'] for item in universe}
        
        logger.info(f"  → 유효 티커 로드 완료: {len(tickers)}개")
        logger.info(f"  → 이미 필터링됨: 금융/유틸/에너지/부동산 제외 완료")
        return tickers
    
    # 이하 기존 레거시 로직...
```

#### 4.3 `run()` 메소드 변경

**변경 전**:
```python
def run(self):
    # 1. S&P500 티커 수집
    tickers = self.get_sp500_tickers()
    
    # 2. 섹터 정보 수집
    sector_map = self.get_sector_info(tickers)
    
    # 3. 섹터 필터링
    filtered_tickers, filtered_sector_map = self.filter_by_sector(sector_map)
    
    # 4~6. 가격 수집, 리샘플링, 저장...
```

**변경 후**:
```python
def run(self):
    # 1. 티커 수집
    tickers = self.get_sp500_tickers()
    
    # ⭐ Step 0 유니버스를 사용했는지 확인
    use_step0_universe = hasattr(self, '_universe_sector_map') and self._universe_sector_map
    
    if use_step0_universe:
        # Step 0에서 이미 필터링됨 → 섹터 수집/필터링 스킵
        logger.info("✅ Step 0 유니버스 사용 - 섹터 필터링 스킵")
        filtered_tickers = tickers
        filtered_sector_map = self._universe_sector_map
    else:
        # 레거시 모드: 직접 섹터 수집 및 필터링
        logger.info("⚠️ 레거시 모드 - 섹터 수집 및 필터링 직접 수행")
        sector_map = self.get_sector_info(tickers)
        filtered_tickers, filtered_sector_map = self.filter_by_sector(sector_map)
    
    # 4~6. 가격 수집, 리샘플링, 저장...
```

---

### 5. `data_collection/step2_fundamental_collector.py` 변경

#### 5.1 Import 변경

```python
# 변경 전
from config.paths import (
    STEP1_META_JSON,
    STEP2_FUNDAMENTALS_CSV,
    DATA_CACHE_DIR
)

# 변경 후
from config.paths import (
    STEP1_META_JSON,
    STEP2_FUNDAMENTALS_CSV,
    DATA_CACHE_DIR,
    STEP0_VALID_UNIVERSE_JSON  # ⭐ 추가
)
```

#### 5.2 `run()` 메소드 완전 재작성

**변경 전**:
```python
def run(self):
    # 1. Step1에서 티커 로드
    meta = load_cache(STEP1_META_JSON)
    tickers = meta['tickers']
    
    # 2. 재무 데이터 수집
    fund_df = self.collect_fundamentals(tickers)
    
    # 3~4. 확인, 저장...
```

**변경 후**:
```python
def run(self):
    import json
    
    # ⭐ Step 0 유니버스 우선 사용
    if STEP0_VALID_UNIVERSE_JSON.exists():
        logger.info("📜 Step 0 유니버스에서 티커/CIK/섹터 로드")
        with open(STEP0_VALID_UNIVERSE_JSON, 'r', encoding='utf-8') as f:
            universe = json.load(f)
        
        tickers = [item['ticker'] for item in universe]
        cik_map = {item['ticker']: item['cik'] for item in universe}
        sector_map = {item['ticker']: item['sector'] for item in universe}
        
        logger.info(f"  → 유효 티커: {len(tickers)}개")
        logger.info(f"  → CIK 매핑 완료: {len(cik_map)}개")
        logger.info(f"  → 섹터 정보 완료: {len(sector_map)}개")
        
        # ⭐ 직접 재무 데이터 수집 (CIK 사용)
        fund_df = self._collect_with_universe(tickers, cik_map, sector_map)
    else:
        # 레거시 모드
        meta = load_cache(STEP1_META_JSON)
        tickers = meta['tickers']
        fund_df = self.collect_fundamentals(tickers)
    
    # 3~4. 확인, 저장...
```

#### 5.3 새로 추가된 메소드: `_collect_with_universe()`

```python
def _collect_with_universe(
    self,
    tickers: List[str],
    cik_map: Dict[str, str],
    sector_map: Dict[str, str]
) -> pd.DataFrame:
    """
    Step 0 유니버스를 활용한 재무 데이터 수집
    
    특징:
    - CIK를 유니버스에서 직접 가져옴 (매핑 오류 방지)
    - 섹터 정보도 유니버스에서 직접 사용 (추가 API 호출 불필요)
    """
    for ticker in tqdm(tickers, desc="SEC 데이터 수집"):
        # ⭐ CIK를 유니버스에서 직접 가져옴
        cik = cik_map.get(ticker)
        
        if not cik:
            continue
        
        # SEC 데이터 수집
        companyfacts = self.fetch_companyfacts(cik, ticker)
        annual_financials = self.parse_financials(ticker, companyfacts)
        
        if annual_financials is not None:
            # ⭐ 섹터 정보를 유니버스에서 직접 가져옴
            annual_financials['Sector'] = sector_map.get(ticker, 'Unknown')
            all_financials.append(annual_financials)
```

---

### 6. `feature_engineering/step3_feature_builder.py` 변경

#### 6.1 `run()` 메소드에 Step 3.5 호출 추가

```python
def run(self) -> pd.DataFrame:
    # ... 기존 Step 3 로직 ...
    
    # 7. 저장
    output_path = CACHE_DIR / 'step3_features_annual.csv'
    features_df.to_csv(output_path)
    
    # ⭐ Step 3.5: 유니버스 리포트 생성 (신규!)
    logger.info("")
    logger.info("="*60)
    logger.info("  Step 3.5: 유니버스 리포트 생성")
    logger.info("="*60)
    self.generate_universe_report(features_df)
    
    return features_df
```

#### 6.2 새로 추가된 메소드: `generate_universe_report()`

```python
def generate_universe_report(self, features_df: pd.DataFrame) -> None:
    """
    Step 3.5: 유니버스 리포트 생성 (Excel)
    
    모델 학습 전 데이터 품질 점검용 리포트
    
    출력 파일: reports/final_universe_report.xlsx
    
    시트 구성:
    1. Summary: 전체 통계
    2. Sector_Summary: 섹터별 분포
    3. Details: 티커별 상세 정보
    """
```

#### 6.3 리포트 컬럼 상세 (Details 시트)

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| Ticker | str | 티커 심볼 |
| Sector | str | GICS 섹터 |
| Start_Year | int | 데이터 시작 연도 |
| End_Year | int | 데이터 끝 연도 |
| Count_Rows | int | 총 데이터 포인트 수 |
| Missing_R&D | bool | R&D 데이터 누락 여부 (True=누락) |
| Valid_m1 | int | m1 유효 데이터 수 |
| Valid_m2 | int | m2 유효 데이터 수 |
| Valid_m3 | int | m3 유효 데이터 수 |
| Valid_y | int | y 유효 데이터 수 |
| Status | str | 'Ready' 또는 'Insufficient Data' |

#### 6.4 Status 판정 로직

```python
# 최소 3년 데이터 + m2 2개 이상 + y 2개 이상 필요
if count_rows >= 3 and valid_m2 >= 2 and valid_y >= 2:
    status = 'Ready'
else:
    status = 'Insufficient Data'
```

---

## 🔄 새로운 파이프라인 흐름도

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 0: Universe Builder (신규)                                │
│  ─────────────────────────────────────────────────────────────  │
│  입력: Raw Ticker List (S&P500 / FULL Market)                   │
│  처리:                                                          │
│    1. yfinance fast_info로 quoteType 확인                       │
│    2. ETF/SPAC/뮤추얼펀드 제외 (EQUITY만 남김)                  │
│    3. 제외 섹터 필터링 (Financials, Utilities, Energy, ...)     │
│    4. SEC CIK 매핑 수행                                         │
│  출력: step0_valid_universe.json                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Price Collection                                       │
│  ─────────────────────────────────────────────────────────────  │
│  입력: step0_valid_universe.json (⭐ 우선) 또는 레거시 방식     │
│  변경: 섹터 수집/필터링 스킵 (이미 완료됨)                      │
│  출력: step1_px_adj_m.csv, step1_px_close_m.csv, step1_meta.json│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Fundamental Collection                                 │
│  ─────────────────────────────────────────────────────────────  │
│  입력: step0_valid_universe.json (⭐ 우선) 또는 레거시 방식     │
│  변경: CIK를 JSON에서 직접 사용 (매핑 오류 방지)                │
│  변경: 섹터 정보도 JSON에서 직접 사용                           │
│  출력: step2_fund_annual.csv                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Feature Engineering                                    │
│  ─────────────────────────────────────────────────────────────  │
│  처리: 기존과 동일 (m1, m2, m3, y 계산)                         │
│  출력: step3_features_annual.csv                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3.5: Universe Report (신규)                               │
│  ─────────────────────────────────────────────────────────────  │
│  입력: Step 3 피처 데이터                                       │
│  처리: 티커별 데이터 품질 분석                                  │
│  출력: reports/final_universe_report.xlsx                       │
│    - Summary 시트: 전체 통계                                    │
│    - Sector_Summary 시트: 섹터별 분포                           │
│    - Details 시트: 티커별 상세 (Start/End Year, Missing R&D)   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Training & Prediction                                  │
│  ─────────────────────────────────────────────────────────────  │
│  처리: 기존과 동일 (Linear PBR 모델 학습)                       │
│  출력: step4_predictions.csv (Gap = yhat - y)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: Backtest                                               │
│  ─────────────────────────────────────────────────────────────  │
│  처리: Gap 상위 5%/10%/20%/30% 롱 전략 백테스트                 │
│  출력: step5_backtest_returns.csv, step5_backtest_metrics.csv   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5.5: Portfolio History Report (신규)                      │
│  ─────────────────────────────────────────────────────────────  │
│  입력: 백테스트 결과                                            │
│  처리: 연도별 선택 티커 및 Gap 정보 저장                        │
│  출력: reports/backtest_portfolio_history.xlsx                  │
│    - Summary 시트: 각 비율별 요약 통계                          │
│    - Top_5pct 시트: 상위 5% 포트폴리오 상세                     │
│    - Top_10pct 시트: 상위 10% 포트폴리오 상세                   │
│    - Top_20pct 시트: 상위 20% 포트폴리오 상세                   │
│    - Top_30pct 시트: 상위 30% 포트폴리오 상세                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 실행 방법

### 전체 파이프라인 실행 순서

```bash
# 1. Step 0: 유니버스 빌드 (최초 1회 또는 티커 변경 시)
python -m data_collection.step0_universe_filter

# 2. Step 1: 가격 수집 (Step 0 JSON 자동 사용)
python -m data_collection.step1_price_collector

# 3. Step 2: 재무 수집 (Step 0 JSON 자동 사용)
python -m data_collection.step2_fundamental_collector

# 4. Step 3 + 3.5: 피처 엔지니어링 + 유니버스 리포트 생성
python -m feature_engineering.step3_feature_builder

# 5. Step 4: 모델 학습
python -m modeling.step4_train_predict

# 6. Step 5 + 5.5: 백테스트 + 포트폴리오 히스토리 저장
python -m backtesting.step5_backtest
```

### 레거시 모드 (Step 0 없이 실행)

Step 0 유니버스 JSON이 없으면 자동으로 레거시 모드로 동작합니다:
- Step 1: 직접 티커 수집 + 섹터 필터링
- Step 2: Step 1 메타에서 티커 로드 + CIK 직접 매핑

---

## ⚠️ 주의사항

### 1. Step 0 유니버스 갱신 시점
- **S&P 500 구성 변경 시**: 분기별 리밸런싱 후 재실행 권장
- **FULL 모드 티커 리스트 변경 시**: `us_market_tickers.txt` 업데이트 후 재실행

### 2. 하위 호환성
- Step 0 JSON이 없어도 기존 코드 동작함 (레거시 모드)
- 기존 캐시 파일들과 충돌 없음

### 3. 필요한 패키지
```
pip install yfinance requests tqdm openpyxl packaging
```

### 4. 제외되는 섹터 목록
```python
EXCLUDED_SECTORS = [
    'Financials',       # GICS 40
    'Utilities',        # GICS 55
    'Energy',           # GICS 10
    'Materials',        # GICS 15
    'Real Estate'       # GICS 60
]
```

---

## 📊 테스트 결과 (2026-01-30)

### Step 0 테스트 (3개 티커)
```
원본 티커: 3개
유효 티커: 3개 (100.0%)

[섹터별 분포]
  Technology: 2개 (AAPL, MSFT)
  Communication: 1개 (GOOGL)
```

### Step 1 연동 테스트
```
📜 Step 0 유니버스 JSON에서 티커 로드
  → 유효 티커 로드 완료: 3개
  → 이미 필터링됨: 금융/유틸/에너지/부동산 제외 완료
```

---

## 🔗 관련 파일 참조

- 전체 파이프라인 개요: [PIPELINE_OVERVIEW.md](PIPELINE_OVERVIEW.md)
- 상수 정의: [config/constants.py](../config/constants.py)
- 경로 정의: [config/paths.py](../config/paths.py)
- XBRL 태그 매핑: [XBRL_TAG_MAPPING.md](XBRL_TAG_MAPPING.md)

---

## 📝 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-01-30 | v2.1.1 | Step 5.5 포트폴리오 히스토리 저장 기능 추가 |
| 2026-01-30 | v2.1 | Step 0 유니버스 빌더 신설, Step 1/2 JSON 연동, Step 3.5 리포트 추가 |

---

## 📊 Step 5.5: 백테스트 포트폴리오 히스토리 상세

### 7. `backtesting/step5_backtest.py` 변경 (신규 추가)

#### 7.1 추가된 속성

```python
class PortfolioBacktester:
    def __init__(self, ...):
        ...
        # ⭐ 포트폴리오 히스토리 저장용 (Step 5.5)
        self.portfolio_history = {}  # {ratio: [{year, tickers, gaps, ...}, ...]}
```

#### 7.2 연도별 선택 티커 정보 캡처

백테스트 실행 중 각 연도마다 선택된 티커와 Gap 정보를 저장합니다:

```python
# run() 메소드 내부
for year in rebalance_years:
    ...
    # ⭐ 선택된 티커의 Gap 정보 추출
    selected_gaps = year_df[year_df['Ticker'].isin(selected_tickers)][['Ticker', 'Gap', 'y', 'yhat']].to_dict('records')
    
    yearly_results.append({
        'Year': year,
        ...
        '_selected_tickers': selected_tickers,  # ⭐ 내부 저장용
        '_selected_gaps': selected_gaps  # ⭐ 내부 저장용
    })

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
```

#### 7.3 새로 추가된 메소드: `save_portfolio_history()`

```python
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
```

#### 7.4 출력 파일 형식: `backtest_portfolio_history.xlsx`

**Summary 시트:**

| Ratio | Years | Avg_Tickers | Avg_Return | Total_Return | Best_Year | Worst_Year |
|-------|-------|-------------|------------|--------------|-----------|------------|
| Top 5% | 10 | 22.3 | 18.42% | 423.56% | FY2019 (42.1%) | FY2022 (-8.3%) |
| Top 10% | 10 | 44.6 | 16.87% | 381.23% | FY2019 (38.2%) | FY2022 (-6.1%) |
| ... | ... | ... | ... | ... | ... | ... |

**Top_5pct 시트 (상세):**

| Year | N_Tickers | Return | Ticker | Gap | y_actual | yhat_pred | Rank |
|------|-----------|--------|--------|-----|----------|-----------|------|
| FY2015 | 22 | 24.52% | NVDA | 0.8234 | 0.12 | 0.94 | 1 |
| FY2015 | 22 | 24.52% | AMD | 0.7891 | 0.15 | 0.94 | 2 |
| FY2015 | 22 | 24.52% | TSLA | 0.7456 | 0.08 | 0.83 | 3 |
| ... | ... | ... | ... | ... | ... | ... | ... |

이 리포트를 통해:
- 어떤 연도에 어떤 종목이 선택되었는지 확인 가능
- Gap이 높았던 종목들이 실제로 수익을 냈는지 검증 가능
- 특정 연도의 포트폴리오 구성 분석 가능
