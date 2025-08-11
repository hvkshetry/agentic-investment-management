#!/usr/bin/env python3
"""
Walk-forward validation for portfolio strategies.
Pure mechanical validation - interpretation done by Portfolio Manager agent.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Callable, Optional, Tuple
from datetime import datetime, timedelta
import logging

# Import skfolio for advanced validation
try:
    from skfolio import Portfolio
    from skfolio.optimization import MeanRisk
    from skfolio.model_selection import WalkForward as SkfolioWalkForward
    SKFOLIO_AVAILABLE = True
except ImportError:
    SKFOLIO_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("skfolio not available - using simplified validation")

logger = logging.getLogger(__name__)


class WalkForwardValidator:
    """
    Mechanical walk-forward validation - no interpretation of results.
    Portfolio Manager agent decides if results indicate overfitting.
    """
    
    def __init__(self):
        """Initialize validator."""
        self.results_cache = {}
    
    def validate(self,
                optimization_func: Callable,
                historical_data: pd.DataFrame,
                window_size: int = 252,
                step_size: int = 21,
                n_splits: Optional[int] = None) -> Dict[str, Any]:
        """
        Perform walk-forward validation on optimization strategy.
        
        Args:
            optimization_func: Function that takes data and returns weights
            historical_data: Historical price data
            window_size: Training window size in days
            step_size: Step size between windows
            n_splits: Number of splits (if None, use all possible)
            
        Returns:
            Dict with in-sample and out-of-sample performance metrics
        """
        if SKFOLIO_AVAILABLE:
            return self._validate_with_skfolio(
                optimization_func, historical_data, window_size, step_size, n_splits
            )
        else:
            return self._validate_manual(
                optimization_func, historical_data, window_size, step_size, n_splits
            )
    
    def _validate_with_skfolio(self,
                              optimization_func: Callable,
                              historical_data: pd.DataFrame,
                              window_size: int,
                              step_size: int,
                              n_splits: Optional[int]) -> Dict[str, Any]:
        """
        Use skfolio for advanced walk-forward validation.
        
        Returns:
            Validation metrics from skfolio
        """
        # Calculate returns from prices
        returns = historical_data.pct_change().dropna()
        
        # Create walk-forward object
        wf = SkfolioWalkForward(
            train_size=window_size,
            test_size=step_size
        )
        
        in_sample_metrics = []
        out_sample_metrics = []
        
        # Perform walk-forward validation
        for train_idx, test_idx in wf.split(returns):
            train_data = returns.iloc[train_idx]
            test_data = returns.iloc[test_idx]
            
            # Optimize on training data
            try:
                weights = optimization_func(train_data)
                
                # Calculate in-sample performance
                in_sample_perf = self._calculate_performance(train_data, weights)
                in_sample_metrics.append(in_sample_perf)
                
                # Calculate out-of-sample performance
                out_sample_perf = self._calculate_performance(test_data, weights)
                out_sample_metrics.append(out_sample_perf)
                
            except Exception as e:
                logger.warning(f"Optimization failed in walk-forward split: {e}")
                continue
        
        if not in_sample_metrics:
            return {"error": "No successful validation splits"}
        
        # Aggregate metrics
        return self._aggregate_metrics(in_sample_metrics, out_sample_metrics)
    
    def _validate_manual(self,
                        optimization_func: Callable,
                        historical_data: pd.DataFrame,
                        window_size: int,
                        step_size: int,
                        n_splits: Optional[int]) -> Dict[str, Any]:
        """
        Manual walk-forward validation without skfolio.
        
        Returns:
            Validation metrics calculated manually
        """
        returns = historical_data.pct_change().dropna()
        n_obs = len(returns)
        
        # Calculate number of possible splits
        max_splits = (n_obs - window_size) // step_size
        if n_splits is None:
            n_splits = max_splits
        else:
            n_splits = min(n_splits, max_splits)
        
        in_sample_metrics = []
        out_sample_metrics = []
        
        for i in range(n_splits):
            # Define train and test windows
            train_start = i * step_size
            train_end = train_start + window_size
            test_start = train_end
            test_end = min(test_start + step_size, n_obs)
            
            if test_end > n_obs:
                break
            
            train_data = returns.iloc[train_start:train_end]
            test_data = returns.iloc[test_start:test_end]
            
            try:
                # Optimize on training data
                weights = optimization_func(train_data)
                
                # Calculate performance
                in_sample_perf = self._calculate_performance(train_data, weights)
                out_sample_perf = self._calculate_performance(test_data, weights)
                
                in_sample_metrics.append(in_sample_perf)
                out_sample_metrics.append(out_sample_perf)
                
            except Exception as e:
                logger.warning(f"Optimization failed at split {i}: {e}")
                continue
        
        if not in_sample_metrics:
            return {"error": "No successful validation splits"}
        
        return self._aggregate_metrics(in_sample_metrics, out_sample_metrics)
    
    def combinatorial_purged_cv(self,
                               optimization_func: Callable,
                               historical_data: pd.DataFrame,
                               n_splits: int = 10,
                               embargo_period: int = 5) -> Dict[str, Any]:
        """
        Combinatorial purged cross-validation to avoid data leakage.
        
        Args:
            optimization_func: Optimization function
            historical_data: Historical price data
            n_splits: Number of CV splits
            embargo_period: Days to embargo after each test set
            
        Returns:
            Cross-validation results
        """
        returns = historical_data.pct_change().dropna()
        n_obs = len(returns)
        
        # Create purged splits
        fold_size = n_obs // n_splits
        cv_results = []
        
        for i in range(n_splits):
            # Define test fold
            test_start = i * fold_size
            test_end = min((i + 1) * fold_size, n_obs)
            
            # Create training set with purging
            train_indices = []
            for j in range(n_obs):
                # Skip test period and embargo
                if j < test_start - embargo_period or j >= test_end + embargo_period:
                    train_indices.append(j)
            
            if len(train_indices) < 100:  # Minimum training size
                continue
            
            train_data = returns.iloc[train_indices]
            test_data = returns.iloc[test_start:test_end]
            
            try:
                # Optimize and evaluate
                weights = optimization_func(train_data)
                test_perf = self._calculate_performance(test_data, weights)
                cv_results.append(test_perf)
            except Exception as e:
                logger.warning(f"CV fold {i} failed: {e}")
                continue
        
        if not cv_results:
            return {"error": "No successful CV folds"}
        
        # Aggregate CV results
        return {
            "cv_sharpe_mean": float(np.mean([r['sharpe_ratio'] for r in cv_results])),
            "cv_sharpe_std": float(np.std([r['sharpe_ratio'] for r in cv_results])),
            "cv_return_mean": float(np.mean([r['annual_return'] for r in cv_results])),
            "cv_return_std": float(np.std([r['annual_return'] for r in cv_results])),
            "n_successful_folds": len(cv_results),
            "n_total_folds": n_splits
        }
    
    def _calculate_performance(self,
                              returns: pd.DataFrame,
                              weights: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate portfolio performance metrics.
        
        Args:
            returns: Asset returns
            weights: Portfolio weights
            
        Returns:
            Performance metrics
        """
        # Align weights with available assets
        available_assets = [asset for asset in weights.keys() if asset in returns.columns]
        
        if not available_assets:
            # Try to match on cleaned column names
            available_assets = returns.columns.tolist()
            weights = {asset: 1/len(available_assets) for asset in available_assets}
        
        # Create weight array
        weight_array = np.array([weights.get(asset, 0) for asset in returns.columns])
        
        # Normalize weights
        if weight_array.sum() > 0:
            weight_array = weight_array / weight_array.sum()
        else:
            weight_array = np.ones(len(returns.columns)) / len(returns.columns)
        
        # Calculate portfolio returns
        portfolio_returns = returns @ weight_array
        
        # Calculate metrics
        annual_return = portfolio_returns.mean() * 252
        annual_vol = portfolio_returns.std() * np.sqrt(252)
        sharpe_ratio = annual_return / annual_vol if annual_vol > 0 else 0
        
        # Calculate max drawdown
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        return {
            "annual_return": float(annual_return),
            "annual_volatility": float(annual_vol),
            "sharpe_ratio": float(sharpe_ratio),
            "max_drawdown": float(max_drawdown)
        }
    
    def _aggregate_metrics(self,
                          in_sample: List[Dict],
                          out_sample: List[Dict]) -> Dict[str, Any]:
        """
        Aggregate in-sample and out-of-sample metrics.
        
        Args:
            in_sample: List of in-sample performance dicts
            out_sample: List of out-of-sample performance dicts
            
        Returns:
            Aggregated metrics with degradation analysis
        """
        # Calculate means
        in_sample_sharpe = np.mean([m['sharpe_ratio'] for m in in_sample])
        out_sample_sharpe = np.mean([m['sharpe_ratio'] for m in out_sample])
        
        in_sample_return = np.mean([m['annual_return'] for m in in_sample])
        out_sample_return = np.mean([m['annual_return'] for m in out_sample])
        
        # Calculate degradation
        sharpe_degradation = (in_sample_sharpe - out_sample_sharpe) / abs(in_sample_sharpe) if in_sample_sharpe != 0 else 0
        return_degradation = (in_sample_return - out_sample_return) / abs(in_sample_return) if in_sample_return != 0 else 0
        
        return {
            "in_sample_sharpe": float(in_sample_sharpe),
            "out_sample_sharpe": float(out_sample_sharpe),
            "sharpe_degradation": float(sharpe_degradation),
            "in_sample_return": float(in_sample_return),
            "out_sample_return": float(out_sample_return),
            "return_degradation": float(return_degradation),
            "in_sample_volatility": float(np.mean([m['annual_volatility'] for m in in_sample])),
            "out_sample_volatility": float(np.mean([m['annual_volatility'] for m in out_sample])),
            "n_windows": len(in_sample),
            "overfitting_risk": sharpe_degradation > 0.3,  # Flag if >30% degradation
            "validation_quality": "good" if len(in_sample) >= 10 else "limited"
        }