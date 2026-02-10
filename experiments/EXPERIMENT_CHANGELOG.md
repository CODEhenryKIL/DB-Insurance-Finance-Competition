# 실험 버전별 변경 기록 (Experiment Changelog)

> 이 문서는 M-Model 파이프라인의 실험별 설정 변경사항을 추적합니다.  
> 최신 버전이 상단에 위치합니다.

---

## 📋 실험 목록

| 실험 ID | 날짜 | 목적 | 주요 변경 |
|---------|------|------|----------|
| [exp_005](#exp_005_y_raw) | 2026-01-31 | Y 타겟 비교 (Raw) | Y = ln(PBR) 절대값 |
| [exp_004](#exp_004_y_sector) | 2026-01-31 | Y 타겟 비교 (Sector) | Y = ln(PBR) - Sector_Median |
| [exp_003](#exp_003_stratified_split) | 2026-01-30 | 섹터 층화 + 강한 규제 | 섹터별 층화 추출, weight_decay=1e-2 |
| [exp_002](#exp_002_hyperparams_v1) | 2026-01-30 | 하이퍼파라미터 튜닝 | Early Stopping, L2 규제, Train/Val split |
| [exp_001](#exp_001_baseline_full_market) | 2026-01-30 | Baseline 측정 | 전체 미국 시장 대상 기본 모델 |

---

## exp_005_y_raw

**실험일**: 2026-01-31  
**목적**: 절대 PBR 학습 효과 검증  
**기준 실험**: exp_003_stratified_split

### 설정 변경

| 파라미터 | 이전 (exp_003) | 변경 (exp_005) | 파일 위치 |
|----------|----------------|----------------|-----------|
| `Y_TARGET_MODE` | (없음) | **'raw'** | `config/constants.py` |

### Y 타겟 정의

| 모드 | 수식 | 의미 |
|------|------|------|
| `raw` | Y = ln(PBR) | 절대적 저평가 학습 |
| `sector` | Y = ln(PBR) - Sector_Median | 섹터 내 상대적 저평가 학습 |

### 결과 요약

| 비율 | CAGR | Sharpe | Alpha |
|------|------|--------|-------|
| Top 5% | 4.00% | 0.19 | -6.99% |
| Top 10% | 5.62% | 0.27 | -5.15% |
| Top 30% | **5.84%** | **0.31** | -5.36% |

---

## exp_004_y_sector

**실험일**: 2026-01-31  
**목적**: 섹터 상대 PBR 학습 효과 검증  
**기준 실험**: exp_003_stratified_split

### 설정 변경

| 파라미터 | 이전 (exp_003) | 변경 (exp_004) | 파일 위치 |
|----------|----------------|----------------|-----------|
| `Y_TARGET_MODE` | (없음) | **'sector'** | `config/constants.py` |

### Y 타겟 정의

```
Y = ln(PBR_i) - Median(ln(PBR)_sector)

각 연도, 각 섹터별로 PBR 중앙값을 빼줌
→ 섹터 내 상대적 저평가 기업 포착
```

### 결과 요약

| 비율 | CAGR | Sharpe | Alpha |
|------|------|--------|-------|
| Top 5% | 2.64% | 0.12 | -8.69% |
| **Top 10%** | **8.12%** | **0.42** | **-3.20%** |
| Top 30% | 6.16% | 0.33 | -4.77% |

### 🏆 exp_004 vs exp_005 비교

| 지표 | exp_004 (Sector) | exp_005 (Raw) | 승자 |
|------|------------------|---------------|------|
| 최적 CAGR | 8.12% | 5.84% | **Sector** |
| 최적 Sharpe | 0.42 | 0.31 | **Sector** |
| 최적 Alpha | -3.20% | -5.15% | **Sector** |

**결론**: 섹터 상대 PBR (exp_004)이 절대 PBR (exp_005)보다 우수

---

## exp_003_stratified_split

**실험일**: 2026-01-30  
**목적**: 섹터별 층화 추출 + 강화된 L2 규제  
**기준 실험**: exp_002_hyperparams_v1

### 설정 변경

| 파라미터 | 이전 (exp_002) | 변경 (exp_003) | 파일 위치 |
|----------|----------------|----------------|-----------|
| `WEIGHT_DECAY` | 1e-4 | **1e-2** | `config/constants.py` |

### 구조 변경

| 항목 | 이전 | 변경 | 파일 위치 |
|------|------|------|-----------|
| Train/Val Split | 기업별 랜덤 분리 | **섹터별 층화 추출** | `modeling/step4_train_predict.py` |
| 섹터 균형 | 없음 (편향 가능) | 각 섹터에서 동일 비율(20%) Val 선정 | `prepare_data()` |

### ⚠️ 섹터별 층화 추출 (Stratified Split)

**왜 필요한가?**
- 기업별 랜덤 분리 시 특정 섹터가 Val에 몰릴 수 있음
- 예: Tech 기업이 Val의 80%를 차지하면 편향 발생

**해결**:
```
각 섹터에서 동일 비율(20%)로 Val 기업 선정

┌─────────────────────────────────────────────────────────────┐
│  Tech: 100개 → Train 80개 / Val 20개 (20%)                  │
│  Healthcare: 80개 → Train 64개 / Val 16개 (20%)              │
│  Industrials: 60개 → Train 48개 / Val 12개 (20%)             │
└─────────────────────────────────────────────────────────────┘
```

### 결과 비교 (Gap_30% 기준)

| 지표 | exp_002 | exp_003 | 차이 |
|------|---------|---------|------|
| CAGR | 5.68% | **6.16%** | **+0.48%p** |
| Sharpe | 0.30 | **0.33** | **+0.03** |
| MDD | -22.42% | -22.12% | +0.30%p |

---

## exp_002_hyperparams_v1

**실험일**: 2026-01-30  
**목적**: 하이퍼파라미터 튜닝 + Early Stopping + L2 규제 적용  
**기준 실험**: exp_001_baseline_full_market

### 설정 변경

| 파라미터 | 이전 (exp_001) | 변경 (exp_002) | 파일 위치 |
|----------|----------------|----------------|-----------|
| `EPOCHS` | 500 | **100** | `config/constants.py` |
| `LEARNING_RATE` | 0.001 | **0.01** | `config/constants.py` |
| `WEIGHT_DECAY` | 없음 | **1e-4** | `config/constants.py` (신규) |
| `EARLY_STOPPING_PATIENCE` | 없음 | **10** | `config/constants.py` (신규) |

### 구조 변경

| 항목 | 이전 | 변경 | 파일 위치 |
|------|------|------|-----------|
| Train/Val Split | 없음 (전체 Train) | **기업별 Cross-sectional Split** | `modeling/step4_train_predict.py` |
| Split 방식 | Train [t-3,t-2,t-1] 전체 | 3년 전체 중 기업별 T:80%/V:20% | `prepare_data()` |
| Early Stopping | 없음 | **Val Loss 기반 조기 종료** | `train_model()` |
| Best Model 복원 | 없음 | **Best Val Loss 모델 저장** | `train_model()` |

### ⚠️ Cross-sectional 데이터의 올바른 Train/Val 분리

**왜 연도순 Split이 아닌가?**
- 3년 Rolling Window의 목적: **최근 3년간의 금융시장 스타일 변화** 학습
- 연도순 split(2년 Train/1년 Val): 실질적으로 **2년만 학습** → 의도와 불일치!

**해결: 기업별 Cross-sectional Split**
```
┌───────────────────────────────────────────────────────────────┐
│       2017         │       2018         │       2019          │
│   기업 A,B,C (T)   │   기업 A,B,C (T)   │   기업 A,B,C (T)    │  → Train 80%
│   기업 D,E (V)     │   기업 D,E (V)     │   기업 D,E (V)      │  → Val 20%
└───────────────────────────────────────────────────────────────┘
                    3년 전체의 스타일 변화 학습!

핵심 원칙:
1. 3년 전체 학습 - 금융시장 스타일 변화를 놓치지 않음
2. 기업별 분리 - 동일 기업은 Train 또는 Val 중 하나에만 존재
3. Data Leakage 방지 - Val 기업의 과거 데이터가 Train에 포함 X
```

### 코드 변경 상세

**`config/constants.py`**:
```python
# 변경 전 (exp_001)
LEARNING_RATE = 1e-3
EPOCHS = 500

# 변경 후 (exp_002)
LEARNING_RATE = 1e-2
EPOCHS = 100
WEIGHT_DECAY = 1e-4  # L2 규제
EARLY_STOPPING_PATIENCE = 10  # 조기 종료
```

**`modeling/step4_train_predict.py`**:
```python
# prepare_data() 변경
# - 3년 전체 데이터에서 기업별로 Train(80%)/Val(20%) 분리
# - unique_tickers로 기업 추출 후 셔플 → val_ratio만큼 Val로 분리
# - 반환값: X_train, y_train, X_val, y_val, X_test, y_test, train_df, test_df

# train_model() 변경
# - optimizer에 weight_decay 추가
# - Early stopping 로직 추가
# - Best model 상태 저장 및 복원
```

### 결과 비교 (Gap_30% 기준)

| 지표 | exp_001 | exp_002 | 차이 |
|------|---------|---------|------|
| CAGR | 6.94% | 5.68% | -1.26%p |
| Sharpe | 0.39 | 0.30 | -0.09 |
| MDD | -19.64% | -22.42% | -2.78%p |
| Alpha | -3.96% | -5.17% | -1.21%p |

---

## exp_001_baseline_full_market

**실험일**: 2026-01-30  
**목적**: 전체 미국 시장 대상 Baseline 모델 성능 측정  
**기준 실험**: 없음 (최초 실험)

### 설정 (Baseline)

| 파라미터 | 값 | 파일 위치 |
|----------|-----|-----------|
| `EPOCHS` | 500 | `config/constants.py` |
| `LEARNING_RATE` | 0.001 | `config/constants.py` |
| `TRAIN_WINDOW_YEARS` | 3 | `config/constants.py` |
| `BACKTEST_START_YEAR` | 2017 | `config/constants.py` |
| `SGA_CAPITALIZATION_RATE` | 0.3 | `config/constants.py` |
| `INTANGIBLE_AMORTIZATION_YEARS` | 3 | `config/constants.py` |

### 모델 구조

| 항목 | 값 |
|------|-----|
| 입력 차원 | 3 (m1, m2, m3) |
| 출력 차원 | 1 (predicted ln(PBR)) |
| 모델 | Linear Layer (PyTorch) |
| 손실 함수 | MSE Loss |
| 옵티마이저 | Adam |
| Validation | ❌ 없음 |
| Early Stopping | ❌ 없음 |

### 피처 정의

| 피처 | 공식 | 의미 | 클리핑 |
|------|------|------|--------|
| m1 | `AdjOI / max(\|OI\|, ε)` | 이익 복원력 | [-5, +5] |
| m2 | `I_t / Avg(I_{t-1}, I_{t-2})` | 투자 가속도 | [0, 10] |
| m3 | `AdjOI / Equity` | 본업 기초체력 | [-5, +5] |

### ⚠️ 한계점

| 문제 | 설명 |
|------|------|
| Validation 없음 | 과적합 검증 불가 |
| 500 epochs 고정 | 조기 종료 없이 강제 학습 |
| Train 전체 사용 | 3년 전체를 Train으로 사용 |

### 결과 (Gap_30% 기준)

| 지표 | 값 |
|------|-----|
| CAGR | 6.94% |
| Sharpe | 0.39 |
| MDD | -19.64% |
| Alpha | -3.96% |
| S&P 500 CAGR | 12.76% |

---

## 🔧 향후 실험 계획

| 실험 ID | 목적 | 예정 변경 |
|---------|------|----------|
| exp_003 | LR 튜닝 | LR 0.01 → 0.005 하향 |
| exp_004 | Patience 조정 | 10 → 20 증가 |
| exp_005 | S&P 500만 | 유니버스 축소 |
| exp_006 | SGA 비율 | 0.3 → 0.2 변경 |
| exp_007 | 상각 기간 | 3년 → 5년 변경 |

---

*Last Updated: 2026-01-30*
