# M-Model 프로젝트

## 📌 프로젝트 개요

**M-Model**은 미국 GAAP 기업의 R&D와 SG&A를 K-IFRS 방식으로 자산화하여 회계 재작성을 수행하고, 이를 기반으로 적정 PBR(Price-to-Book Ratio)을 예측하는 퀀트 투자 전략 시스템입니다.

### 핵심 아이디어

1. **회계 재작성 (Restatement)**
   - 미국 GAAP에서는 R&D와 SG&A가 전액 비용 처리
   - K-IFRS 방식으로 일부를 무형자산으로 자산화
   - → 기술주/바이오 기업의 과소평가된 자산과 이익을 복원

2. **3개 피처로 PBR 예측**
   - **m1**: 이익 복원력 (AdjOI / OI)
   - **m2**: 투자 가속도 (Intensity 증가율)
   - **m3**: 본업 기초체력 (Pre-Investment Margin 비율)

3. **Gap 기반 롱 전략**
   - Gap = 예측 PBR - 시장 PBR
   - Gap이 클수록 저평가 → 롱 포지션
   - 4가지 롱 비율 (5%, 10%, 20%, 30%) 비교

---

## 🗂️ 프로젝트 구조

```
안티그래비티 - 개발/
├── config/                     # 설정 파일
│   ├── constants.py           # 전역 상수
│   └── paths.py               # 경로 관리
├── utils/                      # 공통 유틸리티
│   ├── logger.py              # 로깅 시스템
│   ├── validators.py          # 데이터 검증 및 방어 로직
│   └── helpers.py             # 헬퍼 함수
├── data_collection/            # 데이터 수집
│   ├── step1_price_collector.py
│   └── step2_fundamental_collector.py
├── feature_engineering/        # 피처 생성
│   ├── restatement.py
│   └── step3_feature_builder.py
├── modeling/                   # 모델링
│   ├── model.py
│   └── step4_train_predict.py
├── backtesting/                # 백테스팅
│   ├── universe_filter.py
│   ├── portfolio.py
│   └── step5_backtest.py
├── evaluation/                 # 평가 및 시각화
│   ├── metrics.py
│   └── visualizer.py
├── data_cache/                 # 캐시 (gitignore)
├── reports/                    # 리포트 (gitignore)
├── logs/                       # 로그 (gitignore)
├── main.py                     # 전체 파이프라인 실행
├── requirements.txt
├── .gitignore
├── README.md
├── task.md                     # 개발 태스크 체크리스트
└── implementation_plan.md      # 구현 계획서
```

---

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

**필수 요구사항:**
- Python 3.8 이상
- Pandas 2.2.0 이상 (월말 resample 'ME' 지원)

### 2. 전체 파이프라인 실행

```bash
python main.py
```

실행 순서:
1. Step1: 가격 데이터 수집
2. Step2: 재무 데이터 수집 (edgartools)
3. Step3: Feature Engineering
4. Step4: 모델 학습 및 예측
5. Step5: 백테스트 (4가지 롱 비율)
6. 평가 및 리포트 생성

### 3. 단계별 실행 (선택)

```python
# Step1만 실행
from data_collection.step1_price_collector import PriceCollector
collector = PriceCollector()
collector.run()

# Step3부터 실행 (캐시 활용)
python main.py --skip-step1 --skip-step2
```

---

## 📊 데이터 소스

### 1. 가격 데이터
- **소스**: yfinance (Yahoo Finance API)
- **내용**: S&P500 월말 종가 및 조정종가
- **기간**: 2010년 ~ 현재

### 2. 재무 데이터
- **우선순위 1**: edgartools (SEC Edgar API)
- **우선순위 2**: SimFin API
- **최종 대안**: FMP API (유료)
- **필수 필드**: Revenue, OI, NetIncome, RD, SGA, Equity

---

## 🔧 주요 기능

### 1. 회계 재작성 (Restatement)

```python
# 자산화 투자액 계산
I = RD + 0.3 × SGA

# 3년 정액 상각
A = (I_t + I_{t-1} + I_{t-2}) / 3

# 조정 영업이익
AdjOI = OI + I - A
```

### 2. 피처 엔지니어링

**m1 (이익 복원력)** - 개선된 클리핑 로직
```python
# 기존: abs(OI) < epsilon → NaN (데이터 손실)
# 개선: 클리핑 방식 (데이터 보존)
denominator = max(abs(OI), 1e-6)
m1 = AdjOI / denominator
m1 = clip(m1, -5, +5)
```

**m2 (투자 가속도)**
```python
Intensity = I / Revenue
m2 = Intensity_t / Avg(Intensity_{t-1}, Intensity_{t-2})
```

**m3 (본업 기초체력)**
```python
PIM = (OI + I) / Revenue
m3 = PIM_t / Avg(PIM_{t-1}, PIM_{t-2})
```

### 3. 백테스트 전략

- **리밸런싱**: 매년 12월 말
- **유니버스 필터**:
  - 섹터: Financial, Utilities 제외
  - $5 룰: 최근 12개월 중 80% 이상 $5 이하 제외
- **포트폴리오**: Gap 상위 N% 동일가중 롱
- **홀딩 기간**: 12개월
- **롱 비율**: 5%, 10%, 20%, 30% (4가지 비교)

---

## 📈 성과 지표

백테스트 결과는 다음 지표로 평가됩니다:

- **CAGR** (Compound Annual Growth Rate): 연평균 성장률
- **Sharpe Ratio**: 위험 대비 수익률
- **MDD** (Maximum Drawdown): 최대 낙폭
- **Alpha**: 벤치마크(S&P500) 대비 초과 수익

---

## 🛡️ 방어 로직 (중요)

### 1. m1 계산 시
- **문제**: OI ≈ 0인 기업 (바이오, 초기 테크) 데이터 손실
- **해결**: 결측 처리 대신 클리핑
  ```python
  denom = max(abs(OI), 1e-6)
  m1 = clip(AdjOI / denom, -5, +5)
  ```

### 2. BookValue ≤ 0
- ln(PBR) 계산 불가 → NaN 처리 (필수)

### 3. Revenue = 0
- m2, m3 계산 시 epsilon 적용

### 4. Pandas 버전 호환
- Pandas >= 2.2.0: resample 'ME'
- Pandas < 2.2.0: resample 'M'
- 자동 감지 및 적용 (`utils.helpers.get_month_end_freq()`)

---

## 📝 개발 문서

- **task.md**: 개발 태스크 체크리스트
- **implementation_plan.md**: 상세 구현 계획서
- **각 .py 파일 상단**: 파일별 구조 및 흐름 설명

---

## 🔍 주의사항

### 절대 실수 방지 체크리스트

- ✅ **Gap 정의**: Gap = yhat - y (클수록 저평가)
- ✅ **m1 방어**: 클리핑 방식 (데이터 보존)
- ✅ **BookValue**: ≤ 0 → NaN
- ✅ **$5 룰**: 동적 필터링 (리밸런스 시점 기준)
- ✅ **Pandas resample**: ME 또는 M 자동 선택
- ✅ **백테스트**: 4가지 롱 비율 동시 실행

---

## 📧 문의

프로젝트 관련 문의사항은 아래로 연락 주세요:
- GitHub Issues
- Email: contact@example.com

---

## 📄 라이선스

This project is for research purposes only.

---

**Last Updated**: 2026-01-28  
**Version**: 1.0
