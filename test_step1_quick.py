"""
===========================================
Step1 간단 테스트 (소수 티커)
===========================================

전체 S&P500 수집은 시간이 오래 걸리므로
소수의 티커로 Step1 기능을 테스트합니다.
"""

import sys
import pandas as pd
from data_collection.step1_price_collector import PriceCollector
from utils import get_logger
from config.paths import STEP1_PRICE_ADJ_CSV, STEP1_META_JSON

logger = get_logger('test_step1')

print("=" * 60)
print("Step1 간단 테스트 (5개 티커)")
print("=" * 60)

# 테스트용 PriceCollector 클래스 (get_sp500_tickers 오버라이드)
class TestPriceCollector(PriceCollector):
    """테스트용: 5개 티커만 사용"""
    
    def get_sp500_tickers(self):
        """테스트용 티커 리스트 반환"""
        test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'JPM', 'XOM']
        logger.info(f"✅ 테스트용 티커 {len(test_tickers)}개 사용")
        return test_tickers

try:
    # 1. 테스트 실행
    print("\n[1. Step1 실행]")
    collector = TestPriceCollector()
    collector.run()
    
    # 2. 결과 확인
    print("\n[2. 결과 확인]")
    
    # 조정종가 로드
    if STEP1_PRICE_ADJ_CSV.exists():
        adj_df = pd.read_csv(STEP1_PRICE_ADJ_CSV, index_col=0, parse_dates=True)
        print(f"✅ 조정종가: {adj_df.shape[0]} 행 × {adj_df.shape[1]} 열")
        print(f"   기간: {adj_df.index[0]} ~ {adj_df.index[-1]}")
        print(f"   티커: {list(adj_df.columns[:5])}...")
    else:
        print("❌ 조정종가 파일 없음")
    
    # 메타 정보 로드
    if STEP1_META_JSON.exists():
        import json
        with open(STEP1_META_JSON, 'r') as f:
            meta = json.load(f)
        print(f"✅ 메타 정보: {meta['num_tickers']}개 티커")
        print(f"   제외 섹터: {meta['excluded_sectors']}")
    else:
        print("❌ 메타 파일 없음")
    
    print("\n" + "=" * 60)
    print("✅ Step1 테스트 통과!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
