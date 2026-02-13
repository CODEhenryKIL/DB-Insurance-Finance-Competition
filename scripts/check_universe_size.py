#!/usr/bin/env python3
"""유니버스 크기 확인 스크립트"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from config.paths import CACHE_DIR

# 데이터 로드
pred = pd.read_csv(CACHE_DIR / 'step4_predictions_ranknet.csv')
feat = pd.read_csv(CACHE_DIR / 'step3_features_annual.csv')
merged = pred.merge(feat[['Ticker', 'FiscalYear', 'Sector']], on=['Ticker', 'FiscalYear'], how='left')

print("=" * 50)
print("S&P 500 유니버스 현황")
print("=" * 50)
print()
print(f"전체 데이터 행 수: {len(pred)}개 (연도 x 종목)")
print(f"유니크 기업 수: {pred['Ticker'].nunique()}개")
yearly = pred.groupby('FiscalYear')['Ticker'].count()
print(f"연도별 평균 기업 수: {yearly.mean():.0f}개")
print()
print("연도별 기업 수:")
for y, c in yearly.items():
    print(f"  {y}: {c}개")
print()

biotech_it = merged[merged['Sector'].isin(['Healthcare', 'Technology'])]
print("=" * 50)
print("바이오&IT 필터 후")
print("=" * 50)
print()
print(f"전체 데이터 행 수: {len(biotech_it)}개")
print(f"유니크 기업 수: {biotech_it['Ticker'].nunique()}개")
yearly_bio = biotech_it.groupby('FiscalYear')['Ticker'].count()
print(f"연도별 평균 기업 수: {yearly_bio.mean():.0f}개")
print()
print("연도별 기업 수:")
for y, c in yearly_bio.items():
    print(f"  {y}: {c}개")
