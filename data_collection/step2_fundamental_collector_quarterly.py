"""
===========================================
Step2-Q: SEC 분기별 재무 데이터 수집
===========================================

이 파일의 역할:
- SEC EDGAR CompanyFacts API를 사용하여 분기별 재무 데이터 수집
- 기존 연간(10-K)만 수집하던 것을 분기(10-Q)도 함께 수집
- Q1, Q2, Q3, Q4(=연간) 모든 데이터 포함

주요 변경점 (vs step2_fundamental_collector.py):
1. extract_annual_data → extract_quarterly_data로 변경
2. form 필터: '10-K' + '10-Q' 모두 포함
3. 출력 경로: data_cache_quarterly/

출력 파일:
- data_cache_quarterly/step2_fund_quarterly.csv
  컬럼: Ticker, FiscalYear, FiscalQuarter, EndDate, Period, 
        Revenue, OI, NetIncome, RD, SGA, Equity, Shares, Sector
"""

import pandas as pd
import requests
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# 프로젝트 내부 모듈
from config.constants import (
    START_YEAR,
    SEC_HEADERS,
    API_SLEEP_SECONDS,
    XBRL_TAGS_TIERED,
    GICS_SECTOR_MAPPING
)
from config.paths_quarterly import (
    STEP2_FUNDAMENTALS_QUARTERLY_CSV,
    DATA_CACHE_QUARTERLY_DIR,
    STEP0_VALID_UNIVERSE_JSON,
    SEC_CACHE_DIR
)
from utils import (
    get_logger,
    log_section_header,
    log_dataframe_info,
    save_cache,
    load_cache,
    print_progress
)

# 로거 초기화
logger = get_logger(__name__)


class FundamentalCollectorQuarterly:
    """
    SEC 분기별 재무 데이터 수집 클래스
    
    주요 기능:
    - SEC EDGAR companyfacts API 사용
    - 연간(10-K) + 분기(10-Q) 재무제표 데이터 추출
    - 캐싱으로 중복 다운로드 방지 (기존 SEC 캐시 재사용)
    
    사용 예시:
        collector = FundamentalCollectorQuarterly()
        collector.run()
    """
    
    def __init__(self):
        """초기화"""
        self.start_year = START_YEAR
        self.sec_cache_dir = SEC_CACHE_DIR
        self.headers = SEC_HEADERS
        
        # 분기별 출력 디렉토리 생성
        DATA_CACHE_QUARTERLY_DIR.mkdir(parents=True, exist_ok=True)
        self.sec_cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"FundamentalCollectorQuarterly 초기화 완료")
        logger.info(f"  - 시작 연도: {self.start_year}")
        logger.info(f"  - SEC 캐시: {self.sec_cache_dir}")
        logger.info(f"  - 출력 폴더: {DATA_CACHE_QUARTERLY_DIR}")
    
    
    def load_cik_mapping(self) -> Dict[str, str]:
        """티커 → CIK 매핑 로드"""
        logger.info("티커→CIK 매핑 로드 중...")
        
        try:
            url = 'https://www.sec.gov/files/company_tickers.json'
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            cik_map = {}
            for item in data.values():
                ticker = item['ticker'].upper()
                cik = str(item['cik_str']).zfill(10)
                cik_map[ticker] = cik
            
            logger.info(f"✅ 티커→CIK 매핑 로드 완료: {len(cik_map):,}개")
            return cik_map
            
        except Exception as e:
            logger.error(f"❌ 티커→CIK 매핑 로드 실패: {e}")
            raise
    
    
    def fetch_companyfacts(
        self, 
        cik: str, 
        ticker: str
    ) -> Optional[Dict]:
        """SEC companyfacts API에서 재무 데이터 가져오기 (캐시 우선)"""
        cache_file = self.sec_cache_dir / f"CIK{cik}.json"
        
        # 캐시가 있으면 로드
        if cache_file.exists():
            logger.debug(f"  {ticker}: 캐시 사용 ({cik})")
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        # 캐시 없으면 API 호출
        try:
            url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
            logger.debug(f"  {ticker}: API 호출 중... ({cik})")
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # 캐시 저장
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            
            time.sleep(API_SLEEP_SECONDS)
            return data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"  {ticker}: CIK {cik} 데이터 없음 (404)")
            else:
                logger.error(f"  {ticker}: HTTP 에러 {e.response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"  {ticker}: companyfacts 수집 실패: {e}")
            return None
    
    
    def extract_quarterly_data(
        self,
        tag_data: Dict,
        fiscal_year_filter: int
    ) -> pd.DataFrame:
        """
        XBRL 태그 데이터에서 연간(10-K) + 분기(10-Q) 데이터 추출
        
        ⭐ 핵심 변경: form 필터에 '10-Q'도 포함
        
        Args:
            tag_data: companyfacts JSON의 특정 태그 데이터
            fiscal_year_filter: 이 연도 이상만 필터링
        
        Returns:
            pd.DataFrame: 분기별 데이터
                columns: fiscal_year, fiscal_quarter, end_date, value, form
        """
        if not tag_data or 'units' not in tag_data:
            return pd.DataFrame()
        
        units = tag_data['units']
        
        # 단위 선택 (USD > shares > pure)
        if 'USD' in units:
            unit_data = units['USD']
        elif 'shares' in units:
            unit_data = units['shares']
        elif 'pure' in units:
            unit_data = units['pure']
        else:
            unit_data = next(iter(units.values()))
        
        # ⭐ 연간 + 분기 데이터 모두 필터링
        quarterly_records = []
        for item in unit_data:
            form = item.get('form', '')
            
            # ⭐ 10-K (연간) + 10-Q (분기) 모두 포함
            if form not in ['10-K', '10-Q']:
                continue
            
            fy = item.get('fy')
            fp = item.get('fp', '')  # 'Q1', 'Q2', 'Q3', 'FY'
            
            if not fy or int(fy) < fiscal_year_filter:
                continue
            
            val = item.get('val')
            end_date = item.get('end')
            
            if val is not None and end_date:
                # 분기 결정: FY(10-K)는 Q4로 처리
                if form == '10-K' or fp == 'FY':
                    fiscal_quarter = 4
                elif fp == 'Q1':
                    fiscal_quarter = 1
                elif fp == 'Q2':
                    fiscal_quarter = 2
                elif fp == 'Q3':
                    fiscal_quarter = 3
                else:
                    # fp가 없거나 알 수 없는 경우 end_date로 분기 추정
                    fiscal_quarter = self._infer_quarter_from_date(end_date)
                
                quarterly_records.append({
                    'fiscal_year': int(fy),
                    'fiscal_quarter': fiscal_quarter,
                    'end_date': end_date,
                    'value': float(val),
                    'form': form
                })
        
        if quarterly_records:
            df = pd.DataFrame(quarterly_records)
            # 중복 제거: 같은 (fiscal_year, fiscal_quarter)가 있으면 최신 end_date 우선
            df = df.sort_values('end_date', ascending=False)
            df = df.drop_duplicates(subset=['fiscal_year', 'fiscal_quarter'], keep='first')
            return df
        else:
            return pd.DataFrame()
    
    
    def _infer_quarter_from_date(self, end_date: str) -> int:
        """날짜로부터 분기 추정"""
        try:
            month = int(end_date.split('-')[1])
            if month <= 3:
                return 1
            elif month <= 6:
                return 2
            elif month <= 9:
                return 3
            else:
                return 4
        except:
            return 4
    
    
    def parse_financials_quarterly(
        self,
        ticker: str,
        companyfacts: Dict
    ) -> Optional[pd.DataFrame]:
        """
        companyfacts JSON에서 분기별 재무 필드 추출
        
        필수 필드:
        - Revenue, OI, NetIncome, RD, SGA, Equity, Shares
        
        Returns:
            pd.DataFrame: 분기별 재무 데이터
                columns: Ticker, FiscalYear, FiscalQuarter, Period, EndDate,
                         Revenue, OI, NetIncome, RD, SGA, Equity, Shares
        """
        if not companyfacts:
            return None
            
        try:
            facts = companyfacts.get('facts', {})
            us_gaap = facts.get('us-gaap', {})
            dei = facts.get('dei', {})  # EntityCommonStockSharesOutstanding 등
            
            if not us_gaap and not dei:
                logger.warning(f"  {ticker}: us-gaap/dei 데이터 없음")
                return None
            
            # 모든 facts 병합 (us-gaap + dei)
            all_facts = {**us_gaap, **dei}
            
            # XBRL 태그 매핑 생성
            tag_mappings = {}
            for field_name, tier_config in XBRL_TAGS_TIERED.items():
                all_tags = []
                if 'Tier1' in tier_config:
                    all_tags.extend(tier_config['Tier1'])
                if 'Tier2' in tier_config:
                    all_tags.extend(tier_config['Tier2'])
                elif 'Tier2_Fallback' in tier_config:
                    all_tags.extend(tier_config['Tier2_Fallback'])
                if 'Tier3_Broad' in tier_config:
                    all_tags.extend(tier_config['Tier3_Broad'])
                if 'IFRS' in tier_config:
                    all_tags.extend(tier_config['IFRS'])
                tag_mappings[field_name] = all_tags
            
            # 각 필드 추출
            field_dfs = {}
            end_dates_df = None
            
            for field, possible_tags in tag_mappings.items():
                all_dfs = []
                
                for tag in possible_tags:
                    if tag in all_facts:
                        df = self.extract_quarterly_data(all_facts[tag], self.start_year)
                        if not df.empty:
                            df = df.rename(columns={'value': field})
                            all_dfs.append(df[['fiscal_year', 'fiscal_quarter', 'end_date', field]])
                
                if all_dfs:
                    if len(all_dfs) == 1:
                        combined_df = all_dfs[0]
                    else:
                        combined_df = pd.concat(all_dfs, ignore_index=True)
                        combined_df = combined_df.sort_values('end_date', ascending=False)
                        combined_df = combined_df.drop_duplicates(
                            subset=['fiscal_year', 'fiscal_quarter'], 
                            keep='first'
                        )
                    
                    if end_dates_df is None:
                        end_dates_df = combined_df[['fiscal_year', 'fiscal_quarter', 'end_date']].copy()
                    
                    field_dfs[field] = combined_df[['fiscal_year', 'fiscal_quarter', field]].copy()
            
            if not field_dfs:
                logger.warning(f"  {ticker}: 필수 필드 없음")
                return None
            
            # 모든 필드 병합
            result = None
            for field, df in field_dfs.items():
                if result is None:
                    result = df
                else:
                    result = result.merge(
                        df,
                        on=['fiscal_year', 'fiscal_quarter'],
                        how='outer'
                    )
            
            # end_date 추가
            if end_dates_df is not None:
                result = result.merge(
                    end_dates_df,
                    on=['fiscal_year', 'fiscal_quarter'],
                    how='left'
                )
            
            # Ticker 추가
            result.insert(0, 'Ticker', ticker)
            
            # Period 컬럼 추가 (YYYY-QN 형식)
            result['Period'] = result['fiscal_year'].astype(str) + '-Q' + result['fiscal_quarter'].astype(str)
            
            # 컬럼 이름 정리
            result = result.rename(columns={
                'fiscal_year': 'FiscalYear',
                'fiscal_quarter': 'FiscalQuarter',
                'end_date': 'EndDate'
            })
            
            # 정렬
            result = result.sort_values(['FiscalYear', 'FiscalQuarter'])
            
            logger.debug(f"  {ticker}: {len(result)}건 분기 데이터 반환")
            return result
            
        except Exception as e:
            logger.error(f"  {ticker}: 재무 데이터 파싱 실패: {e}")
            return None
    
    
    def get_sector_info(self, ticker: str) -> str:
        """yfinance로 섹터 정보 수집"""
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            info = stock.info
            
            raw_sector = info.get('sector', None)
            
            if not raw_sector:
                return 'Unknown'
            
            mapped_sector = GICS_SECTOR_MAPPING.get(raw_sector, raw_sector)
            return mapped_sector
            
        except Exception as e:
            logger.warning(f"  {ticker}: 섹터 수집 실패 ({e}) → Unknown")
            return 'Unknown'
    
    
    def run(self):
        """
        전체 파이프라인 실행
        
        실행 순서:
        1. Step 0 유니버스에서 티커/CIK/섹터 로드
        2. SEC companyfacts 수집 (기존 캐시 재사용)
        3. 분기별 재무 데이터 파싱
        4. 캐시 저장 (data_cache_quarterly/)
        """
        log_section_header(logger, "Step2-Q: SEC 분기별 재무 데이터 수집 시작")
        
        # Step 0 유니버스 로드
        if STEP0_VALID_UNIVERSE_JSON.exists():
            logger.info("📜 Step 0 유니버스에서 티커/CIK/섹터 로드")
            with open(STEP0_VALID_UNIVERSE_JSON, 'r', encoding='utf-8') as f:
                universe = json.load(f)
            
            tickers = [item['ticker'] for item in universe]
            cik_map = {item['ticker']: item['cik'] for item in universe}
            sector_map = {item['ticker']: item['sector'] for item in universe}
            
            logger.info(f"  → 유효 티커: {len(tickers)}개")
        else:
            logger.error("❌ Step 0 유니버스 없음! 먼저 step0_universe_filter.py 실행 필요")
            return
        
        # 분기별 재무 데이터 수집
        logger.info(f"SEC 분기별 재무 데이터 수집 중... (총 {len(tickers)}개 티커)")
        
        all_financials = []
        success_count = 0
        fail_count = 0
        
        from tqdm import tqdm
        
        for ticker in tqdm(tickers, desc="SEC 분기 데이터 수집"):
            try:
                cik = cik_map.get(ticker)
                
                if not cik:
                    fail_count += 1
                    continue
                
                # SEC 데이터 다운로드 (캐시 우선)
                companyfacts = self.fetch_companyfacts(cik, ticker)
                
                if companyfacts is None:
                    fail_count += 1
                    continue
                
                # ⭐ 분기별 재무 데이터 파싱
                quarterly_financials = self.parse_financials_quarterly(ticker, companyfacts)
                
                if quarterly_financials is None or quarterly_financials.empty:
                    fail_count += 1
                else:
                    quarterly_financials['Sector'] = sector_map.get(ticker, 'Unknown')
                    all_financials.append(quarterly_financials)
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"  {ticker}: 수집 실패 - {e}")
                fail_count += 1
        
        logger.info(f"✅ SEC 분기 데이터 수집 완료")
        logger.info(f"  - 성공: {success_count}개")
        logger.info(f"  - 실패: {fail_count}개")
        
        if all_financials:
            fund_df = pd.concat(all_financials, ignore_index=True)
            fund_df = fund_df.sort_values(['Ticker', 'FiscalYear', 'FiscalQuarter'])
            
            # 데이터 확인
            log_dataframe_info(logger, fund_df, "분기별 재무 데이터")
            
            # 분기별 통계
            q_counts = fund_df.groupby('FiscalQuarter').size()
            logger.info(f"  - Q1: {q_counts.get(1, 0):,}건")
            logger.info(f"  - Q2: {q_counts.get(2, 0):,}건")
            logger.info(f"  - Q3: {q_counts.get(3, 0):,}건")
            logger.info(f"  - Q4: {q_counts.get(4, 0):,}건")
            
            # 캐시 저장
            save_cache(fund_df, STEP2_FUNDAMENTALS_QUARTERLY_CSV)
            logger.info(f"✅ 분기별 재무 데이터 저장 완료")
            logger.info(f"  - 파일: {STEP2_FUNDAMENTALS_QUARTERLY_CSV}")
        else:
            logger.error("❌ 수집된 데이터 없음!")
        
        log_section_header(logger, "Step2-Q: SEC 분기별 재무 데이터 수집 완료")


# ===========================================
# 메인 실행
# ===========================================

if __name__ == '__main__':
    """
    실행 방법:
        python -m data_collection.step2_fundamental_collector_quarterly
    """
    collector = FundamentalCollectorQuarterly()
    collector.run()
