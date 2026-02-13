import pandas as pd
import os

# Annual features 확인
annual = pd.read_csv('data_cache/step3_features_annual.csv')
print('=== Annual Features ===')
print(f'전체 행: {len(annual)}')
print(f'컬럼: {annual.columns[:5].tolist()}')

# Quarterly features 확인
quarterly = pd.read_csv('data_cache/step3_features_quarterly.csv')
print(f'\n=== Quarterly Features ===')
print(f'전체 행: {len(quarterly)}')
print(f'컬럼: {quarterly.columns[:5].tolist()}')

# Quarterly predictions 확인
quarterly_pred = pd.read_csv('data_cache/step4_predictions_ranknet_quarterly.csv')
print(f'\n=== Quarterly Predictions ===')
print(f'전체 행: {len(quarterly_pred)}')
print(f'컬럼: {quarterly_pred.columns[:5].tolist()}')

# first column의 unique 값 수
first_col = annual.columns[0]
print(f'\n유니크 {first_col}: {annual[first_col].nunique()}')

first_col_q = quarterly.columns[0]
print(f'Quarterly 유니크 {first_col_q}: {quarterly[first_col_q].nunique()}')

# US market tickers 파일 존재 확인
print(f'\n=== 티커 파일 ===')
print(f'us_market_tickers.txt 존재: {os.path.exists("data_cache/us_market_tickers.txt")}')
if os.path.exists('data_cache/us_market_tickers.txt'):
    with open('data_cache/us_market_tickers.txt', 'r') as f:
        us_tickers = [line.strip() for line in f if line.strip()]
    print(f'US Market 총 티커 수: {len(us_tickers)}')

print(f'sp500_tickers.txt 존재: {os.path.exists("data_cache/sp500_tickers.txt")}')
if os.path.exists('data_cache/sp500_tickers.txt'):
    with open('data_cache/sp500_tickers.txt', 'r') as f:
        sp500_tickers = [line.strip() for line in f if line.strip()]
    print(f'SP500 총 티커 수: {len(sp500_tickers)}')
