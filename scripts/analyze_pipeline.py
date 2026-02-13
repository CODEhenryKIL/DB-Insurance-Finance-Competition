import pandas as pd
import json

print("=== 전체 데이터 파이프라인 현황 ===\n")

# Step0: 유효 유니버스
with open('data_cache/step0_valid_universe.json') as f:
    valid = json.load(f)
print(f"Step0 유효 유니버스: {len(valid)} 티커")
valid_tickers = set([v['ticker'] for v in valid])

# Step1: 가격 데이터
px = pd.read_csv('data_cache/step1_px_adj_m.csv', index_col=0)
print(f"Step1 가격 데이터: {px.shape[1]} 티커")

# Step2: 재무데이터
fund = pd.read_csv('data_cache/step2_fund_annual.csv')
step2_tickers = fund['Ticker'].unique()
print(f"Step2 재무데이터: {len(step2_tickers)} 티커")

# Step3: 피처 (연간)
feat = pd.read_csv('data_cache/step3_features_annual.csv')
step3_tickers = feat['Ticker'].unique()
print(f"Step3 피처 (Annual): {len(step3_tickers)} 티커")

# Step4: 예측값
pred = pd.read_csv('data_cache/step4_predictions_ranknet.csv')
step4_tickers = pred['Ticker'].unique()
print(f"Step4 Predictions: {len(step4_tickers)} 티커")

print("\n=== 데이터 흐름 분석 ===")
print(f"Step0 -> Step1: {len(valid_tickers)} -> {px.shape[1]}")
print(f"Step1 -> Step2: {px.shape[1]} -> {len(step2_tickers)} (수집 성공률 {len(step2_tickers)/len(valid_tickers)*100:.1f}%)")
print(f"Step2 -> Step3: {len(step2_tickers)} -> {len(step3_tickers)} *** 병목!")
print(f"Step3 -> Step4: {len(step3_tickers)} -> {len(step4_tickers)}")

# Step3에서 필터링 확인
print("\n=== Step3 병목 원인 분석 ===")

# SP500 티커 확인
sp500 = set(open('data_cache/sp500_tickers.txt').read().strip().split('\n'))
step3_in_sp500 = len(set(step3_tickers) & sp500)
step3_not_sp500 = len(set(step3_tickers) - sp500)
print(f"Step3 티커 중 SP500: {step3_in_sp500}")
print(f"Step3 티커 중 비-SP500: {step3_not_sp500}")

# Step2에서 Step3로 못 간 티커 이유
step2_set = set(step2_tickers)
step3_set = set(step3_tickers)
lost_in_step3 = step2_set - step3_set
print(f"\nStep2->Step3 손실 티커: {len(lost_in_step3)}")

# 샘플 확인
print(f"손실 티커 샘플: {list(lost_in_step3)[:10]}")
