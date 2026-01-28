# SEC XBRL 태그 포괄적 매핑 가이드

## 📋 개요

이 문서는 S&P500 기업의 재무 데이터 수집 시 사용되는 모든 XBRL 태그를 정리한 것입니다.

SEC EDGAR CompanyFacts API는 XBRL 태그를 사용하여 재무 데이터를 제공하는데, 같은 재무 항목이라도 **회사마다, 연도마다, 산업마다 다른 태그를 사용**합니다.

## 🎯 핵심 원칙

1. **여러 태그 시도**: 한 필드당 5~10개의 가능한 태그를 모두 확인
2. **시간순 우선순위**: 최신 태그를 먼저 시도
3. **병합 전략**: 여러 태그의 데이터를 fiscal_year 기준으로 병합
4. **분리 보고 처리**: Microsoft/Google처럼 SGA를 분리 보고하는 경우 자동 합산

---

## 📊 필드별 XBRL 태그 매핑

### 1. Revenue (매출) ⭐ 가장 복잡

#### 배경
- **2018년 1월 31일**: `SalesRevenueNet` deprecated
- **2018년 이후**: ASC 606 도입으로 `RevenueFromContractWithCustomerExcludingAssessedTax` 사용
- **산업별 차이**: 금융, 유틸리티 등은 특수 태그 사용

#### 태그 리스트 (우선순위 순)

```python
'Revenue': [
    # 2018년 이후 표준
    'RevenueFromContractWithCustomerExcludingAssessedTax',  # ASC 606 (2018+)
    'RevenueFromContractWithCustomerIncludingAssessedTax',  # 세금 포함 버전
    
    # 일반적인 태그
    'Revenues',                          # 가장 보편적 (Apple, Exxon 등)
    'SalesRevenueNet',                   # 2018년 이전 (deprecated)
    'SalesRevenueGoodsNet',              # 제품 매출
    'SalesRevenueServicesNet',           # 서비스 매출
    
    # 산업별 특수 태그 (필터링되지만 포함)
    'RevenuesNetOfInterestExpense',      # 금융업
    'InterestAndDividendIncomeOperating',  # 금융업
    'RegulatedOperatingRevenue',         # 유틸리티
]
```

#### 실제 사례
- **AAPL**: `RevenueFromContractWithCustomerExcludingAssessedTax` (2019~2025)
- **MSFT**: `RevenueFromContractWithCustomerExcludingAssessedTax` (2018~2025)
- **XOM**: `Revenues` (2011~2024) + `RevenueFromContractWithCustomerExcludingAssessedTax` (2019~2021)

---

### 2. Operating Income (영업이익)

#### 태그 리스트

```python
'OI': [
    'OperatingIncomeLoss',  # 표준 태그 (대부분 기업)
    'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
    'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
    'OperatingIncome',  # 일부 기업
]
```

#### 특징
- 거의 모든 기업이 `OperatingIncomeLoss` 사용
- 변형이 적어 수집률 98%+

---

### 3. Net Income (순이익)

#### 태그 리스트

```python
'NetIncome': [
    'NetIncomeLoss',                                  # 표준 태그
    'ProfitLoss',                                     # IFRS 스타일
    'NetIncomeLossAvailableToCommonStockholdersBasic',  # 보통주 기준
    'NetIncomeLossAttributableToParent',              # 모회사 귀속
]
```

#### 특징
- 수집률 100%
- 가장 일관성 있는 필드

---

### 4. R&D Expense (연구개발비)

#### 배경
- US GAAP: R&D는 즉시 비용 처리
- IFRS: Development 단계는 자산화 가능 (우리는 US GAAP 기업만)

#### 태그 리스트

```python
'RD': [
    'ResearchAndDevelopmentExpense',  # 표준 태그
    'ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost',  # M&A 제외
    'ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost',  # 소프트웨어
]
```

#### 특징
- 수집률 100%
- 기술주는 거의 항상 보고

---

### 5. SG&A Expense (판매관리비) ⭐ 주의 필요

#### 배경
- 일부 기업(AAPL, XOM 등): 통합 보고
- **Microsoft, Google, Alphabet 등**: **General과 Selling을 분리 보고**

#### 태그 리스트

```python
# 통합 SGA
'SGA': [
    'SellingGeneralAndAdministrativeExpense',  # Apple, ExxonMobil 등
    'GeneralAndAdministrativeExpenses',        # 복수형 버전
]

# 분리 보고 - General
'SGA_General': [
    'GeneralAndAdministrativeExpense',   # Microsoft, Google
    'GeneralAndAdministrativeExpenses',  # 복수형
]

# 분리 보고 - Selling
'SGA_Selling': [
    'SellingAndMarketingExpense',  # Microsoft, Google
    'SellingExpense',              # 일부 기업
    'MarketingExpense',            # 마케팅만 별도
    'SellingExpenses',             # 복수형
]
```

#### 자동 합산 로직

```python
if 'SGA' not in field_dfs and ('SGA_General' in field_dfs or 'SGA_Selling' in field_dfs):
    # SGA = General + Selling (fiscal_year별로 합산)
    SGA = GeneralAndAdministrativeExpense + SellingAndMarketingExpense
```

#### 실제 사례
- **AAPL**: `SellingGeneralAndAdministrativeExpense` (통합)
- **MSFT**: `GeneralAndAdministrativeExpense` + `SellingAndMarketingExpense` (분리)
- **GOOGL**: `GeneralAndAdministrativeExpense` + `SellingAndMarketingExpense` (분리)

---

### 6. Stockholders' Equity (자본)

#### 태그 리스트

```python
'Equity': [
    'StockholdersEquity',  # 표준 태그
    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',  # NCI 포함
    'ShareholdersEquity',  # 동의어
    'PartnersCapital',     # 파트너십 형태 (드물지만)
    'MembersEquity',       # LLC 형태
]
```

#### 특징
- 수집률 100%
- Book Value 계산의 기초

---

## 📈 수집 통계 (4개 티커 테스트)

| 필드 | 수집률 | 결측 |
|------|--------|------|
| Revenue | 98.2% | XOM FY2010만 |
| OI | 98.2% | XOM FY2010만 |
| NetIncome | 100% | 없음 |
| RD | 100% | 없음 |
| SGA | 100% | 없음 ✅ |
| Equity | 100% | 없음 |

**전체 결측치: 3/513 (0.58%)**

---

## 🔍 섹터 필터링 정책

### 제외 섹터

```python
EXCLUDED_SECTORS = [
    'Financial Services',
    'Utilities',
    'Financial',
    'Financials'
]
```

### ⚠️ Energy(석유) 섹터는 제외되지 않습니다!

- **XOM (ExxonMobil)**: Energy 섹터이지만 **필터링되지 않음**
- 이유: `EXCLUDED_SECTORS`에 포함되지 않음
- 테스트에 XOM이 포함된 이유

### 섹터 필터링 근거

1. **Financial (금융업)**
   - 회계 구조가 제조업/서비스업과 완전히 다름
   - Revenue의 개념이 다름 (이자 수익 등)
   - OI(영업이익) 개념 불일치

2. **Utilities (유틸리티)**
   - 규제 산업으로 투자 패턴이 다름
   - 특수한 회계 처리
   - M-Model의 가정과 맞지 않음

---

## 💡 Best Practices

### 1. 태그 우선순위 설정

더 구체적이고 최신 태그를 앞에 배치:

```python
# ✅ Good
['RevenueFromContractWithCustomerExcludingAssessedTax',  # 구체적
 'Revenues',                                             # 일반적
 'SalesRevenueNet']                                      # 오래된 태그

# ❌ Bad
['Revenues',  # 너무 일반적인 태그가 먼저
 'RevenueFromContractWithCustomerExcludingAssessedTax']
```

### 2. 여러 태그 병합

**문제:** XOM Revenue 3개 연도만 수집 (2019~2021)
- 이유: `RevenueFromContractWithCustomerExcludingAssessedTax`가 2019~2021만 있음
- `Revenues` 태그는 2011~2024까지 있었지만 무시됨

**해결:**

```python
# 모든 매칭 태그의 데이터 수집
for tag in possible_tags:
    if tag in us_gaap:
        df = extract_annual_data(us_gaap[tag], start_year)
        if not df.empty:
            all_dfs.append(df)  # break 안 함!

# 병합
combined_df = pd.concat(all_dfs, ignore_index=True)
combined_df = combined_df.drop_duplicates(subset=['fiscal_year'], keep='first')
```

### 3. 분리 보고 처리

Microsoft/Google의 SGA 자동 합산:

```python
if 'SGA' not in field_dfs:
    if 'SGA_General' in field_dfs or 'SGA_Selling' in field_dfs:
        # fiscal_year별로 합산
        for fy in all_fiscal_years:
            general = get_value('SGA_General', fy) or 0
            selling = get_value('SGA_Selling', fy) or 0
            sga_combined[fy] = general + selling
```

---

## 🚀 향후 개선 방향

### S&P500 전체 수집 시

1. **더 많은 태그 추가**
   - 실제 500개 기업 수집 후 누락 태그 발견 시 추가
   - 산업별 특수 태그 확장

2. **Custom Extension 태그 처리**
   - 일부 기업은 자체 확장 태그 사용
   - 패턴 분석으로 자동 매핑

3. **품질 검증**
   - 수집 후 이상치 탐지
   - 연도별 급격한 변화 확인

---

## 📚 참고 자료

- [SEC EDGAR Company Facts API](https://data.sec.gov/api/xbrl/companyfacts/)
- [US GAAP Financial Reporting Taxonomy](https://www.fasb.org/xbrl)
- [SEC XBRL FAQ](https://www.sec.gov/structureddata/osd-faq-xbrl)
- [XBRL US](https://xbrl.us/)

---

## ✅ 요약

**현재 구현 상태:**
- ✅ Revenue: 9개 태그 (2018 전후 대응)
- ✅ OI: 4개 태그
- ✅ NetIncome: 4개 태그
- ✅ RD: 3개 태그
- ✅ SGA: 7개 태그 (분리 보고 자동 합산)
- ✅ Equity: 5개 태그
- ✅ 여러 태그 병합 로직
- ✅ fiscal_year 기준 중복 제거

**결과:**
- 4개 티커 테스트: **99.4% 수집 성공**
- 전체 S&P500 수집 시: **95%+ 예상**
