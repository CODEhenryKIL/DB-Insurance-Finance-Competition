"""
===========================================
M-Model 선형 모델 (MSE + RankNet 통합)
===========================================

두 가지 모델 타입 지원:
1. MSE: Mean Squared Error 손실함수 (기본)
2. RankNet: Pairwise Ranking 손실함수 (순위 학습)

모델 구조 (동일):
    y = w1·m1 + w2·m2 + w3·m3 + b
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from scipy.stats import spearmanr
from typing import Dict, Optional, Tuple


class LinearModel(nn.Module):
    """
    PBR 예측 선형 모델
    
    MSE와 RankNet 모두 동일한 모델 구조 사용.
    손실함수만 다르게 적용.
    
    Parameters
    ----------
    input_dim : int, default=3
        입력 차원 (m1, m2, m3)
    output_dim : int, default=1
        출력 차원 (yhat 또는 score)
    """
    
    def __init__(self, input_dim: int = 3, output_dim: int = 1):
        super().__init__()
        
        self.linear = nn.Linear(input_dim, output_dim, bias=True)
        
        # Xavier 초기화
        nn.init.xavier_uniform_(self.linear.weight)
        nn.init.zeros_(self.linear.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass"""
        return self.linear(x)
    
    def get_weights(self) -> Dict[str, float]:
        """학습된 가중치 반환"""
        weights = self.linear.weight.detach().cpu().numpy().flatten()
        bias = self.linear.bias.detach().cpu().item()
        
        return {
            'w1': float(weights[0]),
            'w2': float(weights[1]),
            'w3': float(weights[2]),
            'b': float(bias)
        }
    
    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """예측 (평가 모드)"""
        self.eval()
        with torch.no_grad():
            return self.forward(x)


class RankNetLoss(nn.Module):
    """
    RankNet Pairwise Ranking Loss
    
    핵심 수식:
    - P(i > j) = sigmoid(sigma * (s_i - s_j))
    - Loss = log(1 + exp(-sigma * (s_i - s_j)))  (for y_i > y_j)
    
    Parameters
    ----------
    sigma : float, default=1.0
        점수 차이 스케일링 파라미터
    """
    
    def __init__(self, sigma: float = 1.0):
        super().__init__()
        self.sigma = sigma
    
    def forward(self, scores: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Pairwise Ranking Loss 계산
        
        Parameters
        ----------
        scores : Tensor (batch_size, 1)
            모델 예측 점수
        targets : Tensor (batch_size, 1)
            실제 타겟 y
        
        Returns
        -------
        Tensor
            스칼라 손실값
        """
        batch_size = scores.size(0)
        
        if batch_size < 2:
            return torch.tensor(0.0, device=scores.device, requires_grad=True)
        
        scores = scores.squeeze(-1)
        targets = targets.squeeze(-1)
        
        # 모든 쌍에 대해 차이 계산 (N x N)
        score_diff = scores.unsqueeze(1) - scores.unsqueeze(0)
        target_diff = targets.unsqueeze(1) - targets.unsqueeze(0)
        
        # S_ij: y_i > y_j 이면 1
        S_ij = (target_diff > 0).float()
        
        # 유효한 쌍만 (y_i != y_j, 대각선 제외)
        valid_pairs = (target_diff != 0)
        diag_mask = ~torch.eye(batch_size, dtype=torch.bool, device=scores.device)
        valid_pairs = valid_pairs & diag_mask
        
        if not valid_pairs.any():
            return torch.tensor(0.0, device=scores.device, requires_grad=True)
        
        # RankNet Loss 계산
        # L = S_ij * log(sigmoid(diff)) + (1-S_ij) * log(1 - sigmoid(diff))
        # = -log(sigmoid(S_ij * 2 - 1) * diff)
        o_ij = self.sigma * score_diff
        loss_matrix = -S_ij * F.logsigmoid(o_ij) - (1 - S_ij) * F.logsigmoid(-o_ij)
        
        # 유효한 쌍만 평균
        loss = loss_matrix[valid_pairs].mean()
        
        return loss


def compute_rank_ic(predictions: np.ndarray, targets: np.ndarray) -> float:
    """
    Rank IC (Information Coefficient) 계산
    
    예측값과 실제값의 스피어만 순위 상관계수
    
    Parameters
    ----------
    predictions : array
        모델 예측값
    targets : array
        실제값
    
    Returns
    -------
    float
        Rank IC (-1 ~ 1)
    """
    if len(predictions) < 3:
        return 0.0
    
    # NaN 제거
    mask = ~(np.isnan(predictions) | np.isnan(targets))
    if mask.sum() < 3:
        return 0.0
    
    corr, _ = spearmanr(predictions[mask], targets[mask])
    return corr if not np.isnan(corr) else 0.0


def compute_ndcg(predictions: np.ndarray, targets: np.ndarray, k: int = 10) -> float:
    """
    NDCG@k (Normalized Discounted Cumulative Gain) 계산
    
    상위 k개 종목의 순위 품질 측정
    
    Parameters
    ----------
    predictions : array
        모델 예측값 (점수)
    targets : array
        실제값 (relevance)
    k : int
        상위 k개 고려
    
    Returns
    -------
    float
        NDCG@k (0 ~ 1)
    """
    if len(predictions) < k:
        k = len(predictions)
    if k == 0:
        return 0.0
    
    # 예측 점수 기준 상위 k개 인덱스
    pred_top_k = np.argsort(predictions)[::-1][:k]
    
    # DCG 계산
    dcg = 0.0
    for i, idx in enumerate(pred_top_k):
        rel = targets[idx]
        dcg += rel / np.log2(i + 2)  # i+2 because log2(1) = 0
    
    # 이상적인 DCG (IDCG)
    ideal_order = np.argsort(targets)[::-1][:k]
    idcg = 0.0
    for i, idx in enumerate(ideal_order):
        rel = targets[idx]
        idcg += rel / np.log2(i + 2)
    
    if idcg == 0:
        return 0.0
    
    return dcg / idcg


# ===========================================
# 하위 호환성 alias
# ===========================================

# 기존 코드에서 사용하는 이름
LinearPBRModel = LinearModel
LinearRankNetModel = LinearModel


if __name__ == '__main__':
    """모델 테스트"""
    print("=" * 60)
    print("LinearModel 테스트")
    print("=" * 60)
    
    # 모델 생성
    model = LinearModel(input_dim=3, output_dim=1)
    print(f"\n[모델 구조]")
    print(model)
    
    # 파라미터 개수
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\n[파라미터]: {total_params}개 (3 weights + 1 bias)")
    
    # 더미 입력
    batch_size = 10
    x = torch.randn(batch_size, 3)
    y = torch.randn(batch_size, 1)
    
    # Forward pass
    pred = model(x)
    print(f"\n[Forward]: 입력 {x.shape} → 출력 {pred.shape}")
    
    # MSE Loss
    mse_loss = nn.MSELoss()(pred, y)
    print(f"[MSE Loss]: {mse_loss.item():.4f}")
    
    # RankNet Loss
    ranknet_loss = RankNetLoss(sigma=1.0)(pred, y)
    print(f"[RankNet Loss]: {ranknet_loss.item():.4f}")
    
    # Rank IC
    ic = compute_rank_ic(pred.detach().numpy().flatten(), y.numpy().flatten())
    print(f"[Rank IC]: {ic:.4f}")
    
    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
