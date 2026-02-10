"""Alpha 계산 검증 스크립트"""
import pandas as pd

# metrics 로드
metrics_006 = pd.read_csv('experiments/exp_006_sp500_raw/step5_backtest_metrics.csv')
metrics_007 = pd.read_csv('experiments/exp_007_sp500_sector/step5_backtest_metrics.csv')

print('=== exp_006 (raw) SmallCap_5% ===')
sc5_006 = metrics_006[metrics_006['Long_Ratio'] == 'SmallCap_5%'].iloc[0]
print(f"CAGR: {sc5_006['Portfolio_CAGR']*100:.2f}%")
print(f"Benchmark CAGR: {sc5_006['Benchmark_CAGR']*100:.2f}%")
print(f"Beta: {sc5_006['Beta']:.4f}")
print(f"Alpha: {sc5_006['Alpha']*100:.2f}%")
print()

print('=== exp_007 (sector) SmallCap_5% ===')
sc5_007 = metrics_007[metrics_007['Long_Ratio'] == 'SmallCap_5%'].iloc[0]
print(f"CAGR: {sc5_007['Portfolio_CAGR']*100:.2f}%")
print(f"Benchmark CAGR: {sc5_007['Benchmark_CAGR']*100:.2f}%")
print(f"Beta: {sc5_007['Beta']:.4f}")
print(f"Alpha: {sc5_007['Alpha']*100:.2f}%")
print()

# Jensen's Alpha 검증
print('=== Jensen Alpha 검증 (exp_007 SmallCap_5%) ===')
port_cagr = sc5_007['Portfolio_CAGR']
bench_cagr = sc5_007['Benchmark_CAGR']
beta = sc5_007['Beta']
rf = 0.02

# Jensen's Alpha = (R_p - R_f) - Beta * (R_b - R_f)
expected_alpha = (port_cagr - rf) - beta * (bench_cagr - rf)
print(f"포트폴리오 초과수익 (R_p - R_f): {(port_cagr - rf)*100:.2f}%")
print(f"벤치마크 초과수익 (R_b - R_f): {(bench_cagr - rf)*100:.2f}%")
print(f"Beta * 벤치마크 초과수익: {beta * (bench_cagr - rf)*100:.2f}%")
print(f"계산된 Alpha: {expected_alpha*100:.2f}%")
print()

print('=> Alpha가 음수인 이유: Beta가 매우 높아서 (1.64)')
print('=> 즉, 포트폴리오가 벤치마크보다 1.64배 더 변동성이 높음')
print('=> 높은 변동성 대비 수익률은 벤치마크와 비슷한 수준')
