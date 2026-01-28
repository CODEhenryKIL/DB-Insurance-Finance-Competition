"""
===========================================
데이터 검증 및 방어 로직 함수 모음
===========================================

이 파일의 역할:
- 데이터의 유효성을 검증하는 함수들 제공
- 0으로 나누기, 음수 로그 등의 수학적 오류 방지
- m1, m2, m3 계산 시 필수적인 방어 로직 구현

주요 함수:
1. safe_divide(): 안전한 나눗셈 (0 방어, 클리핑)
2. clip_value(): 값 클리핑 (극단값 제한)
3. validate_positive(): 양수 검증
4. is_valid_ticker(): 티커 형식 검증

설계 철학:
- 데이터를 최대한 살리되 극단값만 제한
- NaN 결측 처리는 최소화 (특히 m1)
- 명확한 에러 메시지 제공

⭐ 중요: 
이 파일의 함수들은 feature_engineering에서 핵심적으로 사용됩니다.
특히 safe_divide()는 m1, m2, m3 모두에서 사용되므로 신중하게 구현되었습니다.
"""

import numpy as np
import pandas as pd
from typing import Union, Optional, Tuple

from config.constants import EPSILON, M1_CLIP_MIN, M1_CLIP_MAX


# ===========================================
# 1. 안전한 나눗셈 (핵심 함수)
# ===========================================

def safe_divide(
    numerator: Union[float, np.ndarray, pd.Series],
    denominator: Union[float, np.ndarray, pd.Series],
    epsilon: float = EPSILON,
    clip_range: Optional[Tuple[float, float]] = None,
    handle_negative_denom: str = 'abs'
) -> Union[float, np.ndarray, pd.Series]:
    """
    안전한 나눗셈을 수행합니다. (0으로 나누기 방지)
    
    이 함수는 m1, m2, m3 계산에서 모두 사용되는 핵심 함수입니다.
    특히 m1 계산 시 OI가 0에 가까운 경우를 처리하기 위해 
    데이터를 버리지 않고 클리핑 방식을 사용합니다.
    
    주요 기능:
    1. 분모가 0 또는 매우 작은 값이면 epsilon으로 대체
    2. 분모가 음수인 경우 처리 방법 선택 가능
    3. 결과값을 지정된 범위로 클리핑 (선택)
    
    Args:
        numerator: 분자 (스칼라, numpy 배열, pandas Series)
        denominator: 분모 (스칼라, numpy 배열, pandas Series)
        epsilon: 분모의 최소값 (기본값: 1e-6)
                분모의 절대값이 이보다 작으면 epsilon 사용
        clip_range: (min, max) 튜플 또는 None
                   None이면 클리핑 안함
                   예: (-5, 5) → 결과를 [-5, 5] 범위로 제한
        handle_negative_denom: 음수 분모 처리 방식
                              'abs': 절대값 사용 (기본값, m1에 사용)
                              'keep': 음수 그대로 사용
                              'nan': NaN으로 처리
    
    Returns:
        나눗셈 결과 (클리핑 적용 시 해당 범위 내 값)
        입력 타입과 동일한 타입으로 반환
    
    사용 예시:
        # m1 계산: OI가 음수거나 0 근처일 때
        m1 = safe_divide(AdjOI, OI, epsilon=1e-6, clip_range=(-5, 5))
        
        # m2 계산: Revenue가 0일 때
        intensity = safe_divide(I, Revenue, epsilon=1e-6)
        
        # 단순 나눗셈 (클리핑 없음)
        ratio = safe_divide(a, b, epsilon=1e-6)
    
    ⭐ m1 계산 시 주의사항:
        - OI가 0에 가까운 기업(바이오, 초기 테크)의 데이터를 살리기 위해
          결측 처리 대신 클리핑 방식 사용
        - handle_negative_denom='abs'로 음수 OI도 처리
    """
    
    # numpy 배열로 변환 (scalar도 처리 가능하도록)
    num = np.asarray(numerator)
    denom = np.asarray(denominator)
    
    # 분모 처리: 음수 분모 처리 방식에 따라
    if handle_negative_denom == 'abs':
        # 절대값 사용 (m1 계산 시: OI가 음수여도 처리)
        denom_safe = np.abs(denom)
    elif handle_negative_denom == 'keep':
        # 음수 그대로 사용
        denom_safe = denom
    elif handle_negative_denom == 'nan':
        # 음수면 NaN 처리
        denom_safe = np.where(denom < 0, np.nan, denom)
    else:
        raise ValueError(
            f"handle_negative_denom은 'abs', 'keep', 'nan' 중 하나여야 합니다. "
            f"입력값: {handle_negative_denom}"
        )
    
    # 분모가 epsilon보다 작으면 epsilon으로 대체
    # np.maximum: element-wise 최대값 (각 원소마다 비교)
    denom_safe = np.maximum(denom_safe, epsilon)
    
    # 나눗셈 수행
    result = num / denom_safe
    
    # 클리핑 (지정된 경우만)
    if clip_range is not None:
        min_val, max_val = clip_range
        result = np.clip(result, min_val, max_val)
    
    # 입력이 pandas Series였으면 Series로 반환
    if isinstance(numerator, pd.Series):
        result = pd.Series(result, index=numerator.index)
    elif isinstance(numerator, (int, float)) and isinstance(result, np.ndarray):
        # 입력이 스칼라였으면 스칼라로 반환
        result = float(result)
    
    return result


# ===========================================
# 2. 값 클리핑
# ===========================================

def clip_value(
    value: Union[float, np.ndarray, pd.Series],
    min_val: float,
    max_val: float
) -> Union[float, np.ndarray, pd.Series]:
    """
    값을 지정된 범위로 제한합니다.
    
    Args:
        value: 클리핑할 값
        min_val: 최소값
        max_val: 최대값
    
    Returns:
        [min_val, max_val] 범위로 제한된 값
    
    사용 예시:
        # PBR 클리핑 (너무 극단적인 값 제거)
        pbr_clipped = clip_value(pbr, 0.01, 100)
    """
    if isinstance(value, pd.Series):
        return value.clip(lower=min_val, upper=max_val)
    else:
        return np.clip(value, min_val, max_val)


# ===========================================
# 3. 양수 검증
# ===========================================

def validate_positive(
    value: Union[float, np.ndarray, pd.Series],
    allow_zero: bool = False,
    replace_invalid: Optional[float] = None
) -> Union[bool, np.ndarray, pd.Series]:
    """
    값이 양수인지 검증합니다.
    
    사용 목적:
    - BookValue, Revenue 등은 양수여야 의미가 있음
    - 로그 계산 전 검증 필수 (ln(음수) 불가)
    
    Args:
        value: 검증할 값
        allow_zero: True면 0 허용, False면 0도 invalid
        replace_invalid: None이면 boolean 반환
                        float이면 invalid를 해당 값으로 대체
    
    Returns:
        replace_invalid이 None이면:
            boolean (스칼라) 또는 boolean 배열
        replace_invalid이 float이면:
            invalid를 대체한 값
    
    사용 예시:
        # BookValue가 양수인지 확인
        is_valid = validate_positive(book_value, allow_zero=False)
        
        # 음수를 NaN으로 대체
        book_value_clean = validate_positive(
            book_value, 
            allow_zero=False, 
            replace_invalid=np.nan
        )
    """
    if allow_zero:
        # 0 이상
        is_valid = (value >= 0) if not isinstance(value, pd.Series) else (value >= 0)
    else:
        # 0보다 큼
        is_valid = (value > 0) if not isinstance(value, pd.Series) else (value > 0)
    
    if replace_invalid is None:
        # boolean 반환
        return is_valid
    else:
        # invalid를 replace_invalid 값으로 대체
        if isinstance(value, pd.Series):
            return value.where(is_valid, replace_invalid)
        else:
            return np.where(is_valid, value, replace_invalid)


# ===========================================
# 4. 티커 형식 검증
# ===========================================

def is_valid_ticker(ticker: str) -> bool:
    """
    티커 심볼의 형식이 유효한지 검증합니다.
    
    기본 규칙:
    - 1~5자 길이
    - 알파벳 대문자만 (A-Z)
    - 숫자나 특수문자 없음
    
    Args:
        ticker: 티커 심볼 문자열
    
    Returns:
        True: 유효한 형식
        False: 잘못된 형식
    
    사용 예시:
        if is_valid_ticker('AAPL'):
            print("유효한 티커")
        
        is_valid_ticker('AAPL')  # True
        is_valid_ticker('ABC123')  # False (숫자 포함)
        is_valid_ticker('abc')  # False (소문자)
    """
    if not isinstance(ticker, str):
        return False
    
    # 길이 체크 (1~5자)
    if not (1 <= len(ticker) <= 5):
        return False
    
    # 대문자 알파벳만 허용
    if not ticker.isalpha() or not ticker.isupper():
        return False
    
    return True


# ===========================================
# 5. 결측치 비율 계산
# ===========================================

def calculate_missing_ratio(
    data: Union[pd.Series, pd.DataFrame]
) -> Union[float, pd.Series]:
    """
    결측치 비율을 계산합니다.
    
    Args:
        data: pandas Series 또는 DataFrame
    
    Returns:
        Series: 결측치 비율 (0.0 ~ 1.0)
        DataFrame: 각 컬럼별 결측치 비율
    
    사용 예시:
        # DataFrame의 각 컬럼별 결측치 비율
        missing = calculate_missing_ratio(df)
        print(missing[missing > 0.1])  # 10% 이상 결측인 컬럼
        
        # Series의 결측치 비율
        ratio = calculate_missing_ratio(df['m1'])
    """
    if isinstance(data, pd.DataFrame):
        # DataFrame: 각 컬럼별 비율
        return data.isnull().sum() / len(data)
    else:
        # Series: 전체 비율
        return data.isnull().sum() / len(data)


# ===========================================
# 6. 이상치 탐지 (IQR 방식)
# ===========================================

def detect_outliers_iqr(
    data: pd.Series,
    multiplier: float = 1.5
) -> pd.Series:
    """
    IQR(Interquartile Range) 방식으로 이상치를 탐지합니다.
    
    방법:
    - Q1 (25th percentile), Q3 (75th percentile) 계산
    - IQR = Q3 - Q1
    - 이상치: Q1 - multiplier*IQR 미만 또는 Q3 + multiplier*IQR 초과
    
    Args:
        data: pandas Series
        multiplier: IQR 배수 (기본값 1.5)
                   1.5: 일반적 기준
                   3.0: 극단적 이상치만 탐지
    
    Returns:
        boolean Series (True: 이상치, False: 정상)
    
    사용 예시:
        # m1에서 이상치 찾기
        outliers = detect_outliers_iqr(df['m1'])
        print(f"이상치 개수: {outliers.sum()}")
        
        # 이상치 제외한 데이터
        df_clean = df[~outliers]
    """
    # 25th, 75th percentile 계산
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    
    # 이상치 범위 계산
    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR
    
    # 범위 밖이면 이상치
    is_outlier = (data < lower_bound) | (data > upper_bound)
    
    return is_outlier


# ===========================================
# 사용 예시
# ===========================================
if __name__ == '__main__':
    """
    validators 함수들 테스트
    """
    print("=" * 60)
    print("Validators 테스트")
    print("=" * 60)
    
    # 1. safe_divide 테스트
    print("\n[1. safe_divide 테스트]")
    
    # m1 계산 시뮬레이션 (OI가 0 근처)
    AdjOI = np.array([100, 50, -20, 80])
    OI = np.array([50, 0.0001, -10, 40])  # 0 근처와 음수 포함
    
    m1 = safe_divide(AdjOI, OI, epsilon=1e-6, clip_range=(-5, 5), handle_negative_denom='abs')
    print(f"AdjOI: {AdjOI}")
    print(f"OI: {OI}")
    print(f"m1 (클리핑): {m1}")
    print("→ OI가 0이나 음수여도 데이터 보존됩니다")
    
    # 2. validate_positive 테스트
    print("\n[2. validate_positive 테스트]")
    
    book_value = np.array([100, -50, 0, 200])
    valid = validate_positive(book_value, allow_zero=False)
    cleaned = validate_positive(book_value, allow_zero=False, replace_invalid=np.nan)
    
    print(f"BookValue: {book_value}")
    print(f"유효성: {valid}")
    print(f"정제 후: {cleaned}")
    print("→ 음수와 0을 NaN으로 대체")
    
    # 3. is_valid_ticker 테스트
    print("\n[3. is_valid_ticker 테스트]")
    
    tickers = ['AAPL', 'MSFT', 'abc', 'AAPL123', 'A', 'TOOLONG']
    for ticker in tickers:
        result = is_valid_ticker(ticker)
        print(f"  {ticker}: {'✓ 유효' if result else '✗ 무효'}")
    
    # 4. 결측치 비율 테스트
    print("\n[4. 결측치 비율 테스트]")
    
    test_series = pd.Series([1, 2, np.nan, 4, np.nan, 6])
    ratio = calculate_missing_ratio(test_series)
    print(f"데이터: {test_series.values}")
    print(f"결측 비율: {ratio:.1%}")
    
    # 5. 이상치 탐지 테스트
    print("\n[5. 이상치 탐지 테스트]")
    
    data = pd.Series([1, 2, 2, 3, 3, 3, 4, 4, 100])  # 100은 명백한 이상치
    outliers = detect_outliers_iqr(data)
    print(f"데이터: {data.values}")
    print(f"이상치 위치: {np.where(outliers)[0]}")
    print(f"이상치 값: {data[outliers].values}")
    
    print("\n" + "=" * 60)
