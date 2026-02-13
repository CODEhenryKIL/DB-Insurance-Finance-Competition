#!/usr/bin/env python3
"""
===========================================
주기별 전체 파이프라인 실행 스크립트
===========================================

사용법:
    # 연간 리밸런싱 (기본)
    python experiments/run_pipeline.py --frequency annual
    
    # 반기 리밸런싱
    python experiments/run_pipeline.py --frequency semiannual
    
    # 분기 리밸런싱
    python experiments/run_pipeline.py --frequency quarterly
    
    # 특정 스텝만 실행
    python experiments/run_pipeline.py --frequency quarterly --steps 3 4 5
    python experiments/run_pipeline.py --frequency quarterly --steps 5

설명:
    리밸런싱 주기에 따라 적절한 Step3/4/5 파이프라인을 실행합니다.
    
    - annual: 연간 리밸런싱 (12월, 12개월 홀딩)
    - semiannual: 반기 리밸런싱 (6/12월, 6개월 홀딩)
    - quarterly: 분기 리밸런싱 (3/6/9/12월, 3개월 홀딩)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import subprocess
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)


# 주기별 실행 파일 매핑
PIPELINE_FILES = {
    'annual': {
        'step3': 'feature_engineering/step3_feature_builder.py',
        'step4': 'modeling/step4_train_predict.py',
        'step5': 'backtesting/step5_backtest.py'
    },
    'semiannual': {
        'step3': 'feature_engineering/step3_feature_builder_semiannual.py',
        'step4': 'modeling/step4_train_predict_semiannual.py',
        'step5': 'backtesting/step5_backtest_semiannual.py'
    },
    'quarterly': {
        'step3': 'feature_engineering/step3_feature_builder_quarterly.py',
        'step4': 'modeling/step4_train_predict_quarterly.py',
        'step5': 'backtesting/step5_backtest_quarterly.py'
    }
}

# 주기별 설명
FREQUENCY_DESC = {
    'annual': '연간 (12월 리밸런싱, 12개월 홀딩)',
    'semiannual': '반기 (6/12월 리밸런싱, 6개월 홀딩)',
    'quarterly': '분기 (3/6/9/12월 리밸런싱, 3개월 홀딩)'
}


def parse_args():
    """커맨드라인 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='주기별 파이프라인 실행',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--frequency', '-f',
        type=str,
        choices=['annual', 'semiannual', 'quarterly'],
        default='annual',
        help='리밸런싱 주기 (기본: annual)'
    )
    
    parser.add_argument(
        '--steps', '-s',
        type=int,
        nargs='+',
        choices=[3, 4, 5],
        default=[3, 4, 5],
        help='실행할 스텝 (기본: 3 4 5)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 실행 없이 명령어만 출력'
    )
    
    return parser.parse_args()


def run_step(step_num: int, frequency: str, dry_run: bool = False) -> bool:
    """
    특정 스텝 실행
    
    Parameters
    ----------
    step_num : int
        스텝 번호 (3, 4, 5)
    frequency : str
        리밸런싱 주기
    dry_run : bool
        True면 명령어만 출력
        
    Returns
    -------
    bool
        성공 여부
    """
    step_key = f'step{step_num}'
    
    if frequency not in PIPELINE_FILES:
        logger.error(f"❌ 알 수 없는 주기: {frequency}")
        return False
    
    if step_key not in PIPELINE_FILES[frequency]:
        logger.error(f"❌ 알 수 없는 스텝: {step_num}")
        return False
    
    script_path = project_root / PIPELINE_FILES[frequency][step_key]
    
    if not script_path.exists():
        logger.error(f"❌ 스크립트 없음: {script_path}")
        return False
    
    cmd = ['python3', str(script_path)]
    
    logger.info(f"\n{'='*60}")
    logger.info(f"  Step {step_num} 실행 ({frequency})")
    logger.info(f"  스크립트: {script_path.name}")
    logger.info(f"{'='*60}")
    
    if dry_run:
        logger.info(f"  [DRY-RUN] 명령어: {' '.join(cmd)}")
        return True
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Step {step_num} 완료")
            return True
        else:
            logger.error(f"❌ Step {step_num} 실패 (exit code: {result.returncode})")
            return False
            
    except Exception as e:
        logger.error(f"❌ Step {step_num} 실행 오류: {e}")
        return False


def main():
    """메인 함수"""
    args = parse_args()
    
    frequency = args.frequency
    steps = sorted(args.steps)
    dry_run = args.dry_run
    
    logger.info("\n" + "="*60)
    logger.info("  M-Model 파이프라인 실행")
    logger.info("="*60)
    logger.info(f"  리밸런싱 주기: {frequency}")
    logger.info(f"  설명: {FREQUENCY_DESC[frequency]}")
    logger.info(f"  실행 스텝: {steps}")
    logger.info(f"  시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    # 각 스텝 실행
    success_count = 0
    fail_count = 0
    
    for step_num in steps:
        if run_step(step_num, frequency, dry_run):
            success_count += 1
        else:
            fail_count += 1
            # Step 실패 시 중단 (의존성 있음)
            logger.error(f"⚠️ Step {step_num} 실패로 파이프라인 중단")
            break
    
    # 결과 요약
    logger.info("\n" + "="*60)
    logger.info("  파이프라인 완료")
    logger.info("="*60)
    logger.info(f"  성공: {success_count}개 스텝")
    logger.info(f"  실패: {fail_count}개 스텝")
    logger.info(f"  종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    # 출력 파일 경로 안내
    if not dry_run and fail_count == 0:
        logger.info("\n📁 출력 파일:")
        
        if frequency == 'annual':
            logger.info("  - data_cache/step3_features_annual.csv")
            logger.info("  - data_cache/step4_predictions.csv")
            logger.info("  - data_cache/step5_backtest_metrics.csv")
        elif frequency == 'semiannual':
            logger.info("  - data_cache/step3_features_semiannual.csv")
            logger.info("  - data_cache/step4_predictions_semiannual.csv")
            logger.info("  - data_cache/step5_backtest_metrics_semiannual.csv")
        elif frequency == 'quarterly':
            logger.info("  - data_cache/step3_features_quarterly.csv")
            logger.info("  - data_cache/step4_predictions_quarterly.csv")
            logger.info("  - data_cache/step5_backtest_metrics_quarterly.csv")
    
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
