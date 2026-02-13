"""
===========================================
실험 설정 (Configuration)
===========================================

실험 재현성을 위한 설정 관리
- JSON 직렬화 지원
- 기본값 제공
- 검증 로직 포함
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional
from datetime import datetime


@dataclass
class ExperimentConfig:
    """
    실험 설정 클래스
    
    모든 실험 파라미터를 저장하고 JSON으로 직렬화
    """
    
    # ========================================
    # 실험 메타 정보
    # ========================================
    exp_id: str = "exp_001"
    exp_name: str = "baseline"
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # ========================================
    # 데이터 설정
    # ========================================
    market_mode: str = "SP500"  # "SP500" or "FULL_MARKET"
    y_target_mode: str = "raw"  # "raw" or "sector" (섹터 상대 ln(PBR))
    model_type: str = "MSE"     # "MSE" or "RankNet"
    
    # ⭐ 리밸런싱 주기 설정
    # "annual": 연간 (12월 리밸런싱, 12개월 홀딩)
    # "semiannual": 반기 (6월/12월 리밸런싱, 6개월 홀딩)
    # "quarterly": 분기 (3/6/9/12월 리밸런싱, 3개월 홀딩)
    rebalance_frequency: str = "annual"
    
    # ⭐ 섹터 필터 (None = 전체 섹터)
    # 바이오&IT만 분석: ["Healthcare", "Technology"]
    # 전체: None 또는 []
    included_sectors: Optional[List[str]] = None
    
    # ⭐ Safe Lag (미래 참조 편향 방지)
    # 공시 지연을 고려한 리밸런싱 시점 지연 (월 단위)
    # 0 = 기존 방식 (12월 매수), 3 = 편향 해소 (3월 매수)
    # 분기/반기: 2~3개월 권장, 연간: 3개월 권장
    safe_lag_months: int = 0  # 기본값 0 = 기존 방식 유지
    
    # Step4 predictions 파일명
    predictions_file: str = "step4_predictions.csv"
    features_file: str = "step3_features_annual.csv"
    
    # ========================================
    # 모델 설정
    # ========================================
    train_window_years: int = 3
    learning_rate: float = 0.01
    epochs: int = 100
    
    # RankNet 전용
    ranknet_sigma: float = 1.0
    ranknet_batch_size: int = 128
    
    # ========================================
    # 백테스트 설정
    # ========================================
    long_ratios: List[float] = field(default_factory=lambda: [0.05, 0.10, 0.20, 0.30])
    holding_months: int = 12
    rebalance_month: int = 12
    
    # 유니버스 필터
    price_threshold_dollars: float = 5.0
    price_below_threshold_ratio: float = 0.8
    smallcap_percentile: float = 0.3  # 하위 30% = 소형주
    
    # ========================================
    # 벤치마크
    # ========================================
    benchmark_indices: List[str] = field(default_factory=lambda: [
        "S&P500", "Russell1000", "Russell2000", "Russell3000", "Wilshire5000"
    ])
    risk_free_rate: float = 0.02
    
    # ========================================
    # 검정 설정
    # ========================================
    bootstrap_samples: int = 1000
    significance_level: float = 0.05
    
    # ========================================
    # 비교 대상 (이전 실험)
    # ========================================
    compare_with: Optional[str] = None  # 이전 실험 ID
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return asdict(self)
    
    def to_json(self, path: Path) -> None:
        """JSON 파일로 저장"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, path: Path) -> 'ExperimentConfig':
        """JSON 파일에서 로드"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)
    
    def validate(self) -> List[str]:
        """
        설정 유효성 검증
        
        Returns
        -------
        list
            오류 메시지 리스트 (빈 리스트면 OK)
        """
        errors = []
        
        if self.market_mode not in ["SP500", "FULL_MARKET"]:
            errors.append(f"market_mode는 'SP500' 또는 'FULL_MARKET'이어야 함: {self.market_mode}")
        
        if self.y_target_mode not in ["raw", "sector"]:
            errors.append(f"y_target_mode는 'raw' 또는 'sector'이어야 함: {self.y_target_mode}")
        
        if self.model_type not in ["MSE", "RankNet"]:
            errors.append(f"model_type은 'MSE' 또는 'RankNet'이어야 함: {self.model_type}")
        
        if self.rebalance_frequency not in ["annual", "semiannual", "quarterly"]:
            errors.append(f"rebalance_frequency는 'annual', 'semiannual', 'quarterly' 중 하나여야 함: {self.rebalance_frequency}")
        
        if not self.long_ratios:
            errors.append("long_ratios가 비어있음")
        
        if self.train_window_years < 1:
            errors.append(f"train_window_years는 1 이상이어야 함: {self.train_window_years}")
        
        if self.safe_lag_months < 0:
            errors.append(f"safe_lag_months는 0 이상이어야 함: {self.safe_lag_months}")
        
        # included_sectors 검증
        valid_sectors = ['Healthcare', 'Technology', 'Industrials', 'Consumer Discretionary', 
                         'Consumer Staples', 'Communication']
        if self.included_sectors:
            for sector in self.included_sectors:
                if sector not in valid_sectors:
                    errors.append(f"유효하지 않은 섹터: {sector}. 가능: {valid_sectors}")
        
        return errors
    
    def get_exp_folder_name(self) -> str:
        """실험 폴더명 생성"""
        return f"{self.exp_id}_{self.exp_name}"
    
    def summary(self) -> str:
        """설정 요약 문자열"""
        return f"""
========================================
실험 설정: {self.exp_id} - {self.exp_name}
========================================
데이터:
  - Market Mode: {self.market_mode}
  - Y Target Mode: {self.y_target_mode}
  - Model Type: {self.model_type}
  - Rebalance Frequency: {self.rebalance_frequency}
  - Included Sectors: {self.included_sectors or '전체'}
  - Safe Lag: {self.safe_lag_months}개월
  
모델:
  - Train Window: {self.train_window_years}년
  - Learning Rate: {self.learning_rate}
  - Epochs: {self.epochs}
  
백테스트:
  - Long Ratios: {self.long_ratios}
  - Holding: {self.holding_months}개월
  - Rebalance: {self.rebalance_month}월
  
유니버스:
  - Price Threshold: ${self.price_threshold_dollars}
  - SmallCap Percentile: {self.smallcap_percentile*100:.0f}%
========================================
"""


# ========================================
# 사전 정의된 설정 프리셋
# ========================================

def get_baseline_config() -> ExperimentConfig:
    """기본 베이스라인 설정 (실험 1번: S&P 500, 전체 섹터, 5년 롤링, 연간, MSE)"""
    return ExperimentConfig(
        exp_id="exp_001",
        exp_name="baseline_sp500_mse_5y",
        description="S&P 500 + MSE + 5년 롤링 베이스라인 (섹터 상대 PBR)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE",
        train_window_years=5,  # 5년 롤링 윈도우
        learning_rate=0.005  # 안정적 학습
    )


def get_ranknet_config() -> ExperimentConfig:
    """RankNet 설정 (실험 3번: S&P 500, 전체 섹터, 5년 롤링, 연간, RankNet)"""
    return ExperimentConfig(
        exp_id="exp_003",
        exp_name="sp500_ranknet_5y",
        description="S&P 500 + RankNet + 5년 롤링 (섹터 상대 PBR)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        predictions_file="step4_predictions_ranknet.csv",
        train_window_years=5,
        learning_rate=0.005,
        epochs=300
    )


def get_ranknet_3y_config() -> ExperimentConfig:
    """실험 4번: S&P 500, 전체 섹터, 3년 롤링, 연간, RankNet"""
    return ExperimentConfig(
        exp_id="exp_004",
        exp_name="sp500_ranknet_3y",
        description="S&P 500 + RankNet + 3년 롤링 (섹터 상대 PBR)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        predictions_file="step4_predictions_ranknet_3y.csv",
        train_window_years=3,
        learning_rate=0.005,
        epochs=300
    )


# ========================================
# 미래 참조 편향 해소 버전 (Safe Lag 적용)
# ========================================

def get_ranknet_5y_safelag_config() -> ExperimentConfig:
    """실험 3-1번: S&P 500 + 5년 RankNet + Safe Lag 3개월 (편향 해소)"""
    return ExperimentConfig(
        exp_id="exp_003_1",
        exp_name="sp500_ranknet_5y_safelag",
        description="S&P 500 + RankNet + 5년 롤링 + Safe Lag 3개월 (미래참조편향 해소)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        predictions_file="step4_predictions_ranknet.csv",
        train_window_years=5,
        learning_rate=0.005,
        epochs=300,
        safe_lag_months=3  # ⭐ 미래 참조 편향 방지: FY2022 → 2023년 3월 말 매수
    )


def get_ranknet_3y_safelag_config() -> ExperimentConfig:
    """실험 4-1번: S&P 500 + 3년 RankNet + Safe Lag 3개월 (편향 해소)"""
    return ExperimentConfig(
        exp_id="exp_004_1",
        exp_name="sp500_ranknet_3y_safelag",
        description="S&P 500 + RankNet + 3년 롤링 + Safe Lag 3개월 (미래참조편향 해소)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        predictions_file="step4_predictions_ranknet_3y.csv",
        train_window_years=3,
        learning_rate=0.005,
        epochs=300,
        safe_lag_months=3  # ⭐ 미래 참조 편향 방지: FY2022 → 2023년 3월 말 매수
    )


def get_sector_relative_config() -> ExperimentConfig:
    """섹터 상대 설정"""
    return ExperimentConfig(
        exp_id="exp_003",
        exp_name="sp500_sector_relative",
        description="S&P 500 + 섹터 상대 ln(PBR)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE"
    )


def get_baseline_3y_config() -> ExperimentConfig:
    """실험 2번: S&P 500, 전체 섹터, 3년 롤링, 연간, MSE"""
    return ExperimentConfig(
        exp_id="exp_002",
        exp_name="baseline_sp500_mse_3y",
        description="S&P 500 + MSE + 3년 롤링 (섹터 상대 PBR)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE",
        train_window_years=3,  # 3년 롤링 윈도우
        learning_rate=0.005,
        predictions_file="step4_predictions_3y.csv"  # 3년 윈도우 predictions
    )


# ========================================
# 리밸런싱 주기별 프리셋
# ========================================

def get_quarterly_config() -> ExperimentConfig:
    """분기 리밸런싱 설정 (롤링 1년 홀딩)"""
    return ExperimentConfig(
        exp_id="exp_010",
        exp_name="sp500_quarterly",
        description="S&P 500 + 분기 리밸런싱 + 롤링 1년 홀딩",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE",
        rebalance_frequency="quarterly",
        holding_months=12,  # ⭐ 롤링 1년 홀딩: 각 분기 포트폴리오 12개월 보유
        rebalance_month=3,
        predictions_file="step4_predictions_quarterly.csv",
        features_file="step3_features_quarterly.csv",
        safe_lag_months=3  # ⭐ 10-Q 공시 지연 고려 (45일 → 3개월 안전마진)
    )


def get_quarterly_ranknet_config() -> ExperimentConfig:
    """실험 11번: S&P 500 전체 + 분기 + RankNet (롤링 1년 홀딩)"""
    return ExperimentConfig(
        exp_id="exp_011",
        exp_name="sp500_quarterly_ranknet",
        description="S&P 500 + 분기 리밸런싱 + RankNet + 롤링 1년 홀딩",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        rebalance_frequency="quarterly",
        holding_months=12,  # ⭐ 롤링 1년 홀딩
        rebalance_month=3,
        train_window_years=3,  # 12분기
        predictions_file="step4_predictions_ranknet_quarterly.csv",
        features_file="step3_features_quarterly.csv",
        learning_rate=0.005,
        epochs=300,
        safe_lag_months=3
    )


def get_quarterly_ranknet_biotech_it_config() -> ExperimentConfig:
    """실험 12번: S&P 500 바이오&IT + 분기 + RankNet (롤링 1년 홀딩)"""
    return ExperimentConfig(
        exp_id="exp_012",
        exp_name="biotech_it_quarterly_ranknet",
        description="S&P 500 바이오&IT + 분기 리밸런싱 + RankNet + 롤링 1년 홀딩",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        rebalance_frequency="quarterly",
        holding_months=12,  # ⭐ 롤링 1년 홀딩
        rebalance_month=3,
        train_window_years=3,
        included_sectors=["Healthcare", "Technology"],
        predictions_file="step4_predictions_ranknet_quarterly.csv",
        features_file="step3_features_quarterly.csv",
        learning_rate=0.005,
        epochs=300,
        safe_lag_months=3
    )


def get_semiannual_config() -> ExperimentConfig:
    """반기 리밸런싱 설정"""
    return ExperimentConfig(
        exp_id="exp_011",
        exp_name="sp500_semiannual",
        description="S&P 500 + 반기 리밸런싱 (Safe Lag 3개월 적용)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE",
        rebalance_frequency="semiannual",
        holding_months=6,
        rebalance_month=6,
        predictions_file="step4_predictions_semiannual.csv",
        features_file="step3_features_semiannual.csv",
        safe_lag_months=3  # ⭐ 10-Q/10-K 공시 지연 고려
    )


def get_annual_config() -> ExperimentConfig:
    """연간 리밸런싱 설정 (기본값)"""
    return ExperimentConfig(
        exp_id="exp_012",
        exp_name="sp500_annual",
        description="S&P 500 + 연간 리밸런싱 (12월)",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE",
        rebalance_frequency="annual",
        holding_months=12,
        rebalance_month=12,
        predictions_file="step4_predictions.csv",
        features_file="step3_features_annual.csv",
        safe_lag_months=3
    )


# ========================================
# 섹터 필터 프리셋 (바이오&IT)
# ========================================

def get_biotech_it_config() -> ExperimentConfig:
    """바이오&IT 섹터 전용 설정"""
    return ExperimentConfig(
        exp_id="exp_020",
        exp_name="biotech_it_annual",
        description="바이오(Healthcare) + IT(Technology) 섹터만",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE",
        rebalance_frequency="annual",
        included_sectors=["Healthcare", "Technology"],
        safe_lag_months=3
    )


def get_biotech_it_ranknet_5y_config() -> ExperimentConfig:
    """실험 5번: S&P 500, 바이오&IT, 5년 롤링, 연간, RankNet (편향 있음)"""
    return ExperimentConfig(
        exp_id="exp_005",
        exp_name="biotech_it_ranknet_5y",
        description="S&P 500 + 바이오&IT + RankNet + 5년 롤링",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        train_window_years=5,
        rebalance_frequency="annual",
        included_sectors=["Healthcare", "Technology"],
        predictions_file="step4_predictions_ranknet.csv",
        learning_rate=0.005,
        epochs=300
        # safe_lag_months=0 (기본값) - 12월 말 매수
    )


def get_biotech_it_ranknet_3y_config() -> ExperimentConfig:
    """실험 6번: S&P 500, 바이오&IT, 3년 롤링, 연간, RankNet (편향 있음)"""
    return ExperimentConfig(
        exp_id="exp_006",
        exp_name="biotech_it_ranknet_3y",
        description="S&P 500 + 바이오&IT + RankNet + 3년 롤링",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        train_window_years=3,
        rebalance_frequency="annual",
        included_sectors=["Healthcare", "Technology"],
        predictions_file="step4_predictions_ranknet_3y.csv",
        learning_rate=0.005,
        epochs=300
        # safe_lag_months=0 (기본값) - 12월 말 매수
    )


def get_biotech_it_ranknet_5y_safelag_config() -> ExperimentConfig:
    """실험 5-1번: S&P 500 + 바이오&IT + 5년 RankNet + Safe Lag (편향 해소)"""
    return ExperimentConfig(
        exp_id="exp_005_1",
        exp_name="biotech_it_ranknet_5y_safelag",
        description="S&P 500 + 바이오&IT + RankNet + 5년 + Safe Lag 3개월",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        train_window_years=5,
        rebalance_frequency="annual",
        included_sectors=["Healthcare", "Technology"],
        predictions_file="step4_predictions_ranknet.csv",
        learning_rate=0.005,
        epochs=300,
        safe_lag_months=3  # ⭐ 3월 말 매수
    )


def get_biotech_it_ranknet_3y_safelag_config() -> ExperimentConfig:
    """실험 6-1번: S&P 500 + 바이오&IT + 3년 RankNet + Safe Lag (편향 해소)"""
    return ExperimentConfig(
        exp_id="exp_006_1",
        exp_name="biotech_it_ranknet_3y_safelag",
        description="S&P 500 + 바이오&IT + RankNet + 3년 + Safe Lag 3개월",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="RankNet",
        train_window_years=3,
        rebalance_frequency="annual",
        included_sectors=["Healthcare", "Technology"],
        predictions_file="step4_predictions_ranknet_3y.csv",
        learning_rate=0.005,
        epochs=300,
        safe_lag_months=3  # ⭐ 3월 말 매수
    )


def get_biotech_it_quarterly_config() -> ExperimentConfig:
    """바이오&IT 분기 리밸런싱"""
    return ExperimentConfig(
        exp_id="exp_021",
        exp_name="biotech_it_quarterly",
        description="바이오&IT + 분기 리밸런싱",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE",
        rebalance_frequency="quarterly",
        holding_months=3,
        included_sectors=["Healthcare", "Technology"],
        predictions_file="step4_predictions_quarterly.csv",
        features_file="step3_features_quarterly.csv",
        safe_lag_months=3  # ⭐ Safe Lag: 분기 공시 지연 고려
    )


def get_biotech_it_semiannual_config() -> ExperimentConfig:
    """바이오&IT 반기 리밸런싱"""
    return ExperimentConfig(
        exp_id="exp_022",
        exp_name="biotech_it_semiannual",
        description="바이오&IT + 반기 리밸런싱",
        market_mode="SP500",
        y_target_mode="sector",
        model_type="MSE",
        rebalance_frequency="semiannual",
        holding_months=6,
        included_sectors=["Healthcare", "Technology"],
        predictions_file="step4_predictions_semiannual.csv",
        features_file="step3_features_semiannual.csv",
        safe_lag_months=3
    )


# ========================================
# 테스트
# ========================================
if __name__ == '__main__':
    # 기본 설정 테스트
    config = get_baseline_config()
    print(config.summary())
    
    # 유효성 검증
    errors = config.validate()
    if errors:
        print("오류:", errors)
    else:
        print("✅ 설정 유효함")
    
    # JSON 저장/로드 테스트
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        config.to_json(Path(f.name))
        loaded = ExperimentConfig.from_json(Path(f.name))
        print(f"\n✅ JSON 저장/로드 테스트 완료: {f.name}")
