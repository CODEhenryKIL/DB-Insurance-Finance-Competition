# M-Model 프로젝트 작업 현황

**업데이트**: 2026-01-31 01:45

---

## 🎯 현재 상태: S&P 500 실험 완료

### 최신 실험 결과 (exp_007_sp500_sector)

| 전략 | CAGR | Sharpe | MDD | Alpha | IR |
|------|------|--------|-----|-------|-----|
| **Benchmark** | 12.71% | 0.70 | -18.18% | - | - |
| Gap_5% | 12.34% | 0.58 | -20.96% | -1.82% | 0.03 |
| **SmallCap_5%** 🏆 | **17.91%** | **0.62** | -19.37% | -0.03% | **0.43** |

### 핵심 발견
- **SmallCap_5% + sector 모드**가 최적 조합
- CAGR 17.91% (벤치마크 대비 +5.20%p)
- 9년간 총 수익률 340% (벤치마크 194%의 1.75배)

---

## ✅ 완료된 작업

### 2026-01-31

1. **S&P 500 Historical Constituents 구축**
   - [x] Wikipedia에서 S&P 500 변경 이력 수집
   - [x] 연도별 구성종목 역산 (2012~2025)
   - [x] S&P 500 전용 재무 데이터 생성

2. **MARKET_MODE 분기 로직**
   - [x] `config/constants.py`에 MARKET_MODE 추가
   - [x] Step 3에 데이터 파일 분기 로직
   - [x] SP500 vs FULL 모드 전환 가능

3. **SmallCap 전략 복구**
   - [x] 시가총액 하위 50% 필터링
   - [x] SmallCap_5%, 10%, 20% 세 가지 버전

4. **실험 실행 및 기록**
   - [x] exp_006_sp500_raw (Y=raw)
   - [x] exp_007_sp500_sector (Y=sector)
   - [x] 가중치 히스토리 저장
   - [x] 연도별 수익률 저장
   - [x] EXPERIMENT_REPORT.md 작성

### 2026-01-30

- [x] v2.2.0 전체 파이프라인 실행 완료
- [x] Unknown 섹터 제외 (v2.1.2)
- [x] Step 1 데이터 검증 (v2.1.3)
- [x] exp_001~005 실험 완료

---

## 📁 실험 폴더 구조

```
experiments/
├── exp_001_baseline/          # 기본 설정
├── exp_002_y_raw/             # Y=raw 테스트
├── exp_003_stratified_split/  # 계층적 분할
├── exp_004_y_sector/          # Y=sector (FULL)
├── exp_005_y_raw/             # Y=raw (FULL)
├── exp_006_sp500_raw/         # S&P 500 + Y=raw ⭐
└── exp_007_sp500_sector/      # S&P 500 + Y=sector ⭐ BEST
```

---

## 📊 현재 설정

```python
# config/constants.py
MARKET_MODE = 'SP500'          # 'SP500' or 'FULL'
Y_TARGET_MODE = 'sector'       # 'raw' or 'sector'
TRAIN_WINDOW_YEARS = 3
LONG_RATIOS = [0.05, 0.10, 0.20, 0.30]
```

---

## 📝 대기 중 작업

### 단기
- [ ] 연도별 포트폴리오 구성 종목 분석
- [ ] 섹터별 성과 분해
- [ ] 가중치 변화 시각화

### 장기
- [ ] 생존 편향 해결 (S&P 500 제외 종목 추적)
- [ ] 거래 비용 시뮬레이션
- [ ] 실시간 신호 생성 시스템

---

## 📈 성과 요약 (2017-2025, 9년)

| 실험 | 최고 전략 | CAGR | vs 벤치마크 |
|------|----------|------|------------|
| exp_004 (FULL, sector) | Gap_10% | 8.12% | -4.64%p |
| exp_006 (SP500, raw) | SmallCap_5% | 12.56% | -0.13%p |
| **exp_007 (SP500, sector)** | **SmallCap_5%** | **17.91%** | **+5.20%p** 🏆 |

