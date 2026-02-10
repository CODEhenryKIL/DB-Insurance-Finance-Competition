"""
Unknown 섹터 제거 스크립트
- step0_valid_universe.json에서 Unknown 섹터 제거
- step1_meta.json에서 Unknown 티커 제거
- step1_px_adj_m.csv, step1_px_close_m.csv에서 Unknown 티커 컬럼 제거
"""

import json
import pandas as pd
from pathlib import Path

# 파일 경로
cache_dir = Path(__file__).parent.parent / 'data_cache'
universe_json = cache_dir / 'step0_valid_universe.json'
meta_json = cache_dir / 'step1_meta.json'
px_adj = cache_dir / 'step1_px_adj_m.csv'
px_close = cache_dir / 'step1_px_close_m.csv'

print("=" * 60)
print("  Unknown 섹터 제거 스크립트")
print("=" * 60)

# 1. step0_valid_universe.json 로드
with open(universe_json, 'r') as f:
    universe = json.load(f)

print(f'\n📦 step0_valid_universe.json')
print(f'  - 원본: {len(universe)}개 티커')

# Unknown 섹터 티커 목록
unknown_tickers = [item['ticker'] for item in universe if item['sector'] == 'Unknown']
print(f'  - Unknown 섹터: {len(unknown_tickers)}개')

# Unknown 제거
universe_filtered = [item for item in universe if item['sector'] != 'Unknown']
print(f'  - 필터 후: {len(universe_filtered)}개')

# 저장
with open(universe_json, 'w', encoding='utf-8') as f:
    json.dump(universe_filtered, f, ensure_ascii=False, indent=2)
print(f'  ✅ 저장 완료')

# 2. step1_meta.json (있으면)
if meta_json.exists():
    with open(meta_json, 'r') as f:
        meta = json.load(f)
    
    print(f'\n📦 step1_meta.json')
    print(f'  - 원본: {len(meta)}개')
    
    # Unknown 티커 제거
    meta_filtered = {k: v for k, v in meta.items() if k not in unknown_tickers}
    print(f'  - 필터 후: {len(meta_filtered)}개')
    
    with open(meta_json, 'w', encoding='utf-8') as f:
        json.dump(meta_filtered, f, ensure_ascii=False, indent=2)
    print(f'  ✅ 저장 완료')
else:
    print(f'\n📦 step1_meta.json → 파일 없음 (건너뜀)')

# 3. step1_px_adj_m.csv
if px_adj.exists():
    df_adj = pd.read_csv(px_adj, index_col=0)
    print(f'\n📦 step1_px_adj_m.csv')
    print(f'  - 원본: {df_adj.shape[1]}개 컬럼')
    
    # Unknown 티커 컬럼 제거
    cols_to_drop = [c for c in df_adj.columns if c in unknown_tickers]
    df_adj_filtered = df_adj.drop(columns=cols_to_drop, errors='ignore')
    print(f'  - 제거된 컬럼: {len(cols_to_drop)}개')
    print(f'  - 필터 후: {df_adj_filtered.shape[1]}개 컬럼')
    
    df_adj_filtered.to_csv(px_adj)
    print(f'  ✅ 저장 완료')
else:
    print(f'\n📦 step1_px_adj_m.csv → 파일 없음 (건너뜀)')

# 4. step1_px_close_m.csv
if px_close.exists():
    df_close = pd.read_csv(px_close, index_col=0)
    print(f'\n📦 step1_px_close_m.csv')
    print(f'  - 원본: {df_close.shape[1]}개 컬럼')
    
    cols_to_drop = [c for c in df_close.columns if c in unknown_tickers]
    df_close_filtered = df_close.drop(columns=cols_to_drop, errors='ignore')
    print(f'  - 제거된 컬럼: {len(cols_to_drop)}개')
    print(f'  - 필터 후: {df_close_filtered.shape[1]}개 컬럼')
    
    df_close_filtered.to_csv(px_close)
    print(f'  ✅ 저장 완료')
else:
    print(f'\n📦 step1_px_close_m.csv → 파일 없음 (건너뜀)')

print(f'\n{"=" * 60}')
print(f'🎉 Unknown 섹터 제거 완료!')
print(f'  - 제거된 티커 수: {len(unknown_tickers)}개')
print(f'  - 남은 유효 티커: {len(universe_filtered)}개')
print(f'{"=" * 60}')
