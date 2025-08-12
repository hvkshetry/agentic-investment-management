"""
Risk calculation utilities for consistent VaR/ES reporting.
Ensures both VaR and ES are always reported together with clear conventions.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any
from scipy import stats
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# Sign convention: NEGATIVE values represent losses
# This is consistent with industry standard where VaR is quoted as positive
# but represents a negative return threshold


def calculate_var_es(
    returns: Union[np.ndarray, pd.Series],
    confidence: float = 0.95,
    method: str = "historical",
    horizon_days: int = 1
) -> Dict[str, float]:
    """
    Calculate both VaR and ES (CVaR) with consistent conventions.
    
    Args:
        returns: Array or Series of returns (as decimals, not percentages)
        confidence: Confidence level (e.g., 0.95 for 95%)
        method: Calculation method ("historical", "parametric", "cornish_fisher")
        horizon_days: Time horizon in days for scaling
        
    Returns:
        Dictionary with VaR and ES values (positive values representing loss magnitude)
        
    Sign Convention:
        - Returns: positive = gain, negative = loss
        - VaR/ES output: positive values representing potential loss magnitude
        - Example: VaR = 0.025 means 2.5% potential loss
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    # Remove NaN values
    returns = returns[~np.isnan(returns)]
    
    if len(returns) < 20:
        logger.warning(f"Insufficient data for risk calculation: {len(returns)} returns")
        return {"VaR": 0.0, "ES": 0.0, "confidence": confidence, "method": method}
    
    # Scale returns for multi-day horizon using log returns
    if horizon_days > 1:
        # Convert to log returns for proper aggregation
        log_returns = np.log1p(returns)
        
        # Scale using square root of time for log returns
        scaled_std = np.std(log_returns) * np.sqrt(horizon_days)
        scaled_mean = np.mean(log_returns) * horizon_days
        
        # For historical method, we need to simulate the scaled distribution
        if method == "historical":
            # Bootstrap scaled returns
            n_simulations = 10000
            random_indices = np.random.choice(len(log_returns), 
                                            size=(n_simulations, horizon_days), 
                                            replace=True)
            simulated_log_returns = log_returns[random_indices].sum(axis=1)
            scaled_returns = np.expm1(simulated_log_returns)  # Convert back from log
        else:
            # For parametric, adjust the parameters
            scaled_returns = None  # Will use scaled parameters below
    else:
        scaled_returns = returns
        scaled_std = np.std(returns)
        scaled_mean = np.mean(returns)
    
    # Calculate VaR and ES based on method
    if method == "historical":
        var_value, es_value = _calculate_historical_var_es(scaled_returns, confidence)
    elif method == "parametric":
        var_value, es_value = _calculate_parametric_var_es(
            scaled_mean, scaled_std, confidence, horizon_days
        )
    elif method == "cornish_fisher":
        var_value, es_value = _calculate_cornish_fisher_var_es(
            returns, confidence, horizon_days
        )
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # Convert to positive values (magnitude of potential loss)
    var_value = abs(var_value)
    es_value = abs(es_value)
    
    return {
        "VaR": var_value,
        "ES": es_value,
        "confidence": confidence,
        "method": method,
        "horizon_days": horizon_days,
        "units": "return_decimal",
        "sign_convention": "positive_loss"
    }


def _calculate_historical_var_es(
    returns: np.ndarray,
    confidence: float
) -> Tuple[float, float]:
    """
    Calculate historical VaR and ES.
    
    Returns:
        Tuple of (VaR, ES) as negative values (losses)
    """
    alpha = 1 - confidence
    var_index = int(alpha * len(returns))
    
    sorted_returns = np.sort(returns)
    var_value = sorted_returns[var_index]
    
    # ES is the average of returns worse than VaR
    es_value = np.mean(sorted_returns[:var_index]) if var_index > 0 else var_value
    
    return var_value, es_value


def _calculate_parametric_var_es(
    mean: float,
    std: float,
    confidence: float,
    horizon_days: int = 1
) -> Tuple[float, float]:
    """
    Calculate parametric (Gaussian) VaR and ES.
    
    Returns:
        Tuple of (VaR, ES) as negative values (losses)
    """
    alpha = 1 - confidence
    
    # VaR calculation
    z_score = stats.norm.ppf(alpha)
    var_value = mean + z_score * std
    
    # ES calculation (expected value in the tail)
    # For normal distribution: ES = μ - σ * φ(z) / Φ(z)
    # where φ is PDF and Φ is CDF
    pdf_value = stats.norm.pdf(z_score)
    cdf_value = alpha  # By definition
    es_value = mean - std * (pdf_value / cdf_value)
    
    return var_value, es_value


def _calculate_cornish_fisher_var_es(
    returns: np.ndarray,
    confidence: float,
    horizon_days: int = 1
) -> Tuple[float, float]:
    """
    Calculate Cornish-Fisher adjusted VaR and ES.
    Accounts for skewness and kurtosis in the return distribution.
    
    Returns:
        Tuple of (VaR, ES) as negative values (losses)
    """
    alpha = 1 - confidence
    mean = np.mean(returns)
    std = np.std(returns)
    skew = stats.skew(returns)
    kurt = stats.kurtosis(returns, fisher=True)  # Excess kurtosis
    
    # Cornish-Fisher expansion
    z = stats.norm.ppf(alpha)
    z_cf = z + (z**2 - 1) * skew / 6 + (z**3 - 3*z) * kurt / 24 - (2*z**3 - 5*z) * skew**2 / 36
    
    # Scale for horizon
    if horizon_days > 1:
        std = std * np.sqrt(horizon_days)
        mean = mean * horizon_days
    
    var_value = mean + z_cf * std
    
    # For ES with Cornish-Fisher, fall back to historical method in the tail
    sorted_returns = np.sort(returns)
    var_index = int(alpha * len(sorted_returns))
    
    if horizon_days > 1:
        # Scale the tail returns
        tail_returns = sorted_returns[:var_index]
        log_tail = np.log1p(tail_returns)
        scaled_tail = np.expm1(log_tail * horizon_days)
        es_value = np.mean(scaled_tail) if len(scaled_tail) > 0 else var_value
    else:
        es_value = np.mean(sorted_returns[:var_index]) if var_index > 0 else var_value
    
    return var_value, es_value


def calculate_portfolio_risk_metrics(
    returns: pd.DataFrame,
    weights: Optional[np.ndarray] = None,
    confidence: float = 0.95,
    horizons: List[int] = [1, 5, 20]
) -> Dict[str, Any]:
    """
    Calculate comprehensive risk metrics for a portfolio.
    
    Args:
        returns: DataFrame with asset returns (columns are assets)
        weights: Portfolio weights (if None, uses equal weight)
        confidence: Confidence level for VaR/ES
        horizons: List of time horizons in days
        
    Returns:
        Dictionary with risk metrics for all methods and horizons
    """
    if weights is None:
        weights = np.ones(len(returns.columns)) / len(returns.columns)
    
    # Calculate portfolio returns
    portfolio_returns = (returns @ weights).values
    
    results = {
        "summary": {},
        "detailed": {},
        "by_method": {},
        "by_horizon": {}
    }
    
    # Calculate metrics for each method and horizon
    methods = ["historical", "parametric", "cornish_fisher"]
    
    for method in methods:
        results["by_method"][method] = {}
        
        for horizon in horizons:
            metrics = calculate_var_es(
                portfolio_returns,
                confidence=confidence,
                method=method,
                horizon_days=horizon
            )
            
            key = f"{method}_{horizon}d"
            results["detailed"][key] = metrics
            results["by_method"][method][f"{horizon}d"] = metrics
            
            if horizon not in results["by_horizon"]:
                results["by_horizon"][horizon] = {}
            results["by_horizon"][horizon][method] = metrics
    
    # Summary statistics (using historical 1-day as default)
    default_metrics = results["detailed"]["historical_1d"]
    results["summary"] = {
        "VaR_95": default_metrics["VaR"],
        "ES_95": default_metrics["ES"],
        "volatility": np.std(portfolio_returns),
        "annualized_volatility": np.std(portfolio_returns) * np.sqrt(252),
        "skewness": stats.skew(portfolio_returns),
        "kurtosis": stats.kurtosis(portfolio_returns, fisher=True),
        "max_drawdown": calculate_max_drawdown(portfolio_returns),
        "sharpe_ratio": calculate_sharpe_ratio(portfolio_returns)
    }
    
    return results


def calculate_max_drawdown(returns: Union[np.ndarray, pd.Series]) -> float:
    """
    Calculate maximum drawdown from returns.
    
    Args:
        returns: Array or Series of returns
        
    Returns:
        Maximum drawdown as positive fraction (0.20 = 20% drawdown)
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    # Calculate cumulative returns
    cum_returns = np.cumprod(1 + returns)
    
    # Calculate running maximum
    running_max = np.maximum.accumulate(cum_returns)
    
    # Calculate drawdown
    drawdown = (cum_returns - running_max) / running_max
    
    # Return maximum drawdown (as positive value)
    return abs(np.min(drawdown)) if len(drawdown) > 0 else 0.0


def calculate_sharpe_ratio(
    returns: Union[np.ndarray, pd.Series],
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        returns: Array or Series of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year (252 for daily)
        
    Returns:
        Sharpe ratio
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    # Convert annual risk-free rate to period rate
    rf_period = (1 + risk_free_rate) ** (1/periods_per_year) - 1
    
    # Calculate excess returns
    excess_returns = returns - rf_period
    
    # Calculate Sharpe ratio
    if np.std(excess_returns) > 0:
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(periods_per_year)
    else:
        sharpe = 0.0
    
    return sharpe


def stress_test_portfolio(
    returns: pd.DataFrame,
    weights: Optional[np.ndarray] = None,
    scenarios: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    Run stress tests on portfolio.
    
    Args:
        returns: DataFrame with asset returns
        weights: Portfolio weights
        scenarios: Custom stress scenarios (if None, uses defaults)
        
    Returns:
        Dictionary with stress test results
    """
    if weights is None:
        weights = np.ones(len(returns.columns)) / len(returns.columns)
    
    if scenarios is None:
        scenarios = {
            "market_crash_2008": -0.37,      # S&P 500 in 2008
            "covid_march_2020": -0.12,       # March 2020 crash
            "black_monday_1987": -0.22,      # October 1987
            "tech_bubble_2000": -0.49,       # 2000-2002 bear market
            "moderate_correction": -0.10,    # 10% correction
            "severe_correction": -0.20,      # 20% bear market
        }
    
    portfolio_returns = (returns @ weights).values
    current_volatility = np.std(portfolio_returns)
    
    results = {}
    for scenario_name, shock in scenarios.items():
        # Estimate portfolio response based on beta to market
        # This is simplified - in practice you'd model correlations
        estimated_loss = shock * (current_volatility / 0.15)  # Assume market vol of 15%
        results[scenario_name] = {
            "scenario_shock": shock,
            "estimated_portfolio_loss": estimated_loss,
            "dollar_impact_per_100k": estimated_loss * 100000
        }
    
    return results