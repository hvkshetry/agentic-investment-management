#!/usr/bin/env python3
"""
Strategy definitions for backtesting.
These are mechanical implementations - strategy selection done by agents.
"""

import bt
from typing import Dict, List, Any


class StrategyLibrary:
    """
    Library of mechanical strategy implementations.
    Agents decide which strategy to use and when.
    """
    
    @staticmethod
    def buy_and_hold(weights: Dict[str, float]) -> List[bt.Algo]:
        """
        Simple buy and hold strategy with initial weights.
        
        Args:
            weights: Initial portfolio weights
            
        Returns:
            List of bt algos for the strategy
        """
        return [
            bt.algos.RunOnce(),
            bt.algos.SelectAll(),
            bt.algos.WeighTarget(weights),
            bt.algos.Rebalance()
        ]
    
    @staticmethod
    def periodic_rebalance(weights: Dict[str, float], 
                          frequency: str = 'monthly') -> List[bt.Algo]:
        """
        Rebalance to target weights periodically.
        
        Args:
            weights: Target portfolio weights
            frequency: Rebalancing frequency
            
        Returns:
            List of bt algos for the strategy
        """
        freq_map = {
            'daily': bt.algos.RunDaily(),
            'weekly': bt.algos.RunWeekly(),
            'monthly': bt.algos.RunMonthly(),
            'quarterly': bt.algos.RunQuarterly(),
            'yearly': bt.algos.RunYearly()
        }
        
        return [
            freq_map.get(frequency, bt.algos.RunMonthly()),
            bt.algos.SelectAll(),
            bt.algos.WeighTarget(weights),
            bt.algos.Rebalance()
        ]
    
    @staticmethod
    def momentum(lookback: int = 60, n_select: int = 10) -> List[bt.Algo]:
        """
        Momentum strategy - select top performing assets.
        
        Args:
            lookback: Days to look back for momentum
            n_select: Number of top assets to select
            
        Returns:
            List of bt algos for the strategy
        """
        return [
            bt.algos.RunMonthly(),
            bt.algos.SelectAll(),
            bt.algos.SelectMomentum(n_select, lookback=lookback),
            bt.algos.WeighEqually(),
            bt.algos.Rebalance()
        ]
    
    @staticmethod
    def mean_reversion(lookback: int = 60, n_select: int = 10) -> List[bt.Algo]:
        """
        Mean reversion strategy - select worst performing assets.
        
        Args:
            lookback: Days to look back
            n_select: Number of bottom assets to select
            
        Returns:
            List of bt algos for the strategy
        """
        return [
            bt.algos.RunMonthly(),
            bt.algos.SelectAll(),
            bt.algos.SelectMomentum(n_select, lookback=lookback, lag=1, sort_descending=False),
            bt.algos.WeighEqually(),
            bt.algos.Rebalance()
        ]
    
    @staticmethod
    def risk_parity() -> List[bt.Algo]:
        """
        Risk parity strategy - equal risk contribution.
        
        Returns:
            List of bt algos for the strategy
        """
        return [
            bt.algos.RunMonthly(),
            bt.algos.SelectAll(),
            bt.algos.WeighInvVol(),  # Weight inversely to volatility
            bt.algos.Rebalance()
        ]
    
    @staticmethod
    def equal_weight() -> List[bt.Algo]:
        """
        Equal weight strategy.
        
        Returns:
            List of bt algos for the strategy
        """
        return [
            bt.algos.RunMonthly(),
            bt.algos.SelectAll(),
            bt.algos.WeighEqually(),
            bt.algos.Rebalance()
        ]
    
    @staticmethod
    def create_custom_strategy(algos: List[bt.Algo]) -> List[bt.Algo]:
        """
        Create a custom strategy from a list of algos.
        Used when agents define specific strategy rules.
        
        Args:
            algos: List of bt.Algo objects
            
        Returns:
            The list of algos (for consistency)
        """
        return algos