# 다음 에이전트를 위한 가이드

> 마지막 업데이트: 2026-02-13 (v3.1.2)

---

## 필수 참고 문서

1. README.md - 프로젝트 개요
2. docs/PIPELINE_OVERVIEW.md - Step 1~5 파이프라인 상세
3. docs/CHANGELOG.md - 버전별 변경 이력
4. docs/task.md - 현재 진행 중인 태스크

---

## 프로젝트 구조

```
m-model/
├── config/              # 설정 (constants, paths, settings)
├── core/                # 핵심 로직 (models, restatement)
├── data_collection/     # Step 0-2: 유니버스/가격/재무 수집
├── feature_engineering/ # Step 3: 피처 생성
├── modeling/            # Step 4: 모델 학습
├── backtesting/         # Step 5: 백테스트
├── experiments/         # 실험 프레임워크
├── utils/               # 공통 유틸리티
├── scripts/             # 분석 스크립트
├── tests/               # 테스트
├── docs/                # 문서
├── data_cache/          # 캐시 데이터
└── README.md
```

### 파이프라인 흐름

```
Step 0 -> Step 1 -> Step 2 -> Step 3 -> Step 4 -> Step 5
유니버스   가격     재무     피처     모델     백테스트
```

---

## 핵심 개념

### 피처 (m1, m2, m3)

- m1: 이익 복원력 = AdjOI / max(abs(OI), e)
- m2: 투자 가속도 = I_t / Avg(I_{t-1}, I_{t-2})
- m3: 본업 기초체력 = AdjOI / Equity

### Gap (핵심!)

- Gap = 예측 PBR - 시장 PBR
- Gap > 0 -> 저평가 -> 매수 후보

### Safe Lag

- **0**: 12월 결산 → 12월 말 매수 (Look-ahead bias 있음)
- **3**: 12월 결산 → 3월 말 매수 (Look-ahead bias 해소)
- 기본값: 3 (무편향)

---

## 실험 실행 (v3.1.2 CLI)

### 파라미터 기반 실행 (권장)

```bash
# 기본 형태
python run_experiment.py -u SP500 -s ALL -w 5 -f A -l RankNet -sl 3

# 바이오&IT 섹터, 3년 윈도우
python run_experiment.py -u SP500 -s BioIT -w 3 -f A -l RankNet -sl 3

# 분기 리밸런싱
python run_experiment.py -u SP500 -s ALL -w 5 -f Q -l RankNet -sl 3

# 편향 있는 베이스라인 (12월 매수)
python run_experiment.py -u SP500 -s ALL -w 5 -f A -l MSE -sl 0
```

### CLI 파라미터

| 옵션 | 축약 | 선택지 | 기본값 | 설명 |
|------|------|--------|--------|------|
| `--universe` | `-u` | SP500, FULL | SP500 | 유니버스 |
| `--sector` | `-s` | ALL, BioIT | ALL | 섹터 필터 |
| `--window` | `-w` | 3, 5 | 5 | 학습 윈도우(년) |
| `--freq` | `-f` | A, Q, S | A | Annual/Quarterly/Semiannual |
| `--loss` | `-l` | MSE, RankNet | RankNet | 손실함수 |
| `--safe_lag` | `-sl` | 0, 3 | 3 | Safe Lag(월) |

### 프리셋 사용 (deprecated)

```bash
# 기존 방식 (하위 호환)
python run_experiment.py --preset ranknet
```

---

## 자주 사용하는 명령어

```bash
python3 modeling/step4_train_predict.py      # Step4 학습
python3 backtesting/step5_backtest.py        # Step5 백테스트
python3 scripts/verify_leakage.py            # Data Leakage 검증
```

---

## 중요 발견

- m3와 y 상관관계 0.55: Data Leakage 아님 (경제학적으로 당연)
- Safe Lag=3 수익률 > Safe Lag=0: COVID 3월 바닥 매수 타이밍 운
- 검증 완료: scripts/verify_leakage.py

---

v3.1.2 CLI 리팩터링 반영

---

v3.0.0 리팩토링 반영
