"""
Plan C: yfinance 순차 처리 버전
스레드 문제 완전 해결 (1개씩 다운로드)

장점:
- yfinance 사용 (검증된 라이브러리)
- 스레드 문제 없음 (순차 처리)
- 100개 단위 체크포인트 (재시작 가능)
- 실패 복구 기능

단점:
- 느림 (예상 10-12시간)

사용법:
python3 -m data_collection.step1_price_collector_sequential
"""

import pandas as pd
import yfinance as yf
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import logging
import time
from tqdm import tqdm
import json

# 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from config.constants import START_YEAR, MARKET_MODE, TEST_MODE, TEST_TICKERS
from config.paths import CACHE_DIR

class PriceCollectorSequential:
    """yfinance 순차 처리 가격 수집기 (스레드 문제 없음)"""
    
    def __init__(self):
        self.start_date = f"{START_YEAR}-01-01"
        self.end_date = datetime.now().strftime("%Y-%m-%d")
        self.cache_dir = CACHE_DIR
        self.checkpoint_dir = self.cache_dir / 'checkpoints'
        self.checkpoint_dir.mkdir(exist_ok=True)
        
        logger.info("PriceCollectorSequential 초기화")
        logger.info(f"  - 수집 기간: {self.start_date} ~ {self.end_date}")
        logger.info(f"  - 체크포인트: {self.checkpoint_dir}")
    
    def load_tickers(self) -> List[str]:
        """티커 리스트 로드"""
        if TEST_MODE:
            logger.info("⚠️ TEST MODE: 17개 티커")
            return TEST_TICKERS
        
        if MARKET_MODE == 'FULL':
            logger.info("🌍 FULL MARKET MODE")
            ticker_file = self.cache_dir / 'us_market_tickers.txt'
            with open(ticker_file, 'r') as f:
                tickers = [line.strip() for line in f if line.strip()]
            logger.info(f"  → {len(tickers)}개 티커 로드")
            return tickers
        
        logger.error("S&P 500 모드는 원본 collector 사용")
        raise NotImplementedError("S&P 500은 원본 사용")
    
    def download_single_ticker(self, ticker: str) -> pd.Series:
        """
        단일 티커 다운로드 (순차 처리)
        
        Returns
        -------
        pd.Series or None
            월말 조정종가 (Date 인덱스)
        """
        try:
            # yf.download()는 스레드 문제 발생 -> Ticker() 직접 사용
            stock = yf.Ticker(ticker)
            hist = stock.history(start=self.start_date, end=self.end_date)
            
            if hist.empty:
                return None
            
            # 월말 조정종가
            monthly = hist['Close'].resample('ME').last()
            monthly.name = ticker
            
            return monthly
            
        except Exception as e:
            logger.debug(f"{ticker}: {e}")
            return None
    
    def get_completed_tickers(self) -> set:
        """완료된 티커 찾기 (체크포인트)"""
        completed = set()
        
        for checkpoint_file in self.checkpoint_dir.glob('batch_*.csv'):
            df = pd.read_csv(checkpoint_file, index_col=0)
            completed.update(df.columns.tolist())
        
        return completed
    
    def collect_prices_batch(self, tickers: List[str], batch_size: int = 100) -> pd.DataFrame:
        """
        배치 단위 순차 수집
        
        Parameters
        ----------
        tickers : List[str]
            티커 리스트
        batch_size : int
            배치 크기 (체크포인트 간격)
            
        Returns
        -------
        pd.DataFrame
            월말 가격 (Date × Ticker)
        """
        # 완료된 티커 제외
        completed = self.get_completed_tickers()
        remaining = [t for t in tickers if t not in completed]
        
        if completed:
            logger.info(f"📌 체크포인트에서 재개: {len(completed)}개 완료됨")
            logger.info(f"  → 남은 티커: {len(remaining)}개")
        else:
            logger.info(f"🚀 새로 시작: {len(tickers)}개 티커")
            remaining = tickers
        
        all_data = []
        failed = []
        
        total_batches = (len(remaining) + batch_size - 1) // batch_size
        
        for i in range(0, len(remaining), batch_size):
            batch = remaining[i:i+batch_size]
            batch_num = (len(completed) + i) // batch_size + 1
            
            logger.info(f"\n[배치 {batch_num}] {len(batch)}개 티커 처리 중...")
            
            batch_data = []
            
            # 순차 처리 (중요!)
            for ticker in tqdm(batch, desc=f"배치 {batch_num}"):
                series = self.download_single_ticker(ticker)
                
                if series is not None:
                    batch_data.append(series)
                else:
                    failed.append(ticker)
                
                time.sleep(0.05)  # Rate limit
            
            # 배치 저장 (체크포인트)
            if batch_data:
                batch_df = pd.concat(batch_data, axis=1)
                checkpoint_file = self.checkpoint_dir / f'batch_{batch_num:04d}.csv'
                batch_df.to_csv(checkpoint_file)
                logger.info(f"  ✅ 저장: {checkpoint_file.name} ({len(batch_data)}개)")
            
            logger.info(f"  → 성공: {len(batch_data)}, 실패: {len(batch) - len(batch_data)}")
        
        # 전체 병합
        logger.info("\n📊 전체 체크포인트 병합 중...")
        checkpoint_files = sorted(self.checkpoint_dir.glob('batch_*.csv'))
        
        if not checkpoint_files:
            raise ValueError("체크포인트 파일 없음")
        
        all_dfs = []
        for f in checkpoint_files:
            df = pd.read_csv(f, index_col=0, parse_dates=[0])  # ✅ 인덱스 명시적 파싱
            all_dfs.append(df)
            logger.info(f"  - {f.name}: {df.shape[1]}개 티커")
        
        df_all = pd.concat(all_dfs, axis=1)
        
        logger.info(f"\n✅ 최종: {df_all.shape[0]}개월 × {df_all.shape[1]}개 티커")
        logger.info(f"❌ 실패: {len(failed)}개")
        
        if failed:
            logger.warning(f"실패 샘플: {failed[:20]}")
        
        return df_all
    
    def save_data(self, df: pd.DataFrame):
        """최종 데이터 저장"""
        logger.info("\n💾 최종 파일 저장 중...")
        
        # 종가/조정종가
        output_close = self.cache_dir / 'step1_px_close_m.csv'
        output_adj = self.cache_dir / 'step1_px_adj_m.csv'
        
        df.to_csv(output_close)
        df.to_csv(output_adj)
        
        logger.info(f"  ✅ {output_close.name}")
        logger.info(f"  ✅ {output_adj.name}")
        
        # 메타 정보
        meta = {
            'tickers': df.columns.tolist(),
            'start_date': str(df.index[0])[:10],  # ✅ strftime 대신 str 사용
            'end_date': str(df.index[-1])[:10],
            'num_tickers': len(df.columns),
            'num_months': len(df),
            'collection_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'method': 'yfinance_sequential'
        }
        
        meta_file = self.cache_dir / 'step1_meta.json'
        with open(meta_file, 'w') as f:
            json.dump(meta, f, indent=2)
        logger.info(f"  ✅ {meta_file.name}")
        
        # 체크포인트 정리
        logger.info("\n🧹 체크포인트 정리 중...")
        for f in self.checkpoint_dir.glob('batch_*.csv'):
            f.unlink()
        logger.info(f"  ✅ {len(list(self.checkpoint_dir.glob('batch_*.csv')))}개 파일 삭제")
    
    def run(self):
        """메인 실행"""
        logger.info("="*60)
        logger.info("  Step1: 가격 수집 (순차 처리)")
        logger.info("="*60)
        
        # 1. 티커 로드
        tickers = self.load_tickers()
        
        # 2. 순차 수집
        df = self.collect_prices_batch(tickers, batch_size=100)
        
        # 3. 저장
        self.save_data(df)
        
        logger.info("="*60)
        logger.info("  ✅ Step1 완료!")
        logger.info("="*60)

if __name__ == '__main__':
    collector = PriceCollectorSequential()
    collector.run()
