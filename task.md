# M-Model 프로젝트 개발 태스크

## 🎯 전체 목표
미국 GAAP 기업의 R&D와 SG&A를 자산화하여 회계 재작성 후, 3개 핵심 요소(m1, m2, m3)로 적정 PBR을 예측하고 Gap 기반 롱 전략 백테스팅 시스템 구축

**데이터 범위:** 2010년 ~ 현재  
**백테스트 롱 비율:** 5%, 10%, 20%, 30% (4가지 비교)

---

## 📋 태스크 체크리스트

### Phase 1: 프로젝트 구조 설계 및 기본 설정
- [x] 프로젝트 디렉토리 구조 생성
- [x] 공통 유틸리티 모듈 작성 (config, logger, helpers)
- [x] requirements.txt 작성
- [x] README.md 작성
- [x] .gitignore 작성

### Phase 2: Step1 - 가격 데이터 수집 및 섹터 필터링
- [x] Step1 메인 스크립트 작성
  - [x] 섹터 필터링 (Financial, Utilities 제외)
  - [x] 월말 가격 데이터 수집 (AdjClose, Close)
  - [x] Pandas 버전 호환성 처리 (ME/M)
  - [x] 캐시 저장 (prices_monthly)
  - [x] 테스트 완료
  
### Phase 3: Step2 - 재무 데이터 수집 (SEC companyfacts API)
- [x] SEC companyfacts API 직접 사용
- [x] 티커→CIK 매핑
- [x] XBRL 태그 파싱 (Revenue, OI, NetIncome, RD, SGA, Equity)
- [x] 연간(10-K) 데이터만 필터링
- [x] 2010년 이후 데이터 수집
- [x] 캐싱 기능 (중복 다운로드 방지)
- [x] 테스트 완료 (AAPL, MSFT)

### Phase 4: Step3 - Feature Engineering
- [ ] 회계 재작성 로직 구현
  - [ ] 자산화 투자액(I) 계산: I = RD + 0.3×SGA
  - [ ] 3년 정액 상각(A) 계산: A = (I_t + I_t-1 + I_t-2) / 3
  - [ ] 조정 영업이익(AdjOI) 계산: AdjOI = OI + I - A
- [ ] 피처 계산 및 개선된 방어 로직
  - [ ] **m1 (이익 복원력) - 클리핑 방식 적용** ⭐
    - [ ] denominator = max(abs(OI), 1e-6)
    - [ ] m1 = AdjOI / denominator
    - [ ] clip 범위: [-5, +5]
  - [ ] m2 (투자 가속도) - Revenue 0 방어
  - [ ] m3 (본업 기초체력) - 분모 0 방어
  - [ ] y = ln(PBR) - BookValue ≤ 0 방어
- [ ] features_annual 데이터 저장

### Phase 5: Step4 - 모델 학습 및 예측
- [ ] PyTorch 선형 모델 구현
  - [ ] 1-layer Linear NN (3→1)
  - [ ] Adam optimizer
  - [ ] MSE loss
- [ ] Rolling window 학습 로직
  - [ ] Train: 과거 5년
  - [ ] Test: 다음 1년
  - [ ] Standardization (rolling)

### Phase 6: Step5 - 백테스트 및 평가 (4가지 롱 비율)
- [ ] 동적 유니버스 필터 구현
  - [ ] 섹터 필터
  - [ ] $5 룰 (리밸런스 시점 기준 최근 12개월)
- [ ] 포트폴리오 구성 (4가지 버전)
  - [ ] Gap 상위 5% 롱 (버전 1)
  - [ ] Gap 상위 10% 롱 (버전 2)
  - [ ] Gap 상위 20% 롱 (버전 3)
  - [ ] Gap 상위 30% 롱 (버전 4)
  - [ ] 각각 동일가중
  - [ ] 12개월 홀딩
- [ ] 수익률 및 지표 계산
  - [ ] CAGR, Sharpe Ratio, MDD, Alpha (4가지 버전 각각)
  - [ ] 벤치마크 비교 (S&P500)
- [ ] 결과 시각화 및 비교 리포트

### Phase 7: 검증 및 문서화
- [ ] 전체 파이프라인 통합 테스트
- [ ] 4가지 롱 비율 결과 비교 분석
- [ ] 최종 문서 작성

---

## ⚠️ 주요 개선 사항 (2026-01-28)

### 1. m1 방어 로직 개선
- **기존:** 분모 abs(OI) < epsilon → 결측 처리 (데이터 손실)
- **개선:** 클리핑 방식으로 데이터 보존
  ```python
  # 턴어라운드 유망 종목(OI≈0)을 살리기 위해 클리핑 적용
  denominator = max(abs(OI), 1e-6)
  m1 = AdjOI / denominator
  m1 = clip(m1, -5, +5)
  ```

### 2. Pandas 버전 호환성
- **요구사항:** pandas >= 2.2.0 (ME 지원)
- **호환성 처리:** ME 미지원 시 M으로 대체
  ```python
  try:
      df.resample('ME')  # Pandas 2.2.0+
  except ValueError:
      df.resample('M')   # 구버전 호환
  ```

### 3. 백테스트 롱 비율 확대
- **변경:** Gap 상위 20% 단일 → 5%, 10%, 20%, 30% 4가지 동시 비교

---

## 📊 진행 상황
- **완료:** Phase 1 (디렉토리 구조 생성)
- **진행 중:** Phase 1 (설정 파일 작성)
- **다음:** edgartools 평가 및 Step1 구현
