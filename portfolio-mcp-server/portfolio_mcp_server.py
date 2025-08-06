#!/usr/bin/env python3
"""
Portfolio MCP Server - Provides portfolio optimization tools via Model Context Protocol
Uses scipy for optimization and numpy for calculations
"""

from fastmcp import FastMCP
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
from scipy.optimize import minimize
import logging

# Configure logging to stderr only (critical for stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Defaults to stderr
)
logger = logging.getLogger("portfolio-server")

# Initialize FastMCP server
server = FastMCP("Portfolio Optimizer")

# Implementation functions (regular Python functions that can be called directly)
def _optimize_min_variance_impl(
    returns: List[List[float]],
    target_return: Optional[float] = None
) -> Dict[str, Any]:
    """Implementation for minimum variance optimization."""
    try:
        returns_array = np.array(returns)
        mean_returns = np.mean(returns_array, axis=1)
        cov_matrix = np.cov(returns_array)
        
        n_assets = len(mean_returns)
        
        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(cov_matrix, weights))
        
        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        
        if target_return is not None:
            constraints.append({
                'type': 'eq',
                'fun': lambda x: np.dot(x, mean_returns) - target_return
            })
        
        bounds = tuple((0, 1) for _ in range(n_assets))
        initial_weights = np.ones(n_assets) / n_assets
        
        result = minimize(portfolio_variance, initial_weights, method='SLSQP',
                         bounds=bounds, constraints=constraints)
        
        optimal_weights = result.x
        portfolio_return = np.dot(optimal_weights, mean_returns)
        portfolio_vol = np.sqrt(portfolio_variance(optimal_weights))
        
        return {
            "success": result.success,
            "weights": optimal_weights.tolist(),
            "expected_return": float(portfolio_return),
            "volatility": float(portfolio_vol)
        }
    except Exception as e:
        logger.error(f"Min variance optimization failed: {str(e)}")
        raise ValueError(f"Min variance optimization failed: {str(e)}")

@server.tool()
async def optimize_sharpe_ratio(
    returns: List[List[float]],
    risk_free_rate: float = 0.04
) -> Dict[str, Any]:
    """
    Optimize portfolio weights to maximize Sharpe ratio.
    
    Args:
        returns: 2D list where each row is an asset's return series
        risk_free_rate: Annual risk-free rate (default 4%)
    
    Returns:
        Dictionary with optimal weights, expected return, volatility, and Sharpe ratio
    """
    try:
        returns_array = np.array(returns)
        mean_returns = np.mean(returns_array, axis=1)
        cov_matrix = np.cov(returns_array)
        
        n_assets = len(mean_returns)
        
        def neg_sharpe(weights):
            portfolio_return = np.dot(weights, mean_returns)
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            return -(portfolio_return - risk_free_rate) / portfolio_vol
        
        constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        bounds = tuple((0, 1) for _ in range(n_assets))
        initial_weights = np.ones(n_assets) / n_assets
        
        result = minimize(neg_sharpe, initial_weights, method='SLSQP',
                         bounds=bounds, constraints=constraints)
        
        optimal_weights = result.x
        portfolio_return = np.dot(optimal_weights, mean_returns)
        portfolio_vol = np.sqrt(np.dot(optimal_weights.T, np.dot(cov_matrix, optimal_weights)))
        sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_vol
        
        return {
            "success": result.success,
            "weights": optimal_weights.tolist(),
            "expected_return": float(portfolio_return),
            "volatility": float(portfolio_vol),
            "sharpe_ratio": float(sharpe_ratio)
        }
    except Exception as e:
        logger.error(f"Sharpe optimization failed: {str(e)}")
        raise ValueError(f"Sharpe optimization failed: {str(e)}")

@server.tool()
async def optimize_min_variance(
    returns: List[List[float]],
    target_return: Optional[float] = None
) -> Dict[str, Any]:
    """
    Optimize portfolio for minimum variance.
    
    Args:
        returns: 2D list where each row is an asset's return series
        target_return: Optional target return constraint
    
    Returns:
        Dictionary with optimal weights and portfolio metrics
    """
    return _optimize_min_variance_impl(returns, target_return)

@server.tool()
async def calculate_risk_parity(
    returns: List[List[float]]
) -> Dict[str, Any]:
    """
    Calculate risk parity portfolio weights.
    
    Args:
        returns: 2D list where each row is an asset's return series
    
    Returns:
        Dictionary with risk parity weights and risk contributions
    """
    try:
        returns_array = np.array(returns)
        cov_matrix = np.cov(returns_array)
        n_assets = len(returns_array)
        
        def risk_contribution(weights):
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            marginal_contrib = np.dot(cov_matrix, weights)
            contrib = weights * marginal_contrib / portfolio_vol
            return contrib
        
        def risk_parity_objective(weights):
            contrib = risk_contribution(weights)
            avg_contrib = np.mean(contrib)
            return np.sum((contrib - avg_contrib) ** 2)
        
        constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        bounds = tuple((0.01, 1) for _ in range(n_assets))
        initial_weights = np.ones(n_assets) / n_assets
        
        result = minimize(risk_parity_objective, initial_weights, method='SLSQP',
                         bounds=bounds, constraints=constraints)
        
        optimal_weights = result.x
        risk_contrib = risk_contribution(optimal_weights)
        
        return {
            "success": result.success,
            "weights": optimal_weights.tolist(),
            "risk_contributions": risk_contrib.tolist(),
            "equal_risk": float(np.std(risk_contrib) < 0.01)
        }
    except Exception as e:
        logger.error(f"Risk parity calculation failed: {str(e)}")
        raise ValueError(f"Risk parity calculation failed: {str(e)}")

@server.tool()
async def generate_efficient_frontier(
    returns: List[List[float]],
    n_portfolios: int = 50
) -> Dict[str, Any]:
    """
    Generate efficient frontier portfolios.
    
    Args:
        returns: 2D list where each row is an asset's return series
        n_portfolios: Number of portfolios to generate on the frontier
    
    Returns:
        Dictionary containing list of efficient frontier portfolios
    """
    try:
        returns_array = np.array(returns)
        mean_returns = np.mean(returns_array, axis=1)
        
        # Get min and max possible returns
        min_return = np.min(mean_returns)
        max_return = np.max(mean_returns)
        
        target_returns = np.linspace(min_return, max_return, n_portfolios)
        frontier_portfolios = []
        
        for target in target_returns:
            try:
                # Call implementation function directly instead of tool
                result = _optimize_min_variance_impl(returns, float(target))
                if result["success"]:
                    frontier_portfolios.append({
                        "target_return": float(target),
                        "weights": result["weights"],
                        "actual_return": result["expected_return"],
                        "volatility": result["volatility"]
                    })
            except Exception as e:
                # Log the error but continue with other points
                logger.debug(f"Failed to optimize for target return {target}: {str(e)}")
                continue
        
        # Ensure we return at least some portfolios or raise an error
        if not frontier_portfolios:
            logger.warning("No portfolios could be optimized for the efficient frontier")
            # Try to at least return the min variance portfolio
            try:
                min_var_result = _optimize_min_variance_impl(returns, None)
                if min_var_result["success"]:
                    frontier_portfolios = [{
                        "target_return": min_var_result["expected_return"],
                        "weights": min_var_result["weights"],
                        "actual_return": min_var_result["expected_return"],
                        "volatility": min_var_result["volatility"]
                    }]
            except:
                pass
        
        # Return as a dictionary to match other tools' return format
        return {
            "portfolios": frontier_portfolios,
            "count": len(frontier_portfolios),
            "success": len(frontier_portfolios) > 0
        }
    except Exception as e:
        logger.error(f"Efficient frontier generation failed: {str(e)}")
        raise ValueError(f"Efficient frontier generation failed: {str(e)}")

@server.tool()
async def calculate_portfolio_metrics(
    weights: List[float],
    returns: List[List[float]],
    benchmark_returns: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive portfolio performance metrics.
    
    Args:
        weights: Portfolio weights for each asset
        returns: 2D list where each row is an asset's return series
        benchmark_returns: Optional benchmark return series for comparison
    
    Returns:
        Dictionary with performance metrics including return, volatility, Sharpe, max drawdown
    """
    try:
        returns_array = np.array(returns)
        weights_array = np.array(weights)
        
        # Calculate portfolio returns
        portfolio_returns = np.dot(returns_array.T, weights_array)
        
        # Basic metrics
        mean_return = np.mean(portfolio_returns)
        volatility = np.std(portfolio_returns)
        
        # Sharpe ratio (assuming 252 trading days)
        sharpe = mean_return / volatility * np.sqrt(252) if volatility > 0 else 0
        
        # Maximum drawdown
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        # Sortino ratio (downside deviation)
        downside_returns = portfolio_returns[portfolio_returns < 0]
        downside_dev = np.std(downside_returns) if len(downside_returns) > 0 else 0
        sortino = mean_return / downside_dev * np.sqrt(252) if downside_dev > 0 else 0
        
        metrics = {
            "annual_return": float(mean_return * 252),
            "annual_volatility": float(volatility * np.sqrt(252)),
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown": float(max_drawdown),
            "skewness": float(np.nan_to_num(np.mean((portfolio_returns - mean_return) ** 3) / volatility ** 3)),
            "kurtosis": float(np.nan_to_num(np.mean((portfolio_returns - mean_return) ** 4) / volatility ** 4 - 3))
        }
        
        # Beta and alpha if benchmark provided
        if benchmark_returns is not None:
            benchmark_array = np.array(benchmark_returns)
            covariance = np.cov(portfolio_returns, benchmark_array)[0, 1]
            benchmark_var = np.var(benchmark_array)
            beta = covariance / benchmark_var if benchmark_var > 0 else 0
            alpha = mean_return - beta * np.mean(benchmark_array)
            
            metrics["beta"] = float(beta)
            metrics["alpha"] = float(alpha * 252)
        
        return metrics
    except Exception as e:
        logger.error(f"Portfolio metrics calculation failed: {str(e)}")
        raise ValueError(f"Portfolio metrics calculation failed: {str(e)}")

@server.tool()
async def rebalance_portfolio(
    current_weights: List[float],
    target_weights: List[float],
    portfolio_value: float,
    prices: List[float],
    min_trade_size: float = 100.0
) -> Dict[str, Any]:
    """
    Calculate rebalancing trades for a portfolio.
    
    Args:
        current_weights: Current portfolio weights
        target_weights: Target portfolio weights
        portfolio_value: Total portfolio value
        prices: Current prices for each asset
        min_trade_size: Minimum trade size to execute
    
    Returns:
        Dictionary with rebalancing trades and costs
    """
    try:
        current = np.array(current_weights)
        target = np.array(target_weights)
        prices_array = np.array(prices)
        
        # Calculate current and target values
        current_values = current * portfolio_value
        target_values = target * portfolio_value
        
        # Calculate required trades
        trade_values = target_values - current_values
        trade_shares = trade_values / prices_array
        
        # Filter out small trades
        trades = []
        total_turnover = 0
        
        for i, (value, shares) in enumerate(zip(trade_values, trade_shares)):
            if abs(value) >= min_trade_size:
                trades.append({
                    "asset_index": i,
                    "action": "BUY" if value > 0 else "SELL",
                    "shares": float(abs(shares)),
                    "value": float(abs(value)),
                    "price": float(prices_array[i])
                })
                total_turnover += abs(value)
        
        return {
            "trades": trades,
            "total_turnover": float(total_turnover),
            "turnover_percent": float(total_turnover / portfolio_value * 100),
            "estimated_cost": float(total_turnover * 0.001)  # Assume 0.1% transaction cost
        }
    except Exception as e:
        logger.error(f"Rebalancing calculation failed: {str(e)}")
        raise ValueError(f"Rebalancing calculation failed: {str(e)}")

if __name__ == "__main__":
    # Run the server with stdio transport
    logger.info("Starting Portfolio MCP Server v2.0 with FastMCP")
    server.run(transport="stdio")