# M-Model 프로젝트 전체 컨텍스트 문서

> **작성일**: 2026-02-04  
> **목적**: 파일 이동 시 대화 맥락 보존을 위한 전체 프로젝트 정리

---

## 📋 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [핵심 아이디어](#2-핵심-아이디어)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [주요 설정 (config/constants.py)](#4-주요-설정)
5. [데이터 파이프라인](#5-데이터-파이프라인)
6. [실험 기록 (exp_001~011)](#6-실험-기록)
7. [최종 결론 및 권장 설정](#7-최종-결론-및-권장-설정)
8. [미해결 과제](#8-미해결-과제)
9. [exp_008 원본 리포트](#9-exp_008-원본-리포트)

---

## 1. 프로젝트 개요

### 프로젝트명
**M-Model** (안티그래비티 - DB 공모전)

### 핵심 목표
미국 GAAP 기업의 R&D와 SG&A를 K-IFRS 방식으로 자산화하여 회계 재작성을 수행하고, 이를 기반으로 **적정 PBR(Price-to-Book Ratio)**을 예측하는 퀀트 투자 전략 시스템

### 데이터 소스
| 소스 | 용도 | 파일 |
|------|------|------|
| yfinance | 가격 데이터 (월말 종가/조정종가) | step1_px_*.csv |
| SEC EDGAR | 재무제표 (XBRL) | step2_fund_annual.csv |
| Wikipedia | S&P 500 구성종목 | sp500_*.csv/json/txt |

---

## 2. 핵심 아이디어

### 2.1 회계 재작성 (Restatement)

```
자산화 투자액: I = R&D + 0.3 × SG&A
3년 정액 상각: A = (I_t + I_{t-1} + I_{t-2}) / 3
조정 영업이익: AdjOI = OI + I - A
```

**왜 필요한가?**
- 미국 GAAP: R&D, SG&A 전액 비용 처리
- K-IFRS: 일부를 무형자산으로 자산화
- → 기술주/바이오 기업의 **과소평가된 자산과 이익을 복원**

### 2.2 3개 피처로 PBR 예측

| 피처 | 공식 | 의미 | 클리핑 |
|------|------|------|--------|
| **m1** | AdjOI / max(\|OI\|, ε) | 이익 복원력 | [-5, +5] |
| **m2** | I_t / Avg(I_{t-1}, I_{t-2}) | 투자 가속도 | [0, 10] |
| **m3** | AdjOI / Equity | 본업 기초체력 | [-5, +5] |

### 2.3 Gap 기반 롱 전략

```
Gap = 예측 PBR - 시장 PBR
Gap 클수록 저평가 → 롱 포지션
```

**전략 종류**:
- Gap_5%, Gap_10%, Gap_20%, Gap_30%: Gap 상위 N%
- SmallCap_5%, SmallCap_10%, SmallCap_20%: 시총 하위 50% 중 Gap 상위 N%

---

## 3. 프로젝트 구조

```
안티그래비티 - 개발/
├── config/                         # ⚙️ 설정
│   ├── constants.py               # 전역 상수 (⭐ 핵심 설정 파일)
│   └── paths.py                   # 경로 관리
├── utils/                          # 🔧 유틸리티
│   ├── logger.py                  # 로깅
│   ├── validators.py              # 데이터 검증
│   ├── helpers.py                 # 헬퍼 함수
│   └── ticker_fetcher.py          # 티커 수집
├── data_collection/                # 📥 Step 1-2
│   ├── step1_price_collector.py           # 가격 수집 (기본)
│   ├── step1_price_collector_sequential.py # 가격 수집 (대용량)
│   └── step2_fundamental_collector.py     # 재무 수집 (SEC EDGAR)
├── feature_engineering/            # 🔬 Step 3
│   ├── restatement.py             # 회계 재작성 로직
│   └── step3_feature_builder.py   # m1, m2, m3, y 계산
├── modeling/                       # 🤖 Step 4
│   ├── model.py                   # PyTorch Linear 모델
│   └── step4_train_predict.py     # 롤링 학습 + 예측
├── backtesting/                    # 📊 Step 5
│   ├── metrics.py                 # CAGR, Sharpe, MDD, Alpha 등
│   └── step5_backtest.py          # 백테스트 실행
├── data_cache/                     # 💾 데이터 캐시
│   ├── step1_px_adj_m.csv         # 월말 조정종가
│   ├── step1_px_close_m.csv       # 월말 종가
│   ├── step1_meta.json            # 티커 메타정보
│   ├── step2_fund_annual.csv      # 연간 재무제표 (FULL)
│   ├── step2_fund_annual_sp500.csv # 연간 재무제표 (S&P 500)
│   ├── step3_features_annual.csv  # 피처 (m1, m2, m3, y)
│   ├── step4_predictions.csv      # 예측값 + Gap
│   ├── step4_weights_history.csv  # 모델 가중치 이력
│   ├── step5_backtest_returns.csv # 연도별 수익률
│   ├── step5_backtest_metrics.csv # 성과 지표
│   ├── sp500_tickers.txt          # S&P 500 티커 목록
│   ├── sp500_current_constituents.csv    # S&P 500 현재 구성 (섹터 포함)
│   └── sp500_historical_constituents.json # S&P 500 연도별 구성
├── experiments/                    # 🧪 실험 기록
│   ├── EXPERIMENT_CHANGELOG.md    # 실험 변경 이력
│   ├── exp_001_baseline_full_market/
│   ├── exp_002_hyperparams_v1/
│   ├── exp_003_stratified_split/
│   ├── exp_004_y_sector/
│   ├── exp_005_y_raw/
│   ├── exp_006_sp500_raw/
│   ├── exp_007_sp500_sector/
│   ├── exp_008_full_raw_5y/
│   ├── exp_009_full_sector_5y/
│   ├── exp_010_sp500_raw_5y/
│   └── exp_011_sp500_sector_5y/   # 🏆 최고 성과
├── scripts/                        # 📜 유틸 스크립트
│   ├── build_sp500_historical.py  # S&P 500 연도별 구성 생성
│   ├── analyze_lost_tickers.py    # 누락 티커 분석
│   ├── check_sp500_coverage.py    # S&P 500 커버리지 확인
│   └── verify_alpha.py            # Alpha 계산 검증
├── docs/                           # 📚 문서
│   ├── ALL_DEFERRED_TASKS.md      # 미뤄둔 작업 목록
│   ├── DATA_COLLECTION_ANALYSIS.md # 데이터 수집 분석
│   ├── PIPELINE_OPTIMIZATION_v2.1.md
│   └── XBRL_TAG_MAPPING.md        # SEC XBRL 태그 매핑
├── README.md                       # 프로젝트 소개
├── PIPELINE_OVERVIEW.md            # 파이프라인 상세
├── CHANGELOG.md                    # 전체 변경 이력
├── requirements.txt                # 패키지 목록
└── task.md                         # 개발 태스크
```

---

## 4. 주요 설정

### config/constants.py 핵심 파라미터

#### 4.1 데이터 수집 설정

| 파라미터 | 현재값 | 설명 |
|----------|--------|------|
| `TEST_MODE` | False | 테스트 모드 (17개 티커) |
| `MARKET_MODE` | 'SP500' | 'FULL' (3,640개) / 'SP500' (503개) |
| `START_YEAR` | 2012 | 데이터 수집 시작 연도 |
| `BACKTEST_START_YEAR` | 2015 | 백테스트 시작 연도 |

#### 4.2 제외 섹터

```python
EXCLUDED_SECTORS = [
    'Financials',    # GICS 40 - 회계 기준 상이
    'Utilities',     # GICS 55 - 규제 산업
    'Energy',        # GICS 10 - 유가 의존
    'Materials',     # GICS 15 - 원자재 의존
    'Real Estate',   # GICS 60 - REIT 특수 회계
    'Unknown'        # 섹터 정보 없음
]
```

**S&P 500 기준**:
- 전체: 503개
- 제외: 186개 (Financials 76 + Utilities 31 + Energy 22 + Materials 26 + Real Estate 31)
- **학습 대상: 317개** (실제 데이터 있는 것: ~295개)

#### 4.3 회계 재작성 파라미터

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `SGA_WEIGHT` | 0.3 | SG&A 자산화 비율 (30%) |
| `AMORTIZATION_YEARS` | 3 | 무형자산 상각 기간 |

#### 4.4 모델 학습 설정

| 파라미터 | 현재값 | 설명 |
|----------|--------|------|
| `Y_TARGET_MODE` | 'sector' | 'raw' (ln(PBR)) / 'sector' (섹터 상대) |
| `LEARNING_RATE` | 0.01 | Adam optimizer LR |
| `EPOCHS` | 100 | 최대 학습 에폭 |
| `EARLY_STOPPING_PATIENCE` | 10 | Early stopping |
| `WEIGHT_DECAY` | 0.01 | L2 규제 |
| `TRAIN_WINDOW_YEARS` | 5 | 롤링 학습 기간 |

#### 4.5 백테스트 파라미터

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `LONG_RATIOS` | [0.05, 0.10, 0.20, 0.30] | 롱 비율 |
| `HOLDING_PERIOD_MONTHS` | 12 | 홀딩 기간 |
| `REBALANCE_MONTH` | 12 | 리밸런싱 월 (12월) |
| `BENCHMARK_TICKER` | 'SPY' | 벤치마크 |
| `RISK_FREE_RATE` | 0.02 | 무위험 수익률 |

#### 4.6 방어 로직

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `EPSILON` | 1e-6 | 0 나누기 방지 |
| `M1_CLIP` | [-5, +5] | m1 클리핑 |
| `M2_CLIP` | [0, 10] | m2 클리핑 |
| `M3_CLIP` | [-5, +5] | m3 클리핑 |
| `PBR_CLIP` | [0.01, 100] | PBR 클리핑 |

---

## 5. 데이터 파이프라인

### 5.1 전체 흐름

```
Step 1: 가격 수집 (yfinance)
    ↓
    step1_px_adj_m.csv, step1_px_close_m.csv, step1_meta.json
    ↓
Step 2: 재무 수집 (SEC EDGAR)
    ↓
    step2_fund_annual.csv (Revenue, OI, NetIncome, RD, SGA, Equity)
    ↓
Step 3: Feature Engineering
    ↓
    step3_features_annual.csv (Ticker, FiscalYear, m1, m2, m3, y, Sector, MarketCap)
    ↓
Step 4: 모델 학습 (Rolling Window)
    ↓
    step4_predictions.csv (Gap = yhat - y)
    step4_weights_history.csv (연도별 w_m1, w_m2, w_m3, bias)
    ↓
Step 5: 백테스트
    ↓
    step5_backtest_returns.csv (연도별 전략 수익률)
    step5_backtest_metrics.csv (CAGR, Sharpe, MDD, Alpha, Beta, IR)
```

### 5.2 주요 출력 파일

| Step | 파일 | 설명 |
|------|------|------|
| 1 | step1_px_adj_m.csv | 월말 조정종가 (배당 재투자) |
| 1 | step1_px_close_m.csv | 월말 종가 |
| 1 | step1_meta.json | 티커 메타 (섹터, 시작일, 종료일) |
| 2 | step2_fund_annual.csv | 연간 재무제표 |
| 3 | step3_features_annual.csv | m1, m2, m3, y 피처 |
| 4 | step4_predictions.csv | 예측값, Gap |
| 4 | step4_weights_history.csv | 모델 가중치 변화 |
| 5 | step5_backtest_returns.csv | 연도별 수익률 |
| 5 | step5_backtest_metrics.csv | 성과 지표 |

### 5.3 S&P 500 관련 파일

| 파일 | 내용 |
|------|------|
| sp500_tickers.txt | 현재 S&P 500 티커 목록 (503개) |
| sp500_current_constituents.csv | 섹터, 추가일, CIK 등 상세 정보 |
| sp500_historical_constituents.json | 연도별 S&P 500 구성 (2012~2025) |
| step2_fund_annual_sp500.csv | S&P 500 전용 재무 데이터 |

---

## 6. 실험 기록

### 6.1 실험 목록

| 실험 ID | 설정 | 목적 |
|---------|------|------|
| exp_001 | FULL + raw + 3y | Baseline |
| exp_002 | FULL + raw + 3y | Early Stopping, L2 규제 |
| exp_003 | FULL + raw + 3y | 섹터 층화 분할 |
| exp_004 | FULL + sector + 3y | Y=섹터 상대 PBR |
| exp_005 | FULL + raw + 3y | Y=절대 PBR |
| exp_006 | SP500 + raw + 3y | S&P 500 유니버스 |
| exp_007 | SP500 + sector + 3y | S&P 500 + 섹터 상대 |
| exp_008 | FULL + raw + 5y | 5년 롤링 |
| exp_009 | FULL + sector + 5y | 5년 롤링 + 섹터 |
| exp_010 | SP500 + raw + 5y | S&P 500 + 5년 |
| **exp_011** 🏆 | **SP500 + sector + 5y** | **최적 설정** |

### 6.2 실험 결과 비교 (SmallCap_5% 기준)

| 실험 | MARKET | Y_TARGET | TRAIN | CAGR | Alpha | IR | MDD |
|------|--------|----------|-------|------|-------|-----|-----|
| exp_001 | FULL | raw | 3y | 6.94% | -3.96% | - | -19.64% |
| exp_004 | FULL | sector | 3y | 8.12% | -3.20% | - | - |
| exp_005 | FULL | raw | 3y | 5.84% | -5.15% | - | - |
| exp_006 | SP500 | raw | 3y | 14.69% | -0.16% | 0.03 | -26.38% |
| exp_007 | SP500 | sector | 3y | 17.91% | -0.03% | 0.30 | -30.96% |
| exp_008 | FULL | raw | 5y | 7.40% | -4.13% | -0.35 | - |
| exp_009 | FULL | sector | 5y | 7.96% | -3.68% | -0.31 | - |
| exp_010 | SP500 | raw | 5y | 10.64% | -4.29% | -0.06 | -27.85% |
| **exp_011** 🏆 | **SP500** | **sector** | **5y** | **15.58%** | **+0.27%** | **0.28** | -25.77% |

### 6.3 핵심 발견

1. **MARKET_MODE**: FULL < SP500 (S&P 500이 훨씬 우수)
2. **Y_TARGET_MODE**: raw < sector (섹터 상대가 우수)
3. **TRAIN_WINDOW_YEARS**: 
   - 3년: CAGR 높음 (17.91%)
   - 5년: Alpha 양수 (+0.27%), MDD 개선
4. **최고 성과**: exp_011 (SP500 + sector + 5년)
   - 유일하게 **Alpha 양수** (+0.27%)
   - IR 0.28 (초과수익 안정적)

### 6.4 실험별 폴더 구조

각 실험 폴더에 저장되는 파일:
```
exp_XXX_설명/
├── EXPERIMENT_REPORT.md        # 실험 상세 리포트
├── step4_weights_history.csv   # 모델 가중치 이력
├── step5_backtest_metrics.csv  # 성과 지표
└── step5_backtest_returns.csv  # 연도별 수익률
```

---

## 7. 최종 결론 및 권장 설정

### 7.1 최적 설정 (exp_011 기반)

```python
# config/constants.py 권장 설정
MARKET_MODE = 'SP500'           # S&P 500 구성종목만
Y_TARGET_MODE = 'sector'        # 섹터 상대 PBR
TRAIN_WINDOW_YEARS = 5          # 5년 롤링 학습
```

### 7.2 최적 전략

| 항목 | 권장값 |
|------|--------|
| **전략** | SmallCap_5% |
| **정의** | 시총 하위 50% 중 Gap 상위 5% |
| **기대 CAGR** | ~15% |
| **기대 Alpha** | ~0% (시장과 동등한 위험 조정 수익) |
| **MDD** | ~-26% |

### 7.3 3년 vs 5년 비교 (S&P 500 + sector)

| 지표 | 3년 (exp_007) | 5년 (exp_011) | 판단 |
|------|---------------|---------------|------|
| CAGR | 17.91% | 15.58% | 3년 > 5년 |
| Alpha | -0.03% | **+0.27%** | **5년** |
| Sharpe | 0.57 | 0.63 | **5년** |
| MDD | -30.96% | -25.77% | **5년** |
| IR | 0.30 | 0.28 | 3년 ≈ 5년 |

**결론**: 절대 수익률은 3년이 높지만, **리스크 조정 수익률(Alpha, Sharpe, MDD)**은 5년이 우수

---

## 8. 미해결 과제

### 8.1 높은 우선순위

| 과제 | 설명 | 상태 |
|------|------|------|
| 생존 편향 | 현재 상장 종목만 사용 (상장폐지 미반영) | ⏳ 미해결 |

### 8.2 중간 우선순위

| 과제 | 설명 | 상태 |
|------|------|------|
| 가중치 시각화 | weights_history 시각화 코드 | ⏳ 미작성 |
| 섹터별 성과 분석 | 섹터별 Alpha 비교 | ⏳ 미작성 |

### 8.3 낮은 우선순위

| 과제 | 설명 | 상태 |
|------|------|------|
| meta.json 타입 에러 | strftime 에러 (영향 없음) | ⏳ 미수정 |
| 코드 리팩토링 | 중복 코드 제거, 타입 힌팅 | ⏳ 미완료 |

---

## 📎 부록: 주요 문서 위치

| 문서 | 위치 | 내용 |
|------|------|------|
| README.md | 프로젝트 루트 | 프로젝트 소개 |
| PIPELINE_OVERVIEW.md | 프로젝트 루트 | 파이프라인 상세 (800줄) |
| CHANGELOG.md | 프로젝트 루트 | 전체 변경 이력 (651줄) |
| EXPERIMENT_CHANGELOG.md | experiments/ | 실험별 변경 기록 |
| ALL_DEFERRED_TASKS.md | docs/ | 미뤄둔 작업 목록 |
| DATA_COLLECTION_ANALYSIS.md | docs/ | 데이터 수집 분석 |
| XBRL_TAG_MAPPING.md | docs/ | SEC XBRL 태그 매핑 |

---

## 9. exp_008 원본 리포트

> 아래는 이 파일(exp_008_full_raw_5y)의 원본 실험 리포트입니다.

---

# Experiment Report: exp_008_full_raw_5y

## 실험 개요

| 항목 | 내용 |
|------|------|
| **실험명** | exp_008_full_raw_5y |
| **목적** | 전체 시장 + Y = ln(PBR) + 5년 롤링 학습 효과 검증 |
| **실험일** | 2026-01-31 |
| **기준 실험** | exp_006_sp500_raw (3년) |

---

## 실험 조건

| 항목 | 설정값 |
|------|--------|
| **MARKET_MODE** | FULL (~2,042개 Ready) |
| **Y_TARGET_MODE** | raw (ln(PBR)) |
| **TRAIN_WINDOW_YEARS** | **5년** |
| **백테스트 기간** | 2019-2025 (7년) |
| **제외 섹터** | Financials, Utilities, Energy, Materials, Real Estate |

---

## 학습 결과

### 모델 학습 결과 (Gap 통계)

| 지표 | 값 | 설명 |
|------|-----|------|
| **Gap 평균** | -0.395 | 예측 편향 (전반적 저평가) |
| **Gap 표준편차** | 1.404 | 예측 분산 |
| **샘플 수** | 9,922 | 7년 × 평균 1,417개/년 |

### 연도별 가중치 (Weights History)

| FiscalYear | w_m1 | w_m2 | w_m3 | bias | train_samples |
|------------|------|------|------|------|---------------|
| 2019 | -0.183 | 0.153 | -0.285 | 0.841 | 4,268 |
| 2020 | -0.188 | 0.227 | -0.291 | 0.835 | 4,597 |
| 2021 | -0.156 | 0.149 | -0.360 | 0.850 | 4,928 |
| 2022 | -0.154 | 0.158 | -0.283 | 0.849 | 5,261 |
| 2023 | 0.178 | 0.138 | -0.366 | 0.845 | 5,628 |
| 2024 | -0.086 | 0.122 | -0.170 | 0.837 | 6,082 |
| 2025 | 0.041 | 0.107 | -0.059 | 0.830 | 6,569 |

---

## 백테스트 성과

### 주요 지표 (Long Only + SmallCap)

| 전략 | CAGR | Sharpe | MDD | Alpha | Beta | IR |
|------|------|--------|-----|-------|------|-----|
| **Benchmark** | **12.93%** | **0.72** | **-18.18%** | - | - | - |
| Gap_5% | 4.22% | 0.20 | -25.97% | -7.95% | 1.00 | -0.63 |
| Gap_10% | 6.18% | 0.30 | -20.53% | -4.72% | 0.85 | -0.53 |
| Gap_20% | 4.52% | 0.22 | -23.43% | -6.63% | 0.86 | -0.96 |
| Gap_30% | 5.50% | 0.29 | -22.46% | -5.71% | 0.85 | -0.95 |
| SmallCap_5% | -0.84% | -0.02 | -36.82% | -10.71% | 0.84 | -0.70 |
| SmallCap_10% | 2.73% | 0.14 | -30.27% | -7.27% | 0.86 | -0.49 |
| **SmallCap_20%** | **7.40%** | **0.34** | -19.29% | -4.13% | 0.94 | **-0.35** |

### 연도별 수익률

| Year | Gap_5% | Gap_10% | SmallCap_5% | SmallCap_20% | Benchmark |
|------|--------|---------|-------------|--------------|-----------|
| 2019 | 20.67% | 29.08% | 10.99% | 27.48% | 18.33% |
| 2020 | 31.53% | 28.46% | 34.47% | 30.07% | 28.73% |
| 2021 | -25.97% | -20.53% | -23.82% | -19.29% | -18.18% |
| 2022 | 22.05% | 18.46% | 9.35% | 18.66% | 26.18% |
| 2023 | 10.07% | 6.38% | 11.81% | 24.73% | 24.89% |
| 2024 | -15.41% | -8.35% | -32.17% | -16.80% | 17.72% |
| 2025 | 0.00% | 0.00% | 0.00% | 0.00% | 1.30% |

---

## 결론

- **모든 전략이 벤치마크 대폭 하회**
- SmallCap_20%가 7.40%로 최고 성과이나, 벤치마크 대비 -5.53%p
- **FULL 시장 + raw 모드는 효과 없음**
- 2024년 대폭 하락 (-15% ~ -32%)이 전체 성과 악화 요인

---

**문서 끝**

*이 문서는 M-Model 프로젝트의 전체 컨텍스트를 보존하기 위해 작성되었습니다.*
*2026-02-04 작성*
