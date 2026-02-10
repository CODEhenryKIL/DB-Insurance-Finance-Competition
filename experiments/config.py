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
        
        if not self.long_ratios:
            errors.append("long_ratios가 비어있음")
        
        if self.train_window_years < 1:
            errors.append(f"train_window_years는 1 이상이어야 함: {self.train_window_years}")
        
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
    """기본 베이스라인 설정"""
    return ExperimentConfig(
        exp_id="exp_001",
        exp_name="baseline_sp500_mse",
        description="S&P 500 + MSE 기본 베이스라인",
        market_mode="SP500",
        y_target_mode="raw",
        model_type="MSE"
    )


def get_ranknet_config() -> ExperimentConfig:
    """RankNet 설정"""
    return ExperimentConfig(
        exp_id="exp_002",
        exp_name="sp500_ranknet",
        description="S&P 500 + RankNet 손실함수",
        market_mode="SP500",
        y_target_mode="raw",
        model_type="RankNet",
        predictions_file="step4_predictions_ranknet.csv",
        learning_rate=0.005,
        epochs=300
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
