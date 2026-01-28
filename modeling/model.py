"""
===========================================
PyTorch 선형 모델 (PBR 예측)
===========================================

이 파일의 역할:
- 3개 피처(m1, m2, m3)로 y = ln(PBR)을 예측하는 선형 모델
- 1-layer Linear Neural Network
- MSE Loss, Adam Optimizer

모델 구조:
Input: [m1, m2, m3] (3차원)
Output: yhat = w1·m1 + w2·m2 + w3·m3 + b (1차원)

특징:
- 단순하지만 해석 가능 (가중치 의미 명확)
- 빠른 학습 (파라미터 4개)
- 과적합 위험 낮음
"""

import torch
import torch.nn as nn


class LinearPBRModel(nn.Module):
    """
    PBR 예측 선형 모델
    
    y = w1·m1 + w2·m2 + w3·m3 + b
    
    Parameters
    ----------
    input_dim : int, default=3
        입력 차원 (m1, m2, m3)
    output_dim : int, default=1
        출력 차원 (yhat)
    """
    
    def __init__(self, input_dim: int = 3, output_dim: int = 1):
        super(LinearPBRModel, self).__init__()
        
        # 선형 레이어 (3 → 1)
        # bias=True: 절편 포함
        self.linear = nn.Linear(input_dim, output_dim, bias=True)
        
        # 초기화: Xavier uniform (기본값)
        # 작은 모델이므로 초기화가 중요
        nn.init.xavier_uniform_(self.linear.weight)
        nn.init.zeros_(self.linear.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass
        
        Parameters
        ----------
        x : Tensor
            입력 텐서 (batch_size, 3)
        
        Returns
        -------
        Tensor
            출력 텐서 (batch_size, 1)
        """
        # 단순 선형 변환
        # 활성화 함수 없음 (회귀 문제)
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
            'w1': weights[0],  # m1 가중치
            'w2': weights[1],  # m2 가중치
            'w3': weights[2],  # m3 가중치
            'b': bias          # 절편
        }
    
    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """
        예측 (평가 모드)
        
        Parameters
        ----------
        x : Tensor
            입력 텐서 (batch_size, 3)
        
        Returns
        -------
        Tensor
            예측 텐서 (batch_size, 1)
        """
        self.eval()
        with torch.no_grad():
            return self.forward(x)


# ===========================================
# 사용 예시 및 테스트
# ===========================================
if __name__ == '__main__':
    """
    모델 구조 확인
    """
    print("="*60)
    print("LinearPBRModel 테스트")
    print("="*60)
    
    # 모델 생성
    model = LinearPBRModel(input_dim=3, output_dim=1)
    print(f"\n[모델 구조]")
    print(model)
    
    # 파라미터 개수
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\n[파라미터 개수]")
    print(f"  Total: {total_params} (3 weights + 1 bias)")
    
    # 더미 입력
    batch_size = 10
    x = torch.randn(batch_size, 3)
    
    # Forward pass
    print(f"\n[Forward Pass]")
    print(f"  입력 형상: {x.shape}")
    y = model(x)
    print(f"  출력 형상: {y.shape}")
    
    # 가중치 확인
    weights = model.get_weights()
    print(f"\n[초기 가중치]")
    for key, val in weights.items():
        print(f"  {key}: {val:.4f}")
    
    print("\n" + "="*60)
    print("✅ 모델 테스트 완료")
    print("="*60)
