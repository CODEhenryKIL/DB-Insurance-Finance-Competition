#!/usr/bin/env python3
"""Safe Lag 로직 디버깅"""
import pandas as pd
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.paths import CACHE_DIR

def main():
    price_df = pd.read_csv(CACHE_DIR / 'step1_px_close_m.csv', index_col=0, parse_dates=[0])
    price_df.index = pd.to_datetime(price_df.index, utc=True)
    
    print("=== 가격 데이터 범위 ===")
    print(f"  시작: {price_df.index.min().date()}")
    print(f"  끝: {price_df.index.max().date()}")
    print()
    
    rebalance_month = 12
    holding_months = 12
    
    for year in [2019, 2020, 2021, 2022, 2023, 2024]:
        print(f"=== FY{year} 백테스트 시점 비교 ===")
        
        # safe_lag = 0
        buy_sl0 = pd.Timestamp(f'{year}-{rebalance_month:02d}-01', tz='UTC') + pd.offsets.MonthEnd(0)
        sell_sl0 = buy_sl0 + pd.DateOffset(months=holding_months)
        
        # safe_lag = 3
        buy_sl3 = buy_sl0 + pd.DateOffset(months=3)
        sell_sl3 = buy_sl3 + pd.DateOffset(months=holding_months)
        
        print(f"  safe_lag=0: 매수 {buy_sl0.date()} -> 매도 {sell_sl0.date()}")
        print(f"  safe_lag=3: 매수 {buy_sl3.date()} -> 매도 {sell_sl3.date()}")
        
        # 실제 asof 날짜 확인
        actual_sell_sl0 = price_df.index[price_df.index <= sell_sl0]
        actual_sell_sl3 = price_df.index[price_df.index <= sell_sl3]
        
        if len(actual_sell_sl0) > 0:
            print(f"    safe_lag=0 실제 매도일: {actual_sell_sl0[-1].date()}")
        else:
            print(f"    safe_lag=0 실제 매도일: 데이터 없음!")
            
        if len(actual_sell_sl3) > 0:
            print(f"    safe_lag=3 실제 매도일: {actual_sell_sl3[-1].date()}")
        else:
            print(f"    safe_lag=3 실제 매도일: 데이터 없음!")
        print()

if __name__ == "__main__":
    main()
