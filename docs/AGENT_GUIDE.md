# 🤖 다음 에이전트를 위한 가이드

> **마지막 업데이트**: 2026-02-10

이 문서는 프로젝트를 처음 접하는 AI 에이전트가 빠르게 맥락을 파악할 수 있도록 작성되었습니다.

---

## 📖 필수 참고 문서

| 순서 | 문서 | 파악 내용 |
|------|------|----------|
| 1️⃣ | **README.md** | 프로젝트 개요, 폴더 구조, 핵심 아이디어 |
| 2️⃣ | **PIPELINE_OVERVIEW.md** | Step 1~5 파이프라인 상세, 입출력 파일 |
| 3️⃣ | **CHANGELOG.md** | 버전별 변경 이력, 최신 기능 확인 |
| 4️⃣ | **task.md** | 현재 진행 중인 태스크 목록 |
| 5️⃣ | **docs/ALL_DEFERRED_TASKS.md** | 보류된 작업 목록 |

---

## 🏗️ 프로젝트 핵심 구조

### 파이프라인 흐름
```
Step 0 → Step 1 → Step 2 → Step 3 → Step 4 → Step 5
유니버스   가격     재무     피처     모델     백테스트
필터      수집     수집     생성     학습
```

### 주요 폴더
```
config/           # 전역 상수 및 경로
data_collection/  # Step 1-2: 데이터 수집
feature_engineering/  # Step 3: 피처 생성
modeling/         # Step 4: 모델 학습
backtesting/      # Step 5: 백테스트
experiments_v2/   # 실험 프레임워크 (신규)
scripts/          # 유틸리티 스크립트
data_cache/       # 캐싱된 데이터 (gitignore)
```

---

## 🔑 핵심 개념

### 1. 피처 (m1, m2, m3)
| 피처 | 의미 | 공식 |
|------|------|------|
| m1 | 이익 복원력 | AdjOI / max(abs(OI), ε) |
| m2 | 투자 가속도 | I_t / Avg(I_{t-1}, I_{t-2}) |
| m3 | 본업 기초체력 | AdjOI / Equity (≈ ROE) |

### 2. 타겟 (y)
- `y = ln(PBR) = ln(MarketCap / Equity)`
- Y_TARGET_MODE: `raw` (단순) vs `sector` (섹터 상대)

### 3. Gap (핵심!)
- `Gap = ŷ - y = 예측값 - 실제값`
- Gap > 0 → 시장이 저평가 → 매수 후보
- Gap 상위 N% 종목 선택 → 롱 전략

### 4. 모델 타입
| 모델 | 손실함수 | 특징 |
|------|---------|------|
| MSE | Mean Squared Error | 기본, 절대값 학습 |
| RankNet | Pairwise Ranking Loss | 상대 순위 학습 |

---

## ⚠️ 중요 발견 사항

### m3와 y의 높은 상관관계 (0.55)
- m3(≈ROE)와 y(ln PBR)는 경제학적으로 당연히 상관됨
- 효율적 시장에서 ROE 높은 기업은 PBR도 높음
- **Data Leakage 아님** (검증 완료: `scripts/verify_leakage.py`)
- m3 예측력: 동시점 0.52 → t+1 예측 0.49 (persistence)

---

## 🧪 실험 프레임워크 v2

### 실행 방법
```bash
# 베이스라인 (MSE)
python3 experiments_v2/run_experiment.py --preset baseline

# RankNet
python3 experiments_v2/run_experiment.py --preset ranknet

# 커스텀
python3 experiments_v2/run_experiment.py \
  --exp_id exp_010 \
  --exp_name my_test \
  --model_type RankNet \
  --market_mode SP500
```

### 결과 폴더 구조
```
experiments_v2/exp_XXX_name/
├── config.json                 # 설정 (재현용)
├── data/
│   ├── weights_history.csv     # 연도별 가중치
│   ├── returns_by_year.csv     # 연도별 수익률
│   ├── predictions_with_rank.csv
│   ├── portfolio_holdings_normal.csv
│   └── portfolio_holdings_smallcap.csv
├── metrics/
│   ├── performance_metrics.csv # CAGR, Sharpe, MDD 등
│   └── validation_tests.json   # Rank IC, 강건성
└── REPORT.md                   # 자동 생성 보고서
```

---

## 📊 현재 상태 요약

### 구현 완료
- ✅ Step 0~5 전체 파이프라인
- ✅ MSE + RankNet 모델 (선택 가능)
- ✅ 5개 벤치마크 하드코딩 (v2.4.0)
- ✅ experiments_v2 프레임워크 (v2.6.0)
- ✅ Data Leakage 검증

### 최근 실험 결과 (삭제됨, 재실행 필요)
```
실험 1: exp_001_baseline_sp500_mse
실험 2: exp_002_sp500_ranknet
→ 사용자 요청으로 삭제됨
```

### 다음 단계 제안
1. 실험 1번부터 새로 시작
2. m1+m2만 사용하는 실험 (m3 제외)
3. 섹터 상대 y 모드 실험
4. Full Market 모드 실험

---

## 🔧 자주 사용하는 명령어

```bash
# Step4 MSE 학습
python3 modeling/step4_train_predict.py

# Step4 RankNet 학습
python3 modeling/step4_train_predict_ranknet.py

# Step5 백테스트
python3 backtesting/step5_backtest.py

# 실험 실행
python3 experiments_v2/run_experiment.py --preset baseline

# Data Leakage 검증
python3 scripts/verify_leakage.py
```

---

## 📁 주요 데이터 파일

| 파일 | 설명 |
|------|------|
| `data_cache/step1_px_close_m.csv` | 월말 종가 |
| `data_cache/step2_fund_annual.csv` | 연간 재무제표 |
| `data_cache/step3_features_annual.csv` | 피처 (m1, m2, m3, y) |
| `data_cache/step4_predictions.csv` | MSE 예측 결과 |
| `data_cache/step4_predictions_ranknet.csv` | RankNet 예측 결과 |
| `data_cache/step5_backtest_returns.csv` | 백테스트 수익률 |

---

## ❓ FAQ

### Q: 어떤 파일을 먼저 읽어야 하나요?
A: `README.md` → `PIPELINE_OVERVIEW.md` → `CHANGELOG.md` 순서로 읽으세요.

### Q: 실험을 새로 시작하려면?
A: `python3 experiments_v2/run_experiment.py --preset baseline`

### Q: 모델을 MSE에서 RankNet으로 바꾸려면?
A: `--preset ranknet` 또는 `--model_type RankNet`

### Q: 백테스트만 다시 하려면?
A: `python3 backtesting/step5_backtest.py`

---

*이 문서는 AI 에이전트 간 컨텍스트 전달을 위해 작성되었습니다.*
