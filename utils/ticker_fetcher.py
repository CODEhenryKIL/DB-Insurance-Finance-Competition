"""
전체 미국 시장 티커 수집 유틸리티 (간소화 버전)

속도 향상을 위해 Exchange + Price 필터만 적용
Type/Sector 필터는 Step 1에서 처리
"""

import pandas as pd
import yfinance as yf
from typing import List
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 제외할 섹터  
EXCLUDED_SECTORS = [
    'Financial Services',
    'Financials',
    'Utilities',
    'Real Estate',
    'Energy',
    'Materials'
]

def fetch_nasdaq_listed() -> List[str]:
    """NASDAQ FTP에서 상장 종목 다운로드"""
    logger.info("NASDAQ FTP에서 티커 다운로드 중...")
    
    url = "ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt"
    
    try:
        df = pd.read_csv(url, sep='|')
        df = df[df['Symbol'].notna()]
        df = df[:-1]  # 마지막 행 제거
        
        # Test Issue 제외
        df = df[df['Test Issue'] == 'N']
        
        tickers = df['Symbol'].tolist()
        logger.info(f"✅ NASDAQ: {len(tickers)}개")
        return tickers
        
    except Exception as e:
        logger.error(f"NASDAQ 다운로드 실패: {e}")
        return []

def fetch_other_listed() -> List[str]:
    """NYSE, AMEX 티커 다운로드"""
    logger.info("NYSE/AMEX FTP에서 티커 다운로드 중...")
    
    url = "ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt"
    
    try:
        df = pd.read_csv(url, sep='|')
        df = df[df['ACT Symbol'].notna()]
        df = df[:-1]
        
        # NYSE, AMEX만
        df = df[df['Exchange'].isin(['N', 'A', 'P'])]  # N=NYSE, A=AMEX, P=NYSE Arca
        
        # Test Issue 제외
        df = df[df['Test Issue'] == 'N']
        
        # ETF 제외
        df = df[df['ETF'] == 'N']
        
        tickers = df['ACT Symbol'].tolist()
        logger.info(f"✅ NYSE/AMEX: {len(tickers)}개")
        return tickers
        
    except Exception as e:
        logger.error(f"NYSE/AMEX 다운로드 실패: {e}")
        return []

def get_all_us_tickers() -> List[str]:
    """
    전체 미국 시장 티커 수집 (간소화)
    
    필터:
    1. Exchange (NASDAQ/NYSE/AMEX)
    2. Test Issue 제외
    3. ETF 제외
    
    Price/Sector 필터는 Step 1에서 처리
    """
    logger.info("="*60)
    logger.info("  전체 미국 시장 티커 수집 (간소화 버전)")
    logger.info("="*60)
    
    nasdaq = fetch_nasdaq_listed()
    other = fetch_other_listed()
    
    all_tickers = nasdaq + other
    
    # 중복 제거
    all_tickers = list(set(all_tickers))
    all_tickers.sort()
    
    logger.info(f"\n최종 티커 수: {len(all_tickers)}개")
    logger.info("="*60)
    
    return all_tickers

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    tickers = get_all_us_tickers()
    
    # 저장
    cache_dir = Path(__file__).parent.parent / 'data_cache'
    cache_dir.mkdir(exist_ok=True)
    
    output_file = cache_dir / 'us_market_tickers.txt'
    with open(output_file, 'w') as f:
        for ticker in tickers:
            f.write(f"{ticker}\n")
    
    print(f"\n✅ 저장 완료: {output_file}")
    print(f"총 {len(tickers)}개 티커")
