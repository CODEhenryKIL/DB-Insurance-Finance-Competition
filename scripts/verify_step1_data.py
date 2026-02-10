"""
Step 1 데이터 무결성 검증 스크립트
"""
import json
import pandas as pd
from pathlib import Path

def verify_step1_data():
    print('=' * 60)
    print('📋 Step 1 데이터 무결성 검증')
    print('=' * 60)

    # 1. 유니버스 파일 검증
    print('\n[1] step0_valid_universe.json 검증')
    with open('data_cache/step0_valid_universe.json', 'r') as f:
        universe = json.load(f)
    universe_tickers = set(item['ticker'] for item in universe)
    universe_sectors = set(item['sector'] for item in universe)
    print(f'  ✓ 티커 수: {len(universe_tickers)}개')
    print(f'  ✓ 섹터 종류: {universe_sectors}')
    print(f'  ✓ Unknown 섹터 포함: {"있음 ❌" if "Unknown" in universe_sectors else "없음 ✅"}')

    # 2. step1_meta.json 검증
    print('\n[2] step1_meta.json 검증')
    with open('data_cache/step1_meta.json', 'r') as f:
        meta = json.load(f)
    
    # meta.json 구조 확인: {tickers: [...]} 또는 {ticker: {...}}
    if 'tickers' in meta:
        meta_tickers = set(meta['tickers'])
        meta_sectors = set()  # 이 구조에서는 섹터 정보 없음
        print(f'  ✓ 티커 수: {len(meta_tickers)}개')
        print(f'  ℹ️ 메타 구조: 티커 리스트만 포함 (섹터 정보는 유니버스 파일에)')
    else:
        meta_tickers = set(meta.keys())
        meta_sectors = set(item.get('sector', 'Unknown') for item in meta.values() if isinstance(item, dict))
        print(f'  ✓ 티커 수: {len(meta_tickers)}개')
        print(f'  ✓ 섹터 종류: {meta_sectors}')
        print(f'  ✓ Unknown 섹터 포함: {"있음 ❌" if "Unknown" in meta_sectors else "없음 ✅"}')

    # 3. step1_px_adj_m.csv 검증
    print('\n[3] step1_px_adj_m.csv 검증')
    px_adj = pd.read_csv('data_cache/step1_px_adj_m.csv', index_col=0, parse_dates=True)
    px_adj_tickers = set(px_adj.columns)
    print(f'  ✓ 티커 수: {len(px_adj_tickers)}개')
    print(f'  ✓ 기간: {px_adj.index.min().strftime("%Y-%m-%d")} ~ {px_adj.index.max().strftime("%Y-%m-%d")}')
    print(f'  ✓ 데이터 행 수: {len(px_adj)}개')
    print(f'  ✓ NaN 비율: {px_adj.isna().sum().sum() / px_adj.size * 100:.1f}%')

    # 4. step1_px_close_m.csv 검증
    print('\n[4] step1_px_close_m.csv 검증')
    px_close = pd.read_csv('data_cache/step1_px_close_m.csv', index_col=0, parse_dates=True)
    px_close_tickers = set(px_close.columns)
    print(f'  ✓ 티커 수: {len(px_close_tickers)}개')
    print(f'  ✓ 기간: {px_close.index.min().strftime("%Y-%m-%d")} ~ {px_close.index.max().strftime("%Y-%m-%d")}')
    print(f'  ✓ 데이터 행 수: {len(px_close)}개')
    print(f'  ✓ NaN 비율: {px_close.isna().sum().sum() / px_close.size * 100:.1f}%')

    # 5. 교차 검증
    print('\n' + '=' * 60)
    print('📊 교차 검증 결과')
    print('=' * 60)

    # 유니버스 vs 메타
    universe_only = universe_tickers - meta_tickers
    meta_only = meta_tickers - universe_tickers
    print(f'\n[유니버스 vs 메타]')
    print(f'  유니버스에만 있는 티커: {len(universe_only)}개')
    print(f'  메타에만 있는 티커: {len(meta_only)}개')

    # 유니버스 vs 가격 데이터
    universe_only_px = universe_tickers - px_adj_tickers
    px_only = px_adj_tickers - universe_tickers
    print(f'\n[유니버스 vs 가격 데이터]')
    print(f'  유니버스에만 있는 티커: {len(universe_only_px)}개')
    print(f'  가격 데이터에만 있는 티커: {len(px_only)}개')

    # 메타 vs 가격 데이터
    meta_only_px = meta_tickers - px_adj_tickers
    px_only_meta = px_adj_tickers - meta_tickers
    print(f'\n[메타 vs 가격 데이터]')
    print(f'  메타에만 있는 티커: {len(meta_only_px)}개')
    print(f'  가격 데이터에만 있는 티커: {len(px_only_meta)}개')

    # 조정가 vs 종가
    adj_only = px_adj_tickers - px_close_tickers
    close_only = px_close_tickers - px_adj_tickers
    print(f'\n[조정가 vs 종가]')
    print(f'  조정가에만 있는 티커: {len(adj_only)}개')
    print(f'  종가에만 있는 티커: {len(close_only)}개')

    # 6. 최종 요약
    print('\n' + '=' * 60)
    print('✅ 최종 검증 요약')
    print('=' * 60)
    
    all_match = (len(universe_tickers) == len(meta_tickers) == len(px_adj_tickers) == len(px_close_tickers))
    common_tickers = universe_tickers & meta_tickers & px_adj_tickers & px_close_tickers
    
    print(f'  유니버스:  {len(universe_tickers):,}개')
    print(f'  메타:      {len(meta_tickers):,}개')
    print(f'  조정가:    {len(px_adj_tickers):,}개')
    print(f'  종가:      {len(px_close_tickers):,}개')
    print(f'  공통 티커: {len(common_tickers):,}개')
    print(f'\n  모든 파일 일치: {"✅ YES" if all_match else "❌ NO"}')

    if not all_match:
        print('\n⚠️ 불일치 상세:')
        if universe_only:
            sample = list(universe_only)[:10]
            print(f'  유니버스에만 있음 ({len(universe_only)}개): {sample}')
        if meta_only:
            sample = list(meta_only)[:10]
            print(f'  메타에만 있음 ({len(meta_only)}개): {sample}')
        if universe_only_px:
            sample = list(universe_only_px)[:10]
            print(f'  유니버스에만 (가격 없음) ({len(universe_only_px)}개): {sample}')
        if px_only:
            sample = list(px_only)[:10]
            print(f'  가격에만 있음 ({len(px_only)}개): {sample}')
    
    # 7. Unknown 섹터 완전 제거 확인
    print('\n' + '=' * 60)
    print('🔍 Unknown 섹터 최종 확인')
    print('=' * 60)
    
    unknown_in_universe = [item for item in universe if item['sector'] == 'Unknown']
    
    # meta 구조에 따라 처리
    if 'tickers' in meta:
        unknown_in_meta = []  # 티커 리스트만 있는 경우 섹터 정보 없음
    else:
        unknown_in_meta = [t for t, info in meta.items() if isinstance(info, dict) and info.get('sector') == 'Unknown']
    
    print(f'  유니버스 Unknown: {len(unknown_in_universe)}개')
    print(f'  메타 Unknown: {len(unknown_in_meta)}개 (메타 파일에 섹터 정보 있는 경우만)')
    
    if len(unknown_in_universe) == 0 and len(unknown_in_meta) == 0:
        print('\n  ✅ Unknown 섹터 완전 제거 확인!')
    else:
        print('\n  ❌ Unknown 섹터 잔존!')
        if unknown_in_universe:
            print(f'    유니버스: {[item["ticker"] for item in unknown_in_universe[:5]]}...')
        if unknown_in_meta:
            print(f'    메타: {unknown_in_meta[:5]}...')
    
    # 8. 결론
    print('\n' + '=' * 60)
    if all_match and len(unknown_in_universe) == 0:
        print('🎉 검증 통과! Step 2 진행 가능')
    else:
        print('⚠️ 데이터 불일치 발견. 확인 필요.')
    print('=' * 60)
    
    return all_match

if __name__ == '__main__':
    verify_step1_data()
