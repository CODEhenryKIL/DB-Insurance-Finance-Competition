"""Step 2 데이터 분석 스크립트"""
import json
import pandas as pd
from collections import Counter

# Step 0 유니버스 (원본 3,640개)
with open('data_cache/step0_valid_universe.json', 'r') as f:
    universe = json.load(f)

step0_sectors = Counter(item['sector'] for item in universe)
step0_tickers = set(item['ticker'] for item in universe)

# Step 2 재무 데이터 (2,774개)
df = pd.read_csv('data_cache/step2_fund_annual.csv')
step2_tickers = set(df['Ticker'].unique())
step2_sectors = Counter(df.groupby('Ticker')['Sector'].first().values)

print('=' * 70)
print('Step 0 (유니버스) vs Step 2 (재무 데이터) 섹터별 비교')
print('=' * 70)
print()
print(f'{"섹터":<28} {"Step0":>8} {"Step2":>8} {"손실":>8} {"손실률":>8}')
print('-' * 70)

total_step0 = 0
total_step2 = 0

for sector in sorted(step0_sectors.keys(), key=lambda x: -step0_sectors[x]):
    s0 = step0_sectors[sector]
    s2 = step2_sectors.get(sector, 0)
    loss = s0 - s2
    loss_pct = loss / s0 * 100 if s0 > 0 else 0
    total_step0 += s0
    total_step2 += s2
    print(f'{sector:<28} {s0:>8,} {s2:>8,} {loss:>8,} {loss_pct:>7.1f}%')

print('-' * 70)
total_loss = total_step0 - total_step2
total_loss_pct = total_loss / total_step0 * 100
print(f'{"합계":<28} {total_step0:>8,} {total_step2:>8,} {total_loss:>8,} {total_loss_pct:>7.1f}%')
print()

# 손실된 티커
lost_tickers = step0_tickers - step2_tickers
print(f'손실된 티커 수: {len(lost_tickers)}개')
print(f'손실된 티커 예시: {list(lost_tickers)[:10]}...')
print()
print('=' * 70)
