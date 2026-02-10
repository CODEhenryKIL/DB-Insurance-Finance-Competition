# 분기별 재무 데이터 결손 분석 보고서

> **분석 일자:** 2026년 2월 8일  
> **데이터 소스:** `data_cache_quarterly/step2_fund_quarterly.csv`  
> **분석 방법:** pandas DataFrame의 `.isna().sum()` 메서드를 사용한 실측치 기반 분석

---

## 1. 데이터 개요

| 항목 | 수치 |
|------|------|
| 총 레코드 수 | 109,363 |
| 고유 티커 수 | 2,842 |
| 수집 대상 | 전체 미국 시장 (step0_valid_universe.json 기준 3,640개 중 수집 성공) |
| 데이터 기간 | FY 2012 ~ FY 2026 |
| 데이터 출처 | SEC EDGAR CompanyFacts API (10-K, 10-Q 보고서) |

---

## 2. 컬럼별 결손 비율

| 컬럼 | 설명 | 결손 수 | 결손 비율 | 유효 데이터 수 |
|------|------|---------|-----------|----------------|
| Revenue | 매출액 | 9,812 | 9.0% | 99,551 |
| OI | 영업이익 (Operating Income) | 3,219 | 2.9% | 106,144 |
| NetIncome | 순이익 | 138 | 0.1% | 109,225 |
| RD | 연구개발비 | 53,032 | 48.5% | 56,331 |
| SGA | 판매관리비 | 7,599 | 6.9% | 101,764 |
| Equity | 자기자본 | 192 | 0.2% | 109,171 |
| Shares | 발행주식수 | 2,776 | 2.5% | 106,587 |

### 결손 패턴 분석
- **모든 재무 항목이 결손인 행:** 0건 (0.0%)
- **1개 이상 유효한 데이터가 있는 행:** 109,363건 (100.0%)

---

## 3. 분기별 결손 비율 (Revenue 기준)

| 분기 | 총 레코드 | Revenue 결손 | 결손 비율 |
|------|-----------|--------------|-----------|
| Q1 | 27,440 | 2,585 | 9.4% |
| Q2 | 27,708 | 2,521 | 9.1% |
| Q3 | 28,169 | 2,542 | 9.0% |
| Q4 | 26,046 | 2,164 | 8.3% |

> Q4(연말)의 결손 비율이 상대적으로 낮음 — 10-K 보고서의 데이터 완결성이 높기 때문

---

## 4. 결손 원인 분석

### 4.1 RD (연구개발비) 결손율 48.5%
- **주요 원인:** 금융, 유틸리티, 부동산 등 R&D 보고 의무가 없는 섹터
- SEC 규정상 R&D 비용이 없거나 중요하지 않은 경우 별도 공시 불필요
- **해석:** 결손 = R&D 활동 미미 또는 없음

### 4.2 Revenue 결손율 9.0%
- 일부 기업의 XBRL 태그 불일치 (RevenueFromContractWithCustomerExcludingAssessedTax vs Revenues 등)
- 금융업종의 경우 Revenue 대신 InterestIncome, PremiumsEarned 등 사용

### 4.3 기타 항목 결손율 (<7%)
- XBRL 태그 다양성으로 인한 매칭 실패
- 일부 소형주의 상세 항목 미공시

---

## 5. 권장 결손 처리 방법

| 컬럼 | 결손율 | 권장 처리 방법 | 근거 |
|------|--------|----------------|------|
| RD | 48.5% | `fillna(0)` | R&D 미보고 = R&D 활동 없음 |
| Revenue | 9.0% | 해당 행 제외 (`dropna`) | 핵심 지표, 추정값 사용 부적절 |
| OI | 2.9% | 해당 행 제외 또는 forward fill | 상황에 따라 선택 |
| NetIncome | 0.1% | 해당 행 제외 | 결손율 극히 낮음 |
| SGA | 6.9% | `fillna(0)` 또는 제외 | 비용 항목 |
| Equity | 0.2% | 해당 행 제외 | 결손율 극히 낮음 |
| Shares | 2.5% | 전 분기 값 사용 (ffill) | 주식수는 변동 적음 |

### Python 코드 예시
```python
import pandas as pd

df = pd.read_csv('data_cache_quarterly/step2_fund_quarterly.csv')

# 1. 이상 연도 제거 (SEC 날짜 파싱 오류)
df = df[df['FiscalYear'] < 2030]

# 2. RD는 0으로 대체 (R&D 없는 기업)
df['RD'] = df['RD'].fillna(0)

# 3. 핵심 지표 결손 행 제거
df = df.dropna(subset=['Revenue', 'NetIncome', 'Equity'])

# 4. Shares는 전 분기 값으로 채우기
df = df.sort_values(['Ticker', 'FiscalYear', 'FiscalQuarter'])
df['Shares'] = df.groupby('Ticker')['Shares'].ffill()

print(f'정제 후 레코드 수: {len(df):,}')
```

---

## 6. 데이터 품질 이슈

### 6.1 FiscalYear 이상값
분석 중 발견된 이상 연도값:
- 43465, 43555, 43646, 43738, 43830, 43921, 44012

**원인:** SEC EDGAR의 일부 filing에서 날짜가 Excel 시리얼 넘버로 저장됨  
**해결:** `FiscalYear < 2030` 조건으로 필터링 (해당 레코드 10건 미만)

---

## 7. 분석 재현 코드

본 분석에 사용된 정확한 코드:

```python
#!/usr/bin/env python3
"""분기별 재무 데이터 결손 비율 분석"""
import pandas as pd

df = pd.read_csv('data_cache_quarterly/step2_fund_quarterly.csv')

print(f'총 레코드 수: {len(df):,}')
print(f'고유 티커 수: {df["Ticker"].nunique()}')

financial_cols = ['Revenue', 'OI', 'NetIncome', 'RD', 'SGA', 'Equity', 'Shares']

for col in financial_cols:
    missing = df[col].isna().sum()
    missing_pct = missing / len(df) * 100
    valid = len(df) - missing
    print(f'{col}: 결손 {missing:,}건 ({missing_pct:.1f}%), 유효 {valid:,}건')

# 모든 재무 데이터가 결손인 행
all_missing = df[financial_cols].isna().all(axis=1).sum()
print(f'모든 항목 결손: {all_missing:,}건')

# 하나라도 유효한 데이터가 있는 행  
any_valid = df[financial_cols].notna().any(axis=1).sum()
print(f'1개 이상 유효: {any_valid:,}건')
```

---

## 8. 참고사항

- 본 분석은 SEC EDGAR CompanyFacts API에서 수집한 10-K(연간) 및 10-Q(분기) 보고서 기반
- XBRL 태그 매핑은 `config/constants.py`의 `XBRL_TAGS_TIERED` 설정 사용
- 수집 스크립트: `data_collection/step2_fundamental_collector_quarterly.py`

---

*문서 작성일: 2026-02-08*
