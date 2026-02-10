"""
손실된 티커 분석 스크립트
Step 1 (3,640개) vs Step 2 (2,774개) 비교
"""
import json
import pandas as pd
from pathlib import Path

# 1. Step 0/1 유니버스 로드 (3,640개)
with open('data_cache/step0_valid_universe.json', 'r') as f:
    universe = json.load(f)

universe_tickers = {item['ticker']: item for item in universe}
print(f"Step 1 유니버스: {len(universe_tickers):,}개")

# 2. Step 2 재무 데이터 로드
df = pd.read_csv('data_cache/step2_fund_annual.csv')
step2_tickers = set(df['Ticker'].unique())
print(f"Step 2 수집 성공: {len(step2_tickers):,}개")

# 3. 손실된 티커 찾기
lost_tickers = set(universe_tickers.keys()) - step2_tickers
print(f"손실된 티커: {len(lost_tickers):,}개")

# 4. 손실된 티커 상세 정보
lost_data = []
for ticker in sorted(lost_tickers):
    info = universe_tickers.get(ticker, {})
    lost_data.append({
        'ticker': ticker,
        'sector': info.get('sector', 'Unknown'),
        'industry': info.get('industry', 'Unknown'),
        'name': info.get('name', ticker),
        'cik': info.get('cik', '')
    })

lost_df = pd.DataFrame(lost_data)

# 5. 섹터별 손실 분석
print("\n" + "=" * 70)
print("📊 섹터별 손실 분석 (Step 1 유니버스 대비)")
print("=" * 70)

# 유니버스 섹터별 카운트
universe_sector_counts = {}
for item in universe:
    sec = item['sector']
    universe_sector_counts[sec] = universe_sector_counts.get(sec, 0) + 1

# 손실 섹터별 카운트
lost_sector_counts = lost_df['Sector'].value_counts() if 'Sector' in lost_df.columns else lost_df['sector'].value_counts()

print(f"\n{'섹터':<30} {'유니버스':>8} {'손실':>8} {'손실률':>10} {'수집률':>10}")
print("-" * 70)

total_universe = len(universe_tickers)
total_lost = len(lost_tickers)

for sector in sorted(universe_sector_counts.keys()):
    uni_count = universe_sector_counts[sector]
    lost_count = lost_sector_counts.get(sector, 0)
    lost_pct = (lost_count / uni_count * 100) if uni_count > 0 else 0
    collected_pct = 100 - lost_pct
    print(f"  {sector:<28} {uni_count:>6,}개 {lost_count:>6,}개 {lost_pct:>8.1f}% {collected_pct:>8.1f}%")

print("-" * 70)
print(f"  {'합계':<28} {total_universe:>6,}개 {total_lost:>6,}개 {total_lost/total_universe*100:>8.1f}% {(total_universe-total_lost)/total_universe*100:>8.1f}%")

# 6. CSV 저장
output_path = Path('data_cache/step2_lost_tickers.csv')
lost_df.to_csv(output_path, index=False)
print(f"\n✅ 손실 티커 저장 완료: {output_path}")
print(f"   → {len(lost_df)}개 티커")

# 7. 손실 원인 설명
print("\n" + "=" * 70)
print("❓ 손실 원인 (SEC EDGAR API 실패 이유)")
print("=" * 70)
print("""
1. '필수 필드 없음' (us-gaap 태그 누락)
   - SEC 10-K/10-Q에서 아래 핵심 항목을 찾을 수 없는 경우:
     • Assets (자산총계) 또는 StockholdersEquity (자본총계)
     • 이 중 하나라도 없으면 PBR 계산 불가 → 제외
   
2. 'us-gaap 데이터 없음'
   - 외국 기업으로 IFRS(국제회계기준) 사용
   - 예: 중국 ADR (BABA, JD), 유럽 기업 등
   - M-Model은 US-GAAP 기업만 대상

3. '404 에러' (CIK 데이터 없음)
   - SEC에 해당 CIK로 등록된 데이터가 없음
   - 신생 기업이거나 아직 연간보고서 미제출

4. '기타 API 에러'
   - 네트워크 타임아웃
   - SEC 서버 일시적 장애
""")

# 8. 샘플 출력
print("\n" + "=" * 70)
print("📋 손실 티커 샘플 (섹터별 상위 5개)")
print("=" * 70)

for sector in sorted(lost_df['sector'].unique()):
    sector_lost = lost_df[lost_df['sector'] == sector].head(5)
    print(f"\n[{sector}] ({len(lost_df[lost_df['sector'] == sector])}개)")
    for _, row in sector_lost.iterrows():
        print(f"  - {row['ticker']:8s} : {row['name'][:40]}")
