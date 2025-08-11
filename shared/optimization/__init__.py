"""
Optimization library for portfolio management.
LLMs define objectives and constraints, scripts perform mechanical optimization.
"""

from .multi_period import MultiPeriodOptimizer
from .views_entropy import ViewsEntropyPooling
from .quantum import QuantumOptimizer

__all__ = ['MultiPeriodOptimizer', 'ViewsEntropyPooling', 'QuantumOptimizer']