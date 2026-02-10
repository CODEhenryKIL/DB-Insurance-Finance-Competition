# 다음 에이전트를 위한 가이드

> 마지막 업데이트: 2026-02-10 (v3.0.0)

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

---

## 실험 실행

```bash
# 베이스라인 (MSE)
python3 experiments/run_experiment.py --preset baseline

# RankNet
python3 experiments/run_experiment.py --preset ranknet
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
- 검증 완료: scripts/verify_leakage.py

---

v3.0.0 리팩토링 반영
