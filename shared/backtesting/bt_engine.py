#!/usr/bin/env python3
"""
Backtesting Engine - Pure mechanical execution using bt library.
No interpretation or period selection - just execution on specified periods.
"""

import bt
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Mechanical backtesting engine - executes strategies on specified periods.
    All interpretation and period selection done by LLM agents.
    """
    
    def __init__(self):
        """Initialize backtesting engine."""
        self.cache = {}  # Cache backtest results
    
    def run_backtest(self, strategy, weights, data, **kwargs):
        """
        Generic backtest runner for compatibility.
        
        Args:
            strategy: Strategy name
            weights: Portfolio weights
            data: Price data
            **kwargs: Additional parameters
            
        Returns:
            Backtest results
        """
        # Map to backtest_on_periods for compatibility
        periods = kwargs.get('periods', [
            {"period": "full", "start_date": str(data.index[0].date()), "end_date": str(data.index[-1].date())}
        ])
        
        return self.backtest_on_periods(
            strategy_weights=weights,
            historical_data=data,
            periods=periods,
            rebalance_freq=kwargs.get('rebalance_freq', 'monthly'),
            transaction_cost=kwargs.get('transaction_cost', 0.001)
        )
        
    def backtest_on_periods(self,
                           strategy_weights: Dict[str, float],
                           historical_data: pd.DataFrame,
                           periods: List[Dict[str, Any]],
                           rebalance_freq: str = 'monthly',
                           transaction_cost: float = 0.001) -> Dict[str, Any]:
        """
        Mechanically backtest strategy on specific periods identified by Macro Analyst.
        
        Args:
            strategy_weights: Target weights for each asset
            historical_data: Full historical price data
            periods: List of period dicts from Macro Analyst, e.g.:
                     [{"period": "1979-1981", "similarity_score": 0.85}, ...]
            rebalance_freq: Rebalancing frequency ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')
            transaction_cost: Transaction cost as percentage (0.001 = 0.1%)
            
        Returns:
            Dict with backtest results for each period
        """
        results = {}
        
        for period_info in periods:
            # Check if dates are provided directly
            start_date = period_info.get('start_date')
            end_date = period_info.get('end_date')
            period_str = period_info.get('period', '')
            
            # If dates not provided, parse period string
            if not start_date or not end_date:
                if not period_str:
                    logger.warning("No period or dates provided")
                    continue
                    
                # Parse period string (e.g., "1979-1981" or "2007-03 to 2008-11")
                try:
                    start_date, end_date = self._parse_period_string(period_str)
                except ValueError as e:
                    logger.warning(f"Could not parse period '{period_str}': {e}")
                    continue
            else:
                # Use dates directly, create period string for labeling
                if not period_str:
                    period_str = f"{start_date} to {end_date}"
            
            # Extract data for this period
            period_data = historical_data[start_date:end_date]
            
            if period_data.empty:
                logger.warning(f"No data available for period {period_str}")
                continue
            
            # Create bt strategy
            strategy = self._create_strategy(
                strategy_weights,
                rebalance_freq,
                transaction_cost
            )
            
            # Run backtest mechanically
            backtest = bt.Backtest(strategy, period_data)
            result = bt.run(backtest)
            
            # Extract key metrics
            results[period_str] = self._extract_metrics(result, backtest.name)
            
        return results
    
    def backtest_strategy(self,
                         strategy_weights: Dict[str, float],
                         historical_data: pd.DataFrame,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         rebalance_freq: str = 'monthly',
                         transaction_cost: float = 0.001,
                         benchmark: Optional[pd.Series] = None) -> Dict[str, Any]:
        """
        Run a single backtest over a specified period.
        
        Args:
            strategy_weights: Target portfolio weights
            historical_data: Historical price data
            start_date: Start date for backtest
            end_date: End date for backtest
            rebalance_freq: How often to rebalance
            transaction_cost: Cost per transaction
            benchmark: Optional benchmark series for comparison
            
        Returns:
            Backtest results with performance metrics
        """
        # Filter data to date range if specified
        if start_date:
            historical_data = historical_data[start_date:]
        if end_date:
            historical_data = historical_data[:end_date]
        
        # Create strategy
        strategy = self._create_strategy(
            strategy_weights,
            rebalance_freq,
            transaction_cost
        )
        
        # Create backtest
        backtest = bt.Backtest(strategy, historical_data)
        
        # Add benchmark if provided
        if benchmark is not None:
            benchmark_strategy = bt.Strategy('Benchmark', [bt.algos.RunOnce(),
                                                          bt.algos.SelectAll(),
                                                          bt.algos.WeighEqually(),
                                                          bt.algos.Rebalance()])
            benchmark_bt = bt.Backtest(benchmark_strategy, benchmark.to_frame())
            result = bt.run(backtest, benchmark_bt)
        else:
            result = bt.run(backtest)
        
        return self._extract_metrics(result, strategy.name)
    
    def calculate_historical_var(self,
                                strategy_weights: Dict[str, float],
                                similar_periods: List[Dict[str, Any]],
                                historical_data: pd.DataFrame,
                                confidence_level: float = 0.95) -> Dict[str, float]:
        """
        Calculate VaR based on performance in analogous historical periods.
        
        Args:
            strategy_weights: Portfolio weights
            similar_periods: Periods identified as similar by Macro Analyst
            historical_data: Historical price data
            confidence_level: VaR confidence level (e.g., 0.95 for 95% VaR)
            
        Returns:
            VaR metrics from historical analogous periods
        """
        all_returns = []
        
        for period_info in similar_periods:
            period_str = period_info.get('period', '')
            
            try:
                start_date, end_date = self._parse_period_string(period_str)
                period_data = historical_data[start_date:end_date]
                
                if not period_data.empty:
                    # Calculate portfolio returns for this period
                    portfolio_returns = self._calculate_portfolio_returns(
                        period_data,
                        strategy_weights
                    )
                    all_returns.extend(portfolio_returns.tolist())
            except Exception as e:
                logger.warning(f"Error processing period {period_str}: {e}")
                continue
        
        if not all_returns:
            return {"error": "No valid returns calculated from historical periods"}
        
        # Calculate VaR and CVaR
        returns_array = np.array(all_returns)
        var_threshold = np.percentile(returns_array, (1 - confidence_level) * 100)
        cvar = np.mean(returns_array[returns_array <= var_threshold])
        
        return {
            "var_95": float(var_threshold),
            "cvar_95": float(cvar),
            "worst_return": float(np.min(returns_array)),
            "best_return": float(np.max(returns_array)),
            "periods_analyzed": len(similar_periods),
            "total_observations": len(all_returns)
        }
    
    def _create_strategy(self,
                        weights: Dict[str, float],
                        rebalance_freq: str,
                        transaction_cost: float) -> bt.Strategy:
        """
        Create a bt Strategy object with specified parameters.
        
        Args:
            weights: Target weights for each asset
            rebalance_freq: Frequency of rebalancing
            transaction_cost: Transaction cost percentage
            
        Returns:
            bt.Strategy object
        """
        # Map frequency to bt algos
        freq_map = {
            'daily': bt.algos.RunDaily(),
            'weekly': bt.algos.RunWeekly(),
            'monthly': bt.algos.RunMonthly(),
            'quarterly': bt.algos.RunQuarterly(),
            'yearly': bt.algos.RunYearly()
        }
        
        run_algo = freq_map.get(rebalance_freq, bt.algos.RunMonthly())
        
        # Create strategy with target weights
        # bt expects a TargetMap for WeighTarget, not a dict
        strategy = bt.Strategy(
            'Portfolio',
            [
                run_algo,
                bt.algos.SelectAll(),
                bt.algos.WeighSpecified(**weights),  # Use WeighSpecified instead
                bt.algos.Rebalance()
            ]
        )
        
        return strategy
    
    def _parse_period_string(self, period_str: str) -> Tuple[str, str]:
        """
        Parse period string like "1979-1981" or "2007-03 to 2008-11".
        
        Args:
            period_str: Period string from Macro Analyst
            
        Returns:
            Tuple of (start_date, end_date) as strings
        """
        if not period_str:
            raise ValueError("Empty period string provided")
            
        period_str = period_str.strip()
        
        if not period_str:
            raise ValueError("Empty period string provided")
        
        # Handle "YYYY-YYYY" format
        if '-' in period_str and 'to' not in period_str:
            parts = period_str.split('-')
            if len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 4:
                return f"{parts[0]}-01-01", f"{parts[1]}-12-31"
        
        # Handle "YYYY-MM to YYYY-MM" format
        if ' to ' in period_str:
            start, end = period_str.split(' to ')
            return start.strip(), end.strip()
        
        # Handle "YYYY" format (single year)
        if len(period_str) == 4 and period_str.isdigit():
            return f"{period_str}-01-01", f"{period_str}-12-31"
        
        raise ValueError(f"Cannot parse period string: {period_str}")
    
    def _calculate_portfolio_returns(self,
                                    price_data: pd.DataFrame,
                                    weights: Dict[str, float]) -> np.ndarray:
        """
        Calculate portfolio returns from price data and weights.
        
        Args:
            price_data: DataFrame with asset prices
            weights: Portfolio weights
            
        Returns:
            Array of portfolio returns
        """
        # Calculate individual asset returns
        returns = price_data.pct_change().dropna()
        
        # Filter to assets we have weights for
        available_assets = [asset for asset in weights.keys() if asset in returns.columns]
        
        if not available_assets:
            raise ValueError("No matching assets between weights and price data")
        
        # Create weight array
        weight_array = np.array([weights.get(asset, 0) for asset in returns.columns])
        
        # Normalize weights
        weight_array = weight_array / weight_array.sum()
        
        # Calculate portfolio returns
        portfolio_returns = returns @ weight_array
        
        return portfolio_returns.values
    
    def _extract_metrics(self, bt_result: bt.backtest.Result, strategy_name: str) -> Dict[str, Any]:
        """
        Extract key metrics from bt backtest result.
        
        Args:
            bt_result: Result object from bt.run()
            strategy_name: Name of the strategy
            
        Returns:
            Dict with performance metrics
        """
        stats = bt_result[strategy_name]
        
        return {
            "total_return": float(stats.total_return),
            "annualized_return": float(stats.cagr),
            "volatility": float(stats.daily_vol * np.sqrt(252)),
            "sharpe_ratio": float(stats.daily_sharpe * np.sqrt(252)),
            "max_drawdown": float(stats.max_drawdown),
            "calmar_ratio": float(stats.calmar),
            "start_date": str(stats.start),
            "end_date": str(stats.end),
            "best_year": float(stats.yearly_returns.max()) if hasattr(stats, 'yearly_returns') else None,
            "worst_year": float(stats.yearly_returns.min()) if hasattr(stats, 'yearly_returns') else None
        }