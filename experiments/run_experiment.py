#!/usr/bin/env python3
"""
===========================================
실험 실행 스크립트 (run_experiment.py)
===========================================

사용법:
    # 기본 베이스라인 실험
    python experiments_v2/run_experiment.py
    
    # 특정 프리셋 실험
    python experiments_v2/run_experiment.py --preset ranknet
    
    # 커스텀 실험
    python experiments_v2/run_experiment.py --exp_id exp_010 --exp_name custom_test --model_type RankNet

옵션:
    --preset: baseline, ranknet, sector 중 선택
    --exp_id: 실험 ID (예: exp_001)
    --exp_name: 실험 이름
    --model_type: MSE 또는 RankNet
    --market_mode: SP500 또는 FULL_MARKET
    --y_target_mode: raw 또는 sector
    --compare_with: 비교할 이전 실험 ID
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
from datetime import datetime

from experiments_v2.config import (
    ExperimentConfig,
    get_baseline_config,
    get_ranknet_config,
    get_sector_relative_config
)
from experiments_v2.runner import ExperimentRunner
from experiments_v2.saver import ResultSaver
from experiments_v2.reporter import ReportGenerator
from utils.logger import get_logger

logger = get_logger(__name__)


def parse_args():
    """커맨드라인 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='실험 실행 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 프리셋
    parser.add_argument(
        '--preset',
        type=str,
        choices=['baseline', 'ranknet', 'sector'],
        default=None,
        help='사전 정의된 설정 프리셋'
    )
    
    # 실험 메타 정보
    parser.add_argument('--exp_id', type=str, default=None, help='실험 ID')
    parser.add_argument('--exp_name', type=str, default=None, help='실험 이름')
    parser.add_argument('--description', type=str, default='', help='실험 설명')
    
    # 데이터 설정
    parser.add_argument('--market_mode', type=str, choices=['SP500', 'FULL_MARKET'], default=None)
    parser.add_argument('--y_target_mode', type=str, choices=['raw', 'sector'], default=None)
    parser.add_argument('--model_type', type=str, choices=['MSE', 'RankNet'], default=None)
    
    # 비교
    parser.add_argument('--compare_with', type=str, default=None, help='비교할 이전 실험 ID')
    
    return parser.parse_args()


def get_config_from_args(args) -> ExperimentConfig:
    """인자에서 설정 생성"""
    
    # 프리셋 기반
    if args.preset == 'ranknet':
        config = get_ranknet_config()
    elif args.preset == 'sector':
        config = get_sector_relative_config()
    else:
        config = get_baseline_config()
    
    # 오버라이드
    if args.exp_id:
        config.exp_id = args.exp_id
    if args.exp_name:
        config.exp_name = args.exp_name
    if args.description:
        config.description = args.description
    if args.market_mode:
        config.market_mode = args.market_mode
    if args.y_target_mode:
        config.y_target_mode = args.y_target_mode
    if args.model_type:
        config.model_type = args.model_type
        if args.model_type == 'RankNet':
            config.predictions_file = 'step4_predictions_ranknet.csv'
    if args.compare_with:
        config.compare_with = args.compare_with
    
    return config


def auto_generate_exp_id() -> str:
    """자동 실험 ID 생성"""
    base_dir = project_root / 'experiments_v2'
    
    # 기존 실험 폴더 확인
    existing = list(base_dir.glob('exp_*'))
    if not existing:
        return 'exp_001'
    
    # 다음 번호 찾기
    max_num = 0
    for folder in existing:
        try:
            num = int(folder.name[4:7])
            max_num = max(max_num, num)
        except:
            pass
    
    return f'exp_{max_num + 1:03d}'


def run_experiment(config: ExperimentConfig) -> None:
    """실험 실행"""
    print("\n" + "="*70)
    print("  📊 실험 프레임워크 v2")
    print("="*70)
    print(config.summary())
    
    # 설정 검증
    errors = config.validate()
    if errors:
        print("❌ 설정 오류:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    
    # 실험 실행
    runner = ExperimentRunner(config)
    results = runner.run()
    
    # 결과 저장
    saver = ResultSaver()
    exp_dir = saver.save(results)
    
    # 보고서 생성
    reporter = ReportGenerator()
    report_path = reporter.generate(results, exp_dir)
    
    # 완료 메시지
    print("\n" + "="*70)
    print("  ✅ 실험 완료!")
    print("="*70)
    print(f"\n📁 결과 폴더: {exp_dir}")
    print(f"📄 보고서: {report_path}")
    
    # 요약 출력
    print("\n📊 성과 요약:")
    for key, metrics in results.performance_metrics.items():
        cagr = metrics.get('CAGR', 0)
        sharpe = metrics.get('Sharpe', 0)
        print(f"  - {key}: CAGR={cagr*100:.1f}%, Sharpe={sharpe:.2f}")


def main():
    """메인 함수"""
    args = parse_args()
    
    # 설정 생성
    config = get_config_from_args(args)
    
    # exp_id 자동 생성 (지정 안된 경우)
    if args.exp_id is None and args.preset is None:
        config.exp_id = auto_generate_exp_id()
        config.exp_name = f"auto_{datetime.now().strftime('%Y%m%d_%H%M')}"
    
    # 실험 실행
    run_experiment(config)


if __name__ == '__main__':
    main()
