#!/usr/bin/env python3
"""
Risk MCP Server - Provides risk analytics tools via Model Context Protocol
Uses numpy and scipy for risk calculations and stress testing
"""

from fastmcp import FastMCP
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy import stats
import logging

# Configure logging to stderr only (critical for stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Defaults to stderr
)
logger = logging.getLogger("risk-server")

# Initialize FastMCP server
server = FastMCP("Risk Analyzer")

# Implementation functions (regular Python functions that can be called directly)
def _calculate_var_impl(
    returns: List[float],
    confidence: float = 0.95,
    time_horizon: int = 1
) -> Dict[str, float]:
    """Implementation for VaR calculation."""
    try:
        returns_array = np.array(returns)
        
        # Scale returns for time horizon
        scaled_returns = returns_array * np.sqrt(time_horizon)
        
        # Calculate VaR
        var_percentile = (1 - confidence) * 100
        var = np.percentile(scaled_returns, var_percentile)
        
        # Calculate CVaR (Expected Shortfall)
        cvar = np.mean(scaled_returns[scaled_returns <= var])
        
        return {
            "var": float(var),
            "cvar": float(cvar),
            "confidence_level": confidence,
            "time_horizon": time_horizon,
            "expected_shortfall": float(cvar)
        }
    except Exception as e:
        logger.error(f"VaR calculation failed: {str(e)}")
        raise ValueError(f"VaR calculation failed: {str(e)}")

@server.tool()
async def calculate_var(
    returns: List[float],
    confidence: float = 0.95,
    time_horizon: int = 1
) -> Dict[str, float]:
    """
    Calculate Value at Risk and Conditional VaR (CVaR).
    
    Args:
        returns: List of historical returns
        confidence: Confidence level (e.g., 0.95 for 95%)
        time_horizon: Time horizon in days
    
    Returns:
        Dictionary with VaR and CVaR values
    """
    return _calculate_var_impl(returns, confidence, time_horizon)

@server.tool()
async def calculate_portfolio_var(
    returns: List[List[float]],
    weights: List[float],
    confidence: float = 0.95,
    time_horizon: int = 1
) -> Dict[str, float]:
    """
    Calculate portfolio VaR and CVaR with given weights.
    
    Args:
        returns: 2D list where each row is an asset's return series
        weights: Portfolio weights for each asset
        confidence: Confidence level (e.g., 0.95 for 95%)
        time_horizon: Time horizon in days
    
    Returns:
        Dictionary with portfolio VaR and CVaR
    """
    try:
        returns_array = np.array(returns)
        weights_array = np.array(weights)
        
        # Calculate portfolio returns
        portfolio_returns = np.dot(returns_array.T, weights_array)
        
        # Calculate VaR and CVaR using implementation function
        result = _calculate_var_impl(portfolio_returns.tolist(), confidence, time_horizon)
        
        return result
    except Exception as e:
        logger.error(f"Portfolio VaR calculation failed: {str(e)}")
        raise ValueError(f"Portfolio VaR calculation failed: {str(e)}")

@server.tool()
async def stress_test_portfolio(
    returns: List[List[float]],
    weights: List[float],
    scenarios: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Run stress test scenarios on a portfolio.
    
    Args:
        returns: 2D list where each row is an asset's return series
        weights: Portfolio weights for each asset
        scenarios: List of stress scenarios with shocks
    
    Returns:
        List of scenario results with portfolio impacts
    """
    try:
        returns_array = np.array(returns)
        weights_array = np.array(weights)
        
        # Calculate baseline portfolio metrics
        portfolio_returns = np.dot(returns_array.T, weights_array)
        baseline_vol = np.std(portfolio_returns)
        
        results = []
        
        for scenario in scenarios:
            # Apply shocks based on scenario
            equity_shock = scenario.get("equity_shock", 0) / 100
            bond_shock = scenario.get("bond_shock", 0) / 100
            fx_shock = scenario.get("fx_shock", 0) / 100
            commodity_shock = scenario.get("commodity_shock", 0) / 100
            
            # Simple shock application (in practice, would use factor model)
            # Assume first assets are equity-like, later ones bond-like
            n_assets = len(weights_array)
            shocked_returns = returns_array.copy()
            
            # Apply shocks proportionally
            for i in range(n_assets):
                if i < n_assets // 2:  # Equity-like
                    shock = equity_shock
                else:  # Bond-like
                    shock = bond_shock
                    
                shocked_returns[i] = shocked_returns[i] * (1 + shock)
            
            # Calculate stressed portfolio return
            stressed_portfolio = np.dot(shocked_returns.T, weights_array)
            portfolio_loss = np.mean(portfolio_returns - stressed_portfolio)
            
            results.append({
                "scenario": scenario.get("name", "Unnamed"),
                "portfolio_loss_pct": float(portfolio_loss * 100),
                "stressed_volatility": float(np.std(stressed_portfolio)),
                "vol_increase": float((np.std(stressed_portfolio) / baseline_vol - 1) * 100)
            })
        
        return results
    except Exception as e:
        logger.error(f"Stress testing failed: {str(e)}")
        raise ValueError(f"Stress testing failed: {str(e)}")

@server.tool()
async def calculate_correlation_matrix(
    returns: List[List[float]]
) -> Dict[str, Any]:
    """
    Calculate correlation matrix for assets.
    
    Args:
        returns: 2D list where each row is an asset's return series
    
    Returns:
        Dictionary with correlation matrix and statistics
    """
    try:
        returns_array = np.array(returns)
        
        # Calculate correlation matrix
        corr_matrix = np.corrcoef(returns_array)
        
        # Get upper triangle (excluding diagonal)
        upper_triangle = corr_matrix[np.triu_indices_from(corr_matrix, k=1)]
        
        return {
            "correlation_matrix": corr_matrix.tolist(),
            "average_correlation": float(np.mean(upper_triangle)),
            "max_correlation": float(np.max(upper_triangle)),
            "min_correlation": float(np.min(upper_triangle)),
            "median_correlation": float(np.median(upper_triangle))
        }
    except Exception as e:
        logger.error(f"Correlation calculation failed: {str(e)}")
        raise ValueError(f"Correlation calculation failed: {str(e)}")

@server.tool()
async def calculate_risk_metrics(
    returns: List[float],
    benchmark_returns: Optional[List[float]] = None,
    risk_free_rate: float = 0.04
) -> Dict[str, float]:
    """
    Calculate comprehensive risk metrics for returns.
    
    Args:
        returns: List of returns
        benchmark_returns: Optional benchmark returns for relative metrics
        risk_free_rate: Annual risk-free rate
    
    Returns:
        Dictionary with various risk metrics
    """
    try:
        returns_array = np.array(returns)
        
        # Basic statistics
        mean_return = np.mean(returns_array)
        volatility = np.std(returns_array)
        
        # Annualized metrics (assuming daily returns)
        annual_return = mean_return * 252
        annual_vol = volatility * np.sqrt(252)
        
        # Sharpe ratio
        sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0
        
        # Downside deviation and Sortino ratio
        downside_returns = returns_array[returns_array < 0]
        downside_dev = np.std(downside_returns) if len(downside_returns) > 0 else 0
        annual_downside = downside_dev * np.sqrt(252)
        sortino = (annual_return - risk_free_rate) / annual_downside if annual_downside > 0 else 0
        
        # Maximum drawdown
        cumulative = np.cumprod(1 + returns_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        # Calmar ratio
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Skewness and kurtosis
        skewness = stats.skew(returns_array)
        kurtosis = stats.kurtosis(returns_array)
        
        metrics = {
            "annual_return": float(annual_return),
            "annual_volatility": float(annual_vol),
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown": float(max_drawdown),
            "calmar_ratio": float(calmar),
            "downside_deviation": float(annual_downside),
            "skewness": float(skewness),
            "kurtosis": float(kurtosis),
            "var_95": float(np.percentile(returns_array, 5)),
            "cvar_95": float(np.mean(returns_array[returns_array <= np.percentile(returns_array, 5)]))
        }
        
        # Relative metrics if benchmark provided
        if benchmark_returns is not None:
            benchmark_array = np.array(benchmark_returns)
            
            # Beta
            covariance = np.cov(returns_array, benchmark_array)[0, 1]
            benchmark_var = np.var(benchmark_array)
            beta = covariance / benchmark_var if benchmark_var > 0 else 0
            
            # Alpha
            benchmark_return = np.mean(benchmark_array) * 252
            alpha = annual_return - (risk_free_rate + beta * (benchmark_return - risk_free_rate))
            
            # Tracking error and information ratio
            active_returns = returns_array - benchmark_array
            tracking_error = np.std(active_returns) * np.sqrt(252)
            info_ratio = (annual_return - benchmark_return) / tracking_error if tracking_error > 0 else 0
            
            metrics.update({
                "beta": float(beta),
                "alpha": float(alpha),
                "tracking_error": float(tracking_error),
                "information_ratio": float(info_ratio)
            })
        
        return metrics
    except Exception as e:
        logger.error(f"Risk metrics calculation failed: {str(e)}")
        raise ValueError(f"Risk metrics calculation failed: {str(e)}")

@server.tool()
async def monte_carlo_var(
    mean_return: float,
    volatility: float,
    portfolio_value: float,
    time_horizon: int = 1,
    confidence: float = 0.95,
    n_simulations: int = 10000
) -> Dict[str, Any]:
    """
    Calculate VaR using Monte Carlo simulation.
    
    Args:
        mean_return: Expected daily return
        volatility: Daily volatility
        portfolio_value: Portfolio value
        time_horizon: Time horizon in days
        confidence: Confidence level
        n_simulations: Number of Monte Carlo simulations
    
    Returns:
        Dictionary with Monte Carlo VaR results
    """
    try:
        # Generate random returns
        np.random.seed(42)  # For reproducibility
        simulated_returns = np.random.normal(
            mean_return * time_horizon,
            volatility * np.sqrt(time_horizon),
            n_simulations
        )
        
        # Calculate portfolio values
        portfolio_values = portfolio_value * (1 + simulated_returns)
        portfolio_losses = portfolio_value - portfolio_values
        
        # Calculate VaR and CVaR
        var_percentile = (1 - confidence) * 100
        var = np.percentile(portfolio_losses, 100 - var_percentile)
        cvar = np.mean(portfolio_losses[portfolio_losses >= var])
        
        return {
            "var_amount": float(var),
            "var_percent": float(var / portfolio_value * 100),
            "cvar_amount": float(cvar),
            "cvar_percent": float(cvar / portfolio_value * 100),
            "confidence_level": confidence,
            "time_horizon": time_horizon,
            "n_simulations": n_simulations,
            "worst_case": float(np.max(portfolio_losses)),
            "best_case": float(np.min(portfolio_losses))
        }
    except Exception as e:
        logger.error(f"Monte Carlo VaR failed: {str(e)}")
        raise ValueError(f"Monte Carlo VaR failed: {str(e)}")

@server.tool()
async def calculate_component_var(
    returns: List[List[float]],
    weights: List[float],
    confidence: float = 0.95
) -> Dict[str, Any]:
    """
    Calculate component VaR showing risk contribution of each asset.
    
    Args:
        returns: 2D list where each row is an asset's return series
        weights: Portfolio weights
        confidence: Confidence level
    
    Returns:
        Dictionary with component VaR for each asset
    """
    try:
        returns_array = np.array(returns)
        weights_array = np.array(weights)
        
        # Calculate covariance matrix
        cov_matrix = np.cov(returns_array)
        
        # Portfolio volatility
        portfolio_vol = np.sqrt(weights_array.T @ cov_matrix @ weights_array)
        
        # Marginal VaR (derivative of portfolio vol with respect to weights)
        marginal_var = (cov_matrix @ weights_array) / portfolio_vol
        
        # Component VaR
        component_var = weights_array * marginal_var
        
        # Normalize to get percentage contributions
        total_var = np.sum(component_var)
        pct_contributions = component_var / total_var * 100
        
        return {
            "portfolio_volatility": float(portfolio_vol),
            "marginal_var": marginal_var.tolist(),
            "component_var": component_var.tolist(),
            "pct_contributions": pct_contributions.tolist(),
            "total_var": float(total_var)
        }
    except Exception as e:
        logger.error(f"Component VaR calculation failed: {str(e)}")
        raise ValueError(f"Component VaR calculation failed: {str(e)}")

if __name__ == "__main__":
    # Run the server with stdio transport
    logger.info("Starting Risk MCP Server v2.0 with FastMCP")
    server.run(transport="stdio")