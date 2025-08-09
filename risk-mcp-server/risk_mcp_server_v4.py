#!/usr/bin/env python3
"""
Risk MCP Server v4 - Integrated with Portfolio State Server
Uses Portfolio State Server for accurate portfolio data
Provides comprehensive risk analysis based on actual holdings
"""

from fastmcp import FastMCP, Context
from typing import Dict, List, Optional, Any
import numpy as np
from scipy import stats
import logging
import sys
import os
from datetime import datetime
import json
import pandas as pd

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'portfolio-state-mcp-server'))

# Import shared modules
from data_pipeline import MarketDataPipeline
from confidence_scoring import ConfidenceScorer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("risk-server-v4")

# Initialize components
server = FastMCP("Risk Analyzer v4 - State Integrated")
data_pipeline = MarketDataPipeline()
confidence_scorer = ConfidenceScorer()

async def get_portfolio_state():
    """Connect to Portfolio State Server and get current portfolio state"""
    try:
        # Read the portfolio state file directly
        state_file = "/home/hvksh/investing/portfolio-state-mcp-server/state/portfolio_state.json"
        
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            # Process tax lots to get positions
            positions = {}
            for symbol, lots in state_data.get('tax_lots', {}).items():
                total_quantity = sum(lot['quantity'] for lot in lots)
                total_cost_basis = sum(lot['cost_basis'] for lot in lots)
                # Calculate average cost as proxy for current price (will be updated dynamically)
                current_price = (total_cost_basis / total_quantity) if total_quantity > 0 else 0
                current_value = total_quantity * current_price
                unrealized_gain = current_value - total_cost_basis
                
                # Separate long-term and short-term gains
                long_term_gain = sum(lot.get('unrealized_gain', 0) for lot in lots if lot.get('is_long_term', False))
                short_term_gain = unrealized_gain - long_term_gain
                
                positions[symbol] = {
                    'quantity': total_quantity,
                    'cost_basis': total_cost_basis,
                    'current_value': current_value,
                    'current_price': current_price,
                    'unrealized_gain': unrealized_gain,
                    'long_term_gain': long_term_gain,
                    'short_term_gain': short_term_gain,
                    'num_lots': len(lots),
                    'asset_type': lots[0].get('asset_type', 'equity') if lots else 'equity'
                }
            
            # Calculate totals
            total_value = sum(p['current_value'] for p in positions.values())
            total_cost = sum(p['cost_basis'] for p in positions.values())
            
            # Add weights
            for symbol in positions:
                positions[symbol]['weight'] = positions[symbol]['current_value'] / total_value if total_value > 0 else 0
            
            return {
                'total_value': total_value,
                'total_cost': total_cost,
                'total_unrealized_gain': total_value - total_cost,
                'positions': positions,
                'accounts': state_data.get('accounts', {}),
                'last_updated': state_data.get('last_updated', '')
            }
        else:
            logger.warning("Portfolio state file not found")
            return None
            
    except Exception as e:
        logger.error(f"Error reading portfolio state: {e}")
        return None

@server.tool()
async def analyze_portfolio_risk_from_state(
    ctx: Context,
    analysis_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Comprehensive portfolio risk analysis using Portfolio State data.
    Analyzes actual portfolio holdings with all risk metrics.
    
    Args:
        analysis_options: Optional dict to customize analysis:
            - periods: int (default 252 trading days)
            - confidence_levels: List[float] (default [0.95, 0.99])
            - risk_metrics: List[str] (specific metrics to calculate)
            - stress_scenarios: bool (default True)
            - correlation_analysis: bool (default True)
            - factor_analysis: bool (default False)
            - monte_carlo_simulations: int (default 1000)
    
    Returns:
        Complete risk analysis based on actual portfolio state
    """
    try:
        # Get current portfolio state
        portfolio_state = await get_portfolio_state()
        
        if not portfolio_state:
            return {
                "error": "Unable to read portfolio state",
                "suggestion": "Ensure Portfolio State Server has imported your portfolio data",
                "confidence": 0.0
            }
        
        # Parse options
        options = analysis_options or {}
        periods = options.get('periods', 252)
        confidence_levels = options.get('confidence_levels', [0.95, 0.99])
        include_stress = options.get('stress_scenarios', True)
        include_correlation = options.get('correlation_analysis', True)
        include_factors = options.get('factor_analysis', False)
        mc_simulations = options.get('monte_carlo_simulations', 1000)
        
        # Extract tickers and weights from portfolio
        tickers = []
        weights = []
        position_risks = {}
        
        # Problematic tickers to exclude
        EXCLUDED_TICKERS = ['CASH', 'VMFXX', 'N/A', 'TEST', 'BRKB']
        
        for symbol, position in portfolio_state['positions'].items():
            if symbol not in EXCLUDED_TICKERS and position['weight'] > 0:
                tickers.append(symbol)
                weights.append(position['weight'])
                
                # Store position-specific risk info
                position_risks[symbol] = {
                    'value': position['current_value'],
                    'weight': position['weight'],
                    'unrealized_gain': position['unrealized_gain'],
                    'unrealized_pct': (position['unrealized_gain'] / position['cost_basis'] * 100) 
                                     if position['cost_basis'] > 0 else 0,
                    'concentration_risk': 'HIGH' if position['weight'] > 0.20 else 
                                        'MEDIUM' if position['weight'] > 0.10 else 'LOW'
                }
        
        if not tickers:
            return {
                "error": "No positions found in portfolio",
                "confidence": 0.0
            }
        
        logger.info(f"Analyzing risk for {len(tickers)} positions from portfolio state")
        
        # Fetch historical data
        data = data_pipeline.prepare_for_risk_analysis(tickers, periods)
        returns = data['returns']
        prices = data['prices']
        
        # Convert weights to numpy array
        weights = np.array(weights)
        
        # Portfolio returns
        portfolio_returns = returns @ weights
        
        # Initialize results
        result = {
            "portfolio_overview": {
                "total_value": portfolio_state['total_value'],
                "total_positions": len(tickers),
                "total_unrealized_gain": portfolio_state['total_unrealized_gain'],
                "unrealized_return_pct": (portfolio_state['total_unrealized_gain'] / 
                                         portfolio_state['total_cost'] * 100) 
                                        if portfolio_state['total_cost'] > 0 else 0
            },
            "risk_metrics": {},
            "var_cvar": {},
            "drawdown_analysis": {},
            "position_risks": position_risks,
            "concentration_risk": {},
            "correlation_risk": {},
            "stress_tests": {},
            "monte_carlo": {},
            "risk_decomposition": {},
            "recommendations": [],
            "confidence": 0.0
        }
        
        # 1. Basic Risk Metrics
        result["risk_metrics"] = {
            "daily_volatility": float(portfolio_returns.std()),
            "annual_volatility": float(portfolio_returns.std() * np.sqrt(252)),
            "daily_return": float(portfolio_returns.mean()),
            "annual_return": float(portfolio_returns.mean() * 252),
            "sharpe_ratio": float(portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)),
            "sortino_ratio": float(calculate_sortino_ratio(portfolio_returns)),
            "calmar_ratio": float(calculate_calmar_ratio(portfolio_returns)),
            "skewness": float(stats.skew(portfolio_returns)),
            "kurtosis": float(stats.kurtosis(portfolio_returns)),
            "downside_deviation": float(calculate_downside_deviation(portfolio_returns))
        }
        
        # 2. Value at Risk and CVaR
        for conf_level in confidence_levels:
            var = np.percentile(portfolio_returns, (1 - conf_level) * 100)
            cvar = portfolio_returns[portfolio_returns <= var].mean()
            
            result["var_cvar"][f"confidence_{int(conf_level*100)}"] = {
                "var_daily": float(var),
                "var_monthly": float(var * np.sqrt(21)),
                "var_annual": float(var * np.sqrt(252)),
                "cvar_daily": float(cvar),
                "cvar_monthly": float(cvar * np.sqrt(21)),
                "cvar_annual": float(cvar * np.sqrt(252)),
                "var_dollar": float(var * portfolio_state['total_value']),
                "cvar_dollar": float(cvar * portfolio_state['total_value'])
            }
        
        # 3. Drawdown Analysis
        cumulative_returns = (1 + portfolio_returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        
        # Calculate average drawdown safely
        negative_drawdowns = drawdown[drawdown < 0]
        avg_drawdown = float(negative_drawdowns.mean()) if not negative_drawdowns.empty else 0.0
        
        result["drawdown_analysis"] = {
            "current_drawdown": float(drawdown.iloc[-1]),
            "max_drawdown": float(drawdown.min()),
            "max_drawdown_dollar": float(drawdown.min() * portfolio_state['total_value']),
            "avg_drawdown": avg_drawdown,
            "drawdown_duration": int(calculate_max_drawdown_duration(drawdown)),
            "recovery_time": calculate_recovery_time(drawdown)
        }
        
        # 4. Concentration Risk
        weights_sorted = sorted(weights, reverse=True)
        herfindahl = np.sum(weights ** 2)
        
        result["concentration_risk"] = {
            "herfindahl_index": float(herfindahl),
            "effective_n": float(1 / herfindahl) if herfindahl > 0 else 1,
            "top_1_weight": float(weights_sorted[0]) if len(weights_sorted) > 0 else 0,
            "top_3_weight": float(sum(weights_sorted[:3])) if len(weights_sorted) >= 3 else float(sum(weights_sorted)),
            "top_5_weight": float(sum(weights_sorted[:5])) if len(weights_sorted) >= 5 else float(sum(weights_sorted)),
            "top_10_weight": float(sum(weights_sorted[:10])) if len(weights_sorted) >= 10 else float(sum(weights_sorted)),
            "concentration_rating": "HIGH" if herfindahl > 0.2 else "MEDIUM" if herfindahl > 0.1 else "LOW"
        }
        
        # 5. Correlation Risk
        if include_correlation and len(tickers) > 1:
            corr_matrix = returns.corr()
            
            # Average correlation
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            avg_correlation = corr_matrix.where(mask).stack().mean()
            
            # Find highly correlated pairs
            high_corr_pairs = []
            for i in range(len(tickers)):
                for j in range(i+1, len(tickers)):
                    corr = corr_matrix.iloc[i, j]
                    if abs(corr) > 0.7:
                        high_corr_pairs.append({
                            "pair": f"{tickers[i]}-{tickers[j]}",
                            "correlation": float(corr),
                            "combined_weight": float(weights[i] + weights[j])
                        })
            
            result["correlation_risk"] = {
                "average_correlation": float(avg_correlation),
                "max_correlation": float(corr_matrix.where(mask).max().max()),
                "min_correlation": float(corr_matrix.where(mask).min().min()),
                "high_correlation_pairs": high_corr_pairs,
                "diversification_ratio": float(calculate_diversification_ratio(weights, corr_matrix.values))
            }
        
        # 6. Stress Testing
        if include_stress:
            stress_scenarios = {
                "market_crash_2008": -0.20,
                "covid_crash_2020": -0.15,
                "dot_com_burst": -0.25,
                "black_monday_1987": -0.22,
                "moderate_correction": -0.10,
                "severe_correction": -0.30
            }
            
            result["stress_tests"] = {}
            for scenario, shock in stress_scenarios.items():
                impact = portfolio_state['total_value'] * shock
                result["stress_tests"][scenario] = {
                    "shock_percent": shock * 100,
                    "portfolio_impact": float(impact),
                    "new_value": float(portfolio_state['total_value'] + impact),
                    "recovery_days_estimate": int(abs(shock) / (result["risk_metrics"]["daily_return"] + 0.0001))
                }
        
        # 7. Monte Carlo Simulation
        if mc_simulations > 0:
            mc_results = run_monte_carlo(portfolio_returns, mc_simulations, 252)
            
            result["monte_carlo"] = {
                "simulations": mc_simulations,
                "one_year_forecast": {
                    "median_return": float(np.median(mc_results)),
                    "mean_return": float(np.mean(mc_results)),
                    "percentile_5": float(np.percentile(mc_results, 5)),
                    "percentile_95": float(np.percentile(mc_results, 95)),
                    "probability_loss": float(np.mean(mc_results < 0)),
                    "probability_gain_10pct": float(np.mean(mc_results > 0.10))
                }
            }
        
        # 8. Risk Decomposition
        marginal_risk = calculate_marginal_risk(returns.values, weights)
        component_risk = marginal_risk * weights
        
        risk_contributions = []
        for i, ticker in enumerate(tickers):
            risk_contributions.append({
                "ticker": ticker,
                "weight": float(weights[i]),
                "marginal_risk": float(marginal_risk[i]),
                "risk_contribution": float(component_risk[i]),
                "risk_contribution_pct": float(component_risk[i] / np.sum(component_risk) * 100)
            })
        
        result["risk_decomposition"] = sorted(risk_contributions, 
                                             key=lambda x: x['risk_contribution'], 
                                             reverse=True)
        
        # 9. Generate Recommendations
        recommendations = []
        
        # Check concentration
        if result["concentration_risk"]["herfindahl_index"] > 0.2:
            recommendations.append({
                "type": "CONCENTRATION",
                "severity": "HIGH",
                "message": "Portfolio is highly concentrated. Consider diversifying.",
                "action": f"Top position represents {result['concentration_risk']['top_1_weight']*100:.1f}% of portfolio"
            })
        
        # Check correlation
        if result.get("correlation_risk", {}).get("high_correlation_pairs"):
            recommendations.append({
                "type": "CORRELATION",
                "severity": "MEDIUM",
                "message": f"Found {len(result['correlation_risk']['high_correlation_pairs'])} highly correlated position pairs",
                "action": "Consider reducing positions with correlation > 0.7"
            })
        
        # Check drawdown
        if result["drawdown_analysis"]["current_drawdown"] < -0.10:
            recommendations.append({
                "type": "DRAWDOWN",
                "severity": "HIGH",
                "message": f"Portfolio in significant drawdown: {result['drawdown_analysis']['current_drawdown']*100:.1f}%",
                "action": "Review stop-loss levels and consider rebalancing"
            })
        
        # Check volatility
        if result["risk_metrics"]["annual_volatility"] > 0.25:
            recommendations.append({
                "type": "VOLATILITY",
                "severity": "MEDIUM",
                "message": f"High portfolio volatility: {result['risk_metrics']['annual_volatility']*100:.1f}% annualized",
                "action": "Consider adding low-volatility assets or bonds"
            })
        
        result["recommendations"] = recommendations
        
        # Calculate confidence score
        result["confidence"] = confidence_scorer.score_risk_analysis({
            'data_points': len(portfolio_returns),
            'missing_data': data.get('missing_pct', 0),
            'num_assets': len(tickers),
            'lookback_periods': periods
        })
        
        # Add metadata
        result["metadata"] = {
            "analysis_date": datetime.now().isoformat(),
            "portfolio_date": portfolio_state['last_updated'],
            "data_periods": periods,
            "tickers_analyzed": tickers
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Risk analysis failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

@server.tool()
async def calculate_position_risk(
    ctx: Context,
    symbol: str,
    analysis_depth: str = "detailed"
) -> Dict[str, Any]:
    """
    Analyze risk for a specific position in the portfolio.
    
    Args:
        symbol: Ticker symbol to analyze
        analysis_depth: 'basic' or 'detailed'
    
    Returns:
        Position-specific risk metrics
    """
    try:
        # Get portfolio state
        portfolio_state = await get_portfolio_state()
        
        if not portfolio_state:
            return {
                "error": "Unable to read portfolio state",
                "confidence": 0.0
            }
        
        if symbol not in portfolio_state['positions']:
            return {
                "error": f"Position {symbol} not found in portfolio",
                "available_positions": list(portfolio_state['positions'].keys()),
                "confidence": 0.0
            }
        
        position = portfolio_state['positions'][symbol]
        
        # Fetch historical data for the position
        data = data_pipeline.prepare_for_risk_analysis([symbol], 252)
        returns_data = data['returns']
        
        # Handle both DataFrame and Series returns
        if isinstance(returns_data, pd.DataFrame):
            if symbol in returns_data.columns:
                returns = returns_data[symbol]
            else:
                # Single column DataFrame
                returns = returns_data.squeeze()
        elif isinstance(returns_data, pd.Series):
            returns = returns_data
        elif isinstance(returns_data, dict):
            returns = returns_data.get(symbol)
        else:
            raise ValueError(f"Unexpected returns data type: {type(returns_data)}")
        
        # Validate we have data
        if returns is None or (hasattr(returns, 'empty') and returns.empty):
            raise ValueError(f"No returns data available for {symbol}")
        
        # Calculate metrics safely
        daily_vol = float(returns.std())
        mean_return = float(returns.mean())
        
        # Calculate position-specific metrics
        result = {
            "position_summary": {
                "symbol": symbol,
                "current_value": position['current_value'],
                "portfolio_weight": position['weight'],
                "cost_basis": position['cost_basis'],
                "unrealized_gain": position['unrealized_gain'],
                "unrealized_return": (position['unrealized_gain'] / position['cost_basis']) 
                                   if position['cost_basis'] > 0 else 0
            },
            "risk_metrics": {
                "daily_volatility": daily_vol,
                "annual_volatility": daily_vol * np.sqrt(252),
                "beta": calculate_position_beta(returns, data),
                "var_95": float(np.percentile(returns, 5)),
                "cvar_95": float(calculate_cvar(returns, 5)),
                "max_drawdown": float(calculate_position_drawdown(returns)),
                "sharpe_ratio": (mean_return / daily_vol * np.sqrt(252)) if daily_vol > 0 else 0
            },
            "contribution_to_portfolio_risk": {
                "risk_contribution": position['weight'] * float(returns.std()),
                "diversification_benefit": calculate_diversification_benefit(symbol, portfolio_state)
            }
        }
        
        if analysis_depth == "detailed":
            # Add more detailed analysis
            result["detailed_analysis"] = {
                "rolling_volatility": calculate_rolling_volatility(returns),
                "regime_analysis": analyze_market_regimes(returns),
                "tail_risk": analyze_tail_risk(returns)
            }
        
        result["confidence"] = confidence_scorer.score_data_quality({
            'missing_data_pct': data.get('missing_pct', 0),
            'lookback_days': 252,
            'num_assets': 1
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Position risk analysis failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

# Helper functions
def calculate_sortino_ratio(returns, target_return=0):
    """Calculate Sortino ratio"""
    excess_returns = returns - target_return
    downside_returns = excess_returns[excess_returns < 0]
    downside_deviation = np.sqrt(np.mean(downside_returns**2)) if len(downside_returns) > 0 else 0.0001
    return np.mean(excess_returns) / downside_deviation * np.sqrt(252)

def calculate_calmar_ratio(returns):
    """Calculate Calmar ratio"""
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = abs(drawdown.min())
    annual_return = returns.mean() * 252
    return annual_return / max_dd if max_dd > 0 else 0

def calculate_downside_deviation(returns, target_return=0):
    """Calculate downside deviation"""
    downside_returns = returns[returns < target_return]
    return np.sqrt(np.mean((downside_returns - target_return)**2)) if len(downside_returns) > 0 else 0

def calculate_max_drawdown_duration(drawdown):
    """Calculate maximum drawdown duration in days"""
    underwater = drawdown < 0
    runs = underwater.ne(underwater.shift()).cumsum()
    run_lengths = underwater.groupby(runs).sum()
    return run_lengths.max() if len(run_lengths) > 0 else 0

def calculate_recovery_time(drawdown):
    """Calculate average recovery time from drawdowns"""
    # This is simplified - would need more complex logic for actual recovery times
    return "N/A"  # Placeholder

def calculate_diversification_ratio(weights, corr_matrix):
    """Calculate diversification ratio"""
    weighted_avg_vol = np.sum(weights * np.sqrt(np.diag(corr_matrix)))
    portfolio_vol = np.sqrt(weights @ corr_matrix @ weights)
    return weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 1

def run_monte_carlo(returns, num_simulations, num_periods):
    """Run Monte Carlo simulation"""
    mean_return = returns.mean()
    std_return = returns.std()
    
    simulated_returns = []
    for _ in range(num_simulations):
        sim = np.random.normal(mean_return, std_return, num_periods)
        final_return = np.prod(1 + sim) - 1
        simulated_returns.append(final_return)
    
    return np.array(simulated_returns)

def calculate_marginal_risk(returns, weights):
    """Calculate marginal risk contribution"""
    cov_matrix = np.cov(returns.T)
    portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
    marginal_risk = (cov_matrix @ weights) / portfolio_vol if portfolio_vol > 0 else np.zeros_like(weights)
    return marginal_risk

def calculate_beta(asset_returns, market_returns):
    """Calculate beta relative to market"""
    if market_returns is None:
        return None
    
    # Convert to numpy arrays if they're pandas Series
    if hasattr(asset_returns, 'values'):
        asset_returns = asset_returns.values.flatten()
    else:
        asset_returns = np.array(asset_returns).flatten()
        
    if hasattr(market_returns, 'values'):
        market_returns = market_returns.values.flatten()
    else:
        market_returns = np.array(market_returns).flatten()
    
    # Ensure same length by trimming to minimum
    min_len = min(len(asset_returns), len(market_returns))
    if min_len < 2:
        return None
    
    asset_returns = asset_returns[:min_len]
    market_returns = market_returns[:min_len]
    
    covariance = np.cov(asset_returns, market_returns)[0, 1]
    market_variance = np.var(market_returns)
    return float(covariance / market_variance) if market_variance > 0 else 0.0

def calculate_cvar(returns, percentile):
    """Calculate Conditional Value at Risk (CVaR)"""
    if hasattr(returns, 'values'):
        # It's a pandas Series - convert to numpy array
        returns_array = returns.values.flatten()
    else:
        # It's already a numpy array
        returns_array = np.array(returns).flatten()
    
    # Calculate VaR threshold
    var_threshold = np.percentile(returns_array, percentile)
    
    # Get tail returns (values below VaR threshold)
    tail_returns = returns_array[returns_array <= var_threshold]
    
    if len(tail_returns) > 0:
        return float(tail_returns.mean())
    else:
        return 0.0

def calculate_position_beta(returns, data):
    """Calculate beta for a position, handling DataFrame benchmark returns"""
    try:
        if 'benchmark_returns' not in data:
            return None
        
        benchmark = data.get('benchmark_returns')
        
        # If benchmark is a DataFrame, extract SPY column
        if hasattr(benchmark, 'columns'):
            if 'SPY' in benchmark.columns:
                benchmark = benchmark['SPY']
            else:
                # Use first column if SPY not available
                benchmark = benchmark.iloc[:, 0]
        
        return calculate_beta(returns, benchmark)
    except Exception as e:
        logger.warning(f"Failed to calculate beta: {e}")
        return None

def calculate_position_drawdown(returns):
    """Calculate max drawdown for a position"""
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()

def calculate_diversification_benefit(symbol, portfolio_state):
    """Calculate diversification benefit of a position"""
    # Simplified calculation
    return "Calculation pending"

def calculate_rolling_volatility(returns, window=30):
    """Calculate rolling volatility"""
    return {
        "30_day": float(returns.rolling(window=30).std().iloc[-1]) if len(returns) > 30 else None,
        "60_day": float(returns.rolling(window=60).std().iloc[-1]) if len(returns) > 60 else None,
        "90_day": float(returns.rolling(window=90).std().iloc[-1]) if len(returns) > 90 else None
    }

def analyze_market_regimes(returns):
    """Analyze market regimes"""
    # Simplified regime analysis
    recent_vol = returns.tail(30).std()
    historical_vol = returns.std()
    
    if recent_vol > historical_vol * 1.5:
        regime = "High Volatility"
    elif recent_vol < historical_vol * 0.5:
        regime = "Low Volatility"
    else:
        regime = "Normal"
    
    return {
        "current_regime": regime,
        "recent_volatility": float(recent_vol),
        "historical_volatility": float(historical_vol)
    }

def analyze_tail_risk(returns):
    """Analyze tail risk"""
    left_tail = np.percentile(returns, 5)
    right_tail = np.percentile(returns, 95)
    
    return {
        "left_tail_5pct": float(left_tail),
        "right_tail_95pct": float(right_tail),
        "tail_ratio": float(abs(right_tail / left_tail)) if left_tail != 0 else None
    }

if __name__ == "__main__":
    server.run()