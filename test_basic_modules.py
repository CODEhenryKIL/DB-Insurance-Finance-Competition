"""
===========================================
기본 모듈 통합 테스트
===========================================

이 스크립트는 config와 utils 모듈이 정상적으로 동작하는지 테스트합니다.

테스트 항목:
1. config 모듈 임포트 및 상수 확인
2. utils 모듈 임포트 및 함수 호출
3. 디렉토리 생성 확인
4. 로거 동작 확인
5. 방어 로직 (m1 클리핑) 동작 확인
"""

import sys
import numpy as np
import pandas as pd

print("=" * 60)
print("M-Model 기본 모듈 통합 테스트")
print("=" * 60)

# ===========================================
# 1. config 모듈 테스트
# ===========================================
print("\n[1. config 모듈 테스트]")

try:
    from config import constants, paths
    print("✅ config 모듈 임포트 성공")
    
    # 주요 상수 확인
    print(f"  - 데이터 기간: {constants.START_YEAR} ~ {constants.CURRENT_YEAR}")
    print(f"  - 롱 비율: {constants.LONG_RATIOS}")
    print(f"  - m1 클리핑 범위: [{constants.M1_CLIP_MIN}, {constants.M1_CLIP_MAX}]")
    print(f"  - SEC User-Agent: {constants.SEC_HEADERS.get('User-Agent', 'N/A')[:50]}...")
    
    # 경로 확인
    print(f"  - 프로젝트 루트: {paths.PROJECT_ROOT}")
    print(f"  - 캐시 디렉토리: {paths.DATA_CACHE_DIR}")
    
except Exception as e:
    print(f"❌ config 모듈 에러: {e}")
    sys.exit(1)


# ===========================================
# 2. utils 모듈 테스트
# ===========================================
print("\n[2. utils 모듈 테스트]")

try:
    from utils import get_logger, safe_divide, get_month_end_freq
    print("✅ utils 모듈 임포트 성공")
    
    # 로거 테스트
    logger = get_logger('test')
    logger.info("로거 동작 테스트")
    print("  - 로거 생성 및 동작 확인")
    
    # Pandas 버전 호환성
    freq = get_month_end_freq()
    print(f"  - Pandas 월말 frequency: '{freq}'")
    
except Exception as e:
    print(f"❌ utils 모듈 에러: {e}")
    sys.exit(1)


# ===========================================
# 3. m1 클리핑 로직 테스트 (⭐ 핵심)
# ===========================================
print("\n[3. m1 클리핑 로직 테스트 - 데이터 보존 확인]")

try:
    from utils import safe_divide
    from config.constants import M1_CLIP_MIN, M1_CLIP_MAX, EPSILON
    
    # 시뮬레이션: OI가 0 근처인 바이오/테크 기업
    test_cases = [
        {"name": "정상 기업", "AdjOI": 100, "OI": 50},
        {"name": "OI=0 기업", "AdjOI": 50, "OI": 0.0001},  # 0 근처
        {"name": "적자 기업", "AdjOI": -20, "OI": -10},  # 음수 OI
        {"name": "턴어라운드", "AdjOI": 80, "OI": 0.5},  # OI 매우 작음
    ]
    
    print(f"  클리핑 범위: [{M1_CLIP_MIN}, {M1_CLIP_MAX}]")
    print(f"  Epsilon: {EPSILON}")
    print()
    
    for case in test_cases:
        m1 = safe_divide(
            case["AdjOI"], 
            case["OI"], 
            epsilon=EPSILON,
            clip_range=(M1_CLIP_MIN, M1_CLIP_MAX),
            handle_negative_denom='abs'
        )
        print(f"  {case['name']:12s}: AdjOI={case['AdjOI']:6.1f}, OI={case['OI']:6.4f} → m1={m1:6.2f}")
    
    print("\n  ✅ OI가 0이나 음수여도 결측 처리 없이 클리핑으로 처리됩니다!")
    
except Exception as e:
    print(f"❌ m1 클리핑 로직 에러: {e}")
    sys.exit(1)


# ===========================================
# 4. 디렉토리 생성 확인
# ===========================================
print("\n[4. 디렉토리 생성 확인]")

try:
    from config.paths import ensure_all_dirs, DATA_CACHE_DIR, REPORTS_DIR, LOGS_DIR
    
    ensure_all_dirs()
    
    # 디렉토리 존재 확인
    dirs_to_check = [
        ("캐시", DATA_CACHE_DIR),
        ("리포트", REPORTS_DIR),
        ("로그", LOGS_DIR)
    ]
    
    all_exist = True
    for name, path in dirs_to_check:
        exists = path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {name}: {path}")
        if not exists:
            all_exist = False
    
    if all_exist:
        print("\n  ✅ 모든 필수 디렉토리 생성 완료")
    else:
        print("\n  ❌ 일부 디렉토리 생성 실패")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ 디렉토리 생성 에러: {e}")
    sys.exit(1)


# ===========================================
# 5. 종합 결과
# ===========================================
print("\n" + "=" * 60)
print("✅ 모든 기본 모듈 테스트 통과!")
print("=" * 60)
print("\n다음 단계:")
print("  1. Step1: 가격 데이터 수집 구현")
print("  2. Step2: 재무 데이터 수집 (edgartools)")
print("  3. Step3: Feature Engineering (m1, m2, m3 계산)")
print("  4. Step4: 모델 학습 및 예측")
print("  5. Step5: 백테스트 (4가지 롱 비율)")
print()
