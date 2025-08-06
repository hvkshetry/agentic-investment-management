#!/usr/bin/env python3
"""
Risk MCP Server v2 - Enhanced with real data and confidence scoring
Integrates data pipeline and adds advanced risk measures
Addresses feedback from ~/investing/feedback.md
"""

from fastmcp import FastMCP
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy import stats
import logging
import sys
import os

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import shared modules
from data_pipeline import MarketDataPipeline, DataQualityScorer
from confidence_scoring import ConfidenceScorer, ConfidenceMetrics

# Configure logging to stderr only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("risk-server-v2")

# Initialize components
server = FastMCP("Risk Analyzer v2")
data_pipeline = MarketDataPipeline()
confidence_scorer = ConfidenceScorer()

@server.tool()
async def calculate_var_with_data(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    confidence: float = 0.95,
    time_horizon: int = 1,
    lookback_days: int = 504,
    method: str = 'historical'
) -> Dict[str, Any]:
    """
    Calculate VaR and CVaR using real market data.
    
    Args:
        tickers: List of ticker symbols
        weights: Portfolio weights (equal weight if not provided)
        confidence: Confidence level (e.g., 0.95 for 95%)
        time_horizon: Time horizon in days
        lookback_days: Historical data period
        method: 'historical', 'parametric', or 'cornish-fisher'
    
    Returns:
        Dictionary with VaR, CVaR, and confidence metrics
    """
    try:
        # Fetch real market data
        data = data_pipeline.fetch_equity_data(tickers, lookback_days=lookback_days)
        returns = data['returns'].values
        
        # Default to equal weights
        if weights is None:
            weights = np.ones(len(tickers)) / len(tickers)
        else:
            weights = np.array(weights)
        
        # Calculate portfolio returns
        portfolio_returns = returns @ weights
        
        # Scale for time horizon
        scaled_returns = portfolio_returns * np.sqrt(time_horizon)
        
        # Calculate VaR based on method
        if method == 'historical':
            var_percentile = (1 - confidence) * 100
            var = np.percentile(scaled_returns, var_percentile)
            cvar = np.mean(scaled_returns[scaled_returns <= var])
            
        elif method == 'parametric':
            mean = np.mean(scaled_returns)
            std = np.std(scaled_returns)
            z_score = stats.norm.ppf(1 - confidence)
            var = mean + z_score * std
            # CVaR for normal distribution
            cvar = mean - std * stats.norm.pdf(z_score) / (1 - confidence)
            
        elif method == 'cornish-fisher':
            # Cornish-Fisher expansion for non-normal distributions
            mean = np.mean(scaled_returns)
            std = np.std(scaled_returns)
            skew = stats.skew(scaled_returns)
            kurt = stats.kurtosis(scaled_returns, fisher=True)
            
            z = stats.norm.ppf(1 - confidence)
            cf_z = z + (z**2 - 1) * skew / 6 + (z**3 - 3*z) * kurt / 24 - (2*z**3 - 5*z) * skew**2 / 36
            var = mean + cf_z * std
            
            # Approximate CVaR
            tail_returns = scaled_returns[scaled_returns <= var]
            cvar = np.mean(tail_returns) if len(tail_returns) > 0 else var * 1.2
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Test for distribution normality
        _, p_value = stats.jarque_bera(portfolio_returns)
        
        # Calculate confidence score
        confidence_metrics = confidence_scorer.score_risk_calculation(
            sample_size=len(portfolio_returns),
            distribution_test_pvalue=p_value,
            tail_observations=len(portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)]),
            methodology=method
        )
        
        # Prepare result with confidence
        result = {
            "var": float(var),
            "cvar": float(cvar),
            "confidence_level": confidence,
            "time_horizon": time_horizon,
            "method": method,
            "sample_size": len(portfolio_returns),
            "distribution_test": {
                "jarque_bera_pvalue": float(p_value),
                "is_normal": p_value > 0.05
            }
        }
        
        return confidence_scorer.add_confidence_to_response(
            result,
            confidence_metrics,
            calculation_details={
                "data_source": data['metadata']['source'],
                "data_quality": data['quality']
            }
        )
        
    except Exception as e:
        logger.error(f"VaR calculation failed: {str(e)}")
        raise ValueError(f"VaR calculation failed: {str(e)}")

@server.tool()
async def calculate_advanced_risk_measures(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    lookback_days: int = 504
) -> Dict[str, Any]:
    """
    Calculate comprehensive risk measures including fat-tail adjustments.
    Addresses reviewer concern about missing advanced risk measures.
    
    Args:
        tickers: List of ticker symbols
        weights: Portfolio weights
        lookback_days: Historical data period
    
    Returns:
        Dictionary with multiple risk measures and confidence
    """
    try:
        # Fetch real market data
        data = data_pipeline.fetch_equity_data(tickers, lookback_days=lookback_days)
        returns = data['returns'].values
        
        # Default weights
        if weights is None:
            weights = np.ones(len(tickers)) / len(tickers)
        else:
            weights = np.array(weights)
        
        # Portfolio returns
        portfolio_returns = returns @ weights
        annual_factor = np.sqrt(252)
        
        # Basic metrics
        mean_return = np.mean(portfolio_returns)
        volatility = np.std(portfolio_returns)
        
        # VaR at multiple confidence levels
        var_levels = {}
        cvar_levels = {}
        for conf in [0.90, 0.95, 0.99]:
            percentile = (1 - conf) * 100
            var = np.percentile(portfolio_returns, percentile)
            var_levels[f"var_{int(conf*100)}"] = float(var * annual_factor)
            cvar_levels[f"cvar_{int(conf*100)}"] = float(
                np.mean(portfolio_returns[portfolio_returns <= var]) * annual_factor
            )
        
        # Maximum Drawdown
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = float(np.min(drawdown))
        
        # Ulcer Index (root mean square of drawdowns)
        ulcer_index = float(np.sqrt(np.mean(drawdown**2)))
        
        # Modified VaR (Cornish-Fisher)
        skew = stats.skew(portfolio_returns)
        kurt = stats.kurtosis(portfolio_returns, fisher=True)
        z_95 = stats.norm.ppf(0.05)
        cf_z = z_95 + (z_95**2 - 1) * skew / 6 + (z_95**3 - 3*z_95) * kurt / 24
        modified_var = float((mean_return + cf_z * volatility) * annual_factor)
        
        # Tail ratio (right tail / left tail)
        right_tail = np.mean(portfolio_returns[portfolio_returns > np.percentile(portfolio_returns, 95)])
        left_tail = abs(np.mean(portfolio_returns[portfolio_returns < np.percentile(portfolio_returns, 5)]))
        tail_ratio = float(right_tail / left_tail) if left_tail > 0 else float('inf')
        
        # Student-t fit for fat tails
        try:
            t_params = stats.t.fit(portfolio_returns)
            t_var_95 = stats.t.ppf(0.05, *t_params) * annual_factor
            degrees_of_freedom = t_params[0]
        except:
            t_var_95 = var_levels['var_95']
            degrees_of_freedom = None
        
        # Test for normality
        _, jb_pvalue = stats.jarque_bera(portfolio_returns)
        
        # Calculate confidence
        confidence_metrics = confidence_scorer.score_risk_calculation(
            sample_size=len(portfolio_returns),
            distribution_test_pvalue=jb_pvalue,
            tail_observations=len(portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)]),
            methodology='comprehensive'
        )
        
        result = {
            "basic_metrics": {
                "annual_return": float(mean_return * 252),
                "annual_volatility": float(volatility * annual_factor),
                "sharpe_ratio": float(mean_return * 252 / (volatility * annual_factor))
            },
            "var_measures": var_levels,
            "cvar_measures": cvar_levels,
            "advanced_measures": {
                "max_drawdown": max_drawdown,
                "ulcer_index": ulcer_index,
                "modified_var_95": modified_var,
                "student_t_var_95": float(t_var_95),
                "tail_ratio": tail_ratio,
                "skewness": float(skew),
                "excess_kurtosis": float(kurt)
            },
            "distribution_analysis": {
                "degrees_of_freedom": degrees_of_freedom,
                "is_normal": jb_pvalue > 0.05,
                "has_fat_tails": kurt > 1
            }
        }
        
        return confidence_scorer.add_confidence_to_response(
            result,
            confidence_metrics,
            calculation_details={
                "data_source": data['metadata']['source'],
                "data_quality": data['quality']
            }
        )
        
    except Exception as e:
        logger.error(f"Advanced risk calculation failed: {str(e)}")
        raise ValueError(f"Advanced risk calculation failed: {str(e)}")

@server.tool()
async def stress_test_with_real_data(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    scenarios: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Run stress tests using real market data and historical crises.
    
    Args:
        tickers: List of ticker symbols
        weights: Portfolio weights
        scenarios: Custom stress scenarios (uses historical if not provided)
    
    Returns:
        Dictionary with stress test results and confidence
    """
    try:
        # Fetch real market data
        data = data_pipeline.fetch_equity_data(tickers, lookback_days=756)
        returns = data['returns'].values
        prices = data['prices'].values
        
        # Default weights
        if weights is None:
            weights = np.ones(len(tickers)) / len(tickers)
        else:
            weights = np.array(weights)
        
        # Default scenarios based on historical crises
        if scenarios is None:
            scenarios = [
                {
                    "name": "2008 Financial Crisis",
                    "equity_shock": -40,
                    "bond_shock": 5,
                    "volatility_multiplier": 2.5
                },
                {
                    "name": "COVID-19 Crash",
                    "equity_shock": -35,
                    "bond_shock": 2,
                    "volatility_multiplier": 3.0
                },
                {
                    "name": "Tech Bubble Burst",
                    "equity_shock": -45,
                    "bond_shock": 10,
                    "volatility_multiplier": 2.0
                },
                {
                    "name": "Inflation Shock",
                    "equity_shock": -20,
                    "bond_shock": -15,
                    "volatility_multiplier": 1.5
                }
            ]
        
        # Calculate baseline metrics
        portfolio_returns = returns @ weights
        baseline_vol = np.std(portfolio_returns)
        baseline_value = 1000000  # Assume $1M portfolio
        
        results = []
        
        for scenario in scenarios:
            # Apply shocks
            equity_shock = scenario.get("equity_shock", 0) / 100
            bond_shock = scenario.get("bond_shock", 0) / 100
            vol_mult = scenario.get("volatility_multiplier", 1.0)
            
            # Classify assets (simple heuristic)
            shocked_returns = []
            for i, ticker in enumerate(tickers):
                if ticker in ['TLT', 'AGG', 'BND', 'IEF']:  # Bond ETFs
                    shock = bond_shock
                else:  # Assume equity
                    shock = equity_shock
                
                # Apply shock and volatility adjustment
                asset_returns = returns[:, i] * (1 + shock)
                asset_returns = asset_returns * vol_mult
                shocked_returns.append(asset_returns)
            
            shocked_returns = np.array(shocked_returns).T
            stressed_portfolio = shocked_returns @ weights
            
            # Calculate impact
            portfolio_loss = baseline_value * shock if shock < 0 else 0
            stressed_vol = np.std(stressed_portfolio)
            var_95_stressed = np.percentile(stressed_portfolio, 5) * np.sqrt(252)
            
            results.append({
                "scenario": scenario["name"],
                "portfolio_loss": float(portfolio_loss),
                "loss_percentage": float(abs(shock) * 100) if shock < 0 else 0,
                "stressed_volatility": float(stressed_vol * np.sqrt(252)),
                "volatility_increase": float((stressed_vol / baseline_vol - 1) * 100),
                "stressed_var_95": float(var_95_stressed),
                "recovery_days_estimate": int(abs(portfolio_loss) / (baseline_value * 0.01)) if portfolio_loss < 0 else 0
            })
        
        # Calculate confidence
        confidence_metrics = confidence_scorer.score_risk_calculation(
            sample_size=len(portfolio_returns),
            distribution_test_pvalue=0.5,  # Neutral for stress testing
            tail_observations=50,  # Approximate
            methodology='stress_testing'
        )
        
        return confidence_scorer.add_confidence_to_response(
            {
                "baseline_metrics": {
                    "portfolio_value": baseline_value,
                    "annual_volatility": float(baseline_vol * np.sqrt(252))
                },
                "stress_scenarios": results,
                "worst_case": min(results, key=lambda x: x.get("portfolio_loss", 0))
            },
            confidence_metrics,
            calculation_details={
                "data_source": data['metadata']['source'],
                "scenarios_count": len(scenarios)
            }
        )
        
    except Exception as e:
        logger.error(f"Stress testing failed: {str(e)}")
        raise ValueError(f"Stress testing failed: {str(e)}")

@server.tool()
async def calculate_risk_parity_metrics(
    tickers: List[str],
    lookback_days: int = 504
) -> Dict[str, Any]:
    """
    Calculate risk parity metrics showing risk contribution of each asset.
    
    Args:
        tickers: List of ticker symbols
        lookback_days: Historical data period
    
    Returns:
        Dictionary with risk contributions and optimal risk parity weights
    """
    try:
        # Fetch real market data with covariance shrinkage
        data = data_pipeline.prepare_for_optimization(tickers, lookback_days)
        returns = data['returns'].values
        
        # Use Ledoit-Wolf shrunk covariance
        cov_matrix = data['optimization_data']['covariance_matrices'].get(
            'ledoit_wolf',
            data['optimization_data']['covariance_matrices']['sample']
        )
        
        # Calculate equal risk contribution weights
        n_assets = len(tickers)
        
        # Initial guess: equal weights
        weights = np.ones(n_assets) / n_assets
        
        # Iterative solution for risk parity
        for _ in range(100):
            # Risk contributions
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
            marginal_contrib = cov_matrix @ weights
            risk_contrib = weights * marginal_contrib / portfolio_vol
            
            # Update weights inversely proportional to risk contribution
            weights = (1 / marginal_contrib) / np.sum(1 / marginal_contrib)
        
        # Final risk contributions
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        marginal_contrib = cov_matrix @ weights
        risk_contrib = weights * marginal_contrib / portfolio_vol
        
        # Check if equal risk is achieved
        contrib_std = np.std(risk_contrib)
        is_equal_risk = contrib_std < 0.01
        
        # Calculate condition number
        eigenvalues = np.linalg.eigvals(cov_matrix)
        condition_number = max(eigenvalues) / min(eigenvalues) if min(eigenvalues) > 0 else float('inf')
        
        # Calculate confidence
        confidence_metrics = confidence_scorer.score_portfolio_optimization(
            sample_size=len(returns),
            condition_number=condition_number,
            optimization_status=is_equal_risk,
            constraint_violations=contrib_std,
            covariance_method='ledoit_wolf' if 'shrinkage_intensity' in data else 'sample'
        )
        
        result = {
            "risk_parity_weights": {ticker: float(w) for ticker, w in zip(tickers, weights)},
            "risk_contributions": {ticker: float(rc) for ticker, rc in zip(tickers, risk_contrib)},
            "portfolio_volatility": float(portfolio_vol * np.sqrt(252)),
            "equal_risk_achieved": is_equal_risk,
            "contribution_std": float(contrib_std),
            "covariance_conditioning": {
                "condition_number": float(condition_number),
                "shrinkage_applied": 'shrinkage_intensity' in data,
                "shrinkage_intensity": data.get('shrinkage_intensity', 0)
            }
        }
        
        return confidence_scorer.add_confidence_to_response(
            result,
            confidence_metrics,
            calculation_details={
                "data_source": data['metadata']['source'],
                "optimization_method": "iterative_risk_parity"
            }
        )
        
    except Exception as e:
        logger.error(f"Risk parity calculation failed: {str(e)}")
        raise ValueError(f"Risk parity calculation failed: {str(e)}")

@server.tool()
async def get_risk_free_rate(
    maturity: str = '10y'
) -> Dict[str, Any]:
    """
    Get current risk-free rate from Treasury data.
    
    Args:
        maturity: Treasury maturity ('3m', '1y', '5y', '10y', '30y')
    
    Returns:
        Dictionary with current risk-free rate
    """
    try:
        rf_data = data_pipeline.get_risk_free_rate(maturity)
        
        # Add confidence based on source
        confidence = 0.95 if rf_data['source'].startswith('OpenBB') else 0.7
        
        return {
            "rate": rf_data['rate'],
            "annualized": rf_data['annualized'],
            "maturity": rf_data['maturity'],
            "source": rf_data['source'],
            "confidence": confidence,
            "fetch_time": rf_data['fetch_time']
        }
    except Exception as e:
        logger.error(f"Failed to fetch risk-free rate: {str(e)}")
        return {
            "rate": 0.04,
            "annualized": True,
            "maturity": maturity,
            "source": "default",
            "confidence": 0.5,
            "error": str(e)
        }

if __name__ == "__main__":
    logger.info("Starting Risk MCP Server v2 with real data and confidence scoring")
    logger.info("Enhancements per ~/investing/feedback.md:")
    logger.info("- Real market data via OpenBB/yfinance")
    logger.info("- Advanced risk measures (CVaR, Modified VaR, Ulcer Index)")
    logger.info("- Fat-tail modeling with Student-t distribution")
    logger.info("- Confidence scoring on all outputs")
    logger.info("- Ledoit-Wolf covariance shrinkage")
    server.run(transport="stdio")