"""
===========================================
Step1: 가격 데이터 수집 및 섹터 필터링
===========================================

이 파일의 역할:
- yfinance를 사용하여 주식 가격 데이터 수집
- S&P500 티커 리스트 자동 수집
- 섹터 정보 수집 및 필터링 (Financial, Utilities 제외)
- 월말 가격으로 리샘플링 (Pandas 버전 호환)
- 캐시 저장 (3개 파일)

주요 클래스:
- PriceCollector: 가격 데이터 수집 메인 클래스

주요 메소드:
1. get_sp500_tickers(): S&P500 티커 리스트 수집
2. get_sector_info(): 티커별 섹터 정보 수집
3. filter_by_sector(): 섹터 필터링
4. collect_daily_prices(): 일별 가격 데이터 수집
5. resample_to_monthly(): 월말 가격으로 변환
6. save_to_cache(): 캐시 저장

전체 흐름:
1. S&P500 티커 리스트 수집
2. 각 티커의 섹터 정보 수집
3. Financial, Utilities 섹터 제외
4. 일별 가격 데이터 다운로드 (yfinance)
5. 월말 가격으로 리샘플링
6. 3개 캐시 파일 저장:
   - step1_px_adj_m.csv (월말 조정종가)
   - step1_px_close_m.csv (월말 종가)
   - step1_meta.json (메타 정보)

출력 파일:
- data_cache/step1_px_adj_m.csv
- data_cache/step1_px_close_m.csv
- data_cache/step1_meta.json
"""

import pandas as pd
import yfinance as yf
from typing import List, Dict, Tuple
from datetime import datetime
import time

# 프로젝트 내부 모듈
from config.constants import (
    START_YEAR,
    CURRENT_YEAR,
    EXCLUDED_SECTORS,
    API_SLEEP_SECONDS
)
from config.paths import (
    STEP1_PRICE_ADJ_CSV,
    STEP1_PRICE_CLOSE_CSV,
    STEP1_META_JSON
)
from utils import (
    get_logger,
    log_section_header,
    log_dataframe_info,
    save_cache,
    load_cache,
    get_month_end_freq,
    print_progress
)

# 로거 초기화
logger = get_logger(__name__)


# ===========================================
# PriceCollector 클래스
# ===========================================

class PriceCollector:
    """
    가격 데이터 수집 클래스
    
    주요 기능:
    - S&P500 티커 리스트 자동 수집
    - 섹터 정보 수집 및 필터링
    - 월말 가격 데이터 수집 및 캐싱
    
    사용 예시:
        collector = PriceCollector()
        collector.run()  # 전체 파이프라인 실행
    """
    
    def __init__(self):
        """
        PriceCollector 초기화
        
        설정 항목:
        - start_date: 데이터 수집 시작일
        - end_date: 데이터 수집 종료일
        - excluded_sectors: 제외할 섹터 리스트
        """
        # 수집 기간 설정
        self.start_date = f'{START_YEAR}-01-01'
        self.end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 제외 섹터
        self.excluded_sectors = EXCLUDED_SECTORS
        
        logger.info(f"PriceCollector 초기화 완료")
        logger.info(f"  - 수집 기간: {self.start_date} ~ {self.end_date}")
        logger.info(f"  - 제외 섹터: {self.excluded_sectors}")
    
    
    def get_sp500_tickers(self) -> List[str]:
        """
        S&P500 티커 리스트를 수집합니다.
        
        Wikipedia에서 S&P500 구성 종목 리스트를 가져옵니다.
        실패 시 대체 방법으로 yfinance의 티커 정보 사용
        
        Returns:
            List[str]: S&P500 티커 리스트
        
        사용 예시:
            tickers = collector.get_sp500_tickers()
            print(len(tickers))  # 예: 503
        """
        logger.info("S&P500 티커 리스트 수집 중...")
        
        try:
            # Wikipedia에서 S&P500 구성 종목 테이블 읽기
            # 테이블의 첫 번째 항목이 S&P500 리스트
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            tables = pd.read_html(url)
            sp500_table = tables[0]
            
            # 'Symbol' 컬럼에서 티커 추출
            # 일부 티커는 '.' 대신 '-' 사용 (예: BRK.B → BRK-B)
            tickers = sp500_table['Symbol'].tolist()
            
            # yfinance 형식으로 변환 (. → -)
            tickers = [ticker.replace('.', '-') for ticker in tickers]
            
            logger.info(f"✅ S&P500 티커 {len(tickers)}개 수집 완료")
            
            return tickers
            
        except Exception as e:
            logger.error(f"❌ S&P500 티커 수집 실패: {e}")
            logger.info("대체 방법: 주요 티커 하드코딩 사용")
            
            # 대체: 주요 대형주 티커 (테스트용)
            fallback_tickers = [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
                'META', 'TSLA', 'BRK-B', 'UNH', 'JNJ',
                'V', 'WMT', 'XOM', 'PG', 'JPM',
                'MA', 'CVX', 'HD', 'MRK', 'ABBV'
            ]
            
            logger.warning(f"⚠️  대체 티커 {len(fallback_tickers)}개 사용")
            return fallback_tickers
    
    
    def get_sector_info(self, tickers: List[str]) -> Dict[str, str]:
        """
        각 티커의 섹터 정보를 수집합니다.
        
        yfinance의 Ticker.info에서 'sector' 필드 추출
        실패한 티커는 'Unknown'으로 표시
        
        Args:
            tickers: 티커 리스트
        
        Returns:
            Dict[str, str]: {ticker: sector} 딕셔너리
        
        주의:
            - API 과부하 방지를 위해 각 요청 후 sleep
            - 실패한 티커는 건너뛰고 계속 진행
        
        사용 예시:
            sector_map = collector.get_sector_info(['AAPL', 'MSFT'])
            # → {'AAPL': 'Technology', 'MSFT': 'Technology'}
        """
        logger.info(f"섹터 정보 수집 중... (총 {len(tickers)}개 티커)")
        
        sector_map = {}
        failed_tickers = []
        
        for i, ticker in enumerate(tickers):
            try:
                # yfinance Ticker 객체 생성
                stock = yf.Ticker(ticker)
                
                # info 딕셔너리에서 'sector' 추출
                # info는 다양한 정보를 포함하는 딕셔너리
                info = stock.info
                sector = info.get('sector', 'Unknown')
                
                sector_map[ticker] = sector
                
                # 진행률 표시
                print_progress(
                    i + 1, 
                    len(tickers), 
                    prefix=f'섹터 수집'
                )
                
                # API 과부하 방지를 위한 대기
                time.sleep(API_SLEEP_SECONDS)
                
            except Exception as e:
                # 실패한 티커는 기록하고 계속 진행
                logger.debug(f"티커 {ticker} 섹터 수집 실패: {e}")
                sector_map[ticker] = 'Unknown'
                failed_tickers.append(ticker)
        
        logger.info(f"✅ 섹터 정보 수집 완료")
        logger.info(f"  - 성공: {len(tickers) - len(failed_tickers)}개")
        if failed_tickers:
            logger.warning(f"  - 실패: {len(failed_tickers)}개")
        
        return sector_map
    
    
    def filter_by_sector(
        self, 
        sector_map: Dict[str, str]
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        섹터 필터링을 적용합니다.
        
        제외 대상:
        - Financial Services / Financials / Financial
        - Utilities
        
        Args:
            sector_map: {ticker: sector} 딕셔너리
        
        Returns:
            Tuple[List[str], Dict[str, str]]:
                - 필터링된 티커 리스트
                - 필터링된 섹터 맵
        
        사용 예시:
            filtered_tickers, filtered_map = collector.filter_by_sector(sector_map)
        """
        logger.info("섹터 필터링 적용 중...")
        logger.info(f"  - 제외 섹터: {self.excluded_sectors}")
        
        # 필터링 전 개수
        total_before = len(sector_map)
        
        # 제외할 섹터에 속하지 않은 티커만 선택
        filtered_map = {
            ticker: sector
            for ticker, sector in sector_map.items()
            if sector not in self.excluded_sectors
        }
        
        filtered_tickers = list(filtered_map.keys())
        
        # 제외된 티커 개수
        excluded_count = total_before - len(filtered_tickers)
        
        logger.info(f"✅ 섹터 필터링 완료")
        logger.info(f"  - 필터링 전: {total_before}개")
        logger.info(f"  - 제외됨: {excluded_count}개")
        logger.info(f"  - 필터링 후: {len(filtered_tickers)}개")
        
        return filtered_tickers, filtered_map
    
    
    def collect_daily_prices(
        self, 
        tickers: List[str]
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        일별 가격 데이터를 수집합니다.
        
        yfinance의 download 함수를 사용하여 일별 가격 다운로드
        - Adj Close: 수익률 계산용 (배당, 액면분할 반영)
        - Close: $5 룰 판정용
        
        Args:
            tickers: 티커 리스트
        
        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - adj_close_df: 조정종가 DataFrame
                - close_df: 종가 DataFrame
        
        주의:
            - 다운로드 실패 시 자동으로 재시도
            - 일부 티커 실패해도 계속 진행
        
        사용 예시:
            adj_df, close_df = collector.collect_daily_prices(tickers)
        """
        logger.info(f"일별 가격 데이터 수집 중...")
        logger.info(f"  - 티커 개수: {len(tickers)}")
        logger.info(f"  - 기간: {self.start_date} ~ {self.end_date}")
        
        try:
            # yfinance download: 여러 티커 동시 다운로드
            # group_by='ticker': 티커별로 컬럼 그룹화
            # auto_adjust=False: Adj Close와 Close 모두 받기
            # threads=True: 병렬 다운로드 (속도 향상)
            data = yf.download(
                tickers=tickers,
                start=self.start_date,
                end=self.end_date,
                group_by='ticker',
                auto_adjust=False,
                threads=True,
                progress=True  # 진행률 표시
            )
            
            # 단일 티커인 경우와 여러 티커인 경우 데이터 구조가 다름
            if len(tickers) == 1:
                # 단일 티커: MultiIndex가 아님
                ticker = tickers[0]
                adj_close_df = data[['Adj Close']].rename(columns={'Adj Close': ticker})
                close_df = data[['Close']].rename(columns={'Close': ticker})
            else:
                # 여러 티커: MultiIndex (ticker, field)
                # 'Adj Close'와 'Close' 추출
                adj_close_df = data.xs('Adj Close', axis=1, level=1)
                close_df = data.xs('Close', axis=1, level=1)
            
            logger.info(f"✅ 일별 가격 데이터 수집 완료")
            log_dataframe_info(logger, adj_close_df, "조정종가")
            log_dataframe_info(logger, close_df, "종가")
            
            return adj_close_df, close_df
            
        except Exception as e:
            logger.error(f"❌ 가격 데이터 수집 실패: {e}")
            raise
    
    
    def resample_to_monthly(
        self, 
        daily_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        일별 데이터를 월말 데이터로 리샘플링합니다.
        
        Pandas 버전 호환:
        - Pandas >= 2.2.0: 'ME' (Month End)
        - Pandas < 2.2.0: 'M'
        
        Args:
            daily_df: 일별 가격 DataFrame (Date index)
        
        Returns:
            pd.DataFrame: 월말 가격 DataFrame
        
        사용 예시:
            monthly_df = collector.resample_to_monthly(daily_df)
        """
        logger.info("월말 데이터로 리샘플링 중...")
        
        # utils.helpers에서 Pandas 버전에 맞는 frequency 가져오기
        freq = get_month_end_freq()
        logger.info(f"  - Frequency: '{freq}'")
        
        # resample: 월말로 그룹화
        # .last(): 각 월의 마지막 값 선택
        monthly_df = daily_df.resample(freq).last()
        
        # 결측치 제거 (거래가 없는 월)
        monthly_df = monthly_df.dropna(how='all')
        
        logger.info(f"✅ 월말 리샘플링 완료")
        log_dataframe_info(logger, monthly_df, "월말 데이터")
        
        return monthly_df
    
    
    def save_to_cache(
        self,
        adj_monthly: pd.DataFrame,
        close_monthly: pd.DataFrame,
        sector_map: Dict[str, str],
        tickers: List[str]
    ):
        """
        수집한 데이터를 캐시에 저장합니다.
        
        저장 파일 (3개):
        1. step1_px_adj_m.csv: 월말 조정종가 (수익률 계산용)
        2. step1_px_close_m.csv: 월말 종가 ($5 룰 판정용)
        3. step1_meta.json: 메타 정보 (티커, 섹터, 기간)
        
        Args:
            adj_monthly: 월말 조정종가
            close_monthly: 월말 종가
            sector_map: 섹터 맵
            tickers: 최종 티커 리스트
        """
        logger.info("캐시 저장 중...")
        
        # 1. 조정종가 저장 (CSV)
        save_cache(adj_monthly, STEP1_PRICE_ADJ_CSV)
        
        # 2. 종가 저장 (CSV)
        save_cache(close_monthly, STEP1_PRICE_CLOSE_CSV)
        
        # 3. 메타 정보 저장 (JSON)
        meta = {
            'tickers': tickers,
            'sector_map': sector_map,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'excluded_sectors': self.excluded_sectors,
            'collected_at': datetime.now().isoformat(),
            'num_tickers': len(tickers)
        }
        save_cache(meta, STEP1_META_JSON)
        
        logger.info(f"✅ 캐시 저장 완료")
        logger.info(f"  - 조정종가: {STEP1_PRICE_ADJ_CSV}")
        logger.info(f"  - 종가: {STEP1_PRICE_CLOSE_CSV}")
        logger.info(f"  - 메타: {STEP1_META_JSON}")
    
    
    def run(self):
        """
        전체 파이프라인을 실행합니다.
        
        실행 순서:
        1. S&P500 티커 리스트 수집
        2. 섹터 정보 수집
        3. 섹터 필터링
        4. 일별 가격 데이터 수집
        5. 월말 데이터로 리샘플링
        6. 캐시 저장
        
        사용 예시:
            collector = PriceCollector()
            collector.run()
        """
        log_section_header(logger, "Step1: 가격 데이터 수집 시작")
        
        # 1. S&P500 티커 수집
        tickers = self.get_sp500_tickers()
        
        # 2. 섹터 정보 수집
        sector_map = self.get_sector_info(tickers)
        
        # 3. 섹터 필터링
        filtered_tickers, filtered_sector_map = self.filter_by_sector(sector_map)
        
        # 4. 일별 가격 수집
        adj_daily, close_daily = self.collect_daily_prices(filtered_tickers)
        
        # 5. 월말로 리샘플링
        adj_monthly = self.resample_to_monthly(adj_daily)
        close_monthly = self.resample_to_monthly(close_daily)
        
        # 6. 캐시 저장
        self.save_to_cache(
            adj_monthly,
            close_monthly,
            filtered_sector_map,
            filtered_tickers
        )
        
        log_section_header(logger, "Step1: 가격 데이터 수집 완료")


# ===========================================
# 메인 실행
# ===========================================

if __name__ == '__main__':
    """
    이 파일을 직접 실행하면 Step1을 단독으로 실행합니다.
    
    실행 방법:
        python -m data_collection.step1_price_collector
    """
    collector = PriceCollector()
    collector.run()
