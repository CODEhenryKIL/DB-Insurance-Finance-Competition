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

# experiments/src/ -> experiments/ -> 프로젝트 루트
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

from config.constants import BENCHMARK_INDICES, BENCHMARK_RETURNS
from utils.logger import get_logger
from .config import ExperimentConfig
from .runner import ExperimentResults

logger = get_logger(__name__)

# 기본 실험 폴더
EXPERIMENTS_DIR = project_root / 'experiments'


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
    
    @staticmethod
    def _get_exp_num(exp_id: str) -> str:
        """
        exp_id에서 실험 번호 추출
        
        'exp_001' -> '001'
        'exp_012' -> '012'
        """
        import re
        match = re.search(r'(\d+)', exp_id)
        return match.group(1) if match else exp_id
    
    def __init__(self, base_dir: Path = EXPERIMENTS_DIR):
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
        
        # 6. 섹터 비율
        sections.append(self._generate_sector_breakdown(results))
        
        # 7. 이전 실험과 비교
        if compare_results:
            sections.append(self._generate_experiment_comparison(results, compare_results))
        
        # 8. 검정 결과 요약
        sections.append(self._generate_validation_summary(results))
        
        # 9. 현재 문제점
        sections.append(self._generate_problems_section(problems, results))
        
        # 10. 개선 아이디어
        sections.append(self._generate_improvements_section(improvements))
        
        # 11. 결론 및 인사이트
        sections.append(self._generate_conclusions_section(conclusions, results))
        
        # 보고서 저장
        report_content = '\n\n'.join(sections)
        exp_num = self._get_exp_num(results.config.exp_id)
        report_path = exp_dir / f'{exp_num}-REPORT.md'
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"  → {exp_num}-REPORT.md 저장: {report_path}")
        
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
                    bench_ret = yr.benchmark_returns['S&P500']
                    if bench_ret is not None and not np.isnan(bench_ret):
                        row += f" {bench_ret*100:+.1f}% |"
                    else:
                        row += " - |"
                else:
                    row += " - |"
                
                sections.append(row)
        
        return '\n'.join(sections)
    
    def _calculate_benchmark_metrics(self, years: List) -> Dict:
        """벤치마크 CAGR, Sharpe, MDD 계산
        
        Note: years는 매수 연도. 벤치마크 수익률은 year+1 기준으로 조회.
        분기 데이터의 경우 2015.3 같은 float일 수 있으므로 정수 연도로 변환.
        """
        benchmarks = {}
        
        # 분기 데이터의 경우 정수 연도만 추출 (중복 제거)
        unique_years = sorted(set(int(y) for y in years))
        
        for bench in ['S&P500', 'Russell3000', 'Russell2000']:
            returns = []
            for year in unique_years:
                # 수익률은 매수 연도+1에서 발생
                return_year = year + 1
                if return_year in BENCHMARK_RETURNS and bench in BENCHMARK_RETURNS[return_year]:
                    returns.append(BENCHMARK_RETURNS[return_year][bench])
            
            if returns:
                returns = np.array(returns)
                n_years = len(returns)
                
                # CAGR
                total_return = np.prod(1 + returns) - 1
                cagr = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else np.nan
                
                # Sharpe (annualized, rf=2%)
                mean_ret = np.mean(returns)
                std_ret = np.std(returns)
                sharpe = (mean_ret - 0.02) / std_ret if std_ret > 0 else np.nan
                
                # MDD
                cumulative = np.cumprod(1 + returns)
                running_max = np.maximum.accumulate(cumulative)
                drawdown = (cumulative - running_max) / running_max
                mdd = np.min(drawdown)
                
                benchmarks[bench] = {
                    'CAGR': cagr,
                    'Sharpe': sharpe,
                    'MDD': mdd
                }
        
        return benchmarks
    
    def _generate_performance_table(self, results: ExperimentResults) -> str:
        """성과 지표 표 생성 (벤치마크 행 + 3개 Alpha/Beta 포함)"""
        sections = ["## 3. 포트폴리오별 성과 지표"]
        
        if not results.performance_metrics:
            sections.append("\n*성과 지표 없음*")
            return '\n'.join(sections)
        
        # 벤치마크 지표 계산
        years = sorted(set(r.year for r in results.yearly_results))
        bench_metrics = self._calculate_benchmark_metrics(years)
        
        # ===== 일반 포트폴리오 =====
        sections.append("\n### 일반 포트폴리오")
        sections.append("| 비율 | CAGR | Sharpe | MDD | WinRate | α(SPX) | β(SPX) | α(R3K) | β(R3K) |")
        sections.append("|------|------|--------|-----|---------|--------|--------|--------|--------|")
        
        # 벤치마크 행 먼저
        for bench in ['S&P500', 'Russell3000']:
            if bench in bench_metrics:
                bm = bench_metrics[bench]
                bench_label = "S&P500" if bench == "S&P500" else "R3000"
                sections.append(
                    f"| **{bench_label}** | {bm['CAGR']*100:.1f}% | {bm['Sharpe']:.2f} | "
                    f"{bm['MDD']*100:.1f}% | - | - | - | - | - |"
                )
        
        # 포트폴리오 행
        for ratio in results.config.long_ratios:
            key = f"normal_{int(ratio*100)}"
            if key in results.performance_metrics:
                m = results.performance_metrics[key]
                
                # S&P500 Alpha/Beta
                alpha_spx = m.get('Alpha_vs_S&P500', np.nan)
                beta_spx = m.get('Beta_vs_S&P500', np.nan)
                alpha_spx_str = f"{alpha_spx*100:+.1f}%" if not np.isnan(alpha_spx) else "-"
                beta_spx_str = f"{beta_spx:.2f}" if not np.isnan(beta_spx) else "-"
                
                # Russell3000 Alpha/Beta
                alpha_r3k = m.get('Alpha_vs_Russell3000', np.nan)
                beta_r3k = m.get('Beta_vs_Russell3000', np.nan)
                alpha_r3k_str = f"{alpha_r3k*100:+.1f}%" if not np.isnan(alpha_r3k) else "-"
                beta_r3k_str = f"{beta_r3k:.2f}" if not np.isnan(beta_r3k) else "-"
                
                sections.append(
                    f"| {ratio*100:.0f}% | "
                    f"{m.get('CAGR', np.nan)*100:.1f}% | "
                    f"{m.get('Sharpe', np.nan):.2f} | "
                    f"{m.get('MDD', np.nan)*100:.1f}% | "
                    f"{m.get('WinRate', np.nan)*100:.0f}% | "
                    f"{alpha_spx_str} | {beta_spx_str} | "
                    f"{alpha_r3k_str} | {beta_r3k_str} |"
                )
        
        # ===== 소형주 포트폴리오 =====
        sections.append("\n### 소형주 포트폴리오")
        sections.append("| 비율 | CAGR | Sharpe | MDD | WinRate | α(R2K) | β(R2K) | α(R3K) | β(R3K) |")
        sections.append("|------|------|--------|-----|---------|--------|--------|--------|--------|")
        
        # 벤치마크 행 먼저
        for bench in ['Russell2000', 'Russell3000']:
            if bench in bench_metrics:
                bm = bench_metrics[bench]
                bench_label = "R2000" if bench == "Russell2000" else "R3000"
                sections.append(
                    f"| **{bench_label}** | {bm['CAGR']*100:.1f}% | {bm['Sharpe']:.2f} | "
                    f"{bm['MDD']*100:.1f}% | - | - | - | - | - |"
                )
        
        # 포트폴리오 행
        for ratio in results.config.long_ratios:
            key = f"smallcap_{int(ratio*100)}"
            if key in results.performance_metrics:
                m = results.performance_metrics[key]
                
                # Russell2000 Alpha/Beta
                alpha_r2k = m.get('Alpha_vs_Russell2000', np.nan)
                beta_r2k = m.get('Beta_vs_Russell2000', np.nan)
                alpha_r2k_str = f"{alpha_r2k*100:+.1f}%" if not np.isnan(alpha_r2k) else "-"
                beta_r2k_str = f"{beta_r2k:.2f}" if not np.isnan(beta_r2k) else "-"
                
                # Russell3000 Alpha/Beta
                alpha_r3k = m.get('Alpha_vs_Russell3000', np.nan)
                beta_r3k = m.get('Beta_vs_Russell3000', np.nan)
                alpha_r3k_str = f"{alpha_r3k*100:+.1f}%" if not np.isnan(alpha_r3k) else "-"
                beta_r3k_str = f"{beta_r3k:.2f}" if not np.isnan(beta_r3k) else "-"
                
                sections.append(
                    f"| {ratio*100:.0f}% | "
                    f"{m.get('CAGR', np.nan)*100:.1f}% | "
                    f"{m.get('Sharpe', np.nan):.2f} | "
                    f"{m.get('MDD', np.nan)*100:.1f}% | "
                    f"{m.get('WinRate', np.nan)*100:.0f}% | "
                    f"{alpha_r2k_str} | {beta_r2k_str} | "
                    f"{alpha_r3k_str} | {beta_r3k_str} |"
                )
        
        return '\n'.join(sections)
    
    def _generate_benchmark_comparison(self, results: ExperimentResults) -> str:
        """벤치마크 비교 생성 (전체 포트폴리오 vs 벤치마크)"""
        sections = ["## 4. 벤치마크 비교"]
        
        # 벤치마크 지표 계산
        years = sorted(set(r.year for r in results.yearly_results))
        bench_metrics = self._calculate_benchmark_metrics(years)
        
        # 일반 포트폴리오 최고 성과
        sections.append("\n### 일반 포트폴리오 최고 성과")
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
            sections.append("| 지표 | 전략 | S&P500 | Russell3000 | 차이(SPX) |")
            sections.append("|------|------|--------|-------------|-----------|")
            
            strategy_cagr = m.get('CAGR', np.nan)
            strategy_sharpe = m.get('Sharpe', np.nan)
            strategy_mdd = m.get('MDD', np.nan)
            
            spx = bench_metrics.get('S&P500', {})
            r3k = bench_metrics.get('Russell3000', {})
            
            spx_cagr = spx.get('CAGR', np.nan)
            diff_cagr = strategy_cagr - spx_cagr if not np.isnan(spx_cagr) else np.nan
            
            sections.append(
                f"| CAGR | {strategy_cagr*100:.1f}% | {spx.get('CAGR', np.nan)*100:.1f}% | "
                f"{r3k.get('CAGR', np.nan)*100:.1f}% | {diff_cagr*100:+.1f}% |"
            )
            sections.append(
                f"| Sharpe | {strategy_sharpe:.2f} | {spx.get('Sharpe', np.nan):.2f} | "
                f"{r3k.get('Sharpe', np.nan):.2f} | {strategy_sharpe - spx.get('Sharpe', 0):+.2f} |"
            )
            sections.append(
                f"| MDD | {strategy_mdd*100:.1f}% | {spx.get('MDD', np.nan)*100:.1f}% | "
                f"{r3k.get('MDD', np.nan)*100:.1f}% | {(strategy_mdd - spx.get('MDD', 0))*100:+.1f}%p |"
            )
        
        # 소형주 포트폴리오 최고 성과
        sections.append("\n### 소형주 포트폴리오 최고 성과")
        best_smallcap = None
        best_smallcap_cagr = -np.inf
        
        for key, metrics in results.performance_metrics.items():
            if key.startswith('smallcap_'):
                cagr = metrics.get('CAGR', -np.inf)
                if cagr > best_smallcap_cagr:
                    best_smallcap_cagr = cagr
                    best_smallcap = key
        
        if best_smallcap:
            m = results.performance_metrics[best_smallcap]
            sections.append(f"\n**최고 성과 포트폴리오**: {best_smallcap}")
            sections.append("")
            sections.append("| 지표 | 전략 | Russell2000 | Russell3000 | 차이(R2K) |")
            sections.append("|------|------|-------------|-------------|-----------|")
            
            strategy_cagr = m.get('CAGR', np.nan)
            strategy_sharpe = m.get('Sharpe', np.nan)
            strategy_mdd = m.get('MDD', np.nan)
            
            r2k = bench_metrics.get('Russell2000', {})
            r3k = bench_metrics.get('Russell3000', {})
            
            r2k_cagr = r2k.get('CAGR', np.nan)
            diff_cagr = strategy_cagr - r2k_cagr if not np.isnan(r2k_cagr) else np.nan
            
            sections.append(
                f"| CAGR | {strategy_cagr*100:.1f}% | {r2k.get('CAGR', np.nan)*100:.1f}% | "
                f"{r3k.get('CAGR', np.nan)*100:.1f}% | {diff_cagr*100:+.1f}% |"
            )
            sections.append(
                f"| Sharpe | {strategy_sharpe:.2f} | {r2k.get('Sharpe', np.nan):.2f} | "
                f"{r3k.get('Sharpe', np.nan):.2f} | {strategy_sharpe - r2k.get('Sharpe', 0):+.2f} |"
            )
            sections.append(
                f"| MDD | {strategy_mdd*100:.1f}% | {r2k.get('MDD', np.nan)*100:.1f}% | "
                f"{r3k.get('MDD', np.nan)*100:.1f}% | {(strategy_mdd - r2k.get('MDD', 0))*100:+.1f}%p |"
            )
        
        return '\n'.join(sections)
    
    def _generate_sector_breakdown(self, results: ExperimentResults) -> str:
        """
        섹터 비율 분석
        
        각 포트폴리오(normal_5, smallcap_5 등)별로 섹터 비중을 분석
        """
        sections = ["## 5. 섹터 비율 분석"]
        
        # predictions_with_rank에서 섹터 매핑 생성
        if results.predictions_with_rank is None or 'Sector' not in results.predictions_with_rank.columns:
            sections.append("\n*섹터 정보 없음*")
            return '\n'.join(sections)
        
        pred_df = results.predictions_with_rank
        
        # 포트폴리오별 섹터 비율 계산
        for portfolio_type in ["normal", "smallcap"]:
            type_label = "일반 포트폴리오" if portfolio_type == "normal" else "소형주 포트폴리오"
            sections.append(f"\n### {type_label}")
            
            # TOP 5% 포트폴리오만 분석 (다른 비율도 원하면 추가)
            ratio = 0.05
            
            # 연도별로 top N 종목의 섹터 수집
            sector_counts = {}
            total_stocks = 0
            
            for yr in results.yearly_results:
                if yr.portfolio_type != portfolio_type or yr.ratio != ratio:
                    continue
                
                for ticker in yr.tickers:
                    # 해당 연도, 티커의 섹터 찾기
                    mask = (pred_df['Ticker'] == ticker) & (pred_df['FiscalYear'] == yr.year)
                    matched = pred_df[mask]
                    
                    if len(matched) > 0:
                        sector = matched['Sector'].iloc[0]
                        if pd.notna(sector):
                            sector_counts[sector] = sector_counts.get(sector, 0) + 1
                            total_stocks += 1
            
            if total_stocks == 0:
                sections.append("*데이터 없음*")
                continue
            
            # 비율 계산 및 정렬
            sector_pcts = {k: v / total_stocks * 100 for k, v in sector_counts.items()}
            sorted_sectors = sorted(sector_pcts.items(), key=lambda x: -x[1])
            
            sections.append(f"\n**{int(ratio*100)}% 포트폴리오 섹터 비율** (전체 {total_stocks}개 종목-연도)")
            sections.append("")
            sections.append("| 섹터 | 비율 | 종목수 |")
            sections.append("|------|------|--------|")
            
            for sector, pct in sorted_sectors[:10]:  # 상위 10개만
                count = sector_counts[sector]
                sections.append(f"| {sector} | {pct:.1f}% | {count} |")
        
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
        """검정 결과 요약 (Bootstrap 강건성 포함)"""
        sections = ["## 6. 검정 결과 요약"]
        
        tests = results.validation_tests
        
        # Rank IC
        if 'rank_ic' in tests:
            ic = tests['rank_ic']
            sections.append(f"\n### Rank IC (예측력)")
            sections.append("> Rank IC: 예측값(yhat)과 실제값(y)의 Spearman 순위상관. 높을수록 예측력 좋음.")
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
            sections.append("> 모델 가중치(m1, m2, m3)의 연도별 표준편차. 낮을수록 시간에 따른 모델 안정성 높음.")
            sections.append("")
            sections.append("| 피처 | 평균 가중치 | 표준편차 |")
            sections.append("|------|-------------|----------|")
            
            m1_mean = ws.get('m1_mean', np.nan)
            m2_mean = ws.get('m2_mean', np.nan)
            m3_mean = ws.get('m3_mean', np.nan)
            m1_std = ws.get('m1_std', np.nan)
            m2_std = ws.get('m2_std', np.nan)
            m3_std = ws.get('m3_std', np.nan)
            
            sections.append(f"| m1 (PBR역수) | {m1_mean:.4f} | {m1_std:.4f} |")
            sections.append(f"| m2 (ROA) | {m2_mean:.4f} | {m2_std:.4f} |")
            sections.append(f"| m3 (조정영업이익) | {m3_mean:.4f} | {m3_std:.4f} |")
        
        # 강건성 (Bootstrap)
        robust_count = 0
        total_count = 0
        
        sections.append(f"\n### 포트폴리오 강건성 (Bootstrap 95% CI)")
        sections.append("> Bootstrap: 1000회 리샘플링으로 수익률 신뢰구간 계산. 95% CI가 0을 포함하지 않으면 '강건' (통계적으로 유의미한 양수 수익률)")
        sections.append("")
        sections.append("| 포트폴리오 | 평균 수익률 | 95% CI | 강건성 |")
        sections.append("|------------|-------------|--------|--------|")
        
        for key, val in tests.items():
            if key.startswith('robustness_'):
                portfolio_name = key.replace('robustness_', '')
                mean_ret = val.get('mean_return', np.nan)
                ci_lower = val.get('bootstrap_ci_95_lower', np.nan)
                ci_upper = val.get('bootstrap_ci_95_upper', np.nan)
                is_robust = val.get('is_robust', False)
                
                total_count += 1
                if is_robust:
                    robust_count += 1
                
                ci_str = f"[{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]" if not np.isnan(ci_lower) else "-"
                robust_str = "✅ 강건" if is_robust else "⚠️ 불안정"
                
                sections.append(
                    f"| {portfolio_name} | {mean_ret*100:.1f}% | {ci_str} | {robust_str} |"
                )
        
        if total_count > 0:
            sections.append(f"\n**강건 포트폴리오**: {robust_count}/{total_count} ({robust_count/total_count*100:.0f}%)")
            sections.append(f"> {robust_count}개 포트폴리오의 95% 신뢰구간이 0을 포함하지 않음 (통계적으로 유의미한 양수 수익률)")
        
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
