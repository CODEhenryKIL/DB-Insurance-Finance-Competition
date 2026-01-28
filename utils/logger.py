"""
===========================================
통일된 로깅 시스템
===========================================

이 파일의 역할:
- 프로젝트 전체에서 사용할 통일된 로거 제공
- 콘솔 + 파일 동시 출력
- 한글 메시지 utf-8 인코딩
- 타임스탬프 자동 추가

주요 함수:
- get_logger(name): 로거 인스턴스 생성

로그 레벨:
- DEBUG: 상세한 디버깅 정보
- INFO: 일반적인 정보 메시지
- WARNING: 경고 (프로그램은 계속 동작)
- ERROR: 에러 (일부 기능 실패)
- CRITICAL: 치명적 에러 (프로그램 중단 가능)

사용 예시:
    from utils.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("데이터 수집 시작")
    logger.warning("일부 티커 누락")
    logger.error("API 호출 실패")
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# config 모듈에서 경로와 로그 레벨 가져오기
from config.paths import LOGS_DIR, LOG_FILE
from config.constants import LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    """
    로거 인스턴스를 생성하여 반환합니다.
    
    기능:
    1. 콘솔과 파일에 동시 로그 출력
    2. 한글 메시지를 utf-8로 인코딩
    3. 타임스탬프와 로거 이름 자동 추가
    4. 로그 파일은 logs/ 디렉토리에 저장
    
    Args:
        name: 로거 이름 (보통 __name__을 전달)
              예: 'data_collection.step1_price_collector'
    
    Returns:
        logging.Logger: 설정된 로거 인스턴스
    
    사용 예시:
        logger = get_logger(__name__)
        logger.info("작업 시작")
        logger.debug(f"처리 중: {ticker}")
        logger.warning("일부 데이터 누락")
        logger.error("처리 실패")
    """
    
    # 이미 설정된 로거가 있으면 재사용 (중복 핸들러 방지)
    logger = logging.getLogger(name)
    
    # 이미 핸들러가 있으면 설정이 완료된 것이므로 바로 반환
    if logger.handlers:
        return logger
    
    # 로그 레벨 설정 (config.constants.LOG_LEVEL 사용)
    # LOG_LEVEL은 문자열 'DEBUG', 'INFO', 'WARNING' 등
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    
    # ===========================================
    # 로그 포맷 설정
    # ===========================================
    # %(asctime)s: 시간 (예: 2026-01-28 14:00:00)
    # %(name)s: 로거 이름 (예: data_collection.step1)
    # %(levelname)s: 로그 레벨 (INFO, WARNING 등)
    # %(message)s: 실제 로그 메시지
    log_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    
    # ===========================================
    # 콘솔 핸들러 설정 (터미널 출력)
    # ===========================================
    # StreamHandler: 표준 출력(stdout)으로 로그 출력
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # 콘솔은 INFO 이상만 출력
    console_handler.setFormatter(log_format)
    
    # 한글 메시지 처리를 위한 인코딩 설정
    # Python 3에서는 기본적으로 utf-8이지만 명시적으로 설정
    if hasattr(console_handler.stream, 'reconfigure'):
        console_handler.stream.reconfigure(encoding='utf-8')
    
    # 로거에 콘솔 핸들러 추가
    logger.addHandler(console_handler)
    
    
    # ===========================================
    # 파일 핸들러 설정 (파일 저장)
    # ===========================================
    # logs/ 디렉토리가 없으면 생성
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # FileHandler: 파일에 로그 저장
    # mode='a': append (기존 파일에 이어쓰기)
    # encoding='utf-8': 한글 메시지 저장
    file_handler = logging.FileHandler(
        LOG_FILE, 
        mode='a', 
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # 파일은 DEBUG 이상 모두 저장
    file_handler.setFormatter(log_format)
    
    # 로거에 파일 핸들러 추가
    logger.addHandler(file_handler)
    
    
    # 상위 로거로 전파 방지 (중복 로그 방지)
    logger.propagate = False
    
    return logger


def log_section_header(logger: logging.Logger, title: str):
    """
    로그에 섹션 헤더를 출력합니다.
    가독성을 위해 구분선과 함께 제목 표시
    
    Args:
        logger: 로거 인스턴스
        title: 섹션 제목
    
    사용 예시:
        logger = get_logger(__name__)
        log_section_header(logger, "Step1: 가격 데이터 수집")
        logger.info("작업 시작...")
    """
    separator = "=" * 60
    logger.info("")
    logger.info(separator)
    logger.info(f"  {title}")
    logger.info(separator)


def log_dataframe_info(logger: logging.Logger, df, name: str = "DataFrame"):
    """
    DataFrame의 기본 정보를 로그로 출력합니다.
    
    출력 정보:
    - 행/열 개수
    - 컬럼 이름
    - 결측치 개수
    - 메모리 사용량
    
    Args:
        logger: 로거 인스턴스
        df: pandas DataFrame
        name: DataFrame 이름 (로그에 표시)
    
    사용 예시:
        logger = get_logger(__name__)
        log_dataframe_info(logger, price_df, "가격 데이터")
    """
    import pandas as pd
    
    # DataFrame 검증
    if not isinstance(df, pd.DataFrame):
        logger.warning(f"{name}이(가) DataFrame이 아닙니다.")
        return
    
    # 기본 정보
    rows, cols = df.shape
    logger.info(f"{name} 정보:")
    logger.info(f"  - 행 개수: {rows:,}")
    logger.info(f"  - 열 개수: {cols}")
    logger.info(f"  - 컬럼: {list(df.columns)}")
    
    # 결측치 정보
    missing = df.isnull().sum()
    total_missing = missing.sum()
    if total_missing > 0:
        logger.info(f"  - 총 결측치: {total_missing:,}")
        logger.info(f"  - 결측 비율: {total_missing / (rows * cols):.2%}")
        
        # 결측이 많은 컬럼만 표시
        high_missing = missing[missing > rows * 0.1]  # 10% 이상 결측
        if len(high_missing) > 0:
            logger.warning(f"  - 결측 많은 컬럼:")
            for col, count in high_missing.items():
                logger.warning(f"      {col}: {count:,} ({count/rows:.1%})")
    else:
        logger.info(f"  - 결측치: 없음")
    
    # 메모리 사용량
    memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
    logger.info(f"  - 메모리: {memory_mb:.2f} MB")


# ===========================================
# 사용 예시
# ===========================================
if __name__ == '__main__':
    """
    로거 테스트
    """
    # 로거 생성
    logger = get_logger('test_logger')
    
    # 다양한 레벨 테스트
    log_section_header(logger, "로거 테스트")
    
    logger.debug("디버그 메시지 (파일에만 저장)")
    logger.info("정보 메시지 (콘솔과 파일 모두)")
    logger.warning("경고 메시지")
    logger.error("에러 메시지")
    
    # 한글 메시지 테스트
    logger.info("한글 메시지 테스트: 데이터 수집 완료")
    logger.info(f"티커 개수: {100:,}개")
    
    # DataFrame 정보 테스트
    import pandas as pd
    import numpy as np
    
    test_df = pd.DataFrame({
        'A': np.random.randn(1000),
        'B': np.random.randn(1000),
        'C': [np.nan] * 500 + list(range(500))
    })
    log_dataframe_info(logger, test_df, "테스트 데이터")
    
    print(f"\n로그 파일 저장 위치: {LOG_FILE}")
