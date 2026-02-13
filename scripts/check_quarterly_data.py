import pandas as pd
import os

print("=== 기존 분기/반기 데이터 현황 ===\n")

# Step3 Quarterly
quarterly = pd.read_csv('data_cache/step3_features_quarterly.csv')
print(f"Step3 Quarterly Features:")
print(f"  - 전체 레코드: {len(quarterly)}")
print(f"  - 유니크 티커: {quarterly['Ticker'].nunique()}")
print(f"  - 연도 범위: {quarterly['FiscalYear'].min()}-{quarterly['FiscalYear'].max()}")

# Step3 Semiannual
semiannual = pd.read_csv('data_cache/step3_features_semiannual.csv')
print(f"\nStep3 Semiannual Features:")
print(f"  - 전체 레코드: {len(semiannual)}")
print(f"  - 유니크 티커: {semiannual['Ticker'].nunique()}")
print(f"  - 연도 범위: {semiannual['FiscalYear'].min()}-{semiannual['FiscalYear'].max()}")

# Step4 Predictions
pred_q = pd.read_csv('data_cache/step4_predictions_ranknet_quarterly.csv')
pred_s = pd.read_csv('data_cache/step4_predictions_ranknet_semiannual.csv')
print(f"\nStep4 Quarterly Predictions: {len(pred_q)} rows, {pred_q['Ticker'].nunique()} tickers")
print(f"Step4 Semiannual Predictions: {len(pred_s)} rows, {pred_s['Ticker'].nunique()} tickers")

# Step2 fund_quarterly 확인
print(f"\n=== Step2 분기/반기 재무데이터 파일 존재 여부 ===")
print(f"step2_fund_quarterly.csv: {os.path.exists('data_cache/step2_fund_quarterly.csv')}")
print(f"step2_fund_semiannual.csv: {os.path.exists('data_cache/step2_fund_semiannual.csv')}")

# data_cache_quarterly 폴더
print(f"\n=== data_cache_quarterly 폴더 ===")
if os.path.exists('data_cache_quarterly'):
    for f in sorted(os.listdir('data_cache_quarterly')):
        size = os.path.getsize(f'data_cache_quarterly/{f}')
        print(f"  {f}: {size/1024/1024:.1f} MB")
else:
    print("  폴더 없음")
