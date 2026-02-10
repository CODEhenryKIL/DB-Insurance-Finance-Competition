"""
===========================================
보고서 생성 (Reporter)
===========================================

마크다운 보고서 자동 생성
- 설정 요약
- 연도별 수익률 표
- 성과 지표 표
- 벤치마크 비교
- 문제점/개선 아이디어/결론
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

from config.constants import BENCHMARK_INDICES
from utils.logger import get_logger
from .config import ExperimentConfig
from .runner import ExperimentResults

logger = get_logger(__name__)

# 기본 실험 폴더
EXPERIMENTS_V2_DIR = project_root / 'experiments_v2'


class ReportGenerator:
    """
    보고서 생성 클래스
    
    보고서 항목:
    1. 설정 표
    2. 포트폴리오별 연도별 수익률
    3. 포트폴리오별 성과 지표
    4. 벤치마크 비교
    5. 이전 실험과 비교 (있으면)
    6. 현재 문제점
    7. 개선 아이디어
    8. 결론 및 인사이트
    """
    
    def __init__(self, base_dir: Path = EXPERIMENTS_V2_DIR):
        """
        초기화
        
        Parameters
        ----------
        base_dir : Path
            실험 폴더 기본 경로
        """
        self.base_dir = base_dir
    
    def generate(
        self,
        results: ExperimentResults,
        exp_dir: Path,
        compare_results: Optional[ExperimentResults] = None,
        problems: str = "",
        improvements: str = "",
        conclusions: str = ""
    ) -> Path:
        """
        보고서 생성
        
        Parameters
        ----------
        results : ExperimentResults
            현재 실험 결과
        exp_dir : Path
            실험 폴더 경로
        compare_results : ExperimentResults, optional
            비교 대상 실험 결과
        problems : str
            현재 문제점 (수동 입력)
        improvements : str
            개선 아이디어 (수동 입력)
        conclusions : str
            결론 (수동 입력)
        
        Returns
        -------
        Path
            보고서 파일 경로
        """
        logger.info("\n[보고서 생성]")
        
        sections = []
        
        # 1. 헤더
        sections.append(self._generate_header(results.config))
        
        # 2. 설정 표
        sections.append(self._generate_config_table(results.config))
        
        # 3. 포트폴리오별 연도별 수익률
        sections.append(self._generate_returns_table(results))
        
        # 4. 포트폴리오별 성과 지표
        sections.append(self._generate_performance_table(results))
        
        # 5. 벤치마크 비교
        sections.append(self._generate_benchmark_comparison(results))
        
        # 6. 이전 실험과 비교
        if compare_results:
            sections.append(self._generate_experiment_comparison(results, compare_results))
        
        # 7. 검정 결과 요약
        sections.append(self._generate_validation_summary(results))
        
        # 8. 현재 문제점
        sections.append(self._generate_problems_section(problems, results))
        
        # 9. 개선 아이디어
        sections.append(self._generate_improvements_section(improvements))
        
        # 10. 결론 및 인사이트
        sections.append(self._generate_conclusions_section(conclusions, results))
        
        # 보고서 저장
        report_content = '\n\n'.join(sections)
        report_path = exp_dir / 'REPORT.md'
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"  → REPORT.md 저장: {report_path}")
        
        return report_path
    
    def _generate_header(self, config: ExperimentConfig) -> str:
        """헤더 생성"""
        return f"""# 실험 보고서: {config.exp_id} - {config.exp_name}

> **생성 일시**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> **설명**: {config.description}

---"""
    
    def _generate_config_table(self, config: ExperimentConfig) -> str:
        """설정 표 생성"""
        return f"""## 1. 실험 설정

| 항목 | 값 |
|------|-----|
| **실험 ID** | {config.exp_id} |
| **실험명** | {config.exp_name} |
| **Market Mode** | {config.market_mode} |
| **Y Target Mode** | {config.y_target_mode} |
| **Model Type** | {config.model_type} |
| **Train Window** | {config.train_window_years}년 |
| **Learning Rate** | {config.learning_rate} |
| **Epochs** | {config.epochs} |
| **Long Ratios** | {config.long_ratios} |
| **Holding Period** | {config.holding_months}개월 |
| **SmallCap Threshold** | 하위 {config.smallcap_percentile*100:.0f}% |
| **Risk Free Rate** | {config.risk_free_rate*100:.1f}% |"""
    
    def _generate_returns_table(self, results: ExperimentResults) -> str:
        """연도별 수익률 표 생성"""
        sections = ["## 2. 포트폴리오별 연도별 수익률"]
        
        for portfolio_type in ["normal", "smallcap"]:
            type_label = "일반 포트폴리오" if portfolio_type == "normal" else "소형주 포트폴리오"
            sections.append(f"\n### {type_label}")
            
            # 연도 리스트
            years = sorted(set(r.year for r in results.yearly_results))
            
            # 헤더
            header = "| 연도 |"
            separator = "|------|"
            for ratio in results.config.long_ratios:
                header += f" {ratio*100:.0f}% |"
                separator += "------:|"
            header += " S&P500 |"
            separator += "------:|"
            
            sections.append(header)
            sections.append(separator)
            
            # 데이터
            for year in years:
                row = f"| {year} |"
                
                for ratio in results.config.long_ratios:
                    yr = next(
                        (r for r in results.yearly_results 
                         if r.year == year and r.portfolio_type == portfolio_type and r.ratio == ratio),
                        None
                    )
                    if yr and yr.n_stocks > 0:
                        ret = yr.portfolio_return
                        row += f" {ret*100:+.1f}% |"
                    else:
                        row += " - |"
                
                # 벤치마크
                yr = next(
                    (r for r in results.yearly_results 
                     if r.year == year and r.portfolio_type == portfolio_type),
                    None
                )
                if yr and 'S&P500' in yr.benchmark_returns:
                    row += f" {yr.benchmark_returns['S&P500']*100:+.1f}% |"
                else:
                    row += " - |"
                
                sections.append(row)
        
        return '\n'.join(sections)
    
    def _generate_performance_table(self, results: ExperimentResults) -> str:
        """성과 지표 표 생성"""
        sections = ["## 3. 포트폴리오별 성과 지표"]
        
        if not results.performance_metrics:
            sections.append("\n*성과 지표 없음*")
            return '\n'.join(sections)
        
        # 일반 포트폴리오
        sections.append("\n### 일반 포트폴리오")
        sections.append("| 비율 | CAGR | Sharpe | MDD | WinRate | Alpha (S&P500) |")
        sections.append("|------|------|--------|-----|---------|----------------|")
        
        for ratio in results.config.long_ratios:
            key = f"normal_{int(ratio*100)}"
            if key in results.performance_metrics:
                m = results.performance_metrics[key]
                alpha = m.get('Alpha_vs_S&P500', np.nan)
                sections.append(
                    f"| {ratio*100:.0f}% | "
                    f"{m.get('CAGR', np.nan)*100:.1f}% | "
                    f"{m.get('Sharpe', np.nan):.2f} | "
                    f"{m.get('MDD', np.nan)*100:.1f}% | "
                    f"{m.get('WinRate', np.nan)*100:.0f}% | "
                    f"{alpha*100:+.1f}% |" if not np.isnan(alpha) else f"- |"
                )
        
        # 소형주 포트폴리오
        sections.append("\n### 소형주 포트폴리오")
        sections.append("| 비율 | CAGR | Sharpe | MDD | WinRate | Alpha (R2000) |")
        sections.append("|------|------|--------|-----|---------|----------------|")
        
        for ratio in results.config.long_ratios:
            key = f"smallcap_{int(ratio*100)}"
            if key in results.performance_metrics:
                m = results.performance_metrics[key]
                alpha = m.get('Alpha_vs_Russell2000', np.nan)
                alpha_str = f"{alpha*100:+.1f}%" if not np.isnan(alpha) else "-"
                sections.append(
                    f"| {ratio*100:.0f}% | "
                    f"{m.get('CAGR', np.nan)*100:.1f}% | "
                    f"{m.get('Sharpe', np.nan):.2f} | "
                    f"{m.get('MDD', np.nan)*100:.1f}% | "
                    f"{m.get('WinRate', np.nan)*100:.0f}% | "
                    f"{alpha_str} |"
                )
        
        return '\n'.join(sections)
    
    def _generate_benchmark_comparison(self, results: ExperimentResults) -> str:
        """벤치마크 비교 생성"""
        sections = ["## 4. 벤치마크 비교"]
        
        # 최고 성과 포트폴리오 찾기
        best_normal = None
        best_normal_cagr = -np.inf
        
        for key, metrics in results.performance_metrics.items():
            if key.startswith('normal_'):
                cagr = metrics.get('CAGR', -np.inf)
                if cagr > best_normal_cagr:
                    best_normal_cagr = cagr
                    best_normal = key
        
        if best_normal:
            m = results.performance_metrics[best_normal]
            sections.append(f"\n**최고 성과 포트폴리오**: {best_normal}")
            sections.append("")
            sections.append("| 벤치마크 | 전략 CAGR | 벤치마크 CAGR | Alpha |")
            sections.append("|----------|-----------|---------------|-------|")
            
            strategy_cagr = m.get('CAGR', np.nan)
            
            for bench in BENCHMARK_INDICES[:3]:  # 상위 3개만
                alpha = m.get(f'Alpha_vs_{bench}', np.nan)
                if not np.isnan(alpha):
                    bench_cagr = strategy_cagr - alpha
                    sections.append(
                        f"| {bench} | {strategy_cagr*100:.1f}% | "
                        f"{bench_cagr*100:.1f}% | {alpha*100:+.1f}% |"
                    )
        else:
            sections.append("\n*비교 가능한 포트폴리오 없음*")
        
        return '\n'.join(sections)
    
    def _generate_experiment_comparison(
        self,
        current: ExperimentResults,
        previous: ExperimentResults
    ) -> str:
        """이전 실험과 비교"""
        sections = [f"## 5. 이전 실험과 비교 ({previous.config.exp_id})"]
        
        sections.append("")
        sections.append("| 포트폴리오 | 현재 CAGR | 이전 CAGR | 변화 |")
        sections.append("|------------|-----------|-----------|------|")
        
        for key in current.performance_metrics:
            curr_cagr = current.performance_metrics[key].get('CAGR', np.nan)
            prev_cagr = previous.performance_metrics.get(key, {}).get('CAGR', np.nan)
            
            if not np.isnan(curr_cagr) and not np.isnan(prev_cagr):
                diff = curr_cagr - prev_cagr
                sections.append(
                    f"| {key} | {curr_cagr*100:.1f}% | {prev_cagr*100:.1f}% | "
                    f"{diff*100:+.1f}% |"
                )
        
        return '\n'.join(sections)
    
    def _generate_validation_summary(self, results: ExperimentResults) -> str:
        """검정 결과 요약"""
        sections = ["## 6. 검정 결과 요약"]
        
        tests = results.validation_tests
        
        # Rank IC
        if 'rank_ic' in tests:
            ic = tests['rank_ic']
            sections.append(f"\n### Rank IC (예측력)")
            sections.append(f"- **평균 Rank IC**: {ic.get('mean_ic', np.nan):.4f}")
            sections.append(f"- **표준편차**: {ic.get('std_ic', np.nan):.4f}")
            
            target = 0.03
            if ic.get('mean_ic', 0) >= target:
                sections.append(f"- ✅ 목표 달성 (>= {target})")
            else:
                sections.append(f"- ⚠️ 목표 미달 (< {target})")
        
        # 가중치 안정성
        if 'weight_stability' in tests:
            ws = tests['weight_stability']
            sections.append(f"\n### 가중치 안정성")
            sections.append(f"- m1 std: {ws.get('m1_std', np.nan):.4f}")
            sections.append(f"- m2 std: {ws.get('m2_std', np.nan):.4f}")
            sections.append(f"- m3 std: {ws.get('m3_std', np.nan):.4f}")
        
        return '\n'.join(sections)
    
    def _generate_problems_section(self, problems: str, results: ExperimentResults) -> str:
        """문제점 섹션"""
        sections = ["## 7. 현재 문제점"]
        
        if problems:
            sections.append(f"\n{problems}")
        else:
            # 자동 진단
            auto_problems = []
            
            # MDD 확인
            for key, metrics in results.performance_metrics.items():
                mdd = metrics.get('MDD', 0)
                if mdd < -0.30:
                    auto_problems.append(f"- {key}: MDD가 {mdd*100:.1f}%로 높음")
            
            # Win Rate 확인
            for key, metrics in results.performance_metrics.items():
                wr = metrics.get('WinRate', 1)
                if wr < 0.5:
                    auto_problems.append(f"- {key}: WinRate가 {wr*100:.0f}%로 낮음 (<50%)")
            
            # Rank IC 확인
            if 'rank_ic' in results.validation_tests:
                ic = results.validation_tests['rank_ic'].get('mean_ic', 0)
                if ic < 0.03:
                    auto_problems.append(f"- Rank IC가 {ic:.4f}로 낮음 (목표: 0.03+)")
            
            if auto_problems:
                sections.append("\n**자동 진단된 문제점:**")
                sections.extend(auto_problems)
            else:
                sections.append("\n*주요 문제점 없음*")
        
        return '\n'.join(sections)
    
    def _generate_improvements_section(self, improvements: str) -> str:
        """개선 아이디어 섹션"""
        sections = ["## 8. 개선 아이디어"]
        
        if improvements:
            sections.append(f"\n{improvements}")
        else:
            sections.append("""
**잠재적 개선 방향:**

1. **피처 조정**
   - m3 제외 시 알파 변화 확인
   - 새로운 피처 추가 (모멘텀, 퀄리티 등)

2. **유니버스 조정**
   - 섹터 필터링 강화
   - 유동성 조건 추가

3. **포트폴리오 구성**
   - 가중치 방식 변경 (동일 → 시가총액/역변동성)
   - 리밸런싱 주기 조정

4. **리스크 관리**
   - 손절 규칙 추가
   - 섹터 분산 강제
""")
        
        return '\n'.join(sections)
    
    def _generate_conclusions_section(self, conclusions: str, results: ExperimentResults) -> str:
        """결론 섹션"""
        sections = ["## 9. 결론 및 인사이트"]
        
        if conclusions:
            sections.append(f"\n{conclusions}")
        else:
            # 자동 결론
            sections.append("\n**주요 수치 요약:**")
            
            # 최고 성과 찾기
            best_cagr = -np.inf
            best_key = None
            
            for key, metrics in results.performance_metrics.items():
                cagr = metrics.get('CAGR', -np.inf)
                if cagr > best_cagr:
                    best_cagr = cagr
                    best_key = key
            
            if best_key:
                m = results.performance_metrics[best_key]
                sections.append(f"- **최고 성과**: {best_key}")
                sections.append(f"  - CAGR: {m.get('CAGR', np.nan)*100:.1f}%")
                sections.append(f"  - Sharpe: {m.get('Sharpe', np.nan):.2f}")
                sections.append(f"  - MDD: {m.get('MDD', np.nan)*100:.1f}%")
                sections.append(f"  - WinRate: {m.get('WinRate', np.nan)*100:.0f}%")
            
            sections.append("\n**다음 단계:**")
            sections.append("- [ ] 추가 실험 필요 여부 판단")
            sections.append("- [ ] 최적 파라미터 확정")
            sections.append("- [ ] 실전 적용 가능성 검토")
        
        sections.append("\n---\n*이 보고서는 자동 생성되었습니다.*")
        
        return '\n'.join(sections)


# ========================================
# 테스트
# ========================================
if __name__ == '__main__':
    from .config import get_baseline_config
    from .runner import ExperimentResults, YearlyResult
    
    # 더미 결과
    config = get_baseline_config()
    results = ExperimentResults(config=config)
    results.yearly_results = [
        YearlyResult(
            year=2019, portfolio_type="normal", ratio=0.10,
            portfolio_return=0.15, n_stocks=10,
            benchmark_returns={'S&P500': 0.10}
        ),
        YearlyResult(
            year=2020, portfolio_type="normal", ratio=0.10,
            portfolio_return=-0.05, n_stocks=10,
            benchmark_returns={'S&P500': -0.12}
        )
    ]
    results.performance_metrics = {
        'normal_10': {
            'CAGR': 0.12, 'Sharpe': 1.5, 'MDD': -0.15, 'WinRate': 0.7,
            'Alpha_vs_S&P500': 0.03
        }
    }
    results.validation_tests = {
        'rank_ic': {'mean_ic': 0.55, 'std_ic': 0.1}
    }
    
    # 보고서 생성 테스트
    import tempfile
    exp_dir = Path(tempfile.mkdtemp())
    
    reporter = ReportGenerator()
    report_path = reporter.generate(results, exp_dir)
    
    print(f"\n✅ 보고서 생성: {report_path}")
    print("\n--- 보고서 내용 ---")
    with open(report_path, 'r') as f:
        print(f.read()[:3000])
