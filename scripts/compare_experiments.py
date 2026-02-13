import os
import json
import pandas as pd
from pathlib import Path

exp_dir = Path("/Volumes/512 - 기가바이트 ssd/안티그래비티 - 개발/experiments")

results = []

for folder in sorted(exp_dir.iterdir()):
    if folder.is_dir() and folder.name.startswith("exp_"):
        config_files = list(folder.glob("*-config.json"))
        metrics_files = list(folder.glob("metrics/*-performance_metrics.csv"))
        
        if config_files and metrics_files:
            with open(config_files[0]) as f:
                config = json.load(f)
            
            metrics_df = pd.read_csv(metrics_files[0])
            normal_5 = metrics_df[metrics_df['Portfolio'] == 'normal_5'].iloc[0] if 'normal_5' in metrics_df['Portfolio'].values else None
            
            results.append({
                'exp': folder.name.split('_')[1],
                'market': config.get('market_mode', 'N/A'),
                'freq': config.get('rebalance_frequency', 'N/A'),
                'sectors': str(config.get('included_sectors', 'N/A'))[:15],
                'window': config.get('train_window_years', 'N/A'),
                'cagr': f"{normal_5['CAGR']*100:.1f}%" if normal_5 is not None else 'N/A',
                'sharpe': f"{normal_5['Sharpe']:.2f}" if normal_5 is not None else 'N/A',
            })

# 표로 출력
print(f"{'Exp':<5} {'Market':<12} {'Freq':<10} {'Window':<6} {'Sectors':<20} {'CAGR':<8} {'Sharpe':<6}")
print("="*75)
for r in results:
    print(f"{r['exp']:<5} {r['market']:<12} {r['freq']:<10} {r['window']:<6} {r['sectors']:<20} {r['cagr']:<8} {r['sharpe']:<6}")

# 중복 결과 확인
print("\n\n=== 동일 CAGR 검색 ===")
cagr_map = {}
for r in results:
    key = r['cagr']
    if key not in cagr_map:
        cagr_map[key] = []
    cagr_map[key].append(r['exp'])

for cagr, exps in cagr_map.items():
    if len(exps) > 1:
        print(f"CAGR {cagr}: {exps}")
