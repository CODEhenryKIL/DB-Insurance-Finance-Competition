"""
===========================================
Step 0: 유니버스 빌더 (Universe Filter)
===========================================

이 파일의 역할:
- API 호출 전 유효 기업을 미리 확정
- ETF/SPAC/뮤추얼펀드 제외
- 제외 섹터 필터링 (Financials, Utilities, Energy, Materials, Real Estate)
- SEC CIK 매핑 수행

주요 기능:
1. yfinance fast_info로 메타데이터 조회 (가벼움)
2. quoteType이 EQUITY인 것만 남김
3. 제외 섹터 필터링
4. SEC CIK 번호 매핑

출력 파일:
- data_cache/step0_valid_universe.json
  구조: [{"ticker": "AAPL", "cik": "0000320193", "sector": "Technology"}, ...]
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
import time
import requests
import yfinance as yf
from typing import List, Dict, Optional, Tuple
from tqdm import tqdm

from config.constants import (
    EXCLUDED_SECTORS,
    SEC_HEADERS,
    API_SLEEP_SECONDS,
    TEST_MODE,
    TEST_TICKERS,
    MARKET_MODE,
    GICS_SECTOR_MAPPING
)
from config.paths import (
    CACHE_DIR,
    STEP0_VALID_UNIVERSE_JSON
)
from utils.logger import get_logger, log_section_header

logger = get_logger(__name__)


class UniverseBuilder:
    """
    유니버스 빌더 클래스
    
    API 호출 전 유효 기업을 확정하여
    불필요한 데이터 수집을 방지합니다.
    """
    
    def __init__(self):
        """초기화"""
        self.excluded_sectors = EXCLUDED_SECTORS
        self.cik_mapping: Dict[str, str] = {}
        
        logger.info("UniverseBuilder 초기화 완료")
        logger.info(f"  - 제외 섹터: {self.excluded_sectors}")
    
    def get_raw_ticker_list(self) -> List[str]:
        """
        원본 티커 리스트 수집
        
        TEST_MODE=True: 테스트 티커
        MARKET_MODE='SP500': S&P 500
        MARKET_MODE='FULL': 전체 미국 시장
        """
        # 테스트 모드
        if TEST_MODE:
            logger.info("⚠️  TEST MODE: 테스트 티커 사용")
            return TEST_TICKERS
        
        # FULL 시장 모드
        if MARKET_MODE == 'FULL':
            logger.info("🌍 FULL MARKET MODE: 전체 미국 시장")
            ticker_file = CACHE_DIR / 'us_market_tickers.txt'
            
            if not ticker_file.exists():
                raise FileNotFoundError(f"티커 파일 없음: {ticker_file}")
            
            with open(ticker_file, 'r') as f:
                tickers = [line.strip() for line in f if line.strip()]
            
            logger.info(f"  → 티커 파일에서 로드: {len(tickers)}개")
            return tickers
        
        # S&P 500 모드 (기본)
        logger.info("📈 S&P500 모드: Wikipedia에서 수집")
        return self._fetch_sp500_tickers()
    
    def _fetch_sp500_tickers(self) -> List[str]:
        """Wikipedia에서 S&P500 티커 수집"""
        import pandas as pd
        import io
        
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            tables = pd.read_html(io.StringIO(response.text), match='Symbol')
            df = tables[0]
            tickers = df['Symbol'].tolist()
            
            # '.' → '-' 변환 (yfinance 호환)
            tickers = [t.replace('.', '-') for t in tickers]
            
            logger.info(f"✅ S&P500 티커 수집 완료: {len(tickers)}개")
            return tickers
            
        except Exception as e:
            logger.error(f"❌ S&P500 수집 실패: {e}")
            # Fallback 티커
            return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
    
    def load_cik_mapping(self) -> Dict[str, str]:
        """
        SEC 티커→CIK 매핑 로드
        
        Returns:
            {ticker: cik_10자리} 딕셔너리
        """
        logger.info("SEC 티커→CIK 매핑 로드 중...")
        
        try:
            url = 'https://www.sec.gov/files/company_tickers.json'
            response = requests.get(url, headers=SEC_HEADERS, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            cik_map = {}
            for item in data.values():
                ticker = item['ticker'].upper()
                cik = str(item['cik_str']).zfill(10)
                cik_map[ticker] = cik
            
            logger.info(f"✅ CIK 매핑 로드 완료: {len(cik_map):,}개")
            self.cik_mapping = cik_map
            return cik_map
            
        except Exception as e:
            logger.error(f"❌ CIK 매핑 로드 실패: {e}")
            return {}
    
    def normalize_sector(self, sector: Optional[str]) -> str:
        """
        섹터 이름 표준화 (GICS 11개 대분류)
        """
        if not sector or sector == 'Unknown':
            return 'Unknown'
        
        # GICS_SECTOR_MAPPING에서 매핑
        return GICS_SECTOR_MAPPING.get(sector, sector)
    
    def check_ticker_validity(
        self, 
        ticker: str
    ) -> Tuple[bool, Optional[Dict]]:
        """
        개별 티커 유효성 검사
        
        검사 항목:
        1. quoteType이 EQUITY인지 (ETF, SPAC, Fund 제외)
        2. 섹터가 제외 대상인지
        3. CIK 매핑 존재 여부
        
        Returns:
            (is_valid, metadata_dict)
        """
        try:
            stock = yf.Ticker(ticker)
            
            # fast_info 사용 (가벼움)
            try:
                fast_info = stock.fast_info
                quote_type = getattr(fast_info, 'quote_type', None)
            except:
                quote_type = None
            
            # info에서 추가 정보 (필요시)
            try:
                info = stock.info
                quote_type = quote_type or info.get('quoteType', 'Unknown')
                sector_raw = info.get('sector', 'Unknown')
                industry = info.get('industry', 'Unknown')
                long_name = info.get('longName', ticker)
            except:
                sector_raw = 'Unknown'
                industry = 'Unknown'
                long_name = ticker
            
            # Filter 1: quoteType이 EQUITY인지
            if quote_type and quote_type.upper() not in ['EQUITY', 'STOCK']:
                logger.debug(f"  {ticker}: 주식 아님 (type={quote_type}) → 제외")
                return False, None
            
            # 섹터 표준화
            sector = self.normalize_sector(sector_raw)
            
            # Filter 2: 제외 섹터
            if sector in self.excluded_sectors:
                logger.debug(f"  {ticker}: 제외 섹터 ({sector}) → 제외")
                return False, None
            
            # Filter 3: CIK 매핑 존재
            cik = self.cik_mapping.get(ticker.upper())
            if not cik:
                logger.debug(f"  {ticker}: CIK 없음 → 제외")
                return False, None
            
            # 유효한 티커
            metadata = {
                'ticker': ticker.upper(),
                'cik': cik,
                'sector': sector,
                'industry': industry,
                'name': long_name
            }
            
            return True, metadata
            
        except Exception as e:
            logger.debug(f"  {ticker}: 조회 실패 ({e}) → 제외")
            return False, None
    
    def build_universe(self) -> List[Dict]:
        """
        유효 유니버스 구축
        
        Returns:
            유효 티커 메타데이터 리스트
        """
        log_section_header(logger, "Step 0: 유니버스 빌더 시작")
        
        # 1. 원본 티커 리스트 수집
        logger.info("[1단계] 원본 티커 리스트 수집")
        raw_tickers = self.get_raw_ticker_list()
        logger.info(f"  → 원본 티커: {len(raw_tickers)}개")
        
        # 2. CIK 매핑 로드
        logger.info("[2단계] SEC CIK 매핑 로드")
        self.load_cik_mapping()
        
        # 3. 개별 티커 검증
        logger.info("[3단계] 개별 티커 유효성 검사")
        valid_universe = []
        
        # 통계
        stats = {
            'total': len(raw_tickers),
            'not_equity': 0,
            'excluded_sector': 0,
            'no_cik': 0,
            'error': 0,
            'valid': 0
        }
        
        for ticker in tqdm(raw_tickers, desc="티커 검증"):
            is_valid, metadata = self.check_ticker_validity(ticker)
            
            if is_valid and metadata:
                valid_universe.append(metadata)
                stats['valid'] += 1
            
            # Rate limiting
            time.sleep(API_SLEEP_SECONDS * 0.5)  # 가벼운 요청이므로 절반
        
        # 4. 결과 로깅
        logger.info("")
        logger.info("="*50)
        logger.info("  유니버스 빌더 결과")
        logger.info("="*50)
        logger.info(f"  원본 티커: {stats['total']:,}개")
        logger.info(f"  유효 티커: {stats['valid']:,}개 ({stats['valid']/stats['total']*100:.1f}%)")
        logger.info("")
        
        # 섹터별 분포
        sector_counts = {}
        for item in valid_universe:
            sec = item['sector']
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
        
        logger.info("  [섹터별 분포]")
        for sec, cnt in sorted(sector_counts.items(), key=lambda x: -x[1]):
            logger.info(f"    {sec:25s}: {cnt:4d}개")
        
        return valid_universe
    
    def save_universe(self, universe: List[Dict]) -> Path:
        """
        유니버스를 JSON으로 저장
        """
        output_path = STEP0_VALID_UNIVERSE_JSON
        
        # 디렉토리 생성
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(universe, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 유니버스 저장 완료: {output_path}")
        logger.info(f"  → {len(universe)}개 티커")
        
        return output_path
    
    def run(self) -> List[Dict]:
        """
        전체 파이프라인 실행
        """
        universe = self.build_universe()
        self.save_universe(universe)
        
        log_section_header(logger, "Step 0: 유니버스 빌더 완료")
        
        return universe


# ===========================================
# 유틸리티 함수
# ===========================================

def load_valid_universe() -> List[Dict]:
    """
    저장된 유니버스 로드 (다른 모듈에서 사용)
    """
    if not STEP0_VALID_UNIVERSE_JSON.exists():
        raise FileNotFoundError(
            f"유니버스 파일 없음: {STEP0_VALID_UNIVERSE_JSON}\n"
            "먼저 Step 0을 실행하세요: python -m data_collection.step0_universe_filter"
        )
    
    with open(STEP0_VALID_UNIVERSE_JSON, 'r', encoding='utf-8') as f:
        universe = json.load(f)
    
    logger.info(f"유니버스 로드 완료: {len(universe)}개 티커")
    return universe


def get_ticker_cik_mapping() -> Dict[str, str]:
    """
    유니버스에서 ticker→cik 매핑 추출
    """
    universe = load_valid_universe()
    return {item['ticker']: item['cik'] for item in universe}


def get_valid_tickers() -> List[str]:
    """
    유니버스에서 티커 리스트만 추출
    """
    universe = load_valid_universe()
    return [item['ticker'] for item in universe]


# ===========================================
# Main 실행
# ===========================================
if __name__ == '__main__':
    """
    콘솔에서 직접 실행 시
    """
    builder = UniverseBuilder()
    builder.run()
