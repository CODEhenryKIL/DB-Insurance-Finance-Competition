"""S&P 500 티커 커버리지 확인 스크립트"""
import pandas as pd
import requests
from io import StringIO
from pathlib import Path

# S&P 500 원본 데이터 (섹터 포함)
headers = {'User-Agent': 'Mozilla/5.0'}
url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
response = requests.get(url, headers=headers)
tables = pd.read_html(StringIO(response.text))
sp500_df = tables[0]
sp500_df['Symbol'] = sp500_df['Symbol'].str.replace('.', '-', regex=False)

# Step3 features에서 티커 확인
cache_dir = Path(__file__).parent.parent / 'data_cache'
features_df = pd.read_csv(cache_dir / 'step3_features_annual.csv')
existing_tickers = set(features_df['Ticker'].unique())

# 누락된 티커의 섹터 분포
missing = sp500_df[~sp500_df['Symbol'].isin(existing_tickers)]
print('누락된 S&P 500 티커의 섹터 분포:')
print(missing['GICS Sector'].value_counts())
print()

# 사용 가능한 티커의 섹터 분포
available = sp500_df[sp500_df['Symbol'].isin(existing_tickers)]
print('사용 가능한 S&P 500 티커의 섹터 분포:')
print(available['GICS Sector'].value_counts())
print()

# 총계
print(f"총 S&P 500: {len(sp500_df)}개")
print(f"사용 가능: {len(available)}개 ({len(available)/len(sp500_df)*100:.1f}%)")
print(f"누락: {len(missing)}개 ({len(missing)/len(sp500_df)*100:.1f}%)")
