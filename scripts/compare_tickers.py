import pandas as pd

# Annual features
annual = pd.read_csv('data_cache/step3_features_annual.csv')
print(f'Annual features: {annual["Ticker"].nunique()} tickers')

# Annual predictions
pred_annual = pd.read_csv('data_cache/step4_predictions_ranknet.csv')
print(f'Annual predictions: {pred_annual["Ticker"].nunique()} tickers')

# Quarterly features 
quarterly = pd.read_csv('data_cache/step3_features_quarterly.csv')
print(f'Quarterly features: {quarterly["Ticker"].nunique()} tickers')

# Quarterly predictions
pred_q = pd.read_csv('data_cache/step4_predictions_ranknet_quarterly.csv')
print(f'Quarterly predictions: {pred_q["Ticker"].nunique()} tickers')

# Semiannual features
semiannual = pd.read_csv('data_cache/step3_features_semiannual.csv')
print(f'Semiannual features: {semiannual["Ticker"].nunique()} tickers')

# Semiannual predictions
pred_s = pd.read_csv('data_cache/step4_predictions_ranknet_semiannual.csv')
print(f'Semiannual predictions: {pred_s["Ticker"].nunique()} tickers')
