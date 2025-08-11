#!/usr/bin/env python3
"""
Validation metrics calculation.
Pure mechanical calculation - interpretation by agents.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ValidationMetrics:
    """
    Calculate validation metrics for strategy performance.
    """
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calculate annualized Sharpe ratio.
        
        Args:
            returns: Daily returns
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Annualized Sharpe ratio
        """
        excess_returns = returns - risk_free_rate / 252
        return float(np.sqrt(252) * excess_returns.mean() / excess_returns.std())
    
    @staticmethod
    def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino ratio (downside deviation).
        
        Args:
            returns: Daily returns
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sortino ratio
        """
        excess_returns = returns - risk_free_rate / 252
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_dev = np.sqrt(252) * downside_returns.std()
        return float(np.sqrt(252) * excess_returns.mean() / downside_dev)
    
    @staticmethod
    def calculate_max_drawdown(returns: pd.Series) -> float:
        """
        Calculate maximum drawdown.
        
        Args:
            returns: Daily returns
            
        Returns:
            Maximum drawdown (negative value)
        """
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return float(drawdown.min())
    
    @staticmethod
    def calculate_calmar_ratio(returns: pd.Series) -> float:
        """
        Calculate Calmar ratio (return / max drawdown).
        
        Args:
            returns: Daily returns
            
        Returns:
            Calmar ratio
        """
        annual_return = returns.mean() * 252
        max_dd = ValidationMetrics.calculate_max_drawdown(returns)
        
        if max_dd == 0:
            return float('inf')
        
        return float(annual_return / abs(max_dd))
    
    @staticmethod
    def calculate_information_ratio(returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """
        Calculate information ratio.
        
        Args:
            returns: Strategy returns
            benchmark_returns: Benchmark returns
            
        Returns:
            Information ratio
        """
        active_returns = returns - benchmark_returns
        if active_returns.std() == 0:
            return 0.0
        
        return float(np.sqrt(252) * active_returns.mean() / active_returns.std())
    
    @staticmethod
    def calculate_turnover(weights_history: pd.DataFrame) -> float:
        """
        Calculate average portfolio turnover.
        
        Args:
            weights_history: DataFrame with weight history
            
        Returns:
            Average turnover
        """
        weight_changes = weights_history.diff().abs().sum(axis=1)
        return float(weight_changes.mean())
    
    @staticmethod
    def stability_of_returns(returns: pd.Series) -> float:
        """
        Calculate R-squared of returns vs time (stability metric).
        
        Args:
            returns: Daily returns
            
        Returns:
            R-squared value (0-1)
        """
        cumulative_returns = (1 + returns).cumprod()
        log_returns = np.log(cumulative_returns)
        
        # Fit linear regression
        x = np.arange(len(log_returns))
        
        # Handle edge cases
        if len(x) < 2:
            return 0.0
        
        # Calculate R-squared
        correlation = np.corrcoef(x, log_returns)[0, 1]
        return float(correlation ** 2)
    
    @staticmethod
    def calculate_all_metrics(returns: pd.Series, 
                             benchmark_returns: Optional[pd.Series] = None,
                             risk_free_rate: float = 0.02) -> Dict[str, float]:
        """
        Calculate all validation metrics.
        
        Args:
            returns: Strategy returns
            benchmark_returns: Optional benchmark returns
            risk_free_rate: Risk-free rate
            
        Returns:
            Dictionary of all metrics
        """
        metrics = {
            'annual_return': float(returns.mean() * 252),
            'annual_volatility': float(returns.std() * np.sqrt(252)),
            'sharpe_ratio': ValidationMetrics.calculate_sharpe_ratio(returns, risk_free_rate),
            'sortino_ratio': ValidationMetrics.calculate_sortino_ratio(returns, risk_free_rate),
            'max_drawdown': ValidationMetrics.calculate_max_drawdown(returns),
            'calmar_ratio': ValidationMetrics.calculate_calmar_ratio(returns),
            'stability': ValidationMetrics.stability_of_returns(returns)
        }
        
        if benchmark_returns is not None:
            metrics['information_ratio'] = ValidationMetrics.calculate_information_ratio(
                returns, benchmark_returns
            )
        
        return metrics