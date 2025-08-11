"""
Backtesting library for mechanical strategy execution.
LLMs provide strategy and period selection, scripts execute mechanically.
"""

from .bt_engine import BacktestEngine
from .strategies import StrategyLibrary

__all__ = ['BacktestEngine', 'StrategyLibrary']