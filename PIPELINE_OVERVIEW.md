# 📊 M-Model 전체 파이프라인 개요

> 이 문서는 프로젝트의 전체 데이터 흐름과 각 Step별 입출력 파일, 주요 함수를 설명합니다.

---

## 🗂️ 목차

1. [전체 데이터 흐름도](#-전체-데이터-흐름도)
2. [Config 설정](#️-config-설정)
3. [Step 1: 가격 데이터 수집](#-step-1-가격-데이터-수집)
4. [Step 2: 재무 데이터 수집](#-step-2-재무-데이터-수집)
5. [Step 3: Feature Engineering](#-step-3-feature-engineering)
6. [Step 4: 모델 학습 및 예측](#-step-4-모델-학습-및-예측)
7. [Step 5: 백테스트](#-step-5-백테스트)
8. [파일 의존성 매트릭스](#-파일-의존성-매트릭스)

---

## 🔄 전체 데이터 흐름도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              STEP 1: 가격 데이터 수집                         │
│  📁 data_collection/step1_price_collector.py                                 │
│  ─────────────────────────────────────────────────────────────────────────── │
│  입력: Wikipedia S&P500 / us_market_tickers.txt                              │
│  처리: yfinance 가격 다운로드 → 섹터 필터링 → 월말 리샘플링                     │
│  출력: ┌─ step1_px_adj_m.csv   (월말 조정종가)                                │
│        ├─ step1_px_close_m.csv (월말 종가)                                   │
│        └─ step1_meta.json      (티커 메타정보)                                │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
┌─────────────────────────────────┐  ┌────────────────────────────────────────┐
│      STEP 2: 재무 데이터 수집     │  │                                        │
│  📁 data_collection/             │  │                                        │
│     step2_fundamental_collector  │  │                                        │
│  ───────────────────────────────│  │                                        │
│  입력: step1_meta.json          │  │                                        │
│       (티커 리스트)              │  │                                        │
│  처리: SEC EDGAR API 호출        │  │                                        │
│       → 연간 재무제표 파싱        │  │                                        │
│  출력: step2_fund_annual.csv    │  │                                        │
└────────────────┬────────────────┘  │                                        │
                 │                    │                                        │
                 ▼                    │                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STEP 3: Feature Engineering                         │
│  📁 feature_engineering/step3_feature_builder.py                             │
│  ─────────────────────────────────────────────────────────────────────────── │
│  입력: step2_fund_annual.csv + step1_px_close_m.csv                          │
│  처리: 회계 재작성(I, A, AdjOI) → m1, m2, m3, y 피처 계산                      │
│  출력: step3_features_annual.csv                                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STEP 4: 모델 학습 및 예측                             │
│  📁 modeling/step4_train_predict.py                                          │
│  ─────────────────────────────────────────────────────────────────────────── │
│  입력: step3_features_annual.csv                                             │
│  처리: Rolling window 학습 → 예측 → Gap(yhat - y) 계산                        │
│  출력: ┌─ step4_predictions.csv     (예측값 + Gap)                            │
│        └─ step4_weights_history.csv (모델 가중치 이력)                        │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            STEP 5: 백테스트                                   │
│  📁 backtesting/step5_backtest.py                                            │
│  ─────────────────────────────────────────────────────────────────────────── │
│  입력: step4_predictions.csv + step1_px_close_m.csv + step3 (MarketCap)      │
│  처리: Gap 정렬 → $5 룰 필터링 → 상위 N% 선택 → 수익률 계산                    │
│  출력: ┌─ step5_backtest_returns.csv  (연도별 수익률)                         │
│        ├─ step5_backtest_metrics.csv  (CAGR, Sharpe, MDD 등)                 │
│        └─ step5_performance_plot.png  (성과 그래프)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Config 설정

### 📁 `config/paths.py` - 경로 상수

| 상수명 | 값 | 설명 |
|--------|-----|------|
| `PROJECT_ROOT` | 프로젝트 루트 | 기준 디렉토리 |
| `DATA_CACHE_DIR` | `data_cache/` | 캐시 데이터 저장 |
| `LOG_DIR` | `logs/` | 로그 파일 저장 |
| `REPORTS_DIR` | `reports/` | 리포트 저장 |

**Step별 출력 파일 경로:**

| Step | 파일명 | 전체 경로 |
|------|--------|----------|
| 0 | `step0_valid_universe.json` | `data_cache/step0_valid_universe.json` |
| 1 | `step1_px_adj_m.csv` | `data_cache/step1_px_adj_m.csv` |
| 1 | `step1_px_close_m.csv` | `data_cache/step1_px_close_m.csv` |
| 1 | `step1_meta.json` | `data_cache/step1_meta.json` |
| 2 | `step2_fund_annual.csv` | `data_cache/step2_fund_annual.csv` |
| 2 | `step2_lost_tickers.csv` | `data_cache/step2_lost_tickers.csv` |
| 3 | `step3_features_annual.csv` | `data_cache/step3_features_annual.csv` |
| 3.5 | `final_universe_report.xlsx` | `reports/final_universe_report.xlsx` |
| 4 | `step4_predictions.csv` | `data_cache/step4_predictions.csv` |
| 4 | `step4_weights_history.csv` | `data_cache/step4_weights_history.csv` |
| 5 | `step5_backtest_returns.csv` | `data_cache/step5_backtest_returns.csv` |
| 5 | `step5_backtest_metrics.csv` | `data_cache/step5_backtest_metrics.csv` |
| 5.5 | `backtest_portfolio_history.xlsx` | `reports/backtest_portfolio_history.xlsx` |

### 📁 `config/constants.py` - 주요 상수

| 상수 | 값 | 설명 |
|-----|-----|------|
| `TEST_MODE` | `False` | 테스트 모드 (17개 티커) |
| `UNIVERSE_MODE` | `'FULL'` | `'SP500'` 또는 `'FULL'` (8,410개) |
| `BATCH_SIZE` | `100` | 배치 처리 크기 |
| `START_YEAR` | `2012` | 데이터 수집 시작 연도 |
| `BACKTEST_START_YEAR` | `2015` | 백테스트 시작 연도 |
| `EXCLUDE_SECTORS` | `['Financials', 'Utilities', 'Energy', 'Materials', 'Real Estate', 'Unknown']` | 제외 섹터 |
| `SGA_CAPITALIZATION_RATE` | `0.3` | SG&A 자산화 비율 (30%) |
| `INTANGIBLE_AMORTIZATION_YEARS` | `3` | 무형자산 상각 기간 |
| `TRAIN_WINDOW_YEARS` | `3` | Rolling window 학습 기간 |
| `LONG_PERCENTILES` | `[0.05, 0.10, 0.20, 0.30]` | 롱 포트폴리오 비율 |
| `HOLDING_PERIOD_MONTHS` | `12` | 홀딩 기간 (개월) |
| `REBALANCE_MONTH` | `12` | 리밸런싱 월 |

---

## 📥 Step 1: 가격 데이터 수집

### 기본 정보

| 항목 | 내용 |
|-----|------|
| **실행 파일** | `data_collection/step1_price_collector.py` |
| **대용량 처리** | `data_collection/step1_price_collector_sequential.py` |
| **로그 위치** | `logs/m_model.log` |

### 입력 → 출력

```
┌─────────────────────────────┐      ┌────────────────────────────────┐
│         📥 입력              │      │           📤 출력               │
├─────────────────────────────┤      ├────────────────────────────────┤
│ • Wikipedia S&P500 리스트    │  →   │ • step1_px_adj_m.csv (조정종가) │
│ • us_market_tickers.txt     │      │ • step1_px_close_m.csv (종가)   │
│   (FULL 모드시)              │      │ • step1_meta.json (메타정보)    │
└─────────────────────────────┘      └────────────────────────────────┘
```

### 처리 흐름

1. **티커 수집** - Wikipedia에서 S&P500 목록 또는 파일에서 전체 티커 로드
2. **섹터 정보 수집** - yfinance로 각 티커의 GICS 섹터 조회
3. **섹터 필터링** - Financials, Utilities, Energy, Materials, Real Estate 제외
4. **가격 다운로드** - yfinance로 2012년 이후 일별 가격 데이터
5. **월말 리샘플링** - 일별 → 월말 데이터로 변환
6. **캐시 저장** - CSV/JSON 형식으로 저장

<details>
<summary><b>🔧 주요 클래스 및 메소드 (클릭하여 펼치기)</b></summary>

#### 클래스: `PriceCollector`

| 메소드 | 기능 | 반환값 |
|--------|------|--------|
| `__init__()` | 초기화, 로거 설정 | - |
| `get_tickers()` | S&P500 또는 전체 티커 목록 수집 | `List[str]` |
| `get_sector_info(tickers)` | yfinance로 티커별 섹터 정보 조회 | `Dict[str, str]` |
| `filter_by_sector(tickers, sectors)` | 제외 섹터에 해당하는 티커 필터링 | `List[str]` |
| `download_prices(tickers)` | yfinance로 일별 가격 다운로드 | `pd.DataFrame` |
| `resample_to_monthly(df)` | 일별 → 월말 데이터 리샘플링 | `pd.DataFrame` |
| `save_cache(px_adj, px_close, meta)` | CSV/JSON 파일로 저장 | - |
| `run()` | **전체 파이프라인 실행** | `Dict` |

#### 클래스: `SequentialPriceCollector` (대용량용)

| 메소드 | 기능 | 반환값 |
|--------|------|--------|
| `process_batch(tickers, batch_num)` | 배치 단위 처리 (100개) | `pd.DataFrame` |
| `save_checkpoint(df, batch_num)` | 체크포인트 저장 (`checkpoints/batch_*.csv`) | - |
| `load_checkpoints()` | 기존 체크포인트 로드 (중단 후 재시작) | `pd.DataFrame` |
| `merge_and_save()` | 모든 체크포인트 병합 후 최종 저장 | - |

</details>

### 출력 파일 구조

**`step1_px_adj_m.csv`** - 월말 조정종가
```
Date,AAPL,MSFT,GOOGL,...
2012-01-31,14.32,25.67,302.12,...
2012-02-29,15.01,26.34,308.45,...
```

**`step1_meta.json`** - 메타 정보
```json
{
  "tickers": ["AAPL", "MSFT", ...],
  "sectors": {"AAPL": "Technology", "MSFT": "Technology", ...},
  "collected_at": "2026-01-28T14:00:00"
}
```

---

## 📊 Step 2: 재무 데이터 수집

### 기본 정보

| 항목 | 내용 |
|-----|------|
| **실행 파일** | `data_collection/step2_fundamental_collector.py` |
| **로그 위치** | `logs/m_model.log` |
| **캐시 디렉토리** | `data_cache/sec_companyfacts/` |

### 입력 → 출력

```
┌─────────────────────────────┐      ┌────────────────────────────────┐
│         📥 입력              │      │           📤 출력               │
├─────────────────────────────┤      ├────────────────────────────────┤
│ • step1_meta.json           │  →   │ • step2_fund_annual.csv        │
│   (티커 리스트)              │      │   (연간 재무제표)               │
└─────────────────────────────┘      └────────────────────────────────┘
```

### 처리 흐름

1. **티커→CIK 매핑** - SEC의 company_tickers.json으로 CIK 번호 조회
2. **SEC API 호출** - `data.sec.gov/api/xbrl/companyfacts/` 엔드포인트
3. **연간 데이터 필터링** - 10-K (연간 보고서) 데이터만 추출
4. **재무제표 파싱** - Revenue, OI, NetIncome, R&D, SG&A, Equity 추출
5. **섹터 정보 추가** - yfinance로 GICS 섹터 조회
6. **저장** - 전체 데이터 CSV로 저장

<details>
<summary><b>🔧 주요 클래스 및 메소드 (클릭하여 펼치기)</b></summary>

#### 클래스: `FundamentalCollector`

| 메소드 | 기능 | 반환값 |
|--------|------|--------|
| `__init__()` | 초기화, SEC 티커→CIK 매핑 로드 | - |
| `load_cik_mapping()` | SEC company_tickers.json 파싱 | `Dict[str, str]` |
| `fetch_company_facts(cik)` | SEC EDGAR API 호출 (0.15초 rate limit) | `Dict` |
| `extract_annual_data(facts)` | 10-K 연간 데이터만 필터링 | `List[Dict]` |
| `parse_financials(ticker, data)` | 재무제표 항목 파싱 | `pd.DataFrame` |
| `get_sector_info(tickers)` | yfinance로 섹터 정보 일괄 조회 | `Dict[str, str]` |
| `run()` | **전체 파이프라인 실행** | `pd.DataFrame` |

#### SEC XBRL 태그 매핑

| 재무 항목 | XBRL 태그 (우선순위) |
|----------|---------------------|
| Revenue | `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet` |
| OI (영업이익) | `OperatingIncomeLoss` |
| NetIncome | `NetIncomeLoss` |
| R&D | `ResearchAndDevelopmentExpense` |
| SG&A | `SellingGeneralAndAdministrativeExpense` |
| Equity | `StockholdersEquity`, `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` |
| Shares | `CommonStockSharesOutstanding`, `WeightedAverageNumberOfSharesOutstandingBasic` |

</details>

### 출력 파일 구조

**`step2_fund_annual.csv`**
```csv
Ticker,FiscalYear,EndDate,Revenue,OI,NetIncome,RD,SGA,Equity,Shares,Sector
AAPL,2012,2012-09-29,156508000000,55241000000,41733000000,3381000000,10040000000,118210000000,26469000000,Technology
AAPL,2013,2013-09-28,170910000000,48999000000,37037000000,4475000000,10830000000,123549000000,26086000000,Technology
```

| 컬럼 | 설명 |
|-----|------|
| `Ticker` | 티커 심볼 |
| `FiscalYear` | 회계연도 |
| `EndDate` | 회계연도 종료일 |
| `Revenue` | 매출액 |
| `OI` | 영업이익 |
| `NetIncome` | 순이익 |
| `RD` | R&D 비용 |
| `SGA` | 판관비 |
| `Equity` | 자본총계 |
| `Shares` | 발행주식수 |
| `Sector` | GICS 섹터 |

---

## 🔬 Step 3: Feature Engineering

### 기본 정보

| 항목 | 내용 |
|-----|------|
| **실행 파일** | `feature_engineering/step3_feature_builder.py` |
| **로그 위치** | `logs/m_model.log` |

### 입력 → 출력

```
┌─────────────────────────────┐      ┌────────────────────────────────┐
│         📥 입력              │      │           📤 출력               │
├─────────────────────────────┤      ├────────────────────────────────┤
│ • step2_fund_annual.csv     │  →   │ • step3_features_annual.csv    │
│   (재무제표)                 │      │   (m1, m2, m3, y 피처)         │
│ • step1_px_close_m.csv      │      │                                │
│   (주가 - MarketCap 계산용)  │      │                                │
└─────────────────────────────┘      └────────────────────────────────┘
```

### 핵심 피처 정의

| 피처 | 수식 | 의미 | 클리핑 범위 |
|-----|------|------|-----------|
| **m1** | `AdjOI / max(\|OI\|, ε)` | 이익 복원력 | [-5, +5] |
| **m2** | `I_t / Avg(I_{t-1}, I_{t-2})` | 투자 가속도 | [0, 10] |
| **m3** | `AdjOI / Equity` | 본업 기초체력 (ROE 유사) | [-5, +5] |
| **y** | `ln(PBR) = ln(MarketCap / Equity)` | 타겟 변수 | PBR: [0.01, 100] |

### 회계 재작성 (Restatement) 로직

```
I (투자)      = RD + (SGA × 0.3)           ← SG&A의 30%를 무형자산 투자로 간주
A (상각)      = (I_{t-1} + I_{t-2} + I_{t-3}) / 3   ← 3년 정액 상각
AdjOI (조정OI) = OI + I - A               ← 투자 효과 반영한 영업이익
```

### 처리 흐름

1. **데이터 로드** - Step2 재무데이터 + Step1 가격데이터
2. **섹터 필터링** - Financials, Utilities 등 제외
3. **데이터 정제** - SG&A/Revenue NaN 제거, R&D fillna(0)
4. **회계 재작성** - I, A, AdjOI 계산
5. **MarketCap 계산** - 3개월 래그된 주가 × 발행주식수
6. **피처 계산** - m1, m2, m3, y 산출
7. **클리핑** - 이상치 제한
8. **저장**

<details>
<summary><b>🔧 주요 클래스 및 메소드 (클릭하여 펼치기)</b></summary>

#### 클래스: `FeatureBuilder`

| 메소드 | 기능 | 반환값 |
|--------|------|--------|
| `__init__()` | 초기화, 상수 로드 | - |
| `load_data()` | Step1/Step2 데이터 로드 | `Tuple[pd.DataFrame, pd.DataFrame]` |
| `filter_sectors(df)` | 제외 섹터 필터링 | `pd.DataFrame` |
| `calculate_investment(df)` | I = RD + SGA×0.3 계산 | `pd.Series` |
| `calculate_amortization(df)` | A = 3년 정액상각 계산 | `pd.Series` |
| `calculate_adj_oi(df)` | AdjOI = OI + I - A 계산 | `pd.Series` |
| `get_lagged_price(ticker, year)` | 3개월 래그 주가 조회 | `float` |
| `calculate_market_cap(df)` | MarketCap = Price × Shares | `pd.Series` |
| `calculate_m1(df)` | 이익 복원력 피처 | `pd.Series` |
| `calculate_m2(df)` | 투자 가속도 피처 | `pd.Series` |
| `calculate_m3(df)` | 본업 기초체력 피처 | `pd.Series` |
| `calculate_y(df)` | ln(PBR) 타겟 계산 | `pd.Series` |
| `clip_features(df)` | 이상치 클리핑 | `pd.DataFrame` |
| `run()` | **전체 파이프라인 실행** | `pd.DataFrame` |

#### 헬퍼 함수

| 함수 | 기능 |
|-----|------|
| `safe_divide(a, b, default=0)` | 0으로 나누기 방지 |
| `get_fiscal_year_end_month(ticker, year)` | 회계연도 종료월 조회 |

</details>

### 출력 파일 구조

**`step3_features_annual.csv`**
```csv
Ticker,FiscalYear,m1,m2,m3,y,Sector,Investment,Amortization,AdjOI,OI,Equity,Shares,Price,MarketCap
AAPL,2015,1.23,1.45,0.89,2.34,Technology,15000000000,12000000000,58000000000,55000000000,120000000000,5500000000,105.2,578600000000
```

| 컬럼 | 설명 |
|-----|------|
| `m1` | 이익 복원력 (AdjOI / \|OI\|) |
| `m2` | 투자 가속도 (I_t / Avg) |
| `m3` | 본업 기초체력 (AdjOI / Equity) |
| `y` | ln(PBR) 타겟 변수 |
| `Investment` | 투자액 (I) |
| `Amortization` | 상각액 (A) |
| `AdjOI` | 조정 영업이익 |
| `MarketCap` | 시가총액 |

---

## 📋 Step 3.5: 유니버스 리포트

### 기본 정보

| 항목 | 내용 |
|-----|------|
| **실행** | Step 3 완료 후 자동 실행 |
| **출력 파일** | `reports/final_universe_report.xlsx` |

### 리포트 구성

| 시트 | 내용 |
|------|------|
| **Summary** | 전체 통계 (총 티커 수, Ready/Insufficient 비율) |
| **Sector_Summary** | 섹터별 Ready 비율 및 분포 |
| **Ticker_Details** | 티커별 데이터 연도 범위 및 상태 |
| **Missing_Years_Detail** | 기업별 m1/m2/m3/y 누락 연도 목록 |

### 실행 결과 예시 (FULL 모드)

```
피처 데이터 로드: 22,376행
✅ 유니버스 리포트 저장 완료
- 총 티커: 2,516개
- Ready: 2,042개 (81.2%)
- Insufficient: 474개

섹터별 Ready 비율:
- Industrials: 86.1%
- Consumer Staples: 84.0%
- Technology: 83.2%
- Consumer Discretionary: 82.5%
- Healthcare: 76.9%
- Communication: 75.2%
```

---

## 🤖 Step 4: 모델 학습 및 예측

### 기본 정보

| 항목 | 내용 |
|-----|------|
| **실행 파일** | `modeling/step4_train_predict.py` |
| **모델 정의** | `modeling/model.py` (PyTorch LinearPBRModel) |
| **로그 위치** | `logs/m_model.log` |

### 입력 → 출력

```
┌─────────────────────────────┐      ┌────────────────────────────────┐
│         📥 입력              │      │           📤 출력               │
├─────────────────────────────┤      ├────────────────────────────────┤
│ • step3_features_annual.csv │  →   │ • step4_predictions.csv        │
│   (m1, m2, m3, y 피처)       │      │   (예측값 + Gap)               │
│                             │      │ • step4_weights_history.csv    │
│                             │      │   (모델 가중치 이력)            │
└─────────────────────────────┘      └────────────────────────────────┘
```

### Rolling Window 학습 방식

```
            ┌─────────────────────────────────────────────────────────┐
            │  2014  2015  2016  2017  2018  2019  2020  2021  2022  2023  2024  2025 │
            └─────────────────────────────────────────────────────────┘
Window 1:   [Train─────]  Test
            │ 2014-2016 │  2017

Window 2:         [Train─────]  Test
                  │ 2015-2017 │  2018

Window 3:               [Train─────]  Test
                        │ 2016-2018 │  2019
            ...
Window 9:                                       [Train─────]  Test
                                                │ 2022-2024 │  2025
```

- **Train Window**: 3년 (과거 데이터)
- **Test**: 1년 (다음 해 예측)
- **매년 1년씩 슬라이딩**
- **실제 실행**: FY2017 ~ FY2025 (9년간)

### 모델 구조

```
입력: [m1, m2, m3] (3차원)
       ↓
   Linear Layer
       ↓
출력: ŷ (예측 ln(PBR))

손실함수: MSE Loss
옵티마이저: Adam (lr=0.01)
Epochs: 100
```

### Gap 계산

```
Gap = ŷ - y = 예측값 - 실제값

Gap > 0  →  과소평가 (저평가) → 매수 후보
Gap < 0  →  과대평가 (고평가) → 회피
```

<details>
<summary><b>🔧 주요 클래스 및 메소드 (클릭하여 펼치기)</b></summary>

#### 클래스: `MModel` (modeling/model.py)

| 메소드 | 기능 | 반환값 |
|--------|------|--------|
| `__init__(input_dim)` | PyTorch 선형 모델 초기화 | - |
| `forward(x)` | 순전파 | `Tensor` |
| `get_weights()` | 학습된 가중치 조회 | `Dict[str, float]` |

#### 클래스: `ModelTrainer` (step4_train_predict.py)

| 메소드 | 기능 | 반환값 |
|--------|------|--------|
| `__init__()` | 초기화, 상수 로드 | - |
| `load_features()` | Step3 피처 데이터 로드 | `pd.DataFrame` |
| `convert_to_sector_relative(df)` | y → (y - Sector_Median) 변환 | `pd.DataFrame` |
| `prepare_train_test(df, train_years, test_year)` | 학습/테스트 데이터 분리 | `Tuple[X_train, y_train, X_test, y_test]` |
| `standardize(X_train, X_test)` | Z-score 표준화 | `Tuple[X_train_scaled, X_test_scaled, scaler]` |
| `train_model(X, y, epochs=100)` | PyTorch 모델 학습 | `MModel` |
| `predict(model, X)` | 예측 수행 | `np.array` |
| `calculate_gap(y_pred, y_actual)` | Gap = yhat - y 계산 | `np.array` |
| `rolling_window_train()` | **전체 Rolling window 파이프라인** | `Tuple[predictions_df, weights_df]` |
| `run()` | 메인 실행 함수 | - |

</details>

### 출력 파일 구조

**`step4_predictions.csv`**
```csv
Ticker,FiscalYear,y,yhat,Gap
AAPL,2015,2.34,2.56,0.22
MSFT,2015,2.12,2.45,0.33
GOOGL,2015,2.89,2.67,-0.22
```

| 컬럼 | 설명 |
|-----|------|
| `y` | 실제 ln(PBR) (섹터 상대값) |
| `yhat` | 예측 ln(PBR) |
| `Gap` | yhat - y (양수 = 저평가) |

**`step4_weights_history.csv`**
```csv
FiscalYear,w_m1,w_m2,w_m3,bias,train_samples
2015,0.45,0.23,0.32,-0.12,450
2016,0.42,0.25,0.33,-0.10,520
```

### 🔀 RankNet 버전 (v2.5.0 추가)

> ⚠️ **실험적 구현** - MSE와 별도로 RankNet 손실함수 사용

| 항목 | MSE 버전 | RankNet 버전 |
|------|----------|--------------|
| **실행 파일** | `step4_train_predict.py` | `step4_train_predict_ranknet.py` |
| **모델 파일** | `model.py` | `model_ranknet.py` |
| **손실 함수** | MSE | RankNet (Pairwise Ranking) |
| **배치 방식** | Random shuffle | **Cross-sectional (동일 연도만)** |
| **평가 지표** | R² | Rank IC, NDCG |
| **Learning Rate** | 0.01 | 0.005 |
| **Epochs** | 100 | 300 |

**RankNet 출력 파일:**
- `step4_predictions_ranknet.csv`
- `step4_weights_history_ranknet.csv`
- `step4_metrics_ranknet.csv`

#### ⚠️ 검증 결과 주의사항

| 피처 | y(ln PBR)와의 상관계수 |
|------|----------------------|
| m1 | 0.03 (거의 없음) |
| m2 | 0.06 (거의 없음) |
| **m3** | **0.55** (높음) |

**Rank IC가 0.60으로 높게 나오는 이유:**
- m3 = AdjOI / Equity ≈ ROE
- y = ln(PBR)
- **PBR ∝ ROE는 효율적 시장에서 당연한 관계**
- 모델이 "시장이 이미 아는 것"을 예측

**진정한 알파 발굴 시 개선 필요:**
1. m3 제외하고 m1+m2만 사용
2. y를 미스프라이싱으로 재정의

---

## 📈 Step 5: 백테스트

### 기본 정보

| 항목 | 내용 |
|-----|------|
| **실행 파일** | `backtesting/step5_backtest.py` |
| **지표 계산** | `backtesting/metrics.py` |
| **로그 위치** | `logs/m_model.log` |

### 입력 → 출력

```
┌─────────────────────────────┐      ┌────────────────────────────────┐
│         📥 입력              │      │           📤 출력               │
├─────────────────────────────┤      ├────────────────────────────────┤
│ • step4_predictions.csv     │  →   │ • step5_backtest_returns.csv   │
│   (Gap 값)                   │      │   (연도별 수익률)               │
│ • step1_px_close_m.csv      │      │ • step5_backtest_metrics.csv   │
│   (수익률 계산용)            │      │   (CAGR, Sharpe, MDD 등)       │
│ • step3_features_annual.csv │      │ • step5_performance_plot.png   │
│   (MarketCap - 소형주 전략)  │      │   (성과 그래프)                 │
└─────────────────────────────┘      └────────────────────────────────┘
```

### 백테스트 전략

| 설정 | 값 |
|-----|-----|
| 리밸런싱 시점 | 매년 12월 말 |
| 홀딩 기간 | 12개월 |
| 종목 선택 | Gap 상위 N% |
| 테스트 비율 | 5%, 10%, 20%, 30% |
| 가중치 방식 | 동일 가중 |
| 벤치마크 | **5개 지수** (하드코딩 Price Return) |

### 벤치마크 데이터 (v2.4.0 업데이트)

> ⚠️ **yfinance 동적 다운로드 방식 폐기** → 하드코딩 Price Return 사용

| 벤치마크 | 특성 | 비교 목적 |
|----------|------|-----------|
| S&P 500 | 대형주 500개 | 기본 벤치마크 |
| Russell 1000 | 대형주 1000개 | 대형주 확장 비교 |
| Russell 2000 | 소형주 2000개 | **소형주 전략 비교** |
| Russell 3000 | 전체 시장 3000개 | 전체 시장 비교 |
| Wilshire 5000 | 미국 전체 시장 | 최광범위 비교 |

```python
# config/constants.py
BENCHMARK_RETURNS = {
    2012: {'S&P500': 0.1341, 'Russell1000': 0.1392, 'Russell2000': 0.1463, ...},
    ...
    2024: {'S&P500': 0.2331, 'Russell1000': 0.2284, 'Russell2000': 0.1002, ...}
}
```

### $5 룰 필터링

```
12개월 중 80% 이상이 $5 이하인 종목 → 제외 (페니스톡 필터링)
```

### 소형주 전략 (추가)

```
시가총액 하위 50% 유니버스에서 Gap 상위 N% 선택
→ 소형주 효과 + 저평가 효과 복합 전략
```

<details>
<summary><b>🔧 주요 클래스 및 메소드 (클릭하여 펼치기)</b></summary>

#### 클래스: `Backtester` (step5_backtest.py)

| 메소드 | 기능 | 반환값 |
|--------|------|--------|
| `__init__()` | 초기화, 상수 로드 | - |
| `load_data()` | Step1/Step3/Step4 데이터 로드 | `Tuple[prices, features, predictions]` |
| `get_benchmark_returns(year)` | **하드코딩 벤치마크 수익률 조회** | `Dict[str, float]` |
| `apply_five_dollar_rule(df, prices)` | $5 룰 필터링 | `pd.DataFrame` |
| `select_top_gap(df, percentile)` | Gap 상위 N% 종목 선택 | `List[str]` |
| `select_small_cap_top_gap(df, percentile)` | 소형주 중 Gap 상위 선택 | `List[str]` |
| `calculate_portfolio_return(tickers, year)` | 동일가중 포트폴리오 수익률 | `float` |
| `calculate_annual_returns(strategy_name)` | 연도별 수익률 계산 | `pd.DataFrame` |
| `run_backtest()` | **전체 백테스트 실행** | `pd.DataFrame` |

> ⚠️ **DEPRECATED**: `download_benchmark()` - yfinance 동적 다운로드 폐기

#### 클래스: `PerformanceMetrics` (metrics.py)

| 메소드 | 기능 | 반환값 |
|--------|------|--------|
| `calculate_cagr(returns)` | 연평균 복합 성장률 | `float` |
| `calculate_sharpe(returns, rf=0.02)` | 샤프 비율 | `float` |
| `calculate_mdd(returns)` | 최대 낙폭 | `float` |
| `calculate_alpha(returns, benchmark)` | 알파 (초과수익) | `float` |
| `calculate_ir(returns, benchmark)` | 정보 비율 | `float` |
| `calculate_win_rate(returns)` | 승률 | `float` |
| `generate_report(returns_df)` | 전체 성과 리포트 생성 | `pd.DataFrame` |

#### 시각화 함수

| 함수 | 기능 |
|-----|------|
| `plot_cumulative_returns(returns_df)` | 누적 수익률 차트 |
| `plot_annual_returns_bar(returns_df)` | 연도별 수익률 바차트 |
| `plot_drawdown(returns_df)` | 낙폭 차트 |

</details>

### 출력 파일 구조

**`step5_backtest_returns.csv`** (v2.4.0 업데이트)
```csv
Year,Gap_5%,Gap_10%,...,S&P500,Russell1000,Russell2000,Russell3000,Wilshire5000,Alpha_vs_SP500,Alpha_vs_R2000
2015,0.1247,0.1536,...,0.0954,0.0970,0.1948,0.1042,0.1067,0.0293,-0.0701
2016,0.2050,0.2326,...,-0.0073,-0.0109,-0.0571,-0.0147,-0.0232,0.2123,0.2621
...
```

**`step5_backtest_metrics.csv`** (v2.4.0 업데이트)
```csv
Portfolio_CAGR,Portfolio_Sharpe,Portfolio_MDD,Alpha,Alpha_vs_S&P500,Alpha_vs_Russell1000,Alpha_vs_Russell2000,Alpha_vs_Russell3000,Alpha_vs_Wilshire5000,Information_Ratio,Long_Ratio
0.1291,0.58,-0.2247,-0.0185,0.0456,0.0412,0.0891,0.0523,0.0489,0.42,Gap_10%
...
...
```

**`reports/backtest_portfolio_history.xlsx`** (Step 5.5)
| 시트 | 내용 |
|------|------|
| Summary | 각 비율별 요약 통계 |
| Top_5pct | 연도별 선택 티커 상세 |
| Top_10pct | 연도별 선택 티커 상세 |
| Top_20pct | 연도별 선택 티커 상세 |
| Top_30pct | 연도별 선택 티커 상세 |

| 지표 | 설명 |
|-----|------|
| `CAGR` | 연평균 복합 성장률 |
| `Sharpe` | 샤프 비율 (위험조정 수익) |
| `MDD` | 최대 낙폭 |
| `Alpha` | 벤치마크 대비 초과수익 |
| `IR` | 정보 비율 |
| `WinRate` | 벤치마크 대비 승률 |

---

## 🔗 파일 의존성 매트릭스

### 입력-출력 의존성

```
                    Step1    Step2    Step3    Step4    Step5
                   ───────  ───────  ───────  ───────  ───────
step1_px_adj_m      [OUT]     -        -        -        -
step1_px_close_m    [OUT]     -       [IN]      -       [IN]
step1_meta.json     [OUT]    [IN]      -        -        -
step2_fund_annual     -      [OUT]    [IN]      -        -
step3_features        -        -      [OUT]    [IN]     [IN]
step4_predictions     -        -        -      [OUT]    [IN]
step4_weights         -        -        -      [OUT]     -
step5_returns         -        -        -        -      [OUT]
step5_metrics         -        -        -        -      [OUT]
```

### 간단 의존성 다이어그램

```
Wikipedia/티커파일
       │
       ▼
    [Step 1] ─────────────────────────────────────────┐
       │                                              │
       │ step1_meta.json                              │ step1_px_close_m.csv
       ▼                                              │
    [Step 2]                                          │
       │                                              │
       │ step2_fund_annual.csv                        │
       ▼                                              │
    [Step 3] ◄────────────────────────────────────────┘
       │
       │ step3_features_annual.csv
       ▼
    [Step 4]
       │
       │ step4_predictions.csv
       ▼
    [Step 5] ◄──── step1_px_close_m.csv (수익률 계산)
       │         ◄──── step3_features_annual.csv (MarketCap)
       ▼
    [Results]
```

---

## 📝 로그 시스템

모든 Step의 로그는 **`logs/m_model.log`** 파일에 통합 저장됩니다.

### 로그 포맷
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s

예시:
2026-01-28 14:00:00 - data_collection.step1 - INFO - Starting price collection...
2026-01-28 14:05:23 - data_collection.step1 - INFO - Downloaded 500 tickers
2026-01-28 14:10:45 - data_collection.step2 - WARNING - CIK not found for TICKER_XYZ
2026-01-28 15:00:00 - modeling.step4 - INFO - Training window 2012-2014, Test year: 2015
```

### 로거 계층 구조

```
m_model (root)
├── data_collection.step1
├── data_collection.step2
├── feature_engineering.step3
├── modeling.step4
└── backtesting.step5
```

---

## 🚀 실행 방법

### 전체 파이프라인 실행

```bash
# Step 0: 유니버스 빌더 (선택적 - 첨 실행 시 필요)
python -m data_collection.step0_universe_filter

# Step 1: 가격 데이터 수집
python -m data_collection.step1_price_collector

# Step 2: 재무 데이터 수집
python -m data_collection.step2_fundamental_collector

# Step 3: Feature Engineering + Step 3.5 리포트
python -m feature_engineering.step3_feature_builder

# Step 4: 모델 학습 및 예측
python -m modeling.step4_train_predict

# Step 5: 백테스트 + Step 5.5 포트폴리오 히스토리
python -m backtesting.step5_backtest
```

### 대용량 데이터 (FULL 모드)

```bash
# 순차 처리 버전 (8,410개 티커)
python -m data_collection.step1_price_collector_sequential
```

### 주요 출력 파일

| 파일 | 설명 |
|------|------|
| `data_cache/step4_weights_history.csv` | 연도별 모델 가중치 |
| `reports/final_universe_report.xlsx` | Step 3.5 유니버스 리포트 |
| `reports/backtest_portfolio_history.xlsx` | Step 5.5 포트폴리오 히스토리 |

---

*문서 생성일: 2026년 1월 29일*  
*마지막 업데이트: 2026년 1월 30일 22:41*
