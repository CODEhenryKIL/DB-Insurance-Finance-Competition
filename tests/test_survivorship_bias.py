"""
생존 편향(Survivorship Bias) 진단 테스트
==========================================
상장폐지/파산 종목 데이터가 yfinance를 통해 수집되는지 확인
"""

import yfinance as yf
import pandas as pd
from datetime import datetime

def test_delisted_stock(ticker: str, name: str, delisting_date: str):
    """
    상장폐지 종목 데이터 수집 테스트
    
    Parameters
    ----------
    ticker : str
        티커 심볼
    name : str
        회사명
    delisting_date : str
        상장폐지 예상일
    """
    print(f"\n{'='*60}")
    print(f"Testing: {ticker} ({name})")
    print(f"Expected Delisting: {delisting_date}")
    print(f"{'='*60}")
    
    try:
        # yfinance로 데이터 다운로드
        stock = yf.Ticker(ticker)
        hist = stock.history(period="max")
        
        if hist.empty:
            print(f"❌ FAILED: No data available for {ticker}")
            print(f"   → Survivorship Bias 가능성: 높음")
            return False
        
        # 데이터 범위 확인
        first_date = hist.index[0].strftime('%Y-%m-%d')
        last_date = hist.index[-1].strftime('%Y-%m-%d')
        total_days = len(hist)
        
        print(f"✅ SUCCESS: Data found for {ticker}")
        print(f"   → First Date: {first_date}")
        print(f"   → Last Date: {last_date}")
        print(f"   → Total Days: {total_days}")
        
        # 최근 데이터까지 있으면 의심
        if last_date >= '2024-01-01':
            print(f"   ⚠️  WARNING: Data extends to {last_date}")
            print(f"   → This stock should have delisted around {delisting_date}")
            print(f"   → Possible ticker rename or merger (not true delisting)")
        else:
            print(f"   ✓ Data ends at {last_date} (before current date)")
            print(f"   → Delisted stock data IS available!")
        
        # 마지막 몇 개 가격 확인
        print(f"\n   Last 5 prices:")
        print(hist[['Close']].tail())
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def analyze_current_dataset_dates():
    """
    현재 수집된 데이터셋의 Last Date 분포 확인
    """
    print(f"\n{'='*60}")
    print("Analyzing Current Dataset: Last Date Distribution")
    print(f"{'='*60}")
    
    try:
        # Step1 가격 데이터 로드
        price_df = pd.read_csv('../data_cache/step1_px_close_m.csv', index_col=0, parse_dates=True)
        
        # 각 티커별 마지막 날짜 확인
        last_dates = {}
        for ticker in price_df.columns:
            ticker_data = price_df[ticker].dropna()
            if len(ticker_data) > 0:
                last_dates[ticker] = ticker_data.index[-1]
        
        # DataFrame으로 변환
        last_dates_df = pd.DataFrame.from_dict(
            last_dates, 
            orient='index', 
            columns=['Last_Date']
        )
        last_dates_df['Last_Date'] = pd.to_datetime(last_dates_df['Last_Date'])
        last_dates_df['Year'] = last_dates_df['Last_Date'].dt.year
        
        # 통계
        print(f"\n총 티커 수: {len(last_dates_df)}")
        print(f"\nLast Date 연도별 분포:")
        year_counts = last_dates_df['Year'].value_counts().sort_index()
        for year, count in year_counts.items():
            print(f"  {year}: {count}개 ({count/len(last_dates_df)*100:.1f}%)")
        
        # 판단
        recent_data_ratio = len(last_dates_df[last_dates_df['Year'] >= 2024]) / len(last_dates_df)
        print(f"\n2024년 이후 데이터 비율: {recent_data_ratio*100:.1f}%")
        
        if recent_data_ratio > 0.95:
            print("❌ 생존 편향 위험: 매우 높음 (95% 이상이 최신 데이터)")
        elif recent_data_ratio > 0.80:
            print("⚠️  생존 편향 위험: 높음 (80% 이상이 최신 데이터)")
        else:
            print("✓ 생존 편향 위험: 낮음 (과거 상폐 종목 데이터 포함 가능성)")
        
        # 상세 출력 (연도별 티커 샘플)
        print(f"\n연도별 티커 샘플 (각 연도당 최대 5개):")
        for year in sorted(last_dates_df['Year'].unique()):
            tickers = last_dates_df[last_dates_df['Year'] == year].index.tolist()[:5]
            print(f"  {year}: {', '.join(tickers)}")
        
    except FileNotFoundError:
        print("❌ data_cache/step1_px_close_m.csv 파일을 찾을 수 없습니다.")
        print("   → Step1을 먼저 실행하세요.")
    except Exception as e:
        print(f"❌ ERROR: {e}")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("생존 편향(Survivorship Bias) 진단 테스트")
    print("="*60)
    
    # 1. 상장폐지 종목 테스트
    test_stocks = [
        ('SIVB', 'Silicon Valley Bank', '2023-03'),
        ('BBBY', 'Bed Bath & Beyond', '2023-06'),
        ('TWTR', 'Twitter', '2022-10'),
    ]
    
    results = []
    for ticker, name, delisting_date in test_stocks:
        result = test_delisted_stock(ticker, name, delisting_date)
        results.append((ticker, result))
    
    # 2. 현재 데이터셋 분석
    analyze_current_dataset_dates()
    
    # 3. 최종 판단
    print(f"\n{'='*60}")
    print("최종 판단")
    print(f"{'='*60}")
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    print(f"\n상장폐지 종목 데이터 수집 성공: {success_count}/{total_count}")
    
    if success_count == 0:
        print("\n❌ yfinance는 상장폐지 종목 데이터를 제공하지 않습니다.")
        print("   → 현재 백테스트는 생존 편향(Survivorship Bias)에 노출되어 있습니다.")
        print("   → CAGR 19.82%는 과대평가되었을 가능성이 높습니다.")
        print("\n권장 사항:")
        print("  1. S&P 500 Historical Constituents 데이터 확보")
        print("  2. 리포트에 생존 편향 한계 명시")
        print("  3. 보수적 수익률 추정 (예: CAGR * 0.7)")
    elif success_count < total_count:
        print("\n⚠️  일부 상장폐지 종목 데이터만 수집되었습니다.")
        print("   → 부분적 생존 편향 가능성")
    else:
        print("\n✓ 상장폐지 종목 데이터가 수집됩니다!")
        print("   → 생존 편향 위험 낮음")
