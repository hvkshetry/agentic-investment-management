#!/usr/bin/env python3
"""
Risk MCP Server v3 - Consolidated single-tool architecture
One comprehensive tool for complete portfolio risk analysis
Addresses project feedback requirements with maximum simplicity
"""

from fastmcp import FastMCP
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
from scipy import stats
import logging
import sys
import os
from datetime import datetime, timezone, timedelta

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import shared modules
from data_pipeline import MarketDataPipeline
from confidence_scoring import ConfidenceScorer
from portfolio_state_client import get_portfolio_state_client
from risk_conventions import RiskConventions, RiskStack
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'orchestrator'))
from position_lookthrough import PositionLookthrough

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
position_lookthrough = PositionLookthrough(concentration_limit=0.20)  # 20% limit for single names

@server.tool()
async def analyze_portfolio_risk(
    tickers: List[str],
    weights: List[float],
    analysis_options: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """
    Comprehensive portfolio risk analysis in a single call.
    Performs all risk calculations needed for portfolio construction and monitoring.
    
    Args:
        tickers: List of ticker symbols
        weights: Portfolio weights (REQUIRED - will be normalized to sum to 1.0)
        analysis_options: Dict to customize analysis (pass empty dict {} for defaults):
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
        # Handle MCP JSON string serialization
        import json
        
        # Convert JSON strings to native types if needed (MCP protocol serializes to JSON)
        if isinstance(tickers, str):
            try:
                tickers = json.loads(tickers)
                logger.debug(f"Converted tickers from JSON string to list with {len(tickers)} elements")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse tickers as JSON: {tickers[:50]}...")
        
        if isinstance(weights, str):
            try:
                weights = json.loads(weights)
                logger.debug(f"Converted weights from JSON string to list with {len(weights)} elements")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse weights as JSON: {weights[:50]}...")
        
        if isinstance(analysis_options, str):
            try:
                analysis_options = json.loads(analysis_options)
                logger.debug("Converted analysis_options from JSON string to dict")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse analysis_options as JSON: {analysis_options[:50]}...")
        
        # Parse options with defaults (analysis_options is now always a dict, never None)
        options = analysis_options if analysis_options else {}
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
        
        # Convert to numpy array and normalize weights
        actual_weights = np.array(actual_weights)
        # Normalize weights to ensure they sum to 1.0
        actual_weights = actual_weights / np.sum(actual_weights)
        
        # Update variables for consistency
        tickers = actual_tickers
        weights = actual_weights
        
        # Portfolio returns
        portfolio_returns = returns @ weights
        
        # Get risk-free rate
        rf_data = data_pipeline.get_risk_free_rate('10y')
        risk_free_rate = rf_data['rate']
        
        # Initialize result structure with risk_stack
        result = {
            "portfolio_summary": {},
            "risk_stack": None,  # Will be populated with RiskStack object
            "risk_metrics": {
                "basic": {},
                "var_analysis": {},
                "advanced_measures": {},
                "distribution_analysis": {},
                # Schema-required ES fields (populated later)
                "es_975_1day": None,
                "es_limit": 0.025,
                "es_utilization": None,
                "status": None
            },
            "risk_decomposition": {},
            "stress_testing": {},
            "confidence": {},
            "metadata": {},
            "halt_status": None  # Schema-required field (populated later)
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
        # 3. BUILD COMPREHENSIVE RISK STACK (ES PRIMARY)
        # =========================
        
        # ES limit is FIXED at 2.5% - NON-NEGOTIABLE BINDING CONSTRAINT
        # Do NOT calibrate or adjust this limit
        es_limit_binding = 0.025  # 2.5% at 97.5% confidence
        
        # Calculate Expected Shortfall (primary metric)
        es_975 = RiskConventions.compute_expected_shortfall(
            portfolio_returns,
            alpha=0.975,
            horizon_days=1,
            method="historical"
        )
        
        es_99 = RiskConventions.compute_expected_shortfall(
            portfolio_returns,
            alpha=0.99,
            horizon_days=1,
            method="historical"
        )
        
        # Calculate VaR for reference
        var_95 = RiskConventions.compute_var(
            portfolio_returns,
            confidence=0.95,
            horizon_days=1,
            method="historical"
        )
        
        # Fetch Fama-French factors
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        start_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        
        try:
            ff_factors = data_pipeline.fetch_fama_french_factors(
                start_date=start_date,
                end_date=end_date,
                frequency="daily"
            )
            
            # Align dates and compute excess returns
            portfolio_df = pd.DataFrame(portfolio_returns, index=data['returns'].index, columns=['portfolio'])
            ff_factors_aligned = ff_factors.reindex(portfolio_df.index).fillna(method='ffill')
            
            # Compute excess returns for regression
            rf_rate_daily = ff_factors_aligned['RF'] if 'RF' in ff_factors_aligned.columns else 0
            excess_returns = portfolio_df['portfolio'] - rf_rate_daily
            
            # Run factor regression with robust standard errors
            from statsmodels.regression.linear_model import OLS
            import statsmodels.api as sm
            
            factor_cols = ['MKT-RF', 'SMB', 'HML', 'RMW', 'CMA', 'MOM']
            available_factors = [col for col in factor_cols if col in ff_factors_aligned.columns]
            
            if len(available_factors) > 0:
                X = ff_factors_aligned[available_factors]
                X = sm.add_constant(X)  # Add intercept
                
                # Robust regression
                model = OLS(excess_returns, X)
                results = model.fit(cov_type='HAC', cov_kwds={'maxlags': 5})
                
                factor_betas = {factor: float(results.params[factor]) for factor in available_factors}
                factor_betas['alpha'] = float(results.params['const'])
                
                # Get confidence intervals
                conf_int = results.conf_int()
                factor_ci = {factor: [float(conf_int.loc[factor, 0]), float(conf_int.loc[factor, 1])] 
                            for factor in available_factors}
                
                r_squared = float(results.rsquared)
                residual_vol = float(np.std(results.resid))
            else:
                factor_betas = {}
                factor_ci = {}
                r_squared = 0.0
                residual_vol = float(volatility)
        except Exception as e:
            logger.warning(f"Factor analysis failed: {e}, using empty factors")
            factor_betas = {}
            factor_ci = {}
            r_squared = 0.0
            residual_vol = float(volatility)
        
        # Calculate correlation-adjusted concentration metrics
        returns_df = data['returns']
        cov_matrix = returns_df.cov().values * 252  # Annualized
        
        # Weight-based ENB
        enb_weight = 1 / np.sum(weights**2)
        
        # Correlation-adjusted ENB
        portfolio_var = weights @ cov_matrix @ weights
        portfolio_vol_annual = np.sqrt(portfolio_var)
        marginal_contrib = cov_matrix @ weights
        risk_contrib = weights * marginal_contrib / portfolio_vol_annual if portfolio_vol_annual > 0 else weights
        enb_corr_adj = 1 / np.sum(risk_contrib**2) if np.sum(risk_contrib**2) > 0 else enb_weight
        
        # Risk contribution Herfindahl
        risk_contrib_herfindahl = float(np.sum(risk_contrib**2))
        
        # Calculate liquidity metrics (placeholder - would need ADV data)
        # In production, fetch Average Daily Volume (ADV) data
        liquidity = {
            "pct_adv_p95": 0.05,  # Placeholder: 5% of ADV
            "names_over_10pct_adv": 0,  # Placeholder
            "gross_notional_to_adv": 0.1  # Placeholder
        }
        
        # Path risk with explicit windows
        # 1-year window (252 trading days)
        if len(portfolio_returns) >= 252:
            returns_1y = portfolio_returns[-252:]
            cumulative_1y = np.cumprod(1 + returns_1y)
            running_max_1y = np.maximum.accumulate(cumulative_1y)
            drawdown_1y = (cumulative_1y - running_max_1y) / running_max_1y
            max_drawdown_1y = float(np.min(drawdown_1y))
            
            # Ulcer Index (1-year)
            ulcer_index_1y = float(np.sqrt(np.mean(drawdown_1y**2)) * 100)
        else:
            max_drawdown_1y = max_drawdown
            ulcer_index_1y = float(np.sqrt(np.mean(drawdown**2)) * 100)
        
        # Build comprehensive RiskStack
        risk_stack = RiskStack(
            as_of=datetime.now(timezone.utc),
            lookback_days=lookback_days,
            horizon_days=1,
            frequency="daily",
            units="decimal",
            sign_convention="positive_loss",
            
            loss_based={
                "es": {
                    "alpha": 0.975,
                    "value": abs(es_975["value"]),
                    "method": "historical",
                    "horizon_days": 1
                },
                "es_99": {
                    "alpha": 0.99,
                    "value": abs(es_99["value"]),
                    "method": "historical",
                    "horizon_days": 1
                },
                "var": {  # Reference only
                    "alpha": 0.95,
                    "value": abs(var_95.value),
                    "method": "historical",
                    "horizon_days": 1
                },
                "downside_semidev": float(downside_dev)
            },
            
            path_risk={
                "max_drawdown_1y": abs(max_drawdown_1y),
                "ulcer_index_1y": ulcer_index_1y,
                "calmar_ratio": float(calmar)
            },
            
            factor_exposures={
                "window_days": lookback_days,
                "betas": factor_betas,
                "beta_ci": factor_ci,
                "r_squared": r_squared,
                "residual_vol": residual_vol
            },
            
            concentration={
                "max_name_weight": float(np.max(weights)),
                "top5_weight": float(np.sum(sorted(weights)[-5:])),
                "sector_max_weight": 0.0,  # Would need sector mapping
                "enb_weight": float(enb_weight),
                "enb_corr_adj": float(enb_corr_adj),
                "risk_contrib_herfindahl": risk_contrib_herfindahl
            },
            
            liquidity=liquidity
        )
        
        # Validate the risk stack
        validation_errors = risk_stack.validate()
        if validation_errors:
            logger.warning(f"Risk stack validation warnings: {validation_errors}")
        
        # Add risk stack to result
        result["risk_stack"] = risk_stack.to_dict()
        result["risk_stack"]["es_limit_binding"] = float(es_limit_binding)  # FIXED 2.5% limit
        
        # =========================
        # 3b. ETF LOOKTHROUGH CONCENTRATION ANALYSIS
        # =========================
        # Create portfolio dictionary for lookthrough analysis
        portfolio_dict = {ticker: weight for ticker, weight in zip(tickers, weights)}
        
        # Calculate true concentration with ETF lookthrough
        concentration_result = position_lookthrough.check_concentration_limits(portfolio_dict)
        
        # Update concentration metrics with lookthrough results
        result["etf_lookthrough_concentration"] = {
            "max_single_name_exposure": concentration_result.max_concentration,
            "max_single_name_ticker": concentration_result.max_concentration_symbol,
            "funds_total_weight": concentration_result.details.get('funds_total_weight', 0),
            "individuals_total_weight": concentration_result.details.get('individuals_total_weight', 0),
            "concentration_breach": not concentration_result.passed,
            "single_name_limit": concentration_result.details['limit'],
            "violations": concentration_result.violations,
            "fund_positions": concentration_result.details.get('fund_positions', {}),
            "individual_positions": concentration_result.details.get('individual_positions', {}),
            "all_funds_exempt": concentration_result.details.get('all_funds_exempt', True)
        }
        
        # Check if any individual stock (not fund) exceeds limits
        individual_stock_breach = False
        for ticker, weight in zip(tickers, weights):
            # Only check individual stocks, not funds
            if not position_lookthrough.is_fund(ticker) and weight > 0.20:
                individual_stock_breach = True
                break
        
        result["concentration_analysis"] = {
            "simple_max_position": float(np.max(weights)),
            "simple_max_ticker": tickers[np.argmax(weights)],
            "etf_lookthrough_max": concentration_result.max_concentration,
            "concentration_limit_breach": not concentration_result.passed or individual_stock_breach,
            "all_funds_exempt_from_limits": True,
            "concentration_report": position_lookthrough.get_concentration_report(portfolio_dict)
        }
        
        # =========================
        # 3c. TRADITIONAL VAR ANALYSIS (for backward compatibility)
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
        # 7. ADVANCED RISK ANALYTICS FROM SHARED LIBRARIES
        # =========================
        
        # 7A. BACKTEST RISK PROFILE
        if options.get('backtest_risk', False):
            try:
                from backtesting.bt_engine import BacktestEngine
                bt_engine = BacktestEngine()
                
                # Run backtest with current weights
                backtest_result = bt_engine.run_backtest(
                    strategy='buy_and_hold',
                    weights={tickers[i]: weights[i] for i in range(len(tickers))},
                    data=prices,
                    start_date=options.get('backtest_start'),
                    end_date=options.get('backtest_end')
                )
                
                result["backtest_risk_profile"] = {
                    "historical_sharpe": backtest_result.get('sharpe', 0),
                    "historical_sortino": backtest_result.get('sortino', 0),
                    "historical_max_drawdown": backtest_result.get('max_drawdown', 0),
                    "historical_calmar": backtest_result.get('calmar', 0),
                    "performed": True
                }
                
            except Exception as e:
                logger.warning(f"Backtest risk profiling failed: {e}")
                result["backtest_risk_profile"] = {"error": str(e), "performed": False}
        
        # 7B. VALIDATION-BASED RISK ASSESSMENT
        if options.get('validate_risk_model', False):
            try:
                from validation.metrics import ValidationMetrics
                val_metrics = ValidationMetrics()
                
                # Calculate comprehensive validation metrics
                risk_validation = val_metrics.calculate_all_metrics(
                    returns=portfolio_returns,
                    benchmark_returns=options.get('benchmark_returns'),
                    risk_free_rate=options.get('risk_free_rate', 0.02)
                )
                
                result["risk_model_validation"] = {
                    "stability_score": risk_validation.get('stability', 0),
                    "information_ratio": risk_validation.get('information_ratio', 0),
                    "calmar_ratio": risk_validation.get('calmar_ratio', 0),
                    "validation_performed": True
                }
                
            except Exception as e:
                logger.warning(f"Risk model validation failed: {e}")
                result["risk_model_validation"] = {"error": str(e), "validation_performed": False}
        
        # 7C. MULTI-PERIOD RISK EVOLUTION
        if options.get('multi_period_risk', False):
            try:
                from optimization.multi_period import MultiPeriodOptimizer
                mp_optimizer = MultiPeriodOptimizer()
                
                # Analyze how risk evolves over time with rebalancing
                current_holdings = {tickers[i]: weights[i] for i in range(len(tickers))}
                
                # Generate dynamic rebalancing schedule based on volatility
                dynamic_schedule = mp_optimizer.dynamic_rebalancing_schedule(
                    volatility=pd.Series(portfolio_vol),
                    correlation=corr_matrix,
                    market_regime=options.get('market_regime', 'normal')
                )
                
                result["multi_period_risk"] = {
                    "rebalance_frequency": dynamic_schedule['rebalance_frequency_days'],
                    "volatility_trigger": dynamic_schedule['triggers'].get('volatility_spike', False),
                    "correlation_stability": dynamic_schedule['correlation_stability'],
                    "risk_adjusted_schedule": dynamic_schedule['recommended_action'],
                    "analysis_performed": True
                }
                
            except Exception as e:
                logger.warning(f"Multi-period risk analysis failed: {e}")
                result["multi_period_risk"] = {"error": str(e), "analysis_performed": False}
        
        # 7D. SCENARIO-BASED RISK WITH VIEWS
        if 'risk_scenarios' in options and options['risk_scenarios']:
            try:
                from optimization.views_entropy import ViewsEntropyPooling
                entropy_pooler = ViewsEntropyPooling()
                
                # Incorporate scenario-based risk views
                scenario_risk = entropy_pooler.scenario_based_views(
                    scenarios=options['risk_scenarios'],
                    probabilities=options.get('scenario_probabilities', [])
                )
                
                result["scenario_risk_analysis"] = {
                    "expected_var_95": scenario_risk['var_95'].to_dict(),
                    "expected_cvar_95": scenario_risk['cvar_95'].to_dict(),
                    "dominant_risk_scenario": scenario_risk['dominant_scenario'],
                    "risk_adjusted_covariance": scenario_risk['covariance'].to_dict(),
                    "analysis_performed": True
                }
                
            except Exception as e:
                logger.warning(f"Scenario risk analysis failed: {e}")
                result["scenario_risk_analysis"] = {"error": str(e), "analysis_performed": False}
        
        # 7E. EXTREME RISK WITH QUANTUM METHODS
        if options.get('extreme_risk_analysis', False):
            try:
                from optimization.quantum import QuantumOptimizer
                quantum_opt = QuantumOptimizer()
                
                # Use quantum methods to identify extreme risk combinations
                # Find worst-case asset selection that maximizes risk
                extreme_risk_result = quantum_opt.multi_objective_optimization(
                    objectives=[
                        {'type': 'risk', 'weight': 1.0},  # Maximize risk to find worst case
                        {'type': 'return', 'weight': -0.1}  # Slight penalty for zero return
                    ],
                    constraints={'cardinality': min(5, len(tickers))},
                    universe=tickers
                )
                
                result["extreme_risk_analysis"] = {
                    "worst_case_assets": extreme_risk_result['selected_assets'],
                    "extreme_risk_identified": len(extreme_risk_result['selected_assets']) > 0,
                    "recommendation": "Avoid concentration in identified high-risk combinations",
                    "analysis_performed": True
                }
                
            except Exception as e:
                logger.warning(f"Extreme risk analysis failed: {e}")
                result["extreme_risk_analysis"] = {"error": str(e), "analysis_performed": False}
        
        # =========================
        # 8. CONFIDENCE SCORING
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
        # 9. METADATA
        # =========================
        result["metadata"] = {
            "analysis_timestamp": datetime.now(timezone.utc).isoformat() + "Z",
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
        # 10. EXECUTIVE SUMMARY WITH ES METRICS
        # =========================
        # Extract ES metrics for top-level access (CRITICAL for gating)
        es_975_value = abs(es_975["value"])
        es_limit = 0.025  # BINDING CONSTRAINT: 2.5% at 97.5% confidence
        halt_required = es_975_value > es_limit
        es_utilization = es_975_value / es_limit if es_limit > 0 else 0
        es_status = "breach" if halt_required else "pass"

        # Populate schema-required fields in risk_metrics
        result["risk_metrics"]["es_975_1day"] = es_975_value
        result["risk_metrics"]["es_limit"] = es_limit
        result["risk_metrics"]["es_utilization"] = es_utilization
        result["risk_metrics"]["status"] = es_status

        # Populate schema-required halt_status at top level
        # Schema requires: halt_required, es_breach, liquidity_breach, concentration_breach, reasons
        halt_reasons = []
        if halt_required:
            halt_reasons.append("ES @ 97.5% exceeds 2.5% limit")

        result["halt_status"] = {
            "halt_required": halt_required,
            "es_breach": halt_required,  # Currently only checking ES
            "liquidity_breach": False,   # Not yet implemented
            "concentration_breach": False,  # Checked separately in concentration_analysis
            "reasons": halt_reasons
        }

        result["executive_summary"] = {
            "risk_level": "HIGH" if annual_vol > 0.20 else "MODERATE" if annual_vol > 0.10 else "LOW",
            "es_975_1day": es_975_value,  # PRIMARY RISK METRIC
            "es_limit": es_limit,  # BINDING CONSTRAINT
            "halt_required": halt_required,  # TRUE if ES breached (advisory system - no trading authority)
            "risk_alert_level": 3 if halt_required else 0,  # 3 = CRITICAL (trading strongly discouraged)
            "es_status": "🔴 CRITICAL ALERT - Trading Strongly Discouraged" if halt_required else "✅ Within Limits",
            "key_risks": [],
            "recommendations": []
        }

        # Generate key risks (ES BREACH FIRST - MOST CRITICAL)
        if halt_required:
            result["executive_summary"]["key_risks"].append(
                f"🔴 RISK ALERT LEVEL 3 - CRITICAL: ES @ 97.5% = {es_975_value:.2%} exceeds limit of {es_limit:.2%}. "
                f"URGENT REVIEW REQUIRED. Do not execute new trades until ES drops below {es_limit:.2%}."
            )
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
        
        # Add advanced features to summary
        advanced_features_used = []
        if 'backtest_risk_profile' in result and result['backtest_risk_profile'].get('performed'):
            advanced_features_used.append("Historical risk backtesting")
        if 'risk_model_validation' in result and result['risk_model_validation'].get('validation_performed'):
            advanced_features_used.append("Risk model validation")
        if 'multi_period_risk' in result and result['multi_period_risk'].get('analysis_performed'):
            advanced_features_used.append("Multi-period risk evolution")
        if 'scenario_risk_analysis' in result and result['scenario_risk_analysis'].get('analysis_performed'):
            advanced_features_used.append("Scenario-based risk analysis")
        if 'extreme_risk_analysis' in result and result['extreme_risk_analysis'].get('analysis_performed'):
            advanced_features_used.append("Extreme risk identification")
        
        if advanced_features_used:
            result["executive_summary"]["advanced_features"] = advanced_features_used
        
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
    logger.info("Addresses project feedback requirements:")
    logger.info("• Real market data via OpenBB/yfinance")
    logger.info("• Ledoit-Wolf covariance shrinkage")
    logger.info("• Fat-tail adjustments (Cornish-Fisher, Student-t)")
    logger.info("• Comprehensive confidence scoring")
    logger.info("• Data quality assessment")
    logger.info("=" * 60)
    
    server.run(transport="stdio")