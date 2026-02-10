"""
feature_engineering/restatement.py - 하위 호환성 래퍼
실제 구현은 core/restatement.py에 있습니다.
"""

from core.restatement import (
    calculate_investment,
    calculate_amortization,
    calculate_adjusted_oi,
    restate_financials
)

__all__ = [
    'calculate_investment',
    'calculate_amortization',
    'calculate_adjusted_oi',
    'restate_financials'
]
