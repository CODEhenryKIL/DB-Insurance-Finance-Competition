"""
===========================================
S&P 500 Historical Constituents 생성기
===========================================

이 스크립트의 역할:
1. Wikipedia에서 현재 S&P 500 구성종목 가져오기
2. 변경 이력(Added/Removed)을 역산하여 연도별 구성종목 계산
3. 연도별 S&P 500 티커를 JSON으로 저장
4. 기존 step2_fund_annual.csv에서 해당 티커만 추출하여 step2_fund_annual_sp500.csv 생성

출력 파일:
- data_cache/sp500_historical_constituents.json: 연도별 S&P 500 티커
- data_cache/step2_fund_annual_sp500.csv: S&P 500 전용 재무 데이터

이후 Step 3, 4, 5는 이 파일을 사용하면 됩니다.
"""

import sys
from pathlib import Path
import json
from datetime import datetime
from collections import defaultdict

# 프로젝트 루트 설정
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import requests
from io import StringIO

from config.paths import CACHE_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


def fetch_sp500_data():
    """Wikipedia에서 S&P 500 현재 구성종목 및 변경 이력 가져오기"""
    logger.info("Wikipedia에서 S&P 500 데이터 다운로드 중...")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    tables = pd.read_html(StringIO(response.text))
    
    # 현재 구성종목 (첫 번째 테이블)
    current_df = tables[0]
    current_df['Symbol'] = current_df['Symbol'].str.replace('.', '-', regex=False)
    
    # 변경 이력 (두 번째 테이블)
    changes_df = tables[1]
    
    # MultiIndex 컬럼을 평탄화
    changes_df.columns = ['Date', 'Added_Ticker', 'Added_Security', 'Removed_Ticker', 'Removed_Security', 'Reason']
    
    # 티커 정규화
    changes_df['Added_Ticker'] = changes_df['Added_Ticker'].astype(str).str.replace('.', '-', regex=False)
    changes_df['Removed_Ticker'] = changes_df['Removed_Ticker'].astype(str).str.replace('.', '-', regex=False)
    
    logger.info(f"  → 현재 구성종목: {len(current_df)}개")
    logger.info(f"  → 변경 이력: {len(changes_df)}건")
    
    return current_df, changes_df


def parse_change_date(date_str):
    """변경 날짜 파싱"""
    try:
        # 'December 22, 2025' 형식
        return datetime.strptime(date_str.strip(), '%B %d, %Y')
    except:
        try:
            # 'December 2025' 형식 (일 없음)
            return datetime.strptime(date_str.strip(), '%B %Y')
        except:
            return None


def build_historical_constituents(current_df, changes_df, start_year=2012, end_year=2025):
    """
    변경 이력을 역산하여 연도별 S&P 500 구성종목 계산
    
    로직:
    1. 현재(2025) 구성종목에서 시작
    2. 과거로 역산하면서:
       - Added 티커 → 제거
       - Removed 티커 → 추가
    3. 각 연도 말(12월 31일) 기준 구성종목 저장
    """
    logger.info(f"연도별 S&P 500 구성종목 계산 중 ({start_year}~{end_year})...")
    
    # 현재 구성종목으로 시작 (NaN 제거)
    current_tickers = set([t for t in current_df['Symbol'].tolist() if pd.notna(t) and str(t) != 'nan'])
    logger.info(f"  → 현재(2025) 구성종목: {len(current_tickers)}개")
    
    # 변경 이력을 날짜순 정렬 (최신 → 과거)
    changes_df['ParsedDate'] = changes_df['Date'].apply(parse_change_date)
    changes_df = changes_df.dropna(subset=['ParsedDate'])
    changes_df = changes_df.sort_values('ParsedDate', ascending=False)
    
    # 연도별 구성종목 저장
    historical = {}
    
    # 현재 연도부터 시작
    working_set = current_tickers.copy()
    
    for year in range(end_year, start_year - 1, -1):
        year_end = datetime(year, 12, 31)
        
        # 해당 연도에 발생한 변경사항 적용 (역산)
        year_changes = changes_df[
            (changes_df['ParsedDate'] > datetime(year, 1, 1)) & 
            (changes_df['ParsedDate'] <= datetime(year + 1, 1, 1))
        ]
        
        for _, row in year_changes.iterrows():
            added = row['Added_Ticker']
            removed = row['Removed_Ticker']
            
            # 역산: Added → 제거, Removed → 추가
            if pd.notna(added) and str(added) not in ('nan', 'NaN', ''):
                working_set.discard(str(added))
            if pd.notna(removed) and str(removed) not in ('nan', 'NaN', ''):
                working_set.add(str(removed))
        
        # NaN 제거 후 정렬
        clean_set = [t for t in working_set if pd.notna(t) and str(t) not in ('nan', 'NaN', '')]
        historical[year] = sorted(clean_set)
        logger.info(f"  → {year}년 말: {len(historical[year])}개 티커")
    
    return historical


def create_sp500_fundamental_data(historical_constituents, output_file):
    """
    연도별 S&P 500 구성종목 기준으로 step2_fund_annual.csv에서 필터링
    
    각 연도의 재무 데이터는 해당 연도의 S&P 500 구성종목만 포함
    """
    logger.info("S&P 500 전용 재무 데이터 생성 중...")
    
    # Step2 재무 데이터 로드
    fund_df = pd.read_csv(CACHE_DIR / 'step2_fund_annual.csv', index_col=0)
    logger.info(f"  → 원본 재무 데이터: {len(fund_df):,}행, {fund_df['Ticker'].nunique()}개 티커")
    
    # 연도별로 필터링
    filtered_rows = []
    
    for year, tickers in historical_constituents.items():
        year_data = fund_df[
            (fund_df['FiscalYear'] == year) & 
            (fund_df['Ticker'].isin(tickers))
        ]
        filtered_rows.append(year_data)
        logger.debug(f"  → {year}년: {len(year_data)}개 기업 재무 데이터")
    
    # 결합
    sp500_fund_df = pd.concat(filtered_rows, ignore_index=True)
    
    # 저장
    sp500_fund_df.to_csv(output_file)
    logger.info(f"  → S&P 500 재무 데이터 저장: {output_file}")
    logger.info(f"  → 총 {len(sp500_fund_df):,}행, {sp500_fund_df['Ticker'].nunique()}개 티커")
    
    # 연도별 통계
    year_stats = sp500_fund_df.groupby('FiscalYear')['Ticker'].nunique()
    logger.info("  → 연도별 티커 수:")
    for year, count in year_stats.items():
        logger.info(f"     {year}: {count}개")
    
    return sp500_fund_df


def main():
    """메인 실행"""
    logger.info("")
    logger.info("="*60)
    logger.info("  S&P 500 Historical Constituents 생성")
    logger.info("="*60)
    
    # 1. Wikipedia에서 데이터 가져오기
    current_df, changes_df = fetch_sp500_data()
    
    # 2. 연도별 구성종목 계산
    historical = build_historical_constituents(current_df, changes_df, start_year=2012, end_year=2025)
    
    # 3. JSON 저장
    output_json = CACHE_DIR / 'sp500_historical_constituents.json'
    with open(output_json, 'w') as f:
        json.dump(historical, f, indent=2)
    logger.info(f"✅ 연도별 S&P 500 티커 저장: {output_json}")
    
    # 4. S&P 500 전용 재무 데이터 생성
    output_csv = CACHE_DIR / 'step2_fund_annual_sp500.csv'
    create_sp500_fundamental_data(historical, output_csv)
    
    # 5. 현재 S&P 500 구성종목도 별도 저장 (섹터 정보 포함)
    current_df.to_csv(CACHE_DIR / 'sp500_current_constituents.csv', index=False)
    logger.info(f"✅ 현재 S&P 500 구성종목 저장: {CACHE_DIR / 'sp500_current_constituents.csv'}")
    
    logger.info("")
    logger.info("="*60)
    logger.info("  완료!")
    logger.info("="*60)
    logger.info("")
    logger.info("다음 단계:")
    logger.info("  1. config/constants.py에서 MARKET_MODE = 'SP500' 설정")
    logger.info("  2. python -m feature_engineering.step3_feature_builder")
    logger.info("  3. python -m modeling.step4_train_predict")
    logger.info("  4. python -m backtesting.step5_backtest")
    
    return historical


if __name__ == '__main__':
    historical = main()
