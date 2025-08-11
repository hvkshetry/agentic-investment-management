#!/usr/bin/env python3
"""
Multi-period portfolio optimization with tax-aware rebalancing.
Pure mechanical optimization - interpretation by Portfolio Manager agent.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import logging

# Import CVXPortfolio for multi-period optimization
try:
    import cvxportfolio as cvx
    CVXPORTFOLIO_AVAILABLE = True
except ImportError:
    CVXPORTFOLIO_AVAILABLE = False
    logging.warning("CVXPortfolio not available - using simplified multi-period optimization")

logger = logging.getLogger(__name__)


class MultiPeriodOptimizer:
    """
    Multi-period optimization with transaction costs and tax considerations.
    Mechanical execution - Portfolio Manager interprets results.
    """
    
    def __init__(self, tax_rates: Optional[Dict[str, float]] = None):
        """
        Initialize multi-period optimizer.
        
        Args:
            tax_rates: Dict with 'short_term' and 'long_term' capital gains rates
        """
        self.tax_rates = tax_rates or {
            'short_term': 0.37,  # Default to top bracket
            'long_term': 0.20
        }
    
    def optimize_trajectory(self,
                           initial_holdings: Dict[str, float],
                           expected_returns: pd.DataFrame,
                           covariance: pd.DataFrame,
                           horizon: int = 252,
                           rebalance_freq: int = 21,
                           transaction_cost: float = 0.001,
                           holding_cost: float = 0.0001) -> Dict[str, Any]:
        """
        Optimize portfolio trajectory over multiple periods.
        
        Args:
            initial_holdings: Current portfolio holdings (shares, not weights)
            expected_returns: Expected returns for each asset
            covariance: Covariance matrix
            horizon: Investment horizon in days
            rebalance_freq: Days between rebalancing
            transaction_cost: Transaction cost as fraction
            holding_cost: Holding cost per period
            
        Returns:
            Dict with optimal trading schedule and expected performance
        """
        if CVXPORTFOLIO_AVAILABLE:
            return self._optimize_with_cvx(
                initial_holdings, expected_returns, covariance,
                horizon, rebalance_freq, transaction_cost, holding_cost
            )
        else:
            return self._optimize_simplified(
                initial_holdings, expected_returns, covariance,
                horizon, rebalance_freq, transaction_cost
            )
    
    def _optimize_with_cvx(self,
                          initial_holdings: Dict[str, float],
                          expected_returns: pd.DataFrame,
                          covariance: pd.DataFrame,
                          horizon: int,
                          rebalance_freq: int,
                          transaction_cost: float,
                          holding_cost: float) -> Dict[str, Any]:
        """
        Use CVXPortfolio for sophisticated multi-period optimization.
        
        Returns:
            Optimization results with trading schedule
        """
        # Convert to CVXPortfolio format
        assets = list(expected_returns.index)
        n_periods = horizon // rebalance_freq
        
        # Create return forecast
        return_forecast = cvx.ReturnsForecast(expected_returns)
        
        # Create risk model
        risk_model = cvx.FullCovariance(covariance)
        
        # Transaction cost model
        tcost_model = cvx.TransactionCost(
            a=transaction_cost,  # Linear cost
            b=0.0  # No market impact for simplicity
        )
        
        # Holding cost model
        hcost_model = cvx.HoldingCost(holding_cost)
        
        # Create optimization policy
        # Maximize risk-adjusted returns minus costs
        objective = return_forecast - 0.5 * risk_model - tcost_model - hcost_model
        
        # Constraints
        constraints = [
            cvx.LongOnly(),  # No short selling
            cvx.LeverageLimit(1.0)  # Fully invested
        ]
        
        # Create policy
        policy = cvx.SinglePeriodOptimization(
            objective=objective,
            constraints=constraints
        )
        
        # Simulate optimal trajectory
        initial_portfolio = pd.Series(initial_holdings, index=assets).fillna(0)
        
        # Generate trading schedule
        trading_schedule = []
        current_holdings = initial_portfolio.copy()
        
        for period in range(n_periods):
            # Get optimal trades for this period
            # Note: Simplified simulation - in practice would use full CVXPortfolio simulator
            target_weights = self._get_target_weights_cvx(
                current_holdings, expected_returns, covariance
            )
            
            trades = self._calculate_trades(current_holdings, target_weights)
            trading_schedule.append({
                'period': period * rebalance_freq,
                'trades': trades,
                'target_weights': target_weights
            })
            
            # Update holdings (simplified)
            current_holdings = self._update_holdings(current_holdings, trades)
        
        return {
            'trading_schedule': trading_schedule,
            'n_rebalances': n_periods,
            'estimated_turnover': self._estimate_turnover(trading_schedule),
            'estimated_tax_impact': self._estimate_tax_impact(trading_schedule),
            'optimization_method': 'cvxportfolio'
        }
    
    def _optimize_simplified(self,
                           initial_holdings: Dict[str, float],
                           expected_returns: pd.DataFrame,
                           covariance: pd.DataFrame,
                           horizon: int,
                           rebalance_freq: int,
                           transaction_cost: float) -> Dict[str, Any]:
        """
        Simplified multi-period optimization without CVXPortfolio.
        
        Returns:
            Simplified optimization results
        """
        n_periods = horizon // rebalance_freq
        assets = list(expected_returns.index)
        
        # Convert holdings to weights
        total_value = sum(initial_holdings.values())
        if total_value == 0:
            current_weights = {asset: 1/len(assets) for asset in assets}
        else:
            current_weights = {
                asset: initial_holdings.get(asset, 0) / total_value 
                for asset in assets
            }
        
        trading_schedule = []
        
        for period in range(n_periods):
            # Simple mean-variance optimization for each period
            target_weights = self._mean_variance_weights(
                expected_returns, covariance
            )
            
            # Calculate trades needed
            trades = {}
            for asset in assets:
                current = current_weights.get(asset, 0)
                target = target_weights.get(asset, 0)
                trades[asset] = target - current
            
            # Apply transaction cost penalty
            trade_cost = sum(abs(trade) for trade in trades.values()) * transaction_cost
            
            trading_schedule.append({
                'period': period * rebalance_freq,
                'trades': trades,
                'target_weights': target_weights,
                'transaction_cost': trade_cost
            })
            
            # Update current weights
            current_weights = target_weights.copy()
        
        return {
            'trading_schedule': trading_schedule,
            'n_rebalances': n_periods,
            'estimated_turnover': self._estimate_turnover(trading_schedule),
            'estimated_tax_impact': self._estimate_tax_impact(trading_schedule),
            'total_transaction_costs': sum(s.get('transaction_cost', 0) for s in trading_schedule),
            'optimization_method': 'simplified'
        }
    
    def tax_aware_rebalance(self,
                           current_holdings: Dict[str, Tuple[float, pd.Timestamp]],
                           target_weights: Dict[str, float],
                           current_prices: Dict[str, float],
                           cost_basis: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate tax-aware rebalancing trades.
        
        Args:
            current_holdings: Dict of (shares, purchase_date) tuples
            target_weights: Target portfolio weights
            current_prices: Current asset prices
            cost_basis: Cost basis for each position
            
        Returns:
            Tax-optimized trading plan
        """
        # Calculate current values
        current_values = {
            asset: holdings[0] * current_prices.get(asset, 1.0)
            for asset, holdings in current_holdings.items()
        }
        total_value = sum(current_values.values())
        
        # Calculate target values
        target_values = {
            asset: weight * total_value
            for asset, weight in target_weights.items()
        }
        
        trades = {}
        tax_impact = {}
        
        for asset in set(list(current_holdings.keys()) + list(target_weights.keys())):
            current_val = current_values.get(asset, 0)
            target_val = target_values.get(asset, 0)
            trade_value = target_val - current_val
            
            if abs(trade_value) < 0.001 * total_value:  # Skip tiny trades
                continue
            
            # Calculate tax impact if selling
            if trade_value < 0:  # Selling
                shares, purchase_date = current_holdings.get(asset, (0, pd.Timestamp.now()))
                holding_period = (pd.Timestamp.now() - purchase_date).days
                
                # Determine tax rate
                if holding_period > 365:
                    tax_rate = self.tax_rates['long_term']
                else:
                    tax_rate = self.tax_rates['short_term']
                
                # Calculate gain/loss
                current_price = current_prices.get(asset, 1.0)
                basis = cost_basis.get(asset, current_price)
                gain_per_share = current_price - basis
                shares_to_sell = abs(trade_value) / current_price
                
                tax_due = max(0, gain_per_share * shares_to_sell * tax_rate)
                tax_impact[asset] = {
                    'tax_due': tax_due,
                    'holding_period': holding_period,
                    'tax_rate': tax_rate,
                    'realized_gain': gain_per_share * shares_to_sell
                }
            
            trades[asset] = trade_value / current_prices.get(asset, 1.0)  # Convert to shares
        
        # Tax loss harvesting opportunities
        loss_harvest_candidates = [
            asset for asset, impact in tax_impact.items()
            if impact['realized_gain'] < 0
        ]
        
        return {
            'trades': trades,
            'tax_impact': tax_impact,
            'total_tax_due': sum(impact['tax_due'] for impact in tax_impact.values()),
            'loss_harvest_candidates': loss_harvest_candidates,
            'tax_efficiency_score': self._calculate_tax_efficiency(trades, tax_impact)
        }
    
    def dynamic_rebalancing_schedule(self,
                                    volatility: pd.Series,
                                    correlation: pd.DataFrame,
                                    market_regime: str = 'normal') -> Dict[str, Any]:
        """
        Generate dynamic rebalancing schedule based on market conditions.
        
        Args:
            volatility: Asset volatility time series
            correlation: Correlation matrix
            market_regime: Current market regime (from Macro Analyst)
            
        Returns:
            Dynamic rebalancing schedule
        """
        # Base rebalancing frequency
        base_freq = {
            'crisis': 5,  # Daily monitoring in crisis
            'volatile': 10,  # Bi-weekly in volatile markets
            'normal': 21,  # Monthly in normal markets
            'calm': 63  # Quarterly in calm markets
        }
        
        # Adjust based on volatility percentile
        current_vol = volatility.iloc[-1] if isinstance(volatility, pd.Series) else volatility
        vol_percentile = volatility.rank(pct=True).iloc[-1] if isinstance(volatility, pd.Series) else 0.5
        
        # Calculate correlation instability
        if len(correlation) > 1:
            correlation_stability = 1 - correlation.std().mean()
        else:
            correlation_stability = 1.0
        
        # Determine rebalancing frequency
        base = base_freq.get(market_regime, 21)
        
        # Adjust for volatility
        if vol_percentile > 0.8:  # High volatility
            frequency = max(5, base // 2)
        elif vol_percentile < 0.2:  # Low volatility
            frequency = min(63, base * 2)
        else:
            frequency = base
        
        # Rebalancing triggers
        triggers = {
            'calendar': frequency,
            'volatility_spike': vol_percentile > 0.9,
            'correlation_break': correlation_stability < 0.7,
            'drift_threshold': 0.1,  # 10% drift from target
            'tax_loss_harvest': True  # Always check for tax loss opportunities
        }
        
        return {
            'rebalance_frequency_days': frequency,
            'triggers': triggers,
            'market_regime': market_regime,
            'volatility_percentile': float(vol_percentile),
            'correlation_stability': float(correlation_stability),
            'recommended_action': self._get_rebalancing_recommendation(
                frequency, vol_percentile, market_regime
            )
        }
    
    def _mean_variance_weights(self,
                              expected_returns: pd.DataFrame,
                              covariance: pd.DataFrame,
                              risk_aversion: float = 1.0) -> Dict[str, float]:
        """
        Calculate mean-variance optimal weights.
        
        Args:
            expected_returns: Expected returns
            covariance: Covariance matrix
            risk_aversion: Risk aversion parameter
            
        Returns:
            Optimal weights
        """
        try:
            # Convert to numpy arrays
            mu = expected_returns.values.flatten()
            sigma = covariance.values
            
            # Number of assets
            n = len(mu)
            
            # Solve for optimal weights (simplified - no constraints)
            # w = (1/gamma) * inv(Sigma) * mu
            sigma_inv = np.linalg.inv(sigma + 1e-8 * np.eye(n))  # Regularization
            raw_weights = sigma_inv @ mu / risk_aversion
            
            # Normalize to sum to 1 and enforce long-only
            weights = np.maximum(raw_weights, 0)
            weights = weights / weights.sum() if weights.sum() > 0 else np.ones(n) / n
            
            # Convert back to dict
            assets = list(expected_returns.index)
            return {assets[i]: float(weights[i]) for i in range(n)}
            
        except Exception as e:
            logger.warning(f"Mean-variance optimization failed: {e}")
            # Return equal weights as fallback
            n = len(expected_returns)
            return {asset: 1/n for asset in expected_returns.index}
    
    def _get_target_weights_cvx(self,
                               holdings: pd.Series,
                               expected_returns: pd.DataFrame,
                               covariance: pd.DataFrame) -> Dict[str, float]:
        """
        Get target weights using CVXPortfolio optimization.
        
        Returns:
            Target weights
        """
        # For now, use mean-variance as approximation
        return self._mean_variance_weights(expected_returns, covariance)
    
    def _calculate_trades(self,
                         current_holdings: pd.Series,
                         target_weights: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate trades needed to reach target weights.
        
        Returns:
            Trade amounts for each asset
        """
        total_value = current_holdings.sum()
        trades = {}
        
        for asset, target_weight in target_weights.items():
            current_value = current_holdings.get(asset, 0)
            target_value = target_weight * total_value
            trades[asset] = target_value - current_value
        
        return trades
    
    def _update_holdings(self,
                        holdings: pd.Series,
                        trades: Dict[str, float]) -> pd.Series:
        """
        Update holdings after trades.
        
        Returns:
            Updated holdings
        """
        new_holdings = holdings.copy()
        for asset, trade in trades.items():
            if asset in new_holdings.index:
                new_holdings[asset] += trade
            else:
                new_holdings[asset] = trade
        return new_holdings
    
    def _estimate_turnover(self, trading_schedule: List[Dict]) -> float:
        """
        Estimate average turnover from trading schedule.
        
        Returns:
            Average turnover per period
        """
        if not trading_schedule:
            return 0.0
        
        turnovers = []
        for schedule in trading_schedule:
            trades = schedule.get('trades', {})
            turnover = sum(abs(trade) for trade in trades.values()) / 2  # Divide by 2 for one-way
            turnovers.append(turnover)
        
        return float(np.mean(turnovers))
    
    def _estimate_tax_impact(self, trading_schedule: List[Dict]) -> float:
        """
        Estimate tax impact from trading schedule.
        
        Returns:
            Estimated tax cost as percentage
        """
        # Simplified estimation - assumes some gains are realized
        total_sells = 0
        for schedule in trading_schedule:
            trades = schedule.get('trades', {})
            sells = sum(abs(trade) for trade in trades.values() if trade < 0)
            total_sells += sells
        
        # Assume 50% of sells have gains, average gain of 10%
        estimated_gains = total_sells * 0.5 * 0.1
        estimated_tax = estimated_gains * self.tax_rates['long_term']
        
        return float(estimated_tax)
    
    def _calculate_tax_efficiency(self,
                                 trades: Dict[str, float],
                                 tax_impact: Dict[str, Any]) -> float:
        """
        Calculate tax efficiency score (0-1, higher is better).
        
        Returns:
            Tax efficiency score
        """
        if not tax_impact:
            return 1.0
        
        # Calculate ratio of tax-efficient trades
        total_trades = sum(abs(t) for t in trades.values())
        if total_trades == 0:
            return 1.0
        
        # Penalize short-term gains more
        tax_penalty = 0
        for asset, impact in tax_impact.items():
            if impact['tax_rate'] == self.tax_rates['short_term']:
                tax_penalty += abs(trades.get(asset, 0)) * 2
            else:
                tax_penalty += abs(trades.get(asset, 0))
        
        efficiency = 1 - (tax_penalty / (total_trades * 2))
        return float(max(0, min(1, efficiency)))
    
    def _get_rebalancing_recommendation(self,
                                       frequency: int,
                                       vol_percentile: float,
                                       market_regime: str) -> str:
        """
        Get rebalancing recommendation based on conditions.
        
        Returns:
            Recommendation string
        """
        if market_regime == 'crisis' or vol_percentile > 0.9:
            return 'increase_monitoring'
        elif market_regime == 'calm' and vol_percentile < 0.2:
            return 'reduce_frequency'
        else:
            return 'maintain_schedule'