"""
modeling/model_ranknet.py - 하위 호환성 래퍼
실제 구현은 core/models.py에 있습니다.
"""

from core.models import (
    LinearModel,
    RankNetLoss,
    compute_rank_ic,
    compute_ndcg
)

# 하위 호환성을 위한 alias
LinearRankNetModel = LinearModel

__all__ = [
    'LinearRankNetModel',
    'LinearModel',
    'RankNetLoss',
    'compute_rank_ic',
    'compute_ndcg'
]
