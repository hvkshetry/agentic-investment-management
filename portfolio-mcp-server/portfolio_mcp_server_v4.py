#!/usr/bin/env python3
"""
Portfolio MCP Server v4 - Integrated with Portfolio State Server
Uses Portfolio State Server as the source of truth for portfolio data
Implements advanced optimization methods with real portfolio state
"""

from fastmcp import FastMCP, Context
from typing import List, Dict, Optional, Any, Union
import numpy as np
import pandas as pd
import logging
import sys
import os
from datetime import datetime
import warnings
import asyncio
import json
warnings.filterwarnings('ignore')

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
logger = logging.getLogger("portfolio-server-v4")

# Initialize components
server = FastMCP("Portfolio Optimizer v4 - State Integrated")
data_pipeline = MarketDataPipeline()
confidence_scorer = ConfidenceScorer()

# Try to import advanced libraries
try:
    import riskfolio as rp
    RISKFOLIO_AVAILABLE = True
    logger.info("Riskfolio-Lib loaded successfully")
except ImportError:
    RISKFOLIO_AVAILABLE = False
    logger.warning("Riskfolio-Lib not available - install with: pip install Riskfolio-Lib")

try:
    from pypfopt import EfficientFrontier, risk_models, expected_returns
    from pypfopt import HRPOpt, BlackLittermanModel, plotting
    from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices
    PYPFOPT_AVAILABLE = True
    logger.info("PyPortfolioOpt loaded successfully")
except ImportError:
    PYPFOPT_AVAILABLE = False
    logger.warning("PyPortfolioOpt not available - install with: pip install PyPortfolioOpt")

async def get_portfolio_state():
    """Connect to Portfolio State Server and get current portfolio state"""
    try:
        # Read the portfolio state file directly since we're in the same environment
        state_file = "/home/hvksh/investing/portfolio-state-mcp-server/state/portfolio_state.json"
        
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            # Calculate summary statistics
            total_value = 0
            total_cost = 0
            positions = {}
            
            for symbol, lots in state_data.get('tax_lots', {}).items():
                total_quantity = sum(lot['quantity'] for lot in lots)
                total_cost_basis = sum(lot['cost_basis'] for lot in lots)
                # Calculate average cost as proxy for current price (will be updated dynamically)
                current_price = (total_cost_basis / total_quantity) if total_quantity > 0 else 0
                current_value = total_quantity * current_price
                
                total_value += current_value
                total_cost += total_cost_basis
                
                positions[symbol] = {
                    'quantity': total_quantity,
                    'cost_basis': total_cost_basis,
                    'current_value': current_value,
                    'current_price': current_price,
                    'weight': 0  # Will calculate after totals
                }
            
            # Calculate weights
            for symbol in positions:
                positions[symbol]['weight'] = positions[symbol]['current_value'] / total_value if total_value > 0 else 0
            
            return {
                'total_value': total_value,
                'total_cost': total_cost,
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
async def optimize_portfolio_with_state(
    ctx: Context,
    optimization_config: Optional[Dict[str, Any]] = None,
    use_current_portfolio: bool = True,
    additional_tickers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Professional-grade portfolio optimization integrated with Portfolio State.
    Uses current portfolio holdings from Portfolio State Server.
    
    Args:
        optimization_config: Configuration dict with options:
            - lookback_days: int (default 756 for 3 years)
            - risk_measure: str (default 'MV' for variance)
              Options: 'MV', 'CVaR', 'EVaR', 'WR', 'RG', 'CVRG', 'TGRG', 'MDR', 'UCI', 'EDR'
            - optimization_methods: List[str] (default ['HRP', 'Black-Litterman', 'Mean-Risk'])
            - market_views: Dict (for Black-Litterman, optional)
            - confidence_level: float (default 0.95 for CVaR/VaR)
            - risk_free_rate: float (optional, fetched if not provided)
            - constraints: Dict with:
              - min_weight: float (default 0)
              - max_weight: float (default 1)
              - cardinality: int (max number of assets, optional)
              - sectors: Dict[str, List[str]] (sector definitions)
              - sector_limits: Dict[str, float] (sector constraints)
            - rebalance_threshold: float (min change to suggest rebalance, default 0.02)
        use_current_portfolio: bool (default True, use holdings from Portfolio State)
        additional_tickers: List of additional tickers to consider for optimization
    
    Returns:
        Comprehensive optimization results with rebalancing recommendations
    """
    try:
        # Check if required libraries are available
        if not PYPFOPT_AVAILABLE and not RISKFOLIO_AVAILABLE:
            return {
                "error": "Neither PyPortfolioOpt nor Riskfolio-Lib is available",
                "suggestion": "Install with: pip install PyPortfolioOpt Riskfolio-Lib",
                "confidence": 0.0
            }
        
        # Get current portfolio state
        portfolio_state = await get_portfolio_state()
        
        if not portfolio_state and use_current_portfolio:
            return {
                "error": "Unable to read portfolio state",
                "suggestion": "Ensure Portfolio State Server has imported your portfolio data",
                "confidence": 0.0
            }
        
        # Build ticker list
        tickers = []
        current_weights = {}
        
        # Problematic tickers to exclude
        EXCLUDED_TICKERS = ['CASH', 'VMFXX', 'N/A', 'TEST', 'BRKB']  # BRKB has timezone issues, TEST is not real
        
        if use_current_portfolio and portfolio_state:
            # Extract tickers and weights from current portfolio
            for symbol, position in portfolio_state['positions'].items():
                # Skip cash, money market funds, and problematic tickers
                if symbol not in EXCLUDED_TICKERS:
                    tickers.append(symbol)
                    current_weights[symbol] = position['weight']
        
        # Add any additional tickers
        if additional_tickers:
            for ticker in additional_tickers:
                if ticker not in tickers:
                    tickers.append(ticker)
                    current_weights[ticker] = 0.0
        
        if not tickers:
            return {
                "error": "No tickers to optimize",
                "suggestion": "Import portfolio data or provide tickers",
                "confidence": 0.0
            }
        
        # Parse configuration
        config = optimization_config or {}
        lookback_days = config.get('lookback_days', 756)  # 3 years
        risk_measure = config.get('risk_measure', 'MV')
        methods = config.get('optimization_methods', ['HRP', 'Mean-Risk'])
        market_views = config.get('market_views', None)
        confidence_level = config.get('confidence_level', 0.95)
        risk_free_rate = config.get('risk_free_rate', None)
        constraints = config.get('constraints', {})
        rebalance_threshold = config.get('rebalance_threshold', 0.02)
        
        # Fetch real market data
        logger.info(f"Fetching {lookback_days} days of data for {len(tickers)} tickers")
        data = data_pipeline.prepare_for_optimization(tickers, lookback_days)
        prices_df = data['prices']
        returns_df = data['returns']
        
        # Get risk-free rate if needed
        if risk_free_rate is None:
            rf_data = data_pipeline.get_risk_free_rate('10y')
            risk_free_rate = rf_data['rate']
        
        # Initialize result structure
        result = {
            "portfolio_summary": {
                "current_value": portfolio_state['total_value'] if portfolio_state else 0,
                "current_holdings": len(tickers),
                "current_weights": current_weights
            },
            "optimal_portfolios": {},
            "rebalancing_recommendations": {},
            "risk_analytics": {},
            "confidence": {},
            "metadata": {
                "optimization_date": datetime.now().isoformat(),
                "tickers": tickers,
                "lookback_days": lookback_days,
                "risk_free_rate": risk_free_rate
            }
        }
        
        # Run optimizations
        if PYPFOPT_AVAILABLE:
            logger.info("Running PyPortfolioOpt optimizations")
            
            # Calculate expected returns and covariance
            mu = expected_returns.mean_historical_return(prices_df)
            S = risk_models.CovarianceShrinkage(prices_df).ledoit_wolf()
            
            # Store shrinkage intensity
            shrinkage_intensity = S[1] if isinstance(S, tuple) else 0
            S = S[0] if isinstance(S, tuple) else S
            
            # Hierarchical Risk Parity
            if 'HRP' in methods:
                try:
                    hrp = HRPOpt(returns_df)
                    hrp_weights = hrp.optimize()
                    
                    # Clean weights
                    hrp_weights_clean = {k: float(v) for k, v in hrp_weights.items()}
                    
                    # Calculate rebalancing needs
                    rebalancing = {}
                    for ticker in tickers:
                        current = current_weights.get(ticker, 0)
                        optimal = hrp_weights_clean.get(ticker, 0)
                        change = optimal - current
                        
                        if abs(change) > rebalance_threshold:
                            rebalancing[ticker] = {
                                "current_weight": current,
                                "optimal_weight": optimal,
                                "change": change,
                                "action": "BUY" if change > 0 else "SELL",
                                "shares_estimate": int(abs(change) * portfolio_state['total_value'] / 
                                                     prices_df[ticker].iloc[-1]) if portfolio_state else 0
                            }
                    
                    result["optimal_portfolios"]["HRP"] = {
                        "weights": hrp_weights_clean,
                        "method": "Hierarchical Risk Parity",
                        "description": "Diversification without return estimates"
                    }
                    
                    result["rebalancing_recommendations"]["HRP"] = rebalancing
                    
                except Exception as e:
                    logger.error(f"HRP optimization failed: {e}")
            
            # Mean-Variance Optimization
            if 'Mean-Risk' in methods:
                try:
                    ef = EfficientFrontier(mu, S, weight_bounds=(
                        constraints.get('min_weight', 0),
                        constraints.get('max_weight', 1)
                    ))
                    
                    # Add sector constraints if provided
                    if 'sectors' in constraints and 'sector_limits' in constraints:
                        for sector, limit in constraints['sector_limits'].items():
                            sector_tickers = constraints['sectors'].get(sector, [])
                            sector_map = [1 if t in sector_tickers else 0 for t in ef.tickers]
                            ef.add_constraint(lambda w: w @ sector_map <= limit)
                    
                    # Optimize for Sharpe ratio
                    ef.max_sharpe(risk_free_rate=risk_free_rate)
                    sharpe_weights = ef.clean_weights()
                    
                    # Calculate rebalancing needs
                    rebalancing = {}
                    for ticker in tickers:
                        current = current_weights.get(ticker, 0)
                        optimal = sharpe_weights.get(ticker, 0)
                        change = optimal - current
                        
                        if abs(change) > rebalance_threshold:
                            rebalancing[ticker] = {
                                "current_weight": current,
                                "optimal_weight": optimal,
                                "change": change,
                                "action": "BUY" if change > 0 else "SELL",
                                "shares_estimate": int(abs(change) * portfolio_state['total_value'] / 
                                                     prices_df[ticker].iloc[-1]) if portfolio_state else 0
                            }
                    
                    # Get performance metrics
                    expected_return, volatility, sharpe = ef.portfolio_performance(
                        verbose=False, risk_free_rate=risk_free_rate
                    )
                    
                    result["optimal_portfolios"]["MaxSharpe"] = {
                        "weights": sharpe_weights,
                        "expected_return": float(expected_return),
                        "volatility": float(volatility),
                        "sharpe_ratio": float(sharpe),
                        "method": "Mean-Variance (Max Sharpe)",
                        "description": "Maximum risk-adjusted returns"
                    }
                    
                    result["rebalancing_recommendations"]["MaxSharpe"] = rebalancing
                    
                except Exception as e:
                    logger.error(f"Mean-Variance optimization failed: {e}")
        
        # Calculate confidence scores
        result["confidence"] = {
            "data_quality": confidence_scorer.score_data_quality({
                'missing_data_pct': data.get('missing_pct', 0),
                'lookback_days': lookback_days,
                'num_assets': len(tickers)
            }),
            "model_confidence": confidence_scorer.score_model_confidence({
                'libraries_available': int(PYPFOPT_AVAILABLE) + int(RISKFOLIO_AVAILABLE),
                'methods_successful': len(result["optimal_portfolios"]),
                'shrinkage_used': True
            }),
            "overall": 0.0
        }
        
        # Calculate overall confidence
        result["confidence"]["overall"] = np.mean([
            result["confidence"]["data_quality"],
            result["confidence"]["model_confidence"]
        ])
        
        # Add summary recommendations
        result["summary"] = {
            "needs_rebalancing": any(len(r) > 0 for r in result["rebalancing_recommendations"].values()),
            "top_changes": [],
            "estimated_turnover": 0.0
        }
        
        # Find top recommended changes across all methods
        all_changes = {}
        for method, rebalancing in result["rebalancing_recommendations"].items():
            for ticker, change_data in rebalancing.items():
                if ticker not in all_changes:
                    all_changes[ticker] = []
                all_changes[ticker].append(abs(change_data['change']))
        
        # Average changes and sort
        avg_changes = {ticker: np.mean(changes) for ticker, changes in all_changes.items()}
        top_tickers = sorted(avg_changes.items(), key=lambda x: x[1], reverse=True)[:5]
        
        result["summary"]["top_changes"] = [
            {"ticker": ticker, "avg_change": float(change)} 
            for ticker, change in top_tickers
        ]
        
        result["summary"]["estimated_turnover"] = sum(avg_changes.values())
        
        return result
        
    except Exception as e:
        logger.error(f"Portfolio optimization failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

@server.tool()
async def analyze_portfolio_from_state(
    ctx: Context,
    analysis_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Analyze the current portfolio from Portfolio State Server.
    Provides risk metrics, diversification analysis, and performance attribution.
    
    Args:
        analysis_options: Optional configuration:
            - include_correlation: bool (default True)
            - include_var: bool (default True)
            - var_confidence: float (default 0.95)
            - lookback_days: int (default 252)
    
    Returns:
        Comprehensive portfolio analysis
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
        
        config = analysis_options or {}
        lookback_days = config.get('lookback_days', 252)
        include_correlation = config.get('include_correlation', True)
        include_var = config.get('include_var', True)
        var_confidence = config.get('var_confidence', 0.95)
        
        # Extract tickers and weights
        tickers = []
        weights = []
        position_details = []
        
        for symbol, position in portfolio_state['positions'].items():
            if symbol not in ['CASH', 'VMFXX', 'N/A', 'TEST', 'BRKB'] and position['weight'] > 0:
                tickers.append(symbol)
                weights.append(position['weight'])
                position_details.append({
                    'symbol': symbol,
                    'value': position['current_value'],
                    'weight': position['weight'],
                    'cost_basis': position['cost_basis'],
                    'unrealized_gain': position['current_value'] - position['cost_basis']
                })
        
        if not tickers:
            return {
                "error": "No positions found in portfolio",
                "confidence": 0.0
            }
        
        # Fetch market data
        data = data_pipeline.prepare_for_optimization(tickers, lookback_days)
        returns_df = data['returns']
        
        # Calculate portfolio returns
        portfolio_returns = returns_df @ weights
        
        # Basic statistics
        annual_return = portfolio_returns.mean() * 252
        annual_vol = portfolio_returns.std() * np.sqrt(252)
        sharpe_ratio = annual_return / annual_vol if annual_vol > 0 else 0
        
        # Value at Risk
        var_results = {}
        if include_var:
            var_95 = np.percentile(portfolio_returns, (1 - var_confidence) * 100)
            cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()
            
            var_results = {
                "var_daily": float(var_95),
                "var_annual": float(var_95 * np.sqrt(252)),
                "cvar_daily": float(cvar_95),
                "cvar_annual": float(cvar_95 * np.sqrt(252)),
                "confidence_level": var_confidence
            }
        
        # Correlation analysis
        correlation_results = {}
        if include_correlation and len(tickers) > 1:
            corr_matrix = returns_df.corr()
            
            # Find highest correlations
            high_corr_pairs = []
            for i in range(len(tickers)):
                for j in range(i+1, len(tickers)):
                    corr = corr_matrix.iloc[i, j]
                    if abs(corr) > 0.7:  # High correlation threshold
                        high_corr_pairs.append({
                            "pair": f"{tickers[i]}-{tickers[j]}",
                            "correlation": float(corr)
                        })
            
            correlation_results = {
                "average_correlation": float(corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()),
                "high_correlation_pairs": high_corr_pairs,
                "diversification_ratio": float(sum(weights) / np.sqrt(weights @ corr_matrix @ weights))
            }
        
        # Concentration metrics
        weights_array = np.array(weights)
        herfindahl_index = float(np.sum(weights_array ** 2))
        effective_n = 1 / herfindahl_index if herfindahl_index > 0 else 1
        
        result = {
            "portfolio_metrics": {
                "total_value": portfolio_state['total_value'],
                "total_cost": portfolio_state['total_cost'],
                "unrealized_gain": portfolio_state['total_value'] - portfolio_state['total_cost'],
                "unrealized_return": (portfolio_state['total_value'] / portfolio_state['total_cost'] - 1) 
                                   if portfolio_state['total_cost'] > 0 else 0,
                "num_positions": len(tickers),
                "annual_return": float(annual_return),
                "annual_volatility": float(annual_vol),
                "sharpe_ratio": float(sharpe_ratio),
                "max_drawdown": float(calculate_max_drawdown(portfolio_returns))
            },
            "concentration_analysis": {
                "herfindahl_index": herfindahl_index,
                "effective_positions": float(effective_n),
                "top_5_concentration": float(sum(sorted(weights, reverse=True)[:5])),
                "max_position_weight": float(max(weights)),
                "min_position_weight": float(min(weights))
            },
            "risk_metrics": var_results,
            "correlation_analysis": correlation_results,
            "top_positions": sorted(position_details, key=lambda x: x['value'], reverse=True)[:10],
            "confidence": confidence_scorer.score_data_quality({
                'missing_data_pct': data.get('missing_pct', 0),
                'lookback_days': lookback_days,
                'num_assets': len(tickers)
            }),
            "metadata": {
                "analysis_date": datetime.now().isoformat(),
                "portfolio_date": portfolio_state['last_updated'],
                "lookback_days": lookback_days
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Portfolio analysis failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

def calculate_max_drawdown(returns):
    """Calculate maximum drawdown from returns series"""
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()

if __name__ == "__main__":
    server.run()