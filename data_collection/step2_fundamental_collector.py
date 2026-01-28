"""
===========================================
Step2: SEC 재무 데이터 수집
===========================================

이 파일의 역할:
- SEC EDGAR CompanyFacts API를 사용하여 재무 데이터 수집
- 티커 → CIK 변환
- 연간 재무제표 데이터 추출
- 2010년 이후 데이터 필터링

주요 클래스:
- FundamentalCollector: 재무 데이터 수집 메인 클래스

주요 메소드:
1. load_cik_mapping(): 티커→CIK 매핑 로드
2. fetch_companyfacts(): SEC API로 companyfacts 데이터 수집
3. parse_financials(): 재무제표 파싱
4. extract_annual_data(): 연간(FY) 데이터만 추출
5. save_to_cache(): 캐시 저장

전체 흐름:
1. Step1에서 티커 리스트 로드
2. 티커 → CIK 매핑
3. 각 CIK에 대해 companyfacts JSON 다운로드 및 캐시
4. JSON에서 필수 필드 추출: Revenue, OI, NetIncome, RD, SGA, Equity
5. 연간(10-K) 데이터만 필터링
6. 2010년 이후 데이터만 선택
7. step2_fund_annual.csv 저장

출력 파일:
- data_cache/step2_fund_annual.csv
- data_cache/sec_companyfacts/*.json (raw 캐시)

SEC CompanyFacts API:
- URL: https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json
- User-Agent 필수!
- Rate limit: 10 requests/second (우리는 더 보수적으로 0.15초 간격)
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
from config.paths import (
    STEP1_META_JSON,
    STEP2_FUNDAMENTALS_CSV,
    DATA_CACHE_DIR
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

# SEC companyfacts 캐시 디렉토리
SEC_CACHE_DIR = DATA_CACHE_DIR / 'sec_companyfacts'


# ===========================================
# FundamentalCollector 클래스
# ===========================================

class FundamentalCollector:
    """
    SEC 재무 데이터 수집 클래스
    
    주요 기능:
    - SEC EDGAR companyfacts API 사용
    - 연간 재무제표 데이터 추출
    - 캐싱으로 중복 다운로드 방지
    
    사용 예시:
        collector = FundamentalCollector()
        collector.run()
    """
    
    def __init__(self):
        """
        FundamentalCollector 초기화
        
        설정 항목:
        - start_year: 데이터 필터링 시작 연도
        - sec_cache_dir: SEC raw 데이터 캐시 디렉토리
        - headers: SEC API 요청 헤더 (User-Agent 포함)
        """
        self.start_year = START_YEAR
        self.sec_cache_dir = SEC_CACHE_DIR
        self.headers = SEC_HEADERS
        
        # 캐시 디렉토리 생성
        self.sec_cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"FundamentalCollector 초기화 완료")
        logger.info(f"  - 시작 연도: {self.start_year}")
        logger.info(f"  - SEC 캐시: {self.sec_cache_dir}")
        logger.info(f"  - User-Agent: {self.headers['User-Agent'][:50]}...")
    
    
    def load_cik_mapping(self) -> Dict[str, str]:
        """
        티커 → CIK 매핑을 로드합니다.
        
        SEC가 제공하는 ticker-CIK 매핑 JSON 사용
        URL: https://www.sec.gov/files/company_tickers.json
        
        Returns:
            Dict[str, str]: {ticker: CIK} 딕셔너리
        
        사용 예시:
            cik_map = collector.load_cik_mapping()
            # → {'AAPL': '320193', 'MSFT': '789019', ...}
        """
        logger.info("티커→CIK 매핑 로드 중...")
        
        try:
            # SEC에서 공식 매핑 파일 다운로드
            url = 'https://www.sec.gov/files/company_tickers.json'
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # JSON 파싱
            # 형식: {0: {cik_str: ..., ticker: ..., title: ...}, 1: {...}, ...}
            data = response.json()
            
            # 티커 → CIK10자리 문자열 변환
            cik_map = {}
            for item in data.values():
                ticker = item['ticker'].upper()
                # CIK는 10자리로 zero-padding
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
        """
        SEC companyfacts API에서 재무 데이터를 가져옵니다.
        
        캐시가 있으면 캐시 사용, 없으면 API 호출 후 캐시 저장
        
        Args:
            cik: 10자리 CIK 문자열
            ticker: 티커 심볼
        
        Returns:
            Dict: companyfacts JSON 데이터
            None: 실패 시
        
        사용 예시:
            facts = collector.fetch_companyfacts('0000320193', 'AAPL')
        """
        # 캐시 파일 경로
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
            
            # API rate limit 준수
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
    
    
    def extract_annual_data(
        self,
        tag_data: Dict,
        fiscal_year_filter: int
    ) -> pd.DataFrame:
        """
        XBRL 태그 데이터에서 연간(10-K) 데이터만 추출합니다.
        
        Args:
            tag_data: companyfacts JSON의 특정 태그 데이터
                     예: facts['dei']['EntityCommonStockSharesOutstanding']
            fiscal_year_filter: 이 연도 이상만 필터링
        
        Returns:
            pd.DataFrame: 연간 데이터 (columns: fiscal_year, end_date, value)
        
        로직:
        1. 'units' 키에서 적절한 단위 선택 (USD, shares 등)
        2. 각 데이터 포인트에서 'form' 필드 확인
        3. form이 '10-K'인 것만 선택 (연간 보고서)
        4. fiscal_year >= fiscal_year_filter인 것만
        """
        if not tag_data or 'units' not in tag_data:
            return pd.DataFrame()
        
        # units에서 가장 적절한 단위 선택
        # 보통 'USD', 'shares', 'pure' 등
        units = tag_data['units']
        
        # USD가 있으면 USD 우선, 없으면 첫 번째 단위
        if 'USD' in units:
            unit_data = units['USD']
        elif 'shares' in units:
            unit_data = units['shares']
        elif 'pure' in units:
            unit_data = units['pure']
        else:
            # 첫 번째 단위 사용
            unit_data = next(iter(units.values()))
        
        # 연간 데이터만 필터링
        annual_records = []
        for item in unit_data:
            # form 필드 확인 (10-K: 연간, 10-Q: 분기)
            form = item.get('form', '')
            
            # 10-K만 선택
            if form != '10-K':
                continue
            
            # fiscal year 확인
            fy = item.get('fy')
            if not fy or int(fy) < fiscal_year_filter:
                continue
            
            # 값 추출
            val = item.get('val')
            end_date = item.get('end')  # YYYY-MM-DD 형식
            
            if val is not None and end_date:
                annual_records.append({
                    'fiscal_year': int(fy),
                    'end_date': end_date,
                    'value': float(val)
                })
        
        # DataFrame 변환
        if annual_records:
            df = pd.DataFrame(annual_records)
            # 최신 데이터 우선 (같은 fiscal_year 있을 수 있음)
            df = df.sort_values('end_date', ascending=False)
            df = df.drop_duplicates(subset=['fiscal_year'], keep='first')
            return df
        else:
            return pd.DataFrame()
    
    
    def parse_financials(
        self,
        ticker: str,
        companyfacts: Dict
    ) -> Optional[pd.DataFrame]:
        """
        companyfacts JSON에서 필수 재무 필드를 추출합니다.
        
        필수 필드:
        - Revenue: 매출
        - OperatingIncome (OI): 영업이익
        - NetIncome: 순이익
        - ResearchAndDevelopmentExpense (RD): R&D 비용
        - SellingGeneralAndAdministrativeExpense (SGA): 판관비
        - StockholdersEquity (Equity): 자본

        Args:
            ticker: 티커 심볼
            companyfacts: companyfacts JSON 데이터
        
        Returns:
            pd.DataFrame: 연간 재무 데이터
                        columns: Ticker, FiscalYear, EndDate, Revenue, OI, NetIncome, RD, SGA, Equity
            None: 실패 시
        """
        try:
            facts = companyfacts.get('facts', {})
            us_gaap = facts.get('us-gaap', {})
            
            if not us_gaap:
                logger.warning(f"  {ticker}: us-gaap 데이터 없음")
                return None
            
            
            # ===========================================
            # 확장된 XBRL 태그 매핑 (Source 기반)
            # ===========================================
            # XBRL_TAGS_TIERED의 모든 태그를 병합 방식으로 수집
            # 
            # 전략:
            # 1. 여러 태그의 데이터를 모두 수집
            # 2. fiscal_year 기준으로 병합
            # 3. 동일 fiscal_year는 최신 end_date 우선
            # 
            # 출처: Source 761, 764, 478
            # ===========================================
            
            tag_mappings = {}
            
            # XBRL_TAGS_TIERED에서 tag_mappings 생성
            for field_name, tier_config in XBRL_TAGS_TIERED.items():
                all_tags = []
                
                # 모든 Tier의 태그 수집
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
            
            # 각 필드 추출 (기존 병합 로직)
            field_dfs = {}
            end_dates_df = None
            
            for field, possible_tags in tag_mappings.items():
                # 여러 태그의 데이터를 모두 수집
                all_dfs = []
                
                for tag in possible_tags:
                    if tag in us_gaap:
                        df = self.extract_annual_data(us_gaap[tag], self.start_year)
                        if not df.empty:
                            df = df.rename(columns={'value': field})
                            all_dfs.append(df[['fiscal_year', 'end_date', field]])
                
                # 여러 태그의 데이터 병합 (fiscal_year 기준, 최신 end_date 우선)
                if all_dfs:
                    if len(all_dfs) == 1:
                        combined_df = all_dfs[0]
                    else:
                        # 여러 DataFrame 합치기
                        combined_df = pd.concat(all_dfs, ignore_index=True)
                        # 같은 fiscal_year는 최신 end_date 것만 선택
                        combined_df = combined_df.sort_values('end_date', ascending=False)
                        combined_df = combined_df.drop_duplicates(subset=['fiscal_year'], keep='first')
                    
                    # end_date는 첫 번째 필드에서만 저장
                    if end_dates_df is None:
                        end_dates_df = combined_df[['fiscal_year', 'end_date']].copy()
                    
                    # fiscal_year와 value만 저장
                    field_dfs[field] = combined_df[['fiscal_year', field]].copy()
            
            
            # 모든 필드 병합
            if not field_dfs:
                logger.warning(f"  {ticker}: 필수 필드 없음")
                return None
            
            # fiscal_year 기준으로 모든 필드를 한 번에 병합
            result = None
            for field, df in field_dfs.items():
                if result is None:
                    result = df
                else:
                    result = result.merge(
                        df,
                        on='fiscal_year',
                        how='outer'
                    )
            
            # end_date 추가 (첫 번째 필드의 end_date 사용)
            if end_dates_df is not None:
                result = result.merge(
                    end_dates_df,
                    on='fiscal_year',
                    how='left'
                )
            
            # Ticker 추가
            result.insert(0, 'Ticker', ticker)
            
            # 컬럼 이름 정리
            result = result.rename(columns={
                'fiscal_year': 'FiscalYear',
                'end_date': 'EndDate'
            })
            
            logger.debug(f"  [유효성 검사 통과]  {len(result)}건 데이터 반환")        
            return result
            
        except Exception as e:
            logger.error(f"  {ticker}: 재무 데이터 파싱 실패: {e}")
            return None
    
    
    def get_sector_info(self, ticker: str) -> str:
        """
        yfinance로 섹터 정보 수집 후 GICS 표준 섹터로 매핑
        
        개선 2: 섹터 상대 PBR 계산을 위한 섹터 정보
        
        Parameters
        ----------
        ticker : str
            티커 심볼
        
        Returns
        -------
        str
            GICS 표준 섹터명 (매핑 실패 시 'Unknown')
        """
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # sector 필드 추출
            raw_sector = info.get('sector', None)
            
            if not raw_sector:
                logger.debug(f"  {ticker}: 섹터 정보 없음 → Unknown")
                return 'Unknown'
            
            # GICS 매핑
            mapped_sector = GICS_SECTOR_MAPPING.get(raw_sector, raw_sector)
            
            logger.debug(f"  {ticker}: {raw_sector} → {mapped_sector}")
            return mapped_sector
            
        except Exception as e:
            logger.warning(f"  {ticker}: 섹터 수집 실패 ({e}) → Unknown")
            return 'Unknown'
            
    
    def collect_fundamentals(
        self,
        tickers: List[str]
    ) -> pd.DataFrame:
        """
        여러 티커의 재무 데이터를 수집합니다.
        
        Args:
            tickers: 티커 리스트
        
        Returns:
            pd.DataFrame: 통합 재무 데이터
        """
        logger.info(f"재무 데이터 수집 중... (총 {len(tickers)}개 티커)")
        
        # CIK 매핑로드
        cik_map = self.load_cik_mapping()
        
        all_financials = []
        success_count = 0
        fail_count = 0
        
        # ⭐ 개선 2: 섹터 정보 수집
        logger.info("섹터 정보 수집 중...")
        sector_map = {}
        for ticker in tickers:
            sector = self.get_sector_info(ticker)
            sector_map[ticker] = sector
        logger.info(f"✅ 섹터 정보 수집 완료: {len(sector_map)}개")
        
        # 각 티커별로 재무 데이터 수집
        from tqdm import tqdm # tqdm 임포트 추가
        with tqdm(total=len(tickers), desc="SEC 데이터 수집") as pbar:
            for ticker in tickers:
                try:
                    # CIK 조회
                    if ticker not in cik_map:
                        logger.warning(f"  {ticker}: CIK 정보 없음 (건너뛰기)")
                        fail_count += 1
                        pbar.update(1)
                        continue
                    
                    cik = cik_map[ticker]
                    
                    # SEC 데이터 다운로드 및 파싱
                    # NOTE: collect_ticker_data는 기존 fetch_companyfacts와 parse_financials를 묶은 것으로 가정
                    companyfacts = self.fetch_companyfacts(cik, ticker)
                    annual_financials = self.parse_financials(ticker, companyfacts)
                    
                    if annual_financials is None or annual_financials.empty:
                        logger.warning(f"  {ticker}: 재무 데이터 없음")
                        fail_count += 1
                    else:
                        # ⭐ 섹터 정보 추가
                        annual_financials['Sector'] = sector_map.get(ticker, 'Unknown')
                        all_financials.append(annual_financials)
                        success_count += 1
                    
                except Exception as e:
                    logger.error(f"  {ticker}: 수집 실패 - {e}")
                    fail_count += 1
                
                pbar.update(1)
        
        logger.info(f"✅ SEC 데이터 수집 완료")
        logger.info(f"  - 성공: {success_count}개")
        logger.info(f"  - 실패: {fail_count}개")
        
         
        if all_financials:
            df = pd.concat(all_financials, ignore_index=True)
            df = df.sort_values(['Ticker', 'FiscalYear']) # Added this line to maintain original sorting logic
            return df
        else:
            logger.warning("수집된 데이터 없음")
            return pd.DataFrame()
    
    
    def save_to_cache(self, fund_df: pd.DataFrame):
        """
        재무 데이터를 캐시에 저장합니다.
        
        Args:
            fund_df: 재무 데이터 DataFrame
        """
        logger.info("캐시 저장 중...")
        
        save_cache(fund_df, STEP2_FUNDAMENTALS_CSV)
        
        logger.info(f"✅ 캐시 저장 완료")
        logger.info(f"  - 파일: {STEP2_FUNDAMENTALS_CSV}")
    
    
    def run(self):
        """
        전체 파이프라인을 실행합니다.
        
        실행 순서:
        1. Step1 메타 정보에서 티커 리스트 로드
        2. SEC companyfacts 수집
        3. 재무 데이터 파싱
        4. 캐시 저장
        """
        log_section_header(logger, "Step2: SEC 재무 데이터 수집 시작")
        
        # 1. Step1에서 티커 로드
        meta = load_cache(STEP1_META_JSON)
        tickers = meta['tickers']
        logger.info(f"Step1에서 {len(tickers)}개 티커 로드")
        
        # 2. 재무 데이터 수집
        fund_df = self.collect_fundamentals(tickers)
        
        if fund_df.empty:
            logger.error("❌ 수집된 데이터 없음!")
            return
        
        # 3. 데이터 확인
        log_dataframe_info(logger, fund_df, "재무 데이터")
        
        # 4. 캐시 저장
        self.save_to_cache(fund_df)
        
        log_section_header(logger, "Step2: SEC 재무 데이터 수집 완료")


# ===========================================
# 메인 실행
# ===========================================

if __name__ == '__main__':
    """
    이 파일을 직접 실행하면 Step2를 단독으로 실행합니다.
    
    실행 방법:
        python -m data_collection.step2_fundamental_collector
    """
    collector = FundamentalCollector()
    collector.run()
    
    def get_sector_info(self, ticker: str) -> str:
        """
        yfinance로 섹터 정보 수집 후 GICS 표준 섹터로 매핑
        
        개선 2: 섹터 상대 PBR 계산을 위한 섹터 정보
        
        Parameters
        ----------
        ticker : str
            티커 심볼
        
        Returns
        -------
        str
            GICS 표준 섹터명 (매핑 실패 시 'Unknown')
        """
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # sector 필드 추출
            raw_sector = info.get('sector', None)
            
            if not raw_sector:
                logger.debug(f"  {ticker}: 섹터 정보 없음 → Unknown")
                return 'Unknown'
            
            # GICS 매핑
            mapped_sector = GICS_SECTOR_MAPPING.get(raw_sector, raw_sector)
            
            logger.debug(f"  {ticker}: {raw_sector} → {mapped_sector}")
            return mapped_sector
            
        except Exception as e:
            logger.warning(f"  {ticker}: 섹터 수집 실패 ({e}) → Unknown")
            return 'Unknown'

