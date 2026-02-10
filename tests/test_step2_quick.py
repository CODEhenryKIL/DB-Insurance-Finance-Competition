"""
===========================================
Step2 간단 테스트 (2개 티커)
===========================================

전체 티커 수집은 시간이 오래 걸리므로
2개 티커만 테스트합니다.
"""

import sys
import pandas as pd
from data_collection.step2_fundamental_collector import FundamentalCollector
from utils import get_logger
from config.paths import STEP2_FUNDAMENTALS_CSV
import json

logger = get_logger('test_step2')

print("=" * 60)
print("Step2 간단 테스트 (2개 티커: AAPL, MSFT)")
print("=" * 60)

# 테스트용 FundamentalCollector
class TestFundamentalCollector(FundamentalCollector):
    """테스트용: 2개 티커만 사용"""
    
    def run(self):
        """Step1 메타 대신 하드코딩된 티커 사용"""
        from utils import log_section_header
        
        log_section_header(logger, "Step2: 재무 데이터 수집 시작 (테스트)")
        
        # 테스트용 티커
        test_tickers = ['AAPL', 'MSFT']
        logger.info(f"테스트용 티커: {test_tickers}")
        
        # 재무 데이터 수집
        fund_df = self.collect_fundamentals(test_tickers)
        
        if fund_df.empty:
            logger.error("❌ 수집된 데이터 없음!")
            return
        
        # 데이터 확인
        from utils import log_dataframe_info
        log_dataframe_info(logger, fund_df, "재무 데이터")
        
        # 캐시 저장
        self.save_to_cache(fund_df)
        
        log_section_header(logger, "Step2: 재무 데이터 수집 완료 (테스트)")

try:
    # 1. Step2 실행
    print("\n[1. Step2 실행]")
    collector = TestFundamentalCollector()
    collector.run()
    
    # 2. 결과 확인
    print("\n[2. 결과 확인]")
    
    if STEP2_FUNDAMENTALS_CSV.exists():
        fund_df = pd.read_csv(STEP2_FUNDAMENTALS_CSV)
        print(f"✅ 재무 데이터: {fund_df.shape[0]} 행 × {fund_df.shape[1]} 열")
        print(f"   티커: {fund_df['Ticker'].unique().tolist()}")
        print(f"   컬럼: {fund_df.columns.tolist()}")
        print(f"\n   샘플 데이터:")
        print(fund_df.head(10))
        
        # 연도별 데이터 개수
        print(f"\n   연도별 데이터:")
        year_counts = fund_df.groupby('FiscalYear').size()
        print(year_counts.tail(10))
    else:
        print("❌ 재무 데이터 파일 없음")
    
    print("\n" + "=" * 60)
    print("✅ Step2 테스트 완료!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
