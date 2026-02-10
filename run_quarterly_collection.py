"""
===========================================
분기별 데이터 수집 통합 실행 스크립트
===========================================

이 파일의 역할:
- Step1-Q: 분기별 가격 데이터 수집
- Step2-Q: 분기별 재무 데이터 수집
- 기존 연간 데이터(data_cache/)는 그대로 유지
- 새 데이터는 data_cache_quarterly/에 저장

출력 폴더:
- data_cache_quarterly/step1_px_adj_m.csv
- data_cache_quarterly/step1_px_close_m.csv
- data_cache_quarterly/step1_meta.json
- data_cache_quarterly/step2_fund_quarterly.csv

실행 방법:
    python run_quarterly_collection.py
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from utils import get_logger, log_section_header
from data_collection.step1_price_collector_quarterly import PriceCollectorQuarterly
from data_collection.step2_fundamental_collector_quarterly import FundamentalCollectorQuarterly

logger = get_logger(__name__)


def main():
    """분기별 데이터 수집 파이프라인 실행"""
    
    log_section_header(logger, "🚀 분기별 데이터 수집 파이프라인 시작")
    
    print("=" * 60)
    print("  📊 분기별 데이터 수집 파이프라인")
    print("=" * 60)
    print()
    print("  출력 폴더: data_cache_quarterly/")
    print("  ※ 기존 data_cache/ 폴더는 그대로 유지됩니다.")
    print()
    print("  수집 내용:")
    print("    - Step1-Q: 월말 가격 데이터 (조정종가, 종가)")
    print("    - Step2-Q: 분기별 재무 데이터 (Q1~Q4)")
    print()
    print("=" * 60)
    
    # 사용자 확인 (선택적)
    # input("Enter를 눌러 계속...")
    
    # ============================================
    # Step 1-Q: 가격 데이터 수집
    # ============================================
    print("\n[1/2] 가격 데이터 수집 중...")
    try:
        price_collector = PriceCollectorQuarterly()
        price_collector.run()
        print("✅ Step1-Q 완료: 가격 데이터 수집")
    except Exception as e:
        logger.error(f"❌ Step1-Q 실패: {e}")
        print(f"❌ Step1-Q 실패: {e}")
        return 1
    
    # ============================================
    # Step 2-Q: 분기별 재무 데이터 수집
    # ============================================
    print("\n[2/2] 분기별 재무 데이터 수집 중...")
    try:
        fund_collector = FundamentalCollectorQuarterly()
        fund_collector.run()
        print("✅ Step2-Q 완료: 분기별 재무 데이터 수집")
    except Exception as e:
        logger.error(f"❌ Step2-Q 실패: {e}")
        print(f"❌ Step2-Q 실패: {e}")
        return 1
    
    # ============================================
    # 완료 요약
    # ============================================
    print()
    print("=" * 60)
    print("  🎉 분기별 데이터 수집 완료!")
    print("=" * 60)
    print()
    print("  저장된 파일:")
    print("    📁 data_cache_quarterly/")
    print("       ├── step1_px_adj_m.csv    (월말 조정종가)")
    print("       ├── step1_px_close_m.csv  (월말 종가)")
    print("       ├── step1_meta.json       (메타 정보)")
    print("       └── step2_fund_quarterly.csv (분기별 재무)")
    print()
    print("  다음 단계:")
    print("    - step3_feature_builder_quarterly.py로 분기별 피처 생성")
    print("    - 또는 분기별 데이터 분석 진행")
    print()
    
    log_section_header(logger, "🎉 분기별 데이터 수집 파이프라인 완료")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
