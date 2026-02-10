"""
===========================================
RankNet 모델 및 Pairwise Ranking Loss
===========================================

이 파일의 역할:
- 종목 간 상대적 순위를 학습하는 RankNet 모델
- Pairwise Ranking Loss (누가 누구보다 더 좋은가?)
- MSE 회귀와 달리 극단값에 덜 민감

핵심 개념:
1. RankNet Loss
   - 두 종목 i, j의 점수 s_i, s_j 비교
   - 실제 y_i > y_j 이면 s_i > s_j 가 되도록 학습
   - P(i > j) = sigmoid(s_i - s_j)

2. Cross-sectional 비교
   - 동일 시점(FiscalYear) 종목끼리만 비교
   - 시계열 비교는 무의미함

3. 메모리 효율
   - 배치 내 N종목 → N×N 쌍 생성
   - 배치 사이즈 제한 필요 (권장: 64~128)

기대 효과:
- 상위 20~30% 구간의 중상위권 종목 정확도 향상
- 극단값(Outlier)에 휘둘리지 않음
- 포트폴리오 안정성(Robustness) 확보
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from scipy.stats import spearmanr


class LinearRankNetModel(nn.Module):
    """
    RankNet 선형 점수 모델
    
    구조: score = w1·m1 + w2·m2 + w3·m3 + b
    
    기존 LinearPBRModel과 동일한 구조이나,
    학습 시 RankNet Loss를 사용하여 순위 학습
    
    Parameters
    ----------
    input_dim : int, default=3
        입력 차원 (m1, m2, m3)
    output_dim : int, default=1
        출력 차원 (score)
    """
    
    def __init__(self, input_dim: int = 3, output_dim: int = 1):
        super(LinearRankNetModel, self).__init__()
        
        # 선형 레이어 (3 → 1)
        self.linear = nn.Linear(input_dim, output_dim, bias=True)
        
        # 초기화: Xavier uniform
        nn.init.xavier_uniform_(self.linear.weight)
        nn.init.zeros_(self.linear.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass - 점수 예측
        
        Parameters
        ----------
        x : Tensor
            입력 텐서 (batch_size, 3)
        
        Returns
        -------
        Tensor
            점수 텐서 (batch_size, 1)
        """
        return self.linear(x)
    
    def get_weights(self) -> dict:
        """
        학습된 가중치 반환
        
        Returns
        -------
        dict
            {'w1': float, 'w2': float, 'w3': float, 'b': float}
        """
        weights = self.linear.weight.detach().cpu().numpy().flatten()
        bias = self.linear.bias.detach().cpu().item()
        
        return {
            'w1': weights[0],
            'w2': weights[1],
            'w3': weights[2],
            'b': bias
        }
    
    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """
        예측 (평가 모드)
        """
        self.eval()
        with torch.no_grad():
            return self.forward(x)


class RankNetLoss(nn.Module):
    """
    RankNet Pairwise Ranking Loss
    
    핵심 수식:
    - P(i > j) = sigmoid(sigma * (s_i - s_j))
    - Loss = -[S_ij * log(P_ij) + (1 - S_ij) * log(1 - P_ij)]
    
    여기서:
    - s_i, s_j: 모델이 예측한 점수
    - S_ij: 실제 라벨 (y_i > y_j 이면 1, 아니면 0)
    - sigma: 스케일링 파라미터
    
    단순화된 구현 (S_ij = 1인 경우만):
    - Loss = log(1 + exp(-sigma * (s_i - s_j)))
    
    Parameters
    ----------
    sigma : float, default=1.0
        점수 차이 스케일링 파라미터
    margin : float, default=0.0
        마진 (optional, 더 강한 분리 원할 시)
    """
    
    def __init__(self, sigma: float = 1.0, margin: float = 0.0):
        super(RankNetLoss, self).__init__()
        self.sigma = sigma
        self.margin = margin
    
    def forward(
        self, 
        scores: torch.Tensor, 
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Pairwise Ranking Loss 계산
        
        배치 내 모든 쌍에 대해 손실 계산
        
        Parameters
        ----------
        scores : Tensor
            모델 예측 점수 (batch_size, 1)
        targets : Tensor
            실제 타겟 y (batch_size, 1)
        
        Returns
        -------
        Tensor
            스칼라 손실값
        
        Note
        ----
        메모리: O(batch_size^2)
        배치 사이즈 N이면 N×N 매트릭스 생성
        """
        batch_size = scores.size(0)
        
        if batch_size < 2:
            # 배치 크기가 2 미만이면 비교 불가
            return torch.tensor(0.0, device=scores.device, requires_grad=True)
        
        # scores: (N, 1) → (N,)
        scores = scores.squeeze(-1)
        targets = targets.squeeze(-1)
        
        # 모든 쌍에 대해 점수 차이 계산
        # s_i - s_j for all pairs
        # (N, 1) - (1, N) = (N, N) 브로드캐스팅
        score_diff = scores.unsqueeze(1) - scores.unsqueeze(0)  # (N, N)
        
        # 실제 y 기준 라벨: y_i > y_j 이면 1, y_i < y_j 이면 -1, 같으면 0
        target_diff = targets.unsqueeze(1) - targets.unsqueeze(0)  # (N, N)
        
        # S_ij: 실제 순위 라벨
        # y_i > y_j → S_ij = 1 (i가 더 좋음)
        # y_i < y_j → S_ij = 0 (j가 더 좋음)
        # y_i = y_j → 비교 제외
        S_ij = (target_diff > 0).float()  # (N, N)
        
        # 유효한 쌍만 마스킹 (y_i != y_j)
        valid_pairs = (target_diff != 0)  # (N, N)
        
        # 대각선 제외 (자기 자신과의 비교)
        diag_mask = ~torch.eye(batch_size, dtype=torch.bool, device=scores.device)
        valid_pairs = valid_pairs & diag_mask
        
        if not valid_pairs.any():
            return torch.tensor(0.0, device=scores.device, requires_grad=True)
        
        # RankNet Loss 계산
        # L = -[S_ij * log(sigmoid(s_i - s_j)) + (1 - S_ij) * log(1 - sigmoid(s_i - s_j))]
        # = log(1 + exp(-(2*S_ij - 1) * sigma * (s_i - s_j)))
        
        # 더 안정적인 공식:
        # P_ij = sigmoid(sigma * (s_i - s_j))
        # Loss = -S_ij * log(P_ij) - (1-S_ij) * log(1-P_ij)
        #      = S_ij * log(1 + exp(-sigma*(s_i-s_j))) + (1-S_ij) * log(1 + exp(sigma*(s_i-s_j)))
        
        # 방향 조정: S_ij=1이면 s_i > s_j가 되어야 함
        # (2*S_ij - 1) = 1 if S_ij=1, -1 if S_ij=0
        direction = 2 * S_ij - 1  # (N, N)
        
        # 마진 적용
        scaled_diff = self.sigma * (score_diff - self.margin * direction)
        
        # Log-loss (numerically stable)
        # log(1 + exp(-x)) where x = direction * scaled_diff
        loss_matrix = F.softplus(-direction * scaled_diff)  # (N, N)
        
        # 유효한 쌍에 대해서만 평균
        loss = loss_matrix[valid_pairs].mean()
        
        return loss


class ListwiseLoss(nn.Module):
    """
    ListNet 스타일의 Listwise Ranking Loss (대안)
    
    Cross-entropy between predicted and actual probability distributions
    
    사용 방법:
    - 배치 내 모든 종목의 예측 점수를 정규화하여 확률 분포로 변환
    - 실제 y 값도 softmax로 변환하여 확률 분포 생성
    - KL Divergence 또는 Cross Entropy 계산
    
    장점:
    - Pairwise보다 메모리 효율적 (O(N) vs O(N^2))
    - 전체 리스트의 순서 학습
    
    Parameters
    ----------
    temperature : float, default=1.0
        Softmax 온도 파라미터
    """
    
    def __init__(self, temperature: float = 1.0):
        super(ListwiseLoss, self).__init__()
        self.temperature = temperature
    
    def forward(
        self, 
        scores: torch.Tensor, 
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Listwise Loss 계산
        
        Parameters
        ----------
        scores : Tensor
            모델 예측 점수 (batch_size, 1)
        targets : Tensor
            실제 타겟 y (batch_size, 1)
        
        Returns
        -------
        Tensor
            스칼라 손실값
        """
        scores = scores.squeeze(-1)
        targets = targets.squeeze(-1)
        
        # Softmax로 확률 분포 변환
        pred_probs = F.softmax(scores / self.temperature, dim=0)
        target_probs = F.softmax(targets / self.temperature, dim=0)
        
        # Cross Entropy Loss
        # L = -sum(target_probs * log(pred_probs))
        loss = -torch.sum(target_probs * torch.log(pred_probs + 1e-10))
        
        return loss


def calculate_rank_ic(
    predictions: np.ndarray, 
    actuals: np.ndarray
) -> float:
    """
    Rank IC (Information Coefficient) 계산
    
    예측 점수와 실제 수익률의 스피어만 순위 상관계수
    
    Parameters
    ----------
    predictions : ndarray
        모델 예측 점수 (N,)
    actuals : ndarray
        실제 타겟 y (N,)
    
    Returns
    -------
    float
        Rank IC (-1 ~ 1)
        
    Note
    ----
    목표: Rank IC >= 0.03 ~ 0.05 안정적 유지
    """
    if len(predictions) < 2:
        return 0.0
    
    # 스피어만 순위 상관계수
    rank_ic, p_value = spearmanr(predictions, actuals)
    
    if np.isnan(rank_ic):
        return 0.0
    
    return rank_ic


def calculate_ndcg(
    predictions: np.ndarray, 
    actuals: np.ndarray, 
    k: int | None = None
) -> float:
    """
    NDCG (Normalized Discounted Cumulative Gain) 계산
    
    상위 k개 종목의 순위 품질 평가
    
    Parameters
    ----------
    predictions : ndarray
        모델 예측 점수 (N,)
    actuals : ndarray
        실제 타겟 y (N,)
    k : int, optional
        상위 k개만 평가 (None이면 전체)
    
    Returns
    -------
    float
        NDCG (0 ~ 1)
    """
    if len(predictions) < 2:
        return 1.0
    
    n = len(predictions)
    if k is None:
        k = n
    k = min(k, n)
    
    # 예측 점수 기준 정렬된 인덱스
    pred_order = np.argsort(-predictions)  # 내림차순
    
    # DCG 계산
    # relevance = actual y values (높을수록 좋음)
    # DCG = sum(rel_i / log2(i + 2))
    dcg = 0.0
    for i in range(k):
        idx = pred_order[i]
        rel = actuals[idx]
        # 정규화를 위해 min-max 스케일링 적용
        dcg += rel / np.log2(i + 2)  # i=0 → log2(2)=1
    
    # Ideal DCG (실제 y 기준 최적 정렬)
    ideal_order = np.argsort(-actuals)
    idcg = 0.0
    for i in range(k):
        idx = ideal_order[i]
        rel = actuals[idx]
        idcg += rel / np.log2(i + 2)
    
    if idcg == 0:
        return 1.0
    
    return dcg / idcg


# ===========================================
# 테스트 및 사용 예시
# ===========================================
if __name__ == '__main__':
    """
    RankNet 모듈 테스트
    """
    print("="*60)
    print("RankNet 모듈 테스트")
    print("="*60)
    
    # 1. 모델 테스트
    print("\n[1] LinearRankNetModel 테스트")
    model = LinearRankNetModel(input_dim=3, output_dim=1)
    print(model)
    
    batch_size = 10
    x = torch.randn(batch_size, 3)
    scores = model(x)
    print(f"  입력: {x.shape} → 출력: {scores.shape}")
    
    # 2. RankNet Loss 테스트
    print("\n[2] RankNetLoss 테스트")
    criterion = RankNetLoss(sigma=1.0)
    
    scores = torch.randn(batch_size, 1, requires_grad=True)
    targets = torch.randn(batch_size, 1)
    
    loss = criterion(scores, targets)
    print(f"  Loss: {loss.item():.4f}")
    
    # Gradient 확인
    loss.backward()
    print(f"  Gradient 존재: {scores.grad is not None}")
    
    # 3. Rank IC 테스트
    print("\n[3] Rank IC 테스트")
    pred = np.array([0.8, 0.6, 0.9, 0.4, 0.7])
    actual = np.array([0.7, 0.5, 0.95, 0.3, 0.65])
    
    rank_ic = calculate_rank_ic(pred, actual)
    print(f"  Rank IC: {rank_ic:.4f}")
    
    # 4. NDCG 테스트
    print("\n[4] NDCG 테스트")
    ndcg = calculate_ndcg(pred, actual, k=3)
    print(f"  NDCG@3: {ndcg:.4f}")
    
    print("\n" + "="*60)
    print("✅ RankNet 모듈 테스트 완료")
    print("="*60)
