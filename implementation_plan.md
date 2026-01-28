# M-Model 프로젝트 구현 계획서 (v1.1)

## 📊 프로젝트 개요

미국 GAAP 기업의 R&D와 SG&A를 K-IFRS 방식으로 자산화하여 회계 재작성을 수행하고, 이를 기반으로 적정 PBR을 예측하는 퀀트 투자 전략 시스템을 구축합니다.

**핵심 아이디어:**
- 회계 재작성으로 기술주/바이오 기업의 과소평가된 자산과 이익을 복원
- 3개 피처(m1, m2, m3)로 적정 PBR 예측
- Gap(예측 PBR - 시장 PBR) 기반 롱 전략 백테스팅

**데이터 범위:** 2010년 이후  
**백테스트 롱 비율:** 5%, 10%, 20%, 30% (4가지 동시 비교)

---

## 🔄 주요 업데이트 (v1.1 - 2026-01-28)

### 1. 데이터 소스 변경
- **우선순위 1:** edgartools (Python 라이브러리, 2010년~현재 지원)
- **우선순위 2:** SimFin API
- **최종 대안:** FMP API (유료)

### 2. m1 방어 로직 개선 ⭐ 중요
**문제점:**
- 기존 로직: `abs(OI) < epsilon` → 결측 처리
- 바이오/초기 테크 기업은 OI≈0이 많아 데이터 대량 손실
- **턴어라운드 유망 종목을 놓치는 치명적 문제**

**개선 방안:**
```python
# ❌ 기존 (데이터 손실)
if abs(OI) < epsilon:
    m1 = NaN
    
# ✅ 개선 (데이터 보존 + 클리핑)
denominator = max(abs(OI), 1e-6)  # 0 대신 매우 작은 수
m1 = AdjOI / denominator
m1 = clip(m1, -5, +5)  # 극단값만 제한
```

### 3. Pandas 버전 호환성
- **요구사항:** pandas >= 2.2.0 (월말 resample 'ME' 지원)
- **호환성 처리:** 'ME' 실패 시 'M'으로 자동 대체

### 4. 백테스트 확장
- Gap 상위 5%, 10%, 20%, 30% (4가지 버전 동시 실행)
- 결과 비교 리포트 자동 생성

---

## 📁 프로젝트 디렉토리 구조

```
/Users/kilminkyu/Desktop/DB 공모전/안티그래비티 - 개발/
│
├── README.md                          # 프로젝트 전체 설명서
├── requirements.txt                   # 패키지 의존성
├── task.md                            # 개발 태스크 체크리스트
├── implementation_plan.md             # 이 파일
├── .gitignore                         # Git 제외 파일
│
├── config/                            # 설정 파일
│   ├── __init__.py
│   ├── constants.py                   # 전역 상수 (섹터, 기간, 파라미터)
│   └── paths.py                       # 경로 설정
│
├── utils/                             # 공통 유틸리티
│   ├── __init__.py
│   ├── logger.py                      # 로깅 설정
│   ├── validators.py                  # 데이터 검증 함수
│   └── helpers.py                     # 공통 헬퍼 함수
│
├── data_collection/                   # 데이터 수집 모듈
│   ├── __init__.py
│   ├── step1_price_collector.py       # 가격 데이터 수집
│   └── step2_fundamental_collector.py # 재무 데이터 수집 (edgartools 우선)
│
├── feature_engineering/               # 피처 엔지니어링
│   ├── __init__.py
│   ├── restatement.py                 # 회계 재작성 로직
│   └── step3_feature_builder.py       # m1, m2, m3, y 계산
│
├── modeling/                          # 모델링
│   ├── __init__.py
│   ├── model.py                       # PyTorch 선형 모델
│   └── step4_train_predict.py         # Rolling window 학습/예측
│
├── backtesting/                       # 백테스팅
│   ├── __init__.py
│   ├── universe_filter.py             # 유니버스 필터링
│   ├── portfolio.py                   # 포트폴리오 구성 (4가지 롱 비율)
│   └── step5_backtest.py              # 백테스트 실행
│
├── evaluation/                        # 평가 및 시각화
│   ├── __init__.py
│   ├── metrics.py                     # 성과 지표 계산
│   └── visualizer.py                  # 차트 및 리포트
│
├── data_cache/                        # 데이터 캐시 (gitignore)
│   ├── step1_px_adj_m.csv
│   ├── step1_px_close_m.csv
│   ├── step1_meta.json
│   ├── step2_fund_annual.csv
│   ├── step3_features_annual.csv
│   ├── step4_predictions.csv
│   ├── step5_backtest_results_5pct.csv
│   ├── step5_backtest_results_10pct.csv
│   ├── step5_backtest_results_20pct.csv
│   ├── step5_backtest_results_30pct.csv
│   └── edgar_cache/                   # edgartools raw 데이터
│       └── *.json
│
├── main.py                            # 전체 파이프라인 실행
└── notebooks/                         # 분석 노트북 (선택)
    └── analysis.ipynb
```

---

## 🔧 주요 컴포넌트 설명

### 1. config/ - 설정 모듈

#### [NEW] [constants.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/config/constants.py)

**파일 개요:**
```python
\"\"\"
===========================================
M-Model 프로젝트 전역 상수 정의
===========================================

이 파일의 역할:
- 프로젝트 전체에서 사용되는 모든 상수를 중앙에서 관리
- 하드코딩 방지 및 유지보수성 향상

주요 상수 그룹:
1. DATA_CONFIG: 데이터 수집 설정
2. RESTATEMENT_CONFIG: 회계 재작성 파라미터
3. MODEL_CONFIG: 모델 학습 설정
4. BACKTEST_CONFIG: 백테스트 전략 파라미터
5. DEFENSE_CONFIG: 방어 로직 파라미터 (⭐ 중요)
\"\"\"
```

**주요 내용:**
- `START_YEAR = 2010`: 데이터 수집 시작 연도
- `EXCLUDED_SECTORS = ['Financial', 'Utilities']`: 제외 섹터
- `SGA_WEIGHT = 0.3`: SG&A 자산화 가중치
- `AMORTIZATION_YEARS = 3`: 상각 기간
- `LONG_RATIOS = [0.05, 0.10, 0.20, 0.30]`: 백테스트 롱 비율 4가지
- `EPSILON = 1e-6`: 0 방어용 최소값
- `M1_CLIP_RANGE = (-5, 5)`: m1 클리핑 범위

---

#### [NEW] [paths.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/config/paths.py)

**파일 개요:**
```python
\"\"\"
===========================================
M-Model 프로젝트 경로 관리
===========================================

이 파일의 역할:
- 모든 파일 경로를 중앙에서 관리
- 상대 경로 문제 방지

정의된 경로:
- PROJECT_ROOT: 프로젝트 루트 디렉토리
- DATA_CACHE_DIR: 캐시 디렉토리
- STEP1~5_OUTPUT: 각 단계별 출력 파일 경로
\"\"\"
```

---

### 2. utils/ - 공통 유틸리티

#### [NEW] [logger.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/utils/logger.py)

**파일 개요:**
```python
\"\"\"
===========================================
통일된 로깅 시스템
===========================================

주요 클래스/함수:
- get_logger(name): 로거 인스턴스 생성
  
기능:
- 콘솔 + 파일 동시 출력
- 한글 메시지 utf-8 인코딩
- 타임스탬프 자동 추가
- 로그 레벨: DEBUG, INFO, WARNING, ERROR

사용 예시:
logger = get_logger(__name__)
logger.info(\"데이터 수집 시작\")
\"\"\"
```

---

#### [NEW] [validators.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/utils/validators.py)

**파일 개요:**
```python
\"\"\"
===========================================
데이터 검증 및 방어 로직 함수 모음
===========================================

주요 함수:
1. safe_divide(num, denom, epsilon=1e-6, clip_range=None)
   - 안전한 나눗셈 (0 방어)
   - m1, m2, m3 계산에 필수
   
2. clip_value(value, min_val, max_val)
   - 극단값 클리핑
   
3. validate_positive(value, allow_zero=False)
   - 양수 검증 (BookValue, Revenue 등)
   
4. is_valid_ticker(ticker)
   - 티커 형식 검증

설계 철학:
- 데이터를 최대한 살리되, 극단값만 제한
- NaN 결측 처리는 최소화
\"\"\"
```

**핵심 함수 상세:**
```python
def safe_divide(numerator, denominator, epsilon=1e-6, clip_range=None):
    \"\"\"
    안전한 나눗셈 (m1, m2, m3 공통 사용)
    
    Args:
        numerator: 분자
        denominator: 분모
        epsilon: 0 대신 사용할 최소값 (기본 1e-6)
        clip_range: (min, max) 튜플, None이면 클리핑 안함
        
    Returns:
        나눗셈 결과 (클리핑 적용 시 클리핑된 값)
        
    예시:
        # m1 계산 시
        m1 = safe_divide(AdjOI, OI, epsilon=1e-6, clip_range=(-5, 5))
    \"\"\"
```

---

#### [NEW] [helpers.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/utils/helpers.py)

**파일 개요:**
```python
\"\"\"
===========================================
공통 헬퍼 함수
===========================================

주요 함수:
- ensure_dir(path): 디렉토리 생성 (없으면)
- load_cache(filepath): 캐시 파일 로드 (csv/json 자동 판별)
- save_cache(data, filepath): 캐시 파일 저장
- get_month_end_freq(): Pandas 버전 호환 월말 freq 반환 (ME 또는 M)
\"\"\"
```

**Pandas 호환성 처리:**
```python
def get_month_end_freq():
    \"\"\"
    Pandas 버전에 따라 월말 resample frequency 반환
    
    Returns:
        'ME' (pandas >= 2.2.0) 또는 'M' (구버전)
        
    사용 예시:
        freq = get_month_end_freq()
        df_monthly = df.resample(freq).last()
    \"\"\"
    import pandas as pd
    from packaging import version
    
    if version.parse(pd.__version__) >= version.parse('2.2.0'):
        return 'ME'
    else:
        return 'M'
```

---

### 3. data_collection/ - 데이터 수집

#### [NEW] [step1_price_collector.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/data_collection/step1_price_collector.py)

**파일 개요:**
```python
\"\"\"
===========================================
Step1: 가격 데이터 수집 및 섹터 필터링
===========================================

정의된 클래스:
- PriceCollector

주요 메소드:
1. get_sp500_tickers() → List[str]
   - S&P500 티커 리스트 수집
   
2. filter_by_sector(tickers) → Dict[str, str]
   - Financial, Utilities 제외
   - 반환: {ticker: sector} 딕셔너리
   
3. collect_monthly_prices(tickers, start_date, end_date) → Tuple[DataFrame, DataFrame]
   - 월말 AdjClose, Close 수집
   - Pandas 버전 호환 처리 (ME/M)
   - 반환: (adj_df, close_df)
   
4. save_to_cache(adj_df, close_df, sector_map)
   - 3개 파일 저장: adj, close, meta.json

전체 흐름:
1. S&P500 티커 수집
2. 섹터 필터링
3. yfinance로 월말 가격 다운로드
4. 캐시 저장

출력 파일:
- data_cache/step1_px_adj_m.csv
- data_cache/step1_px_close_m.csv
- data_cache/step1_meta.json
\"\"\"
```

---

#### [NEW] [step2_fundamental_collector.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/data_collection/step2_fundamental_collector.py)

**파일 개요:**
```python
\"\"\"
===========================================
Step2: 재무 데이터 수집 (edgartools 우선)
===========================================

정의된 클래스:
- FundamentalCollector

주요 메소드:
1. collect_via_edgartools(tickers, start_year) → DataFrame
   - edgartools 라이브러리 사용
   - 2010년 이후 연간 재무제표 수집
   - 필수 필드: Revenue, OI, NetIncome, RD, SGA, Equity
   
2. (대안) collect_via_simfin(tickers) → DataFrame
   - SimFin API 사용
   
3. (최종 대안) collect_via_fmp(tickers) → DataFrame
   - FMP API 사용 (유료)
   
4. parse_annual_data(raw_data) → DataFrame
   - Raw 데이터를 표준 스키마로 변환
   - 스키마: Ticker, FiscalYear, EndDate, Revenue, OI, NetIncome, RD, SGA, Equity
   
5. save_to_cache(fund_df)
   - data_cache/step2_fund_annual.csv 저장

전체 흐름:
1. edgartools 시도 (우선순위 1)
2. 실패 시 SimFin 시도
3. 최종 대안으로 FMP 사용
4. 표준 스키마로 변환 및 저장

출력 파일:
- data_cache/step2_fund_annual.csv
- data_cache/edgar_cache/*.json (raw 캐시)
\"\"\"
```

**edgartools 평가 기준:**
- 2010년 이후 데이터 가용성
- Revenue, OI, RD, SGA, Equity 추출 가능 여부
- API 속도 및 안정성

---

### 4. feature_engineering/ - 피처 생성

#### [NEW] [restatement.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/feature_engineering/restatement.py)

**파일 개요:**
```python
\"\"\"
===========================================
회계 재작성 로직 (K-IFRS 방식)
===========================================

주요 함수:
1. calculate_investment(RD, SGA) → I
   - 자산화 투자액 계산
   - 공식: I = RD + 0.3 × SGA
   
2. calculate_amortization(I_series, years=3) → A
   - 정액 상각 계산
   - 공식: A_t = (I_t + I_t-1 + I_t-2) / 3
   - pandas rolling 사용
   
3. calculate_adj_oi(OI, I, A) → AdjOI
   - 조정 영업이익 계산
   - 공식: AdjOI = OI + I - A
   
전체 흐름:
1. I 계산 (각 연도)
2. A 계산 (3년 rolling)
3. AdjOI 계산

사용 예시:
I = calculate_investment(df['RD'], df['SGA'])
A = calculate_amortization(I)
AdjOI = calculate_adj_oi(df['OI'], I, A)
\"\"\"
```

---

#### [NEW] [step3_feature_builder.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/feature_engineering/step3_feature_builder.py)

**파일 개요:**
```python
\"\"\"
===========================================
Step3: Feature Engineering (m1, m2, m3, y)
===========================================

정의된 클래스:
- FeatureBuilder

주요 메소드:
1. calculate_m1(AdjOI, OI) → m1
   - 이익 복원력
   - ⭐ 개선된 방어 로직 적용
   - 공식: m1 = AdjOI / max(abs(OI), 1e-6)
   - clip: [-5, +5]
   
2. calculate_m2(I, Revenue) → m2
   - 투자 가속도
   - 공식: m2 = Int_t / Avg(Int_t-1, Int_t-2)
   - Int = I / Revenue
   - Revenue 0 방어
   
3. calculate_m3(OI, I, Revenue) → m3
   - 본업 기초체력
   - 공식: m3 = PIM_t / Avg(PIM_t-1, PIM_t-2)
   - PIM = (OI + I) / Revenue
   
4. calculate_y(MktCap, BookValue) → y
   - 타겟 변수
   - 공식: y = ln(MktCap / BookValue)
   - BookValue ≤ 0 → NaN (로그 불가)
   
5. build_features(fund_df, price_df) → DataFrame
   - 전체 파이프라인 실행
   - 반환: (Ticker, FiscalYear, m1, m2, m3, y)

⭐ m1 방어 로직 상세 (중요):
기존 문제:
- abs(OI) < epsilon → NaN 처리
- 바이오/초기 테크 기업 (OI≈0) 대량 손실
- 턴어라운드 유망 종목을 놓침

개선 방안:
```python
# 분모를 매우 작은 수로 대체 (0 방지)
denom = np.maximum(np.abs(OI), 1e-6)
m1 = AdjOI / denom

# 극단값만 클리핑 (데이터 보존)
m1 = np.clip(m1, -5, +5)
```

설계 철학:
- OI가 0에 가까워도 데이터 유지
- AdjOI가 크면 m1도 큼 (저평가 신호)
- 극단값만 [-5, +5]로 제한

출력 파일:
- data_cache/step3_features_annual.csv
\"\"\"
```

---

### 5. modeling/ - 모델링

#### [NEW] [model.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/modeling/model.py)

**파일 개요:**
```python
\"\"\"
===========================================
PyTorch 선형 모델 정의
===========================================

정의된 클래스:
- LinearPBRModel(nn.Module)

모델 구조:
- 입력: (m1, m2, m3) - 3차원
- 출력: yhat - 1차원 (ln(PBR) 예측값)
- Layer: nn.Linear(3, 1, bias=True)

Loss: MSELoss
Optimizer: Adam(lr=1e-3)

사용 예시:
model = LinearPBRModel()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
criterion = nn.MSELoss()

for epoch in range(epochs):
    yhat = model(X_train)
    loss = criterion(yhat, y_train)
    loss.backward()
    optimizer.step()
\"\"\"
```

---

#### [NEW] [step4_train_predict.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/modeling/step4_train_predict.py)

**파일 개요:**
```python
\"\"\"
===========================================
Step4: Rolling Window 학습 및 예측
===========================================

정의된 클래스:
- RollingTrainer

주요 메소드:
1. prepare_data(features_df, rebalance_date) → (X_train, y_train, X_test)
   - 리밸런스 날짜 기준 Train/Test 분할
   - Train: 과거 5년 (예: 2011~2015)
   - Test: 다음 1년 (예: 2016)
   
2. standardize(X_train, X_test) → (X_train_scaled, X_test_scaled, scaler)
   - Train 기준으로 mean/std 계산
   - Train, Test 모두 동일한 scaler로 변환
   
3. train_model(X_train, y_train, epochs=500) → model
   - PyTorch 모델 학습
   - Adam optimizer
   - MSELoss
   
4. predict(model, X_test) → yhat
   - 다음 해 적정 PBR 예측
   
5. calculate_gap(yhat, y_actual) → Gap
   - Gap = yhat - y
   - 양수: 저평가 (롱 신호)
   - 음수: 고평가
   
6. run_rolling_backtest(features_df, rebalance_dates) → results_df
   - 전체 리밸런스 날짜에 대해 반복
   - 각 시점: 학습 → 예측 → Gap 계산
   - 반환: (Ticker, FiscalYear, y, yhat, Gap)

전체 흐름:
1. 리밸런스 날짜 생성 (매년 12월 말)
2. 각 날짜마다:
   a. Train/Test 데이터 준비
   b. 표준화
   c. 모델 학습
   d. 예측 (다음 해)
   e. Gap 계산
3. 모든 결과 합쳐서 저장

출력 파일:
- data_cache/step4_predictions.csv
\"\"\"
```

---

### 6. backtesting/ - 백테스팅

#### [NEW] [universe_filter.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/backtesting/universe_filter.py)

**파일 개요:**
```python
\"\"\"
===========================================
동적 유니버스 필터링
===========================================

정의된 클래스:
- UniverseFilter

주요 메소드:
1. filter_by_sector(tickers, sector_map) → List[str]
   - Financial, Utilities 제외
   
2. filter_by_price(tickers, price_df, rebalance_date) → List[str]
   - $5 룰 적용
   - 리밸런스 시점 기준 최근 12개월 Close 가격
   - 12개월 중 80% 이상이 $5 이하면 제외
   
3. filter_by_data_availability(tickers, features_df, rebalance_date) → List[str]
   - 필수 데이터 존재 여부 확인
   - m1, m2, m3, y 모두 non-NaN
   
4. apply_all_filters(tickers, ...) → List[str]
   - 모든 필터 순차 적용
   - 최종 투자 가능 유니버스 반환

설계 철학:
- 전역 필터 없음 (동적 유니버스)
- 각 리밸런스 시점마다 독립적으로 판단
- 상장/상폐 기업도 데이터 있으면 참여 가능
\"\"\"
```

---

#### [NEW] [portfolio.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/backtesting/portfolio.py)

**파일 개요:**
```python
\"\"\"
===========================================
포트폴리오 구성 및 수익률 계산
===========================================

정의된 클래스:
- Portfolio

주요 메소드:
1. select_top_gap(predictions_df, universe, long_ratio) → List[str]
   - Gap 기준 상위 N% 종목 선정
   - long_ratio: 0.05, 0.10, 0.20, 0.30 중 하나
   - 예: long_ratio=0.20 → 상위 20% 롱
   
2. calculate_12m_return(ticker, price_df, start_date, end_date) → float
   - 12개월 홀딩 수익률
   - 공식: (AdjClose_t+12 / AdjClose_t) - 1
   
3. calculate_portfolio_return(portfolio_tickers, price_df, start_date) → float
   - 동일가중 포트폴리오 수익률
   - 각 종목 12개월 수익률의 평균
   
4. rebalance_and_hold(predictions_df, universe, price_df, rebalance_date, long_ratio) → Dict
   - 한 번의 리밸런싱 실행
   - 반환: {'date': ..., 'portfolio': [...], 'return': ...}

사용 예시:
portfolio = Portfolio()
result = portfolio.rebalance_and_hold(
    predictions_df, 
    universe, 
    price_df, 
    rebalance_date='2015-12-31',
    long_ratio=0.20  # 상위 20%
)
\"\"\"
```

---

#### [NEW] [step5_backtest.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/backtesting/step5_backtest.py)

**파일 개요:**
```python
\"\"\"
===========================================
Step5: 백테스트 실행 (4가지 롱 비율 비교)
===========================================

정의된 클래스:
- Backtester

주요 메소드:
1. generate_rebalance_dates(start_year, end_year) → List[str]
   - 매년 12월 월말 생성
   - 예: ['2015-12-31', '2016-12-31', ...]
   
2. run_backtest_single_ratio(predictions_df, price_df, long_ratio) → DataFrame
   - 하나의 롱 비율에 대해 백테스트 실행
   - 각 리밸런스 날짜마다:
     a. 유니버스 필터링
     b. Gap 상위 N% 롱 포트폴리오 구성
     c. 12개월 홀딩 수익률 계산
   - 반환: (Date, LongRatio, Return, NumStocks)
   
3. run_all_backtests(predictions_df, price_df) → Dict[float, DataFrame]
   - 4가지 롱 비율 (5%, 10%, 20%, 30%) 모두 실행
   - 반환: {0.05: df_5pct, 0.10: df_10pct, ...}
   
4. calculate_benchmark(price_df, spy_ticker='SPY') → DataFrame
   - S&P500 벤치마크 수익률 계산
   
5. save_results(results_dict)
   - 4개 파일 저장
   - data_cache/step5_backtest_results_5pct.csv
   - data_cache/step5_backtest_results_10pct.csv
   - data_cache/step5_backtest_results_20pct.csv
   - data_cache/step5_backtest_results_30pct.csv

전체 흐름:
1. 리밸런스 날짜 생성 (2015-12-31부터)
2. 4가지 롱 비율에 대해 각각:
   - 각 리밸런스 시점마다:
     a. 유니버스 필터링
     b. 포트폴리오 구성
     c. 수익률 계산
3. 벤치마크 계산
4. 결과 저장

출력 파일:
- data_cache/step5_backtest_results_Xpct.csv (X=5,10,20,30)
\"\"\"
```

---

### 7. evaluation/ - 평가 및 시각화

#### [NEW] [metrics.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/evaluation/metrics.py)

**파일 개요:**
```python
\"\"\"
===========================================
성과 지표 계산
===========================================

주요 함수:
1. calculate_cagr(returns, years) → float
   - 연평균 성장률
   - 공식: (최종값 / 초기값)^(1/년수) - 1
   
2. calculate_sharpe(returns, risk_free_rate=0.02) → float
   - 샤프 비율
   - 공식: (평균 수익률 - 무위험 수익률) / 표준편차
   
3. calculate_mdd(cumulative_returns) → float
   - 최대 낙폭 (Maximum Drawdown)
   - 공식: max((peak - trough) / peak)
   
4. calculate_alpha(portfolio_returns, benchmark_returns) → float
   - 초과 수익 (연평균)
   - 공식: CAGR(포트폴리오) - CAGR(벤치마크)
   
5. calculate_all_metrics(backtest_df, benchmark_df) → Dict
   - 모든 지표를 딕셔너리로 반환
   - {'CAGR': ..., 'Sharpe': ..., 'MDD': ..., 'Alpha': ...}

사용 예시:
metrics = calculate_all_metrics(backtest_results, spy_returns)
print(f\"CAGR: {metrics['CAGR']:.2%}\")
print(f\"Sharpe: {metrics['Sharpe']:.2f}\")
\"\"\"
```

---

#### [NEW] [visualizer.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/evaluation/visualizer.py)

**파일 개요:**
```python
\"\"\"
===========================================
결과 시각화 및 리포트 생성
===========================================

주요 함수:
1. plot_cumulative_returns(results_dict, benchmark_df) → Figure
   - 4가지 롱 비율 + 벤치마크 누적 수익률 차트
   - 한 개 그래프에 5개 라인
   
2. plot_annual_returns_comparison(results_dict) → Figure
   - 4가지 롱 비율 연간 수익률 바 차트 비교
   - 서브플롯 4개
   
3. plot_gap_distribution(predictions_df) → Figure
   - Gap 분포 히스토그램
   - 롱 기준선 표시 (상위 5%, 10%, 20%, 30%)
   
4. plot_metrics_table(metrics_dict) → Figure
   - 4가지 롱 비율 성과 지표 테이블
   - CAGR, Sharpe, MDD, Alpha 비교
   
5. generate_report(results_dict, benchmark_df, predictions_df, output_path)
   - 종합 리포트 생성 (PDF 또는 HTML)
   - 모든 차트 + 지표 테이블 포함

전체 흐름:
1. 백테스트 결과 로드
2. 4가지 차트 생성
3. 성과 지표 계산 및 테이블 생성
4. PDF/HTML 리포트로 저장

출력 파일:
- reports/m_model_backtest_report.pdf
\"\"\"
```

---

### 8. main.py - 통합 실행

#### [NEW] [main.py](file:///Users/kilminkyu/Desktop/DB%20공모전/안티그래비티%20-%20개발/main.py)

**파일 개요:**
```python
\"\"\"
===========================================
M-Model 전체 파이프라인 실행
===========================================

주요 함수:
- main()

전체 워크플로우:
1. 로거 초기화
2. Step1: 가격 데이터 수집
   - PriceCollector 실행
   - 캐시 확인 (있으면 스킵)
3. Step2: 재무 데이터 수집
   - FundamentalCollector 실행 (edgartools 우선)
   - 캐시 확인
4. Step3: Feature Engineering
   - FeatureBuilder 실행
   - m1, m2, m3, y 계산
5. Step4: 모델 학습 및 예측
   - RollingTrainer 실행
   - Gap 계산
6. Step5: 백테스트 (4가지 롱 비율)
   - Backtester 실행
   - 5%, 10%, 20%, 30% 동시 실행
7. 평가 및 리포트 생성
   - 성과 지표 계산
   - 시각화 차트 생성
   - PDF 리포트 저장

실행 방법:
python main.py

옵션:
--skip-step1: Step1 스킵 (캐시 사용)
--skip-step2: Step2 스킵
--long-ratios: 롱 비율 커스텀 (예: 0.05,0.15,0.25)
\"\"\"
```

---

## 🔍 검증 계획

### Step1 검증
1. 월말 가격 데이터 정합성
   - resample 결과 확인 (ME/M 자동 선택)
   - 결측치 비율 < 10%
2. 섹터 필터링 정확성
   - Financial, Utilities 완전 제거 확인

### Step2 검증
1. edgartools 데이터 가용성
   - 2010년 이후 커버리지 확인
   - Revenue, OI, RD, SGA, Equity 추출 성공률
2. 대체 데이터 소스 연동 가능 여부

### Step3 검증
1. m1 데이터 보존율
   - 기존 방식 vs 클리핑 방식 비교
   - OI≈0 종목 개수 확인
2. 피처 결측치 비율
   - 전체 < 30%
   - m1 결측 < 10% (클리핑 적용 후)

### Step4 검증
1. Train/Test 분할 정확성
2. Loss 수렴 패턴
3. Gap 분포 합리성 (평균≈0, 표준편차 적절)

### Step5 검증
1. 4가지 롱 비율 결과 일관성
   - 일반적으로 롱 비율 작을수록 수익률 높음 (집중도)
2. 수익률 계산 정확성 (수동 검산)
3. 벤치마크 대비 성과
   - Sharpe > 0.5 기대
   - MDD < 50% 기대

---

## 🚀 개발 순서

### Week 1: 기본 설정 및 Step1-2
1. ✅ Phase 1: 프로젝트 구조 및 설정 (완료)
2. Phase 2: config, utils 모듈 구현
3. Phase 3: Step1 구현 및 테스트
4. Phase 4: edgartools 평가 및 Step2 구현

### Week 2: Feature Engineering 및 모델링
5. Phase 5: Step3 구현 (m1 클리핑 로직 포함)
6. Phase 6: Step4 구현 (PyTorch 모델)

### Week 3: 백테스트 및 평가
7. Phase 7: Step5 구현 (4가지 롱 비율)
8. Phase 8: 평가 및 시각화
9. Phase 9: 통합 테스트 및 최적화

---

## ⚠️ 절대 실수 방지 체크리스트

- ✅ **Gap 정의:** Gap = yhat - y (클수록 저평가)
- ✅ **m1 방어:** 클리핑 방식 (denominator = max(abs(OI), 1e-6), clip [-5, +5])
- ✅ **BookValue:** ≤ 0 → y 결측 처리 (로그 불가)
- ✅ **$5 룰:** 동적 필터링 (리밸런스 시점 기준 최근 12개월)
- ✅ **Pandas resample:** ME (2.2.0+) 또는 M (구버전)
- ✅ **백테스트:** 4가지 롱 비율 (5%, 10%, 20%, 30%) 동시 실행

---

> [!NOTE]
> 이 구현 계획서는 프로젝트 진행에 따라 지속적으로 업데이트됩니다.
> 마지막 업데이트: 2026-01-28 v1.1
