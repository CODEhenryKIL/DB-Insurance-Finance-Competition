# M-Model 프로젝트 작업 현황

**업데이트**: 2026-02-13

---

## 🎯 현재 상태: v3.1.2 CLI 리팩터링 및 롤링 홀딩 완료

### 새로 추가된 기능 (v3.1.2)

#### 1. CLI 파라미터 기반 실험 실행
```bash
# 새로운 방식 (권장)
python run_experiment.py -u SP500 -s ALL -w 5 -f A -l RankNet -sl 3

# 가능한 조합 예시
python run_experiment.py -u SP500 -s BioIT -w 3 -f Q -l RankNet -sl 3
```

| 옵션 | 축약 | 선택지 | 기본값 |
|------|------|--------|--------|
| `--universe` | `-u` | SP500, FULL | SP500 |
| `--sector` | `-s` | ALL, BioIT | ALL |
| `--window` | `-w` | 3, 5 | 5 |
| `--freq` | `-f` | A, Q, S | A |
| `--loss` | `-l` | MSE, RankNet | RankNet |
| `--safe_lag` | `-sl` | 0, 3 | 3 |

#### 2. 분기/반기 롤링 12개월 홀딩
| 주기 | 리밸런싱 시점 | 홀딩 기간 | 동작 |
|------|--------------|----------|------|
| Annual | 12월 말 | 12개월 | 기존과 동일 |
| Quarterly | 3/6/9/12월 | **12개월** | 롤링 (4개 포트폴리오 동시 운용) |
| Semiannual | 6/12월 | **12개월** | 롤링 (2개 포트폴리오 동시 운용) |

#### 3. Safe Lag CLI 옵션
- `--safe_lag 0`: 12월 결산 → 12월 매수 (편향 있음)
- `--safe_lag 3`: 12월 결산 → 3월 매수 (무편향, 기본값)

### Safe Lag 실험 결과

| 실험 | Safe Lag | CAGR | 비고 |
|------|----------|------|------|
| exp_003 | 0 | 24.99% | 12월 매수 |
| exp_003_1 | 3 | **28.46%** | 3월 매수 (COVID 바닥) |
| exp_004 | 0 | 25.33% | 12월 매수 |
| exp_004_1 | 3 | **28.17%** | 3월 매수 (COVID 바닥) |

**발견**: Safe Lag=3이 더 높은 수익률 → FY2019 + 3월 = 2020년 COVID 바닥 매수 (타이밍 행운)

---

### 새로 추가된 기능 (v3.1.0)

#### 1. 리밸런싱 주기 옵션
| 주기 | 리밸런싱 시점 | 홀딩 기간 |
|------|--------------|----------|
| Annual | 12월 말 | 12개월 |
| Semiannual | 6월/12월 말 | 6개월 |
| Quarterly | 3/6/9/12월 말 | 3개월 |

#### 2. Safe Lag (Look-ahead Bias 방지)
- 10-Q 공시 지연 (~45일) 반영
- 분기실적 마감 후 **3개월 뒤** 리밸런싱
- 예: Q1(3월말) 실적 → 6월말 투자

#### 3. 섹터 필터 옵션
- `included_sectors` 파라미터 추가
- 바이오&IT 전용 실험: `['Healthcare', 'Technology']`

### 실험 계획 (14개 실험)

| # | Universe | Sector | Window | Frequency | Loss |
|---|----------|--------|--------|-----------|------|
| 1 | S&P 500 | All | 5y | Annual | MSE |
| 2 | S&P 500 | All | 5y | Annual | RankNet |
| 3 | S&P 500 | All | 5y | Semiannual | MSE |
| 4 | S&P 500 | All | 5y | Quarterly | MSE |
| 5-6 | S&P 500 | Bio&IT | 5y | Annual | MSE/RankNet |
| 7-8 | S&P 500 | Bio&IT | 5y | Semi | MSE/RankNet |
| 9-10 | S&P 500 | Bio&IT | 5y | Quarterly | MSE/RankNet |
| 11-14 | Rolling Window 3y vs 5y 비교 | ... | ... | ... |

---

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

### 2026-02-13

1. **v3.1.2 CLI 리팩터링**
   - [x] `run_experiment.py` 파라미터 기반으로 전면 재작성
   - [x] `-u`, `-s`, `-w`, `-f`, `-l`, `-sl` 축약 옵션 추가
   - [x] `--preset` deprecated (하위 호환 유지)
   - [x] 자동 실험 ID 및 이름 생성

2. **분기/반기 롤링 12개월 홀딩**
   - [x] `runner.py`에 `run_backtest_for_quarter()` 추가
   - [x] 분기별 포트폴리오 1년간 유지 (4개 동시 운용)
   - [x] `config.py` quarterly 프리셋 `holding_months=12`

3. **Safe Lag CLI 옵션화**
   - [x] `--safe_lag` / `-sl` 옵션 추가
   - [x] 기본값 3 (무편향)
   - [x] 실험 재실행 및 결과 검증 (exp_003_1, exp_004_1)

4. **Safe Lag 분석**
   - [x] Safe Lag=3 > Safe Lag=0 원인 분석
   - [x] COVID 2020년 3월 바닥 매수 타이밍 확인
   - [x] FY2019 단일 연도 105% 수익률 확인

### 2026-02-11

1. **v3.1.0 멀티 프리퀀시 파이프라인**
   - [x] Step3 분기/반기 feature builder 생성
   - [x] Step4 분기/반기 MSE trainer 생성
   - [x] Step4 분기/반기 RankNet trainer 생성
   - [x] Step5 분기/반기 backtester 생성

2. **Safe Lag 적용 (Look-ahead Bias 방지)**
   - [x] `SAFE_LAG_MONTHS = 3` 상수 추가
   - [x] 리밸런싱 시점에 Safe Lag 적용
   - [x] 분기/반기 backtest 모두 적용

3. **experiments/config.py 확장**
   - [x] `rebalance_frequency` 옵션 추가
   - [x] `included_sectors` 옵션 추가
   - [x] `safe_lag_months` 옵션 추가
   - [x] 바이오&IT 프리셋 함수 추가

### 2026-02-10

1. **v3.0.0 코드 리팩토링**
   - [x] `core/models.py` - MSE + RankNet 모델 통합
   - [x] `core/restatement.py` - 회계 재작성 로직 통합
   - [x] `config/settings.py` - 설정 파일 통합
   - [x] 7개 중복 파일 삭제
   - [x] 호환성 래퍼 생성 (기존 import 유지)
   - [x] 코드량 16% 감소 (9,013줄 → 7,549줄)

2. **v3.0.1 폴더 구조 정리**
   - [x] 문서 이동: CHANGELOG.md, PIPELINE_OVERVIEW.md, task.md → docs/
   - [x] 테스트 통합: test_*.py → tests/
   - [x] 빈 폴더 삭제: evaluation/, notebooks/, pipeline/
   - [x] 실험 폴더 통합: experiments_v2/ → experiments/

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

