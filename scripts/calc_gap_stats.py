"""각 실험별 Gap 통계 계산"""
import pandas as pd
import numpy as np

print("=" * 60)
print("각 실험별 Gap 통계 (Gap = y_actual - y_pred)")
print("=" * 60)

# exp_003 (현재 data_cache)
try:
    pred = pd.read_csv('data_cache/step4_predictions.csv')
    pred['Gap'] = pred['y_actual'] - pred['y_pred']
    print('\n=== exp_003 (현재 data_cache) ===')
    print(f'Gap 평균: {pred["Gap"].mean():.4f}')
    print(f'Gap 표준편차: {pred["Gap"].std():.4f}')
    print(f'Gap 최소: {pred["Gap"].min():.4f}')
    print(f'Gap 최대: {pred["Gap"].max():.4f}')
    print(f'샘플 수: {len(pred)}')
except Exception as e:
    print(f'exp_003 오류: {e}')

# exp_001
try:
    pred1 = pd.read_csv('experiments/exp_001_baseline_full_market/step4_predictions.csv')
    pred1['Gap'] = pred1['y_actual'] - pred1['y_pred']
    print('\n=== exp_001 ===')
    print(f'Gap 평균: {pred1["Gap"].mean():.4f}')
    print(f'Gap 표준편차: {pred1["Gap"].std():.4f}')
    print(f'Gap 최소: {pred1["Gap"].min():.4f}')
    print(f'Gap 최대: {pred1["Gap"].max():.4f}')
    print(f'샘플 수: {len(pred1)}')
except Exception as e:
    print(f'exp_001 오류: {e}')

# exp_002  
try:
    pred2 = pd.read_csv('experiments/exp_002_hyperparams_v1/step4_predictions.csv')
    pred2['Gap'] = pred2['y_actual'] - pred2['y_pred']
    print('\n=== exp_002 ===')
    print(f'Gap 평균: {pred2["Gap"].mean():.4f}')
    print(f'Gap 표준편차: {pred2["Gap"].std():.4f}')
    print(f'Gap 최소: {pred2["Gap"].min():.4f}')
    print(f'Gap 최대: {pred2["Gap"].max():.4f}')
    print(f'샘플 수: {len(pred2)}')
except Exception as e:
    print(f'exp_002 오류: {e}')
