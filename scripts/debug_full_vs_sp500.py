import pandas as pd

# SP500 실험과 FULL 실험 predictions 비교
print("=== Predictions 파일 비교 ===\n")

# Semiannual
semi = pd.read_csv('data_cache/step4_predictions_ranknet_semiannual.csv')
print(f"Semiannual predictions: {len(semi)} rows, {semi['Ticker'].nunique()} tickers")

# Quarterly  
quarterly = pd.read_csv('data_cache/step4_predictions_ranknet_quarterly.csv')
print(f"Quarterly predictions: {len(quarterly)} rows, {quarterly['Ticker'].nunique()} tickers")

# 실험 016 (FULL Semiannual)과 008 (SP500 Semiannual) 포트폴리오 비교
print("\n=== 포트폴리오 Holdings 비교 ===")

# 008
try:
    h008 = pd.read_csv('experiments/exp_008_sp500_ranknet_3y_semiannual_all_safelag/data/008-portfolio_holdings_normal.csv')
    print(f"exp_008 holdings: {len(h008)} rows")
    print(f"exp_008 tickers: {h008['Ticker'].nunique()}")
    tickers_008 = set(h008['Ticker'].unique())
except Exception as e:
    print(f"exp_008 파일 없음: {e}")
    tickers_008 = set()

# 016
try:
    h016 = pd.read_csv('experiments/exp_016_full_ranknet_3y_semiannual_all_safelag/data/016-portfolio_holdings_normal.csv')
    print(f"exp_016 holdings: {len(h016)} rows")
    print(f"exp_016 tickers: {h016['Ticker'].nunique()}")
    tickers_016 = set(h016['Ticker'].unique())
except Exception as e:
    print(f"exp_016 파일 없음: {e}")
    tickers_016 = set()

# 비교
if tickers_008 and tickers_016:
    common = tickers_008 & tickers_016
    only_008 = tickers_008 - tickers_016
    only_016 = tickers_016 - tickers_008
    print(f"\n공통 티커: {len(common)}")
    print(f"008만: {len(only_008)}")
    print(f"016만: {len(only_016)}")

# SP500 필터링 여부 확인
sp500 = set(open('data_cache/sp500_tickers.txt').read().strip().split('\n'))
print(f"\nSP500 티커 수: {len(sp500)}")

# Semiannual predictions 중 SP500 비율
semi_tickers = set(semi['Ticker'].unique())
semi_in_sp500 = semi_tickers & sp500
print(f"Semiannual predictions 중 SP500: {len(semi_in_sp500)}/{len(semi_tickers)} ({len(semi_in_sp500)/len(semi_tickers)*100:.1f}%)")

# runner.py에서 SP500 필터 확인
print("\n=== Runner 설정 확인 필요 ===")
