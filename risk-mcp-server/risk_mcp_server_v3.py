#!/usr/bin/env python3
"""
Risk MCP Server v3 - Consolidated single-tool architecture
One comprehensive tool for complete portfolio risk analysis
Addresses feedback from ~/investing/feedback.md with maximum simplicity
"""

from fastmcp import FastMCP
from typing import Dict, List, Optional, Any
import numpy as np
from scipy import stats
import logging
import sys
import os
from datetime import datetime

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import shared modules
from data_pipeline import MarketDataPipeline
from confidence_scoring import ConfidenceScorer
from portfolio_state_client import get_portfolio_state_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("risk-server-v3")

# Initialize components
server = FastMCP("Risk Analyzer v3 - Consolidated")
data_pipeline = MarketDataPipeline()
confidence_scorer = ConfidenceScorer()
portfolio_state_client = get_portfolio_state_client()

@server.tool()
async def analyze_portfolio_risk(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    analysis_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Comprehensive portfolio risk analysis in a single call.
    Performs all risk calculations needed for portfolio construction and monitoring.
    
    Args:
        tickers: List of ticker symbols
        weights: Portfolio weights (equal weight if not provided)
        analysis_options: Optional dict to customize analysis:
            - lookback_days: int (default 504)
            - confidence_levels: List[float] (default [0.90, 0.95, 0.99])
            - time_horizons: List[int] (default [1, 5, 10, 21] days)
            - include_stress_test: bool (default True)
            - include_risk_parity: bool (default True)
            - include_advanced_measures: bool (default True)
            - var_methods: List[str] (default ['historical', 'parametric', 'cornish-fisher'])
            - custom_scenarios: List[Dict] (optional stress scenarios)
    
    Returns:
        Comprehensive risk analysis with all metrics, stress tests, and confidence scores
    """
    try:
        # Parse options with defaults
        options = analysis_options or {}
        lookback_days = options.get('lookback_days', 504)
        confidence_levels = options.get('confidence_levels', [0.90, 0.95, 0.99])
        time_horizons = options.get('time_horizons', [1, 5, 10, 21])
        include_stress = options.get('include_stress_test', True)
        include_parity = options.get('include_risk_parity', True)
        include_advanced = options.get('include_advanced_measures', True)
        var_methods = options.get('var_methods', ['historical', 'parametric', 'cornish-fisher'])
        custom_scenarios = options.get('custom_scenarios', None)
        use_portfolio_state = options.get('use_portfolio_state', portfolio_state_client.use_portfolio_state)
        
        # Try to use real portfolio positions if available
        actual_tickers = tickers
        actual_weights = weights
        portfolio_source = "provided"
        
        if use_portfolio_state and (tickers is None or tickers == ["PORTFOLIO"]):
            try:
                logger.info("Fetching real portfolio positions from Portfolio State")
                positions = await portfolio_state_client.get_positions()
                
                if positions:
                    # Use actual portfolio composition
                    actual_tickers = list(positions.keys())
                    total_value = sum(pos.current_value for pos in positions.values())
                    actual_weights = [positions[ticker].current_value / total_value for ticker in actual_tickers]
                    portfolio_source = "portfolio_state"
                    logger.info(f"Using {len(actual_tickers)} positions from Portfolio State")
                else:
                    logger.warning("No positions found in Portfolio State, using provided tickers")
            except Exception as e:
                logger.warning(f"Could not fetch from Portfolio State: {e}, using provided tickers")
        
        # Ensure we have tickers to analyze
        if not actual_tickers:
            raise ValueError("No tickers provided and no positions in Portfolio State")
        
        # Fetch real market data with quality assessment
        logger.info(f"Fetching {lookback_days} days of data for {actual_tickers}")
        data = data_pipeline.prepare_for_optimization(actual_tickers, lookback_days)
        returns = data['returns'].values
        prices = data['prices'].values
        
        # Default to equal weights if not provided
        if actual_weights is None:
            actual_weights = np.ones(len(actual_tickers)) / len(actual_tickers)
        else:
            actual_weights = np.array(actual_weights)
            # Normalize weights
            actual_weights = actual_weights / np.sum(actual_weights)
        
        # Update variables for consistency
        tickers = actual_tickers
        weights = actual_weights
        
        # Portfolio returns
        portfolio_returns = returns @ weights
        
        # Get risk-free rate
        rf_data = data_pipeline.get_risk_free_rate('10y')
        risk_free_rate = rf_data['rate']
        
        # Initialize result structure
        result = {
            "portfolio_summary": {},
            "risk_metrics": {
                "basic": {},
                "var_analysis": {},
                "advanced_measures": {},
                "distribution_analysis": {}
            },
            "risk_decomposition": {},
            "stress_testing": {},
            "confidence": {},
            "metadata": {}
        }
        
        # =========================
        # 1. PORTFOLIO SUMMARY
        # =========================
        result["portfolio_summary"] = {
            "assets": tickers,
            "weights": {ticker: float(w) for ticker, w in zip(tickers, weights)},
            "effective_assets": float(1 / np.sum(weights**2)),  # Herfindahl index
            "portfolio_value_assumed": 1000000  # $1M default
        }
        
        # =========================
        # 2. BASIC RISK METRICS
        # =========================
        mean_return = np.mean(portfolio_returns)
        volatility = np.std(portfolio_returns)
        annual_return = mean_return * 252
        annual_vol = volatility * np.sqrt(252)
        
        # Sharpe and Sortino
        sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0
        downside_returns = portfolio_returns[portfolio_returns < 0]
        downside_dev = np.std(downside_returns) if len(downside_returns) > 0 else 0
        annual_downside = downside_dev * np.sqrt(252)
        sortino = (annual_return - risk_free_rate) / annual_downside if annual_downside > 0 else 0
        
        # Maximum drawdown
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = float(np.min(drawdown))
        
        # Calmar ratio
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        result["risk_metrics"]["basic"] = {
            "annual_return": float(annual_return),
            "annual_volatility": float(annual_vol),
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown": max_drawdown,
            "calmar_ratio": float(calmar),
            "downside_deviation": float(annual_downside),
            "risk_free_rate_used": float(risk_free_rate)
        }
        
        # =========================
        # 3. VAR ANALYSIS
        # =========================
        var_results = {}
        
        for confidence in confidence_levels:
            conf_key = f"conf_{int(confidence*100)}"
            var_results[conf_key] = {}
            
            for horizon in time_horizons:
                horizon_key = f"horizon_{horizon}d"
                var_results[conf_key][horizon_key] = {}
                
                # Scale returns for time horizon
                scaled_returns = portfolio_returns * np.sqrt(horizon)
                
                # Historical VaR
                if 'historical' in var_methods:
                    percentile = (1 - confidence) * 100
                    var_hist = np.percentile(scaled_returns, percentile)
                    cvar_hist = np.mean(scaled_returns[scaled_returns <= var_hist])
                    var_results[conf_key][horizon_key]["historical_var"] = float(var_hist)
                    var_results[conf_key][horizon_key]["historical_cvar"] = float(cvar_hist)
                
                # Parametric VaR
                if 'parametric' in var_methods:
                    mean = np.mean(scaled_returns)
                    std = np.std(scaled_returns)
                    z_score = stats.norm.ppf(1 - confidence)
                    var_param = mean + z_score * std
                    cvar_param = mean - std * stats.norm.pdf(z_score) / (1 - confidence)
                    var_results[conf_key][horizon_key]["parametric_var"] = float(var_param)
                    var_results[conf_key][horizon_key]["parametric_cvar"] = float(cvar_param)
                
                # Cornish-Fisher VaR
                if 'cornish-fisher' in var_methods:
                    mean = np.mean(scaled_returns)
                    std = np.std(scaled_returns)
                    skew = stats.skew(scaled_returns)
                    kurt = stats.kurtosis(scaled_returns, fisher=True)
                    z = stats.norm.ppf(1 - confidence)
                    cf_z = z + (z**2 - 1) * skew / 6 + (z**3 - 3*z) * kurt / 24
                    var_cf = mean + cf_z * std
                    var_results[conf_key][horizon_key]["modified_var"] = float(var_cf)
        
        result["risk_metrics"]["var_analysis"] = var_results
        
        # =========================
        # 4. ADVANCED MEASURES
        # =========================
        if include_advanced:
            # Distribution analysis
            skewness = stats.skew(portfolio_returns)
            kurtosis = stats.kurtosis(portfolio_returns, fisher=True)
            _, jb_pvalue = stats.jarque_bera(portfolio_returns)
            
            # Student-t fit for fat tails
            try:
                t_params = stats.t.fit(portfolio_returns)
                t_df = t_params[0]
                t_var_95 = stats.t.ppf(0.05, *t_params) * np.sqrt(252)
            except Exception as e:
                logger.error(f"Student-t distribution fitting failed: {e}")
                raise ValueError(f"Failed to fit Student-t distribution: {str(e)}")
            
            # Ulcer Index
            ulcer_index = float(np.sqrt(np.mean(drawdown**2)))
            
            # Tail ratio
            right_tail = np.mean(portfolio_returns[portfolio_returns > np.percentile(portfolio_returns, 95)])
            left_tail = abs(np.mean(portfolio_returns[portfolio_returns < np.percentile(portfolio_returns, 5)]))
            tail_ratio = float(right_tail / left_tail) if left_tail > 0 else None
            
            result["risk_metrics"]["advanced_measures"] = {
                "ulcer_index": ulcer_index,
                "tail_ratio": tail_ratio,
                "student_t_var_95_annual": float(t_var_95) if t_var_95 else None,
                "student_t_df": float(t_df) if t_df else None
            }
            
            result["risk_metrics"]["distribution_analysis"] = {
                "skewness": float(skewness),
                "excess_kurtosis": float(kurtosis),
                "is_normal": bool(jb_pvalue > 0.05),
                "jarque_bera_pvalue": float(jb_pvalue),
                "has_fat_tails": bool(kurtosis > 1),
                "has_negative_skew": bool(skewness < -0.5)
            }
        
        # =========================
        # 5. RISK DECOMPOSITION
        # =========================
        # Use shrunk covariance for stability
        cov_matrix = data['optimization_data']['covariance_matrices'].get(
            'ledoit_wolf',
            data['optimization_data']['covariance_matrices']['sample']
        )
        
        # Portfolio volatility
        portfolio_var = weights @ cov_matrix @ weights
        portfolio_vol = np.sqrt(portfolio_var)
        
        # Marginal contributions
        marginal_contrib = cov_matrix @ weights
        risk_contrib = weights * marginal_contrib / portfolio_vol
        risk_contrib_pct = risk_contrib / np.sum(risk_contrib) * 100
        
        result["risk_decomposition"]["risk_contributions"] = {
            ticker: {
                "weight": float(w),
                "risk_contribution": float(rc),
                "risk_contribution_pct": float(rcp)
            }
            for ticker, w, rc, rcp in zip(tickers, weights, risk_contrib, risk_contrib_pct)
        }
        
        # Risk parity analysis
        if include_parity:
            # Calculate equal risk contribution weights
            n_assets = len(tickers)
            rp_weights = np.ones(n_assets) / n_assets
            
            # Iterative solution
            for _ in range(100):
                rp_vol = np.sqrt(rp_weights @ cov_matrix @ rp_weights)
                rp_marginal = cov_matrix @ rp_weights
                rp_weights = (1 / rp_marginal) / np.sum(1 / rp_marginal)
            
            # Final risk contributions for risk parity
            rp_vol = np.sqrt(rp_weights @ cov_matrix @ rp_weights)
            rp_marginal = cov_matrix @ rp_weights
            rp_contrib = rp_weights * rp_marginal / rp_vol
            
            result["risk_decomposition"]["risk_parity"] = {
                "optimal_weights": {ticker: float(w) for ticker, w in zip(tickers, rp_weights)},
                "equal_risk_achieved": bool(float(np.std(rp_contrib)) < 0.01),
                "risk_contribution_std": float(np.std(rp_contrib))
            }
        
        # Correlation matrix stats
        if len(tickers) > 1:
            corr_matrix = data['returns'].corr().values
            upper_triangle = corr_matrix[np.triu_indices_from(corr_matrix, k=1)]
            
            result["risk_decomposition"]["correlation_stats"] = {
                "average_correlation": float(np.mean(upper_triangle)) if len(upper_triangle) > 0 else 0.0,
                "max_correlation": float(np.max(upper_triangle)) if len(upper_triangle) > 0 else 0.0,
                "min_correlation": float(np.min(upper_triangle)) if len(upper_triangle) > 0 else 0.0
            }
        else:
            # Single asset - no correlations
            result["risk_decomposition"]["correlation_stats"] = {
                "average_correlation": 1.0,
                "max_correlation": 1.0,
                "min_correlation": 1.0,
                "note": "Single asset - correlation with itself is 1.0"
            }
        
        # =========================
        # 6. STRESS TESTING
        # =========================
        if include_stress:
            # Default historical crisis scenarios
            if custom_scenarios is None:
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
                        "name": "Dot-Com Burst",
                        "equity_shock": -45,
                        "bond_shock": 10,
                        "volatility_multiplier": 2.0
                    },
                    {
                        "name": "Inflation Shock",
                        "equity_shock": -20,
                        "bond_shock": -15,
                        "volatility_multiplier": 1.5
                    },
                    {
                        "name": "Rate Hike Scenario",
                        "equity_shock": -15,
                        "bond_shock": -20,
                        "volatility_multiplier": 1.3
                    }
                ]
            else:
                scenarios = custom_scenarios
            
            stress_results = []
            portfolio_value = result["portfolio_summary"]["portfolio_value_assumed"]
            
            for scenario in scenarios:
                equity_shock = scenario.get("equity_shock", 0) / 100
                bond_shock = scenario.get("bond_shock", 0) / 100
                
                # Simple classification (could be enhanced)
                portfolio_shock = 0
                for i, ticker in enumerate(tickers):
                    if ticker in ['TLT', 'AGG', 'BND', 'IEF', 'SHY']:
                        portfolio_shock += weights[i] * bond_shock
                    else:
                        portfolio_shock += weights[i] * equity_shock
                
                portfolio_loss = portfolio_value * abs(portfolio_shock) if portfolio_shock < 0 else 0
                
                stress_results.append({
                    "scenario": scenario["name"],
                    "portfolio_impact_pct": float(portfolio_shock * 100),
                    "estimated_loss": float(portfolio_loss),
                    "recovery_days_estimate": int(abs(portfolio_loss) / (portfolio_value * 0.005)) if portfolio_loss > 0 else 0
                })
            
            result["stress_testing"] = {
                "scenarios_analyzed": len(scenarios),
                "results": stress_results,
                "worst_scenario": min(stress_results, key=lambda x: x["portfolio_impact_pct"])
            }
        
        # =========================
        # 7. CONFIDENCE SCORING
        # =========================
        # Calculate condition number
        eigenvalues = np.linalg.eigvals(cov_matrix)
        condition_number = max(eigenvalues) / min(eigenvalues) if min(eigenvalues) > 0 else float('inf')
        
        # Generate confidence score
        confidence_metrics = confidence_scorer.score_portfolio_optimization(
            sample_size=len(portfolio_returns),
            condition_number=condition_number,
            optimization_status=True,
            constraint_violations=0,
            covariance_method='ledoit_wolf' if 'shrinkage_intensity' in data else 'sample'
        )
        
        result["confidence"] = confidence_metrics.to_dict()
        result["confidence"]["data_quality"] = data['quality']
        
        # =========================
        # 8. METADATA
        # =========================
        result["metadata"] = {
            "analysis_timestamp": datetime.now().isoformat(),
            "data_source": data['metadata']['source'],
            "portfolio_source": portfolio_source,
            "lookback_days": lookback_days,
            "sample_size": len(portfolio_returns),
            "covariance_method": 'ledoit_wolf' if 'shrinkage_intensity' in data else 'sample',
            "shrinkage_intensity": data.get('shrinkage_intensity', 0),
            "condition_number": float(condition_number),
            "using_portfolio_state": portfolio_source == "portfolio_state"
        }
        
        # =========================
        # 9. EXECUTIVE SUMMARY
        # =========================
        result["executive_summary"] = {
            "risk_level": "HIGH" if annual_vol > 0.20 else "MODERATE" if annual_vol > 0.10 else "LOW",
            "key_risks": [],
            "recommendations": []
        }
        
        # Generate key risks
        if max_drawdown < -0.20:
            result["executive_summary"]["key_risks"].append(f"High drawdown risk: {max_drawdown:.1%}")
        if kurtosis > 2:
            result["executive_summary"]["key_risks"].append("Fat-tail risk detected")
        if skewness < -1:
            result["executive_summary"]["key_risks"].append("Significant negative skew")
        if condition_number > 1000:
            result["executive_summary"]["key_risks"].append("Unstable covariance matrix")
        
        # Generate recommendations
        if result["confidence"]["overall_score"] < 0.7:
            result["executive_summary"]["recommendations"].append("Increase data history for more reliable estimates")
        if include_parity and not result["risk_decomposition"]["risk_parity"]["equal_risk_achieved"]:
            result["executive_summary"]["recommendations"].append("Consider risk parity weighting for better diversification")
        if annual_vol > 0.25:
            result["executive_summary"]["recommendations"].append("Portfolio volatility is high - consider risk reduction")
        
        return result
        
    except Exception as e:
        logger.error(f"Portfolio risk analysis failed: {str(e)}")
        raise ValueError(f"Risk analysis failed: {str(e)}")

@server.tool()
async def get_risk_free_rate(
    maturity: str = '10y'
) -> Dict[str, Any]:
    """
    Utility function to get current risk-free rate.
    Kept separate as it's a market data query, not portfolio-specific.
    
    Args:
        maturity: Treasury maturity ('3m', '1y', '5y', '10y', '30y')
    
    Returns:
        Current risk-free rate with metadata
    """
    try:
        rf_data = data_pipeline.get_risk_free_rate(maturity)
        # Use the confidence from the data pipeline if available
        if 'confidence' in rf_data:
            confidence = rf_data['confidence']
        else:
            confidence = 0.95 if rf_data['source'].startswith('OpenBB') else 0.7
        
        return {
            "rate": rf_data['rate'],
            "annualized": True,
            "maturity": rf_data['maturity'],
            "source": rf_data['source'],
            "confidence": confidence,
            "fetch_time": rf_data['fetch_time']
        }
    except Exception as e:
        logger.error(f"Failed to fetch risk-free rate: {str(e)}")
        raise ValueError(f"Unable to fetch risk-free rate for {maturity}: {str(e)}")

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Risk MCP Server v3 - Consolidated Architecture")
    logger.info("=" * 60)
    logger.info("Improvements from v2:")
    logger.info("✓ Single comprehensive tool for all risk analysis")
    logger.info("✓ One API call instead of 5+ separate calls")
    logger.info("✓ Unified confidence scoring across all metrics")
    logger.info("✓ Efficient data fetching (once per analysis)")
    logger.info("✓ Complete risk profile in structured response")
    logger.info("")
    logger.info("Features (all in one tool):")
    logger.info("• Basic risk metrics (Sharpe, Sortino, Max DD)")
    logger.info("• VaR/CVaR at multiple confidence levels and horizons")
    logger.info("• Advanced measures (Ulcer Index, tail ratios, Student-t)")
    logger.info("• Risk decomposition and contribution analysis")
    logger.info("• Risk parity optimization")
    logger.info("• Stress testing with historical scenarios")
    logger.info("• Distribution analysis (skew, kurtosis, fat tails)")
    logger.info("• Executive summary with recommendations")
    logger.info("")
    logger.info("Addresses ~/investing/feedback.md requirements:")
    logger.info("• Real market data via OpenBB/yfinance")
    logger.info("• Ledoit-Wolf covariance shrinkage")
    logger.info("• Fat-tail adjustments (Cornish-Fisher, Student-t)")
    logger.info("• Comprehensive confidence scoring")
    logger.info("• Data quality assessment")
    logger.info("=" * 60)
    
    server.run(transport="stdio")