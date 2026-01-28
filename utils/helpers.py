"""
===========================================
공통 헬퍼 함수
===========================================

이 파일의 역할:
- 프로젝트 전반에서 자주 사용되는 유틸리티 함수 제공
- 파일 I/O, 캐시 관리, Pandas 호환성 처리 등

주요 함수:
1. ensure_dir(): 디렉토리 생성
2. load_cache(): 캐시 파일 로드 (csv/json 자동 판별)
3. save_cache(): 캐시 파일 저장
4. get_month_end_freq(): Pandas 버전 호환 월말 frequency
5. convert_to_datetime(): 다양한 형식의 날짜를 datetime으로 변환

Pandas 호환성:
- Pandas 2.2.0+: resample 'ME' 사용
- Pandas < 2.2.0: resample 'M' 사용
- 자동 판별하여 적절한 frequency 반환
"""

import json
import pandas as pd
from pathlib import Path
from typing import Union, Any, Dict
from packaging import version

from utils.logger import get_logger

# 로거 초기화
logger = get_logger(__name__)


# ===========================================
# 1. 디렉토리 관리
# ===========================================

def ensure_dir(directory: Union[str, Path]) -> Path:
    """
    디렉토리가 없으면 생성합니다.
    이미 존재하면 아무 작업도 하지 않습니다.
    
    Args:
        directory: 디렉토리 경로 (문자열 또는 Path 객체)
    
    Returns:
        Path: 생성된 (또는 기존) 디렉토리 경로
    
    사용 예시:
        # 캐시 디렉토리 확인 및 생성
        cache_dir = ensure_dir('data_cache')
        
        # 중첩 디렉토리도 자동 생성
        ensure_dir('data_cache/edgar_cache/2020')
    """
    # Path 객체로 변환
    dir_path = Path(directory)
    
    # 디렉토리 생성
    # parents=True: 중간 경로도 자동 생성
    # exist_ok=True: 이미 존재해도 에러 안남
    dir_path.mkdir(parents=True, exist_ok=True)
    
    return dir_path


# ===========================================
# 2. 캐시 관리
# ===========================================

def load_cache(
    filepath: Union[str, Path],
    file_type: str = 'auto'
) -> Union[pd.DataFrame, Dict]:
    """
    캐시 파일을 로드합니다.
    파일 확장자에 따라 자동으로 포맷 판별
    
    지원 포맷:
    - CSV: pandas DataFrame으로 로드
    - JSON: dict으로 로드
    
    Args:
        filepath: 파일 경로
        file_type: 파일 타입 ('auto', 'csv', 'json')
                  'auto'면 확장자로 자동 판별
    
    Returns:
        DataFrame (CSV) 또는 dict (JSON)
    
    Raises:
        FileNotFoundError: 파일이 없는 경우
        ValueError: 지원하지 않는 파일 타입
    
    사용 예시:
        # CSV 로드
        df = load_cache('data_cache/step1_px_adj_m.csv')
        
        # JSON 로드
        meta = load_cache('data_cache/step1_meta.json')
        
        # 타입 명시
        df = load_cache('data.txt', file_type='csv')
    """
    filepath = Path(filepath)
    
    # 파일 존재 확인
    if not filepath.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")
    
    # 파일 타입 결정
    if file_type == 'auto':
        ext = filepath.suffix.lower()
        if ext == '.csv':
            file_type = 'csv'
        elif ext == '.json':
            file_type = 'json'
        else:
            raise ValueError(f"지원하지 않는 확장자: {ext}. CSV 또는 JSON만 가능합니다.")
    
    # 파일 타입별 로드
    logger.info(f"캐시 로드 중: {filepath.name}")
    
    if file_type == 'csv':
        # CSV → DataFrame
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        logger.info(f"  → CSV 로드 완료: {df.shape[0]:,} 행 × {df.shape[1]} 열")
        return df
    
    elif file_type == 'json':
        # JSON → dict
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"  → JSON 로드 완료: {len(data)} 개 키")
        return data
    
    else:
        raise ValueError(f"지원하지 않는 파일 타입: {file_type}")


def save_cache(
    data: Union[pd.DataFrame, Dict],
    filepath: Union[str, Path],
    file_type: str = 'auto'
):
    """
    데이터를 캐시 파일로 저장합니다.
    
    Args:
        data: 저장할 데이터 (DataFrame 또는 dict)
        filepath: 저장 경로
        file_type: 파일 타입 ('auto', 'csv', 'json')
                  'auto'면 데이터 타입으로 자동 판별
    
    사용 예시:
        # DataFrame을 CSV로 저장
        save_cache(df, 'data_cache/step1_px_adj_m.csv')
        
        # dict을 JSON으로 저장
        save_cache(meta_dict, 'data_cache/step1_meta.json')
    """
    filepath = Path(filepath)
    
    # 디렉토리 생성
    ensure_dir(filepath.parent)
    
    # 파일 타입 결정
    if file_type == 'auto':
        if isinstance(data, pd.DataFrame):
            file_type = 'csv'
        elif isinstance(data, dict):
            file_type = 'json'
        else:
            raise ValueError(f"지원하지 않는 데이터 타입: {type(data)}")
    
    # 파일 타입별 저장
    logger.info(f"캐시 저장 중: {filepath.name}")
    
    if file_type == 'csv':
        # DataFrame → CSV
        if not isinstance(data, pd.DataFrame):
            raise ValueError("CSV 저장은 DataFrame만 가능합니다")
        
        data.to_csv(filepath)
        logger.info(f"  → CSV 저장 완료: {data.shape[0]:,} 행 × {data.shape[1]} 열")
    
    elif file_type == 'json':
        # dict → JSON
        if not isinstance(data, dict):
            raise ValueError("JSON 저장은 dict만 가능합니다")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"  → JSON 저장 완료: {len(data)} 개 키")
    
    else:
        raise ValueError(f"지원하지 않는 파일 타입: {file_type}")


# ===========================================
# 3. Pandas 버전 호환성
# ===========================================

def get_month_end_freq() -> str:
    """
    Pandas 버전에 따라 월말 resample frequency를 반환합니다.
    
    Pandas 버전별 차이:
    - Pandas >= 2.2.0: 'ME' (Month End) 사용
    - Pandas < 2.2.0: 'M' 사용
    
    이 함수는 자동으로 버전을 감지하여 적절한 frequency를 반환합니다.
    
    Returns:
        str: 'ME' 또는 'M'
    
    사용 예시:
        # 월말 가격 데이터 리샘플링
        freq = get_month_end_freq()
        df_monthly = df.resample(freq).last()
        
        # 버전 호환 코드
        prices_monthly = prices_daily.resample(get_month_end_freq(), on='Date').last()
    """
    # 현재 pandas 버전 확인
    pd_version = version.parse(pd.__version__)
    target_version = version.parse('2.2.0')
    
    if pd_version >= target_version:
        logger.debug(f"Pandas {pd.__version__}: 'ME' 사용")
        return 'ME'
    else:
        logger.debug(f"Pandas {pd.__version__}: 'M' 사용 (구버전 호환)")
        return 'M'


# ===========================================
# 4. 날짜 변환
# ===========================================

def convert_to_datetime(
    date_input: Any,
    format: str = None
) -> pd.Timestamp:
    """
    다양한 형식의 날짜를 pandas Timestamp로 변환합니다.
    
    지원 형식:
    - 문자열: '2020-12-31', '2020/12/31' 등
    - datetime 객체
    - pandas Timestamp
    - epoch (Unix timestamp)
    
    Args:
        date_input: 날짜 데이터 (다양한 형식)
        format: 날짜 포맷 (선택, 자동 판별 가능)
    
    Returns:
        pandas Timestamp 객체
    
    사용 예시:
        # 문자열 변환
        dt = convert_to_datetime('2020-12-31')
        
        # 다양한 형식 처리
        dt = convert_to_datetime('12/31/2020')
        dt = convert_to_datetime(pd.Timestamp('2020-12-31'))
    """
    if isinstance(date_input, pd.Timestamp):
        # 이미 Timestamp면 그대로 반환
        return date_input
    
    elif isinstance(date_input, str):
        # 문자열 → Timestamp
        if format:
            return pd.to_datetime(date_input, format=format)
        else:
            return pd.to_datetime(date_input)
    
    else:
        # 기타 (datetime, epoch 등) → Timestamp
        return pd.Timestamp(date_input)


# ===========================================
# 5. 기간 생성
# ===========================================

def generate_fiscal_years(
    start_year: int,
    end_year: int
) -> list:
    """
    연도 범위를 리스트로 생성합니다.
    
    Args:
        start_year: 시작 연도 (포함)
        end_year: 종료 연도 (포함)
    
    Returns:
        list: 연도 리스트 [start_year, ..., end_year]
    
    사용 예시:
        # 2010~2023 연도 리스트
        years = generate_fiscal_years(2010, 2023)
        # → [2010, 2011, ..., 2023]
    """
    return list(range(start_year, end_year + 1))


def generate_rebalance_dates(
    start_year: int,
    end_year: int,
    month: int = 12
) -> list:
    """
    리밸런스 날짜 리스트를 생성합니다.
    
    Args:
        start_year: 시작 연도
        end_year: 종료 연도
        month: 리밸런스 월 (기본값: 12월)
    
    Returns:
        list: Timestamp 리스트 (각 연도의 해당 월 말일)
    
    사용 예시:
        # 2015~2023년 12월 말 리밸런스 날짜
        dates = generate_rebalance_dates(2015, 2023, month=12)
        # → [Timestamp('2015-12-31'), ..., Timestamp('2023-12-31')]
    """
    dates = []
    
    for year in range(start_year, end_year + 1):
        # 해당 월의 마지막 날 계산
        # pandas Period: 'month end'
        date = pd.Period(f'{year}-{month:02d}', freq='M').to_timestamp(how='end')
        dates.append(date)
    
    return dates


# ===========================================
# 6. 진행률 표시
# ===========================================

def print_progress(
    current: int,
    total: int,
    prefix: str = '',
    length: int = 50
):
    """
    진행률을 콘솔에 출력합니다. (간단한 프로그레스 바)
    
    Args:
        current: 현재 진행량
        total: 전체량
        prefix: 진행률 앞에 표시할 텍스트
        length: 프로그레스 바 길이 (문자 개수)
    
    사용 예시:
        for i, ticker in enumerate(tickers):
            process_ticker(ticker)
            print_progress(i+1, len(tickers), prefix='데이터 수집')
    """
    percent = 100 * (current / float(total))
    filled = int(length * current // total)
    bar = '█' * filled + '-' * (length - filled)
    
    print(f'\r{prefix} |{bar}| {percent:.1f}% ({current}/{total})', end='')
    
    # 완료 시 줄바꿈
    if current == total:
        print()


# ===========================================
# 사용 예시
# ===========================================
if __name__ == '__main__':
    """
    helpers 함수들 테스트
    """
    print("=" * 60)
    print("Helpers 테스트")
    print("=" * 60)
    
    # 1. Pandas 버전 확인
    print("\n[1. Pandas 버전 호환성]")
    freq = get_month_end_freq()
    print(f"Pandas 버전: {pd.__version__}")
    print(f"월말 frequency: '{freq}'")
    
    # 2. 날짜 생성
    print("\n[2. 리밸런스 날짜 생성]")
    rebal_dates = generate_rebalance_dates(2020, 2023, month=12)
    for date in rebal_dates:
        print(f"  {date.strftime('%Y-%m-%d')}")
    
    # 3. 캐시 저장/로드 테스트
    print("\n[3. 캐시 저장/로드 테스트]")
    
    import tempfile
    import numpy as np
    
    # 임시 디렉토리 사용
    with tempfile.TemporaryDirectory() as tmpdir:
        # DataFrame 저장/로드
        test_df = pd.DataFrame({
            'A': np.random.randn(10),
            'B': range(10)
        })
        
        csv_path = Path(tmpdir) / 'test.csv'
        save_cache(test_df, csv_path)
        loaded_df = load_cache(csv_path)
        print(f"  DataFrame 저장/로드: {loaded_df.shape}")
        
        # JSON 저장/로드
        test_dict = {'tickers': ['AAPL', 'MSFT'], 'count': 2}
        json_path = Path(tmpdir) / 'test.json'
        save_cache(test_dict, json_path)
        loaded_dict = load_cache(json_path)
        print(f"  JSON 저장/로드: {loaded_dict}")
    
    # 4. 진행률 테스트
    print("\n[4. 진행률 표시 테스트]")
    import time
    
    for i in range(101):
        time.sleep(0.02)
        print_progress(i, 100, prefix='테스트 진행')
    
    print("\n" + "=" * 60)
