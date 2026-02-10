"""
===========================================
Step1: 분기별 가격 데이터 수집
===========================================

이 파일의 역할:
- 기존 step1_price_collector.py와 동일한 로직
- 출력 경로만 data_cache_quarterly/ 폴더로 변경
- 기존 연간 데이터는 그대로 유지

주요 변경점:
- 저장 경로: data_cache_quarterly/
- 월말 가격 데이터 (분기별 재무와 조인 시 사용)

출력 파일:
- data_cache_quarterly/step1_px_adj_m.csv
- data_cache_quarterly/step1_px_close_m.csv
- data_cache_quarterly/step1_meta.json
"""

import pandas as pd
import yfinance as yf
from typing import List, Dict, Tuple
from datetime import datetime
import time
import json

# 프로젝트 내부 모듈
from config.constants import (
    START_YEAR,
    CURRENT_YEAR,
    EXCLUDED_SECTORS,
    API_SLEEP_SECONDS,
    TEST_MODE,
    TEST_TICKERS,
    MARKET_MODE
)
from config.paths_quarterly import (
    STEP1_PRICE_ADJ_CSV_Q,
    STEP1_PRICE_CLOSE_CSV_Q,
    STEP1_META_JSON_Q,
    STEP0_VALID_UNIVERSE_JSON,
    DATA_CACHE_QUARTERLY_DIR
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


class PriceCollectorQuarterly:
    """
    분기별 가격 데이터 수집 클래스
    
    기존 PriceCollector와 동일한 로직,
    저장 경로만 data_cache_quarterly/로 변경
    """
    
    def __init__(self):
        """초기화: 수집 기간 및 제외 섹터 설정"""
        self.start_date = f'{START_YEAR}-01-01'
        self.end_date = datetime.now().strftime('%Y-%m-%d')
        self.excluded_sectors = EXCLUDED_SECTORS
        
        # 출력 디렉토리 생성
        DATA_CACHE_QUARTERLY_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"PriceCollectorQuarterly 초기화 완료")
        logger.info(f"  - 수집 기간: {self.start_date} ~ {self.end_date}")
        logger.info(f"  - 출력 폴더: {DATA_CACHE_QUARTERLY_DIR}")
    
    
    def get_sp500_tickers(self) -> List[str]:
        """
        티커 리스트 수집
        Step 0 유니버스 JSON이 있으면 우선 사용
        """
        # Step 0 유니버스 JSON이 있으면 우선 사용
        if STEP0_VALID_UNIVERSE_JSON.exists():
            logger.info("📜 Step 0 유니버스 JSON에서 티커 로드")
            with open(STEP0_VALID_UNIVERSE_JSON, 'r', encoding='utf-8') as f:
                universe = json.load(f)
            
            tickers = [item['ticker'] for item in universe]
            self._universe_sector_map = {item['ticker']: item['sector'] for item in universe}
            
            logger.info(f"  → 유효 티커 로드 완료: {len(tickers)}개")
            return tickers
        
        logger.warning("⚠️  Step 0 유니버스 없음 - 레거시 모드로 동작")
        
        # 테스트 모드
        if TEST_MODE:
            logger.info("⚠️  TEST MODE: 17개 티커만 사용")
            return TEST_TICKERS
        
        # S&P 500 모드 (기본)
        logger.info("S&P500 티커 리스트 수집 중...")
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        
        try:
            import requests
            import io
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            tables = pd.read_html(io.StringIO(response.text), match='Symbol')
            df = tables[0]
            tickers = df['Symbol'].tolist()
            tickers = [t.replace('.', '-') for t in tickers]
            
            logger.info(f"✅ S&P500 티커 수집 완료: {len(tickers)}개")
            return tickers
            
        except Exception as e:
            logger.error(f"❌ S&P500 티커 수집 실패: {e}")
            return TEST_TICKERS
    
    
    def collect_daily_prices(
        self, 
        tickers: List[str]
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """일별 가격 데이터 수집"""
        logger.info(f"일별 가격 데이터 수집 중...")
        logger.info(f"  - 티커 개수: {len(tickers)}")
        logger.info(f"  - 기간: {self.start_date} ~ {self.end_date}")
        
        try:
            BATCH_SIZE = 500
            
            if len(tickers) > BATCH_SIZE:
                logger.info(f"  - 배치 처리: {BATCH_SIZE}개씩 나눠서 다운로드")
                all_adj_close = []
                all_close = []
                
                for i in range(0, len(tickers), BATCH_SIZE):
                    batch = tickers[i:i + BATCH_SIZE]
                    batch_num = i // BATCH_SIZE + 1
                    total_batches = (len(tickers) + BATCH_SIZE - 1) // BATCH_SIZE
                    logger.info(f"  → 배치 {batch_num}/{total_batches}: {len(batch)}개 티커")
                    
                    data = yf.download(
                        tickers=batch,
                        start=self.start_date,
                        end=self.end_date,
                        group_by='ticker',
                        auto_adjust=False,
                        threads=8,
                        progress=True
                    )
                    
                    if len(batch) == 1:
                        ticker = batch[0]
                        batch_adj = data[['Adj Close']].rename(columns={'Adj Close': ticker})
                        batch_close = data[['Close']].rename(columns={'Close': ticker})
                    else:
                        batch_adj = data.xs('Adj Close', axis=1, level=1)
                        batch_close = data.xs('Close', axis=1, level=1)
                    
                    all_adj_close.append(batch_adj)
                    all_close.append(batch_close)
                
                adj_close_df = pd.concat(all_adj_close, axis=1)
                close_df = pd.concat(all_close, axis=1)
            else:
                data = yf.download(
                    tickers=tickers,
                    start=self.start_date,
                    end=self.end_date,
                    group_by='ticker',
                    auto_adjust=False,
                    threads=8,
                    progress=True
                )
                
                if len(tickers) == 1:
                    ticker = tickers[0]
                    adj_close_df = data[['Adj Close']].rename(columns={'Adj Close': ticker})
                    close_df = data[['Close']].rename(columns={'Close': ticker})
                else:
                    adj_close_df = data.xs('Adj Close', axis=1, level=1)
                    close_df = data.xs('Close', axis=1, level=1)
            
            logger.info(f"✅ 일별 가격 데이터 수집 완료")
            return adj_close_df, close_df
            
        except Exception as e:
            logger.error(f"❌ 가격 데이터 수집 실패: {e}")
            raise
    
    
    def resample_to_monthly(
        self, 
        daily_df: pd.DataFrame
    ) -> pd.DataFrame:
        """일별 데이터를 월말 데이터로 리샘플링"""
        logger.info("월말 데이터로 리샘플링 중...")
        
        freq = get_month_end_freq()
        monthly_df = daily_df.resample(freq).last()
        monthly_df = monthly_df.dropna(how='all')
        
        logger.info(f"✅ 월말 리샘플링 완료: {len(monthly_df)}개 행")
        return monthly_df
    
    
    def save_to_cache(
        self,
        adj_monthly: pd.DataFrame,
        close_monthly: pd.DataFrame,
        sector_map: Dict[str, str],
        tickers: List[str]
    ):
        """수집한 데이터를 캐시에 저장 (분기별 폴더)"""
        logger.info("캐시 저장 중...")
        
        # 1. 조정종가 저장 (CSV)
        save_cache(adj_monthly, STEP1_PRICE_ADJ_CSV_Q)
        
        # 2. 종가 저장 (CSV)
        save_cache(close_monthly, STEP1_PRICE_CLOSE_CSV_Q)
        
        # 3. 메타 정보 저장 (JSON)
        meta = {
            'tickers': tickers,
            'sector_map': sector_map,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'excluded_sectors': self.excluded_sectors,
            'collected_at': datetime.now().isoformat(),
            'num_tickers': len(tickers),
            'data_type': 'quarterly'  # 분기별 데이터 표시
        }
        save_cache(meta, STEP1_META_JSON_Q)
        
        logger.info(f"✅ 캐시 저장 완료 (분기별 폴더)")
        logger.info(f"  - 조정종가: {STEP1_PRICE_ADJ_CSV_Q}")
        logger.info(f"  - 종가: {STEP1_PRICE_CLOSE_CSV_Q}")
        logger.info(f"  - 메타: {STEP1_META_JSON_Q}")
    
    
    def run(self):
        """전체 파이프라인 실행"""
        log_section_header(logger, "Step1-Q: 분기별 가격 데이터 수집 시작")
        
        # 1. 티커 수집
        tickers = self.get_sp500_tickers()
        
        # Step 0 유니버스 사용 여부 확인
        use_step0_universe = hasattr(self, '_universe_sector_map') and self._universe_sector_map
        
        if use_step0_universe:
            logger.info("✅ Step 0 유니버스 사용 - 섹터 필터링 스킵")
            filtered_tickers = tickers
            filtered_sector_map = self._universe_sector_map
        else:
            logger.info("⚠️ 레거시 모드 - 전체 티커 사용")
            filtered_tickers = tickers
            filtered_sector_map = {}
        
        # 2. 일별 가격 수집
        adj_daily, close_daily = self.collect_daily_prices(filtered_tickers)
        
        # 3. 월말로 리샘플링
        adj_monthly = self.resample_to_monthly(adj_daily)
        close_monthly = self.resample_to_monthly(close_daily)
        
        # 4. 캐시 저장
        self.save_to_cache(
            adj_monthly,
            close_monthly,
            filtered_sector_map,
            filtered_tickers
        )
        
        log_section_header(logger, "Step1-Q: 분기별 가격 데이터 수집 완료")


# ===========================================
# 메인 실행
# ===========================================

if __name__ == '__main__':
    """
    실행 방법:
        python -m data_collection.step1_price_collector_quarterly
    """
    collector = PriceCollectorQuarterly()
    collector.run()
