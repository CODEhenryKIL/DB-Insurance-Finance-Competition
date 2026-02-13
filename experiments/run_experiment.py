#!/usr/bin/env python3
"""
===========================================
실험 실행 스크립트 (run_experiment.py) v2
===========================================

사용법:
    # 파라미터 직접 지정 (권장)
    python run_experiment.py --universe SP500 --sector ALL --window 5 --freq A --loss RankNet --safe_lag 3
    
    # 축약형
    python run_experiment.py -u SP500 -s ALL -w 5 -f A -l RankNet -sl 3
    
    # 프리셋 사용 (기존 호환)
    python run_experiment.py --preset ranknet
    
파라미터:
    --universe, -u  : SP500, FULL (기본: SP500)
    --sector, -s    : ALL, BioIT (기본: ALL)
    --window, -w    : 3, 5 (학습 윈도우 연수, 기본: 5)
    --freq, -f      : A (연간), Q (분기), S (반기) (기본: A)
    --loss, -l      : MSE, RankNet (기본: RankNet)
    --safe_lag, -sl : 0 (12월 매수), 3 (3월 매수) (기본: 3)
    --exp_id        : 실험 ID (자동 생성)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
from datetime import datetime

from experiments.src.config import ExperimentConfig
from experiments.src.runner import ExperimentRunner
from experiments.src.saver import ResultSaver
from experiments.src.reporter import ReportGenerator
from utils.logger import get_logger

logger = get_logger(__name__)


def parse_args():
    """커맨드라인 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='M-Model 실험 실행 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # S&P 500, 전체 섹터, 5년 윈도우, 연간, RankNet, Safe Lag 3개월
  python run_experiment.py -u SP500 -s ALL -w 5 -f A -l RankNet -sl 3
  
  # S&P 500, 바이오&IT, 3년 윈도우, 분기, RankNet, Safe Lag 3개월
  python run_experiment.py -u SP500 -s BioIT -w 3 -f Q -l RankNet -sl 3
  
  # 편향 있는 베이스라인 (12월 매수)
  python run_experiment.py -u SP500 -s ALL -w 5 -f A -l MSE -sl 0
        """
    )
    
    # ========================================
    # 핵심 파라미터 (축약형 지원)
    # ========================================
    parser.add_argument(
        '-u', '--universe',
        type=str,
        choices=['SP500', 'FULL'],
        default='SP500',
        help='유니버스: SP500 (S&P 500), FULL (전체 시장)'
    )
    
    parser.add_argument(
        '-s', '--sector',
        type=str,
        choices=['ALL', 'BioIT'],
        default='ALL',
        help='섹터: ALL (전체), BioIT (바이오+IT만)'
    )
    
    parser.add_argument(
        '-w', '--window',
        type=int,
        choices=[3, 5],
        default=5,
        help='학습 윈도우 (연수): 3 또는 5'
    )
    
    parser.add_argument(
        '-f', '--freq',
        type=str,
        choices=['A', 'Q', 'S'],
        default='A',
        help='리밸런싱 주기: A (연간), Q (분기), S (반기)'
    )
    
    parser.add_argument(
        '-l', '--loss',
        type=str,
        choices=['MSE', 'RankNet'],
        default='RankNet',
        help='손실함수: MSE (회귀), RankNet (순위 학습)'
    )
    
    parser.add_argument(
        '-sl', '--safe_lag',
        type=int,
        choices=[0, 3],
        default=3,
        help='Safe Lag: 0 (12월 매수, 편향 있음), 3 (3월 매수, 편향 해소)'
    )
    
    # ========================================
    # 실험 메타 정보
    # ========================================
    parser.add_argument('--exp_id', type=str, default=None, help='실험 ID (자동 생성)')
    parser.add_argument('--exp_name', type=str, default=None, help='실험 이름 (자동 생성)')
    parser.add_argument('--description', type=str, default='', help='실험 설명')
    
    # ========================================
    # 기존 프리셋 호환 (deprecated)
    # ========================================
    parser.add_argument(
        '--preset',
        type=str,
        default=None,
        help='[deprecated] 기존 프리셋 사용'
    )
    
    return parser.parse_args()


def build_config_from_params(args) -> ExperimentConfig:
    """
    파라미터에서 ExperimentConfig 생성
    
    Parameters
    ----------
    args : Namespace
        파싱된 인자
    
    Returns
    -------
    ExperimentConfig
        실험 설정
    """
    # 기본 설정
    config = ExperimentConfig()
    
    # ========================================
    # Universe
    # ========================================
    if args.universe == 'SP500':
        config.market_mode = 'SP500'
    else:
        config.market_mode = 'FULL_MARKET'
    
    # ========================================
    # Sector
    # ========================================
    if args.sector == 'BioIT':
        config.included_sectors = ['Healthcare', 'Technology']
    else:
        config.included_sectors = None  # 전체
    
    # ========================================
    # Window
    # ========================================
    config.train_window_years = args.window
    
    # ========================================
    # Frequency
    # ========================================
    if args.freq == 'A':
        config.rebalance_frequency = 'annual'
        config.holding_months = 12
        config.rebalance_month = 12
        config.features_file = 'step3_features_annual.csv'
        if args.loss == 'MSE':
            if args.window == 3:
                config.predictions_file = 'step4_predictions_3y.csv'
            else:
                config.predictions_file = 'step4_predictions.csv'
        else:
            # RankNet: 윈도우별 predictions 파일
            if args.window == 3:
                config.predictions_file = 'step4_predictions_ranknet.csv'
            else:
                config.predictions_file = 'step4_predictions_ranknet_5y.csv'
    elif args.freq == 'Q':
        config.rebalance_frequency = 'quarterly'
        config.holding_months = 12  # 롤링 1년 홀딩
        config.rebalance_month = 3
        config.features_file = 'step3_features_quarterly.csv'
        # 윈도우별 predictions 파일 (3년=기본, 5년=_5y 접미사)
        if args.window == 3:
            config.predictions_file = 'step4_predictions_ranknet_quarterly.csv'
        else:
            config.predictions_file = 'step4_predictions_ranknet_quarterly_5y.csv'
    else:  # S
        config.rebalance_frequency = 'semiannual'
        config.holding_months = 12  # 롤링 1년 홀딩
        config.rebalance_month = 6
        config.features_file = 'step3_features_semiannual.csv'
        # 윈도우별 predictions 파일 (3년=기본, 5년=_5y 접미사)
        if args.window == 3:
            config.predictions_file = 'step4_predictions_ranknet_semiannual.csv'
        else:
            config.predictions_file = 'step4_predictions_ranknet_semiannual_5y.csv'
    
    # ========================================
    # Loss
    # ========================================
    config.model_type = args.loss
    if args.loss == 'RankNet':
        config.learning_rate = 0.005
        config.epochs = 300
        config.y_target_mode = 'sector'  # 섹터 상대 ln(PBR)
    else:
        config.y_target_mode = 'raw'     # 원본 ln(PBR)
    
    # ========================================
    # Safe Lag
    # ========================================
    config.safe_lag_months = args.safe_lag
    
    # ========================================
    # 자동 ID 및 이름 생성
    # ========================================
    # 조합명 생성
    freq_map = {'A': 'annual', 'Q': 'quarterly', 'S': 'semiannual'}
    sector_str = 'biotech_it' if args.sector == 'BioIT' else 'all'
    safe_str = '_safelag' if args.safe_lag == 3 else ''
    
    auto_name = f"{args.universe.lower()}_{args.loss.lower()}_{args.window}y_{freq_map[args.freq]}_{sector_str}{safe_str}"
    
    if args.exp_id:
        config.exp_id = args.exp_id
    else:
        config.exp_id = auto_generate_exp_id()
    
    if args.exp_name:
        config.exp_name = args.exp_name
    else:
        config.exp_name = auto_name
    
    if args.description:
        config.description = args.description
    else:
        config.description = f"Universe={args.universe}, Sector={args.sector}, Window={args.window}y, Freq={args.freq}, Loss={args.loss}, SafeLag={args.safe_lag}"
    
    return config


def auto_generate_exp_id() -> str:
    """자동 실험 ID 생성"""
    base_dir = project_root / 'experiments'
    
    # 기존 실험 폴더 확인
    existing = list(base_dir.glob('exp_*'))
    if not existing:
        return 'exp_001'
    
    # 다음 번호 찾기
    max_num = 0
    for folder in existing:
        try:
            # exp_001, exp_001_1 등 지원
            name_part = folder.name.split('_')[1]
            num = int(name_part)
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
    
    # 프리셋 사용 (deprecated)
    if args.preset:
        print("⚠️  --preset은 deprecated입니다. 새로운 파라미터 방식을 사용하세요.")
        print("    예: python run_experiment.py -u SP500 -s ALL -w 5 -f A -l RankNet -sl 3")
        
        # 기존 프리셋 호환을 위해 임포트
        from experiments.src.config import (
            get_baseline_config, get_baseline_3y_config,
            get_ranknet_config, get_ranknet_3y_config,
            get_ranknet_5y_safelag_config, get_ranknet_3y_safelag_config,
            get_biotech_it_ranknet_5y_config, get_biotech_it_ranknet_3y_config,
            get_biotech_it_ranknet_5y_safelag_config, get_biotech_it_ranknet_3y_safelag_config,
            get_quarterly_ranknet_config, get_quarterly_ranknet_biotech_it_config
        )
        
        preset_map = {
            'baseline': get_baseline_config,
            'baseline_3y': get_baseline_3y_config,
            'ranknet': get_ranknet_config,
            'ranknet_3y': get_ranknet_3y_config,
            'ranknet_5y_safelag': get_ranknet_5y_safelag_config,
            'ranknet_3y_safelag': get_ranknet_3y_safelag_config,
            'biotech_it_5y': get_biotech_it_ranknet_5y_config,
            'biotech_it_3y': get_biotech_it_ranknet_3y_config,
            'biotech_it_5y_safelag': get_biotech_it_ranknet_5y_safelag_config,
            'biotech_it_3y_safelag': get_biotech_it_ranknet_3y_safelag_config,
            'quarterly_ranknet': get_quarterly_ranknet_config,
            'quarterly_biotech_it': get_quarterly_ranknet_biotech_it_config,
        }
        
        if args.preset in preset_map:
            config = preset_map[args.preset]()
        else:
            print(f"❌ 알 수 없는 프리셋: {args.preset}")
            sys.exit(1)
    else:
        # 새로운 파라미터 방식
        config = build_config_from_params(args)
    
    # 실험 실행
    run_experiment(config)


if __name__ == '__main__':
    main()
