"""
===========================================
Data Leakage 검증 스크립트
===========================================

핵심 질문: m3와 y가 같은 시점 데이터를 사용하는가?
         만약 그렇다면, 이것이 미래 데이터 사용(Leakage)인가?

검증 방법:
1. 현재 구조: m3[t] vs y[t] 상관관계
2. 진정한 예측 구조: m3[t] vs y[t+1] 상관관계

만약 (1)이 높고 (2)가 낮으면:
→ "동시점 관계"를 학습한 것 (Leakage 아님, 하지만 예측력 의심)

만약 (1)과 (2) 모두 높으면:
→ 진짜 예측력이 있음
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from scipy.stats import spearmanr

def main():
    print("=" * 60)
    print("  Data Leakage 검증")
    print("=" * 60)
    
    # 데이터 로드
    df = pd.read_csv(project_root / 'data_cache/step3_features_annual.csv', index_col=0)
    
    print("\n[1] 데이터 구조 확인")
    print("-" * 40)
    print("현재 구조 (FY2023 row 예시):")
    print("  - m3 = FY2023 AdjOI / FY2023 Equity (2023년 12월 결산)")
    print("  - y = ln(MarketCap / Equity)")
    print("      - Price = EndDate + 3개월 = 2024년 3월 주가")
    print("      - Equity = FY2023 결산치")
    print()
    print("→ m3와 y 모두 '공시 시점'의 정보")
    print("→ 미래 데이터 사용 X (Leakage 아님)")
    
    print("\n[2] 동시점 vs 예측 상관계수 비교")
    print("-" * 40)
    
    valid = df.dropna(subset=['m1', 'm2', 'm3', 'y'])
    results = []
    
    for ticker in valid['Ticker'].unique():
        t = valid[valid['Ticker'] == ticker].sort_values('FiscalYear').copy()
        if len(t) < 3:
            continue
        
        # y[t+1] = 다음 해의 y
        t['y_next'] = t['y'].shift(-1)
        t_valid = t.dropna(subset=['m3', 'y_next'])
        
        if len(t_valid) >= 2:
            results.append(t_valid[['m3', 'y', 'y_next']])
    
    all_data = pd.concat(results)
    
    corr_same, _ = spearmanr(all_data['m3'], all_data['y'])
    corr_next, _ = spearmanr(all_data['m3'], all_data['y_next'])
    
    print(f"m3 vs y (동시점, t):    {corr_same:.4f}")
    print(f"m3 vs y_next (예측, t+1): {corr_next:.4f}")
    print()
    print(f"상관계수 변화: {corr_same:.4f} → {corr_next:.4f}")
    print(f"감소율: {(1 - corr_next/corr_same) * 100:.1f}%")
    
    print("\n[3] 연도별 Cross-sectional 비교")
    print("-" * 40)
    
    print(f"{'Year':<6} {'m3 vs y[t]':<12} {'m3 vs y[t+1]':<12} {'차이':<8}")
    print("-" * 40)
    
    for year in sorted(valid['FiscalYear'].unique()):
        year_df = valid[valid['FiscalYear'] == year]
        next_year_df = valid[valid['FiscalYear'] == year + 1]
        
        if len(year_df) < 10:
            continue
        
        # 동시점
        corr_t, _ = spearmanr(year_df['m3'], year_df['y'])
        
        # 예측: 올해 m3로 내년 y 예측
        merged = year_df[['Ticker', 'm3']].merge(
            next_year_df[['Ticker', 'y']], 
            on='Ticker', 
            how='inner',
            suffixes=('', '_next')
        )
        
        if len(merged) >= 10:
            corr_next, _ = spearmanr(merged['m3'], merged['y'])
            diff = corr_next - corr_t
            print(f"FY{year}  {corr_t:>8.4f}     {corr_next:>8.4f}     {diff:>+.4f}")
        else:
            print(f"FY{year}  {corr_t:>8.4f}     {'N/A':>8}     {'N/A':>8}")
    
    print("\n[4] 결론")
    print("-" * 40)
    
    if corr_next < 0.1:
        print("🚨 경고: m3의 예측력(t+1)이 거의 없음!")
        print()
        print("해석:")
        print("  - 동시점 상관계수가 높은 이유:")
        print("    ROE 높은 기업은 PBR도 높다 (효율적 시장)")
        print()
        print("  - 예측 상관계수가 낮은 이유:")
        print("    올해 ROE가 내년 PBR을 예측하지 못함")
        print("    (시장은 이미 ROE를 반영했고, 내년은 새로운 정보가 필요)")
        print()
        print("조치 필요:")
        print("  1. 현재 모델은 '예측'이 아니라 '동시점 설명'")
        print("  2. 진정한 예측을 위해 y를 t+1로 shift 필요")
        print("  3. 또는 m3 제외하고 m1+m2만 사용")
    else:
        print("✅ m3가 다음 해 y를 어느 정도 예측함")
        print(f"   예측 상관계수: {corr_next:.4f}")


if __name__ == '__main__':
    main()
