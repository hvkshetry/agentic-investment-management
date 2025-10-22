#!/usr/bin/env python3
"""
Tax Optimization MCP Server - Integrates Oracle with Portfolio State
Provides intelligent tax-aware portfolio optimization and rebalancing
"""

from fastmcp import FastMCP, Context
from typing import Dict, List, Optional, Any, Union
import logging
import sys
import os
from datetime import datetime, timedelta
import json
import pandas as pd
import numpy as np
import pulp

# Add required paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared', 'services'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'portfolio-state-mcp-server'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'oracle'))

# Import Oracle components
try:
    from src.service.oracle import Oracle
    from src.service.oracle_strategy import OracleStrategy
    from src.service.helpers.enums import OracleOptimizationType
    ORACLE_AVAILABLE = True
except ImportError as e:
    ORACLE_AVAILABLE = False
    logger.error(f"Oracle import error: {e}")

# Import confidence scoring and shared services
from confidence_scoring import ConfidenceScorer
from tax_rate_service import get_tax_rate_service
from portfolio_value_service import get_portfolio_value_service
from correlation_service import get_correlation_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("tax-optimization-server")

# Initialize components
server = FastMCP("Tax Optimization Server - Oracle Powered")
confidence_scorer = ConfidenceScorer()
tax_rate_service = get_tax_rate_service()
portfolio_value_service = get_portfolio_value_service()
correlation_service = get_correlation_service()

def get_tax_lots_by_symbol(portfolio_state):
    """Helper to get tax lots grouped by symbol from portfolio state"""
    tax_lots_data = portfolio_state.get('tax_lots', [])
    
    # If it's already a dict, return it
    if isinstance(tax_lots_data, dict):
        return tax_lots_data
    
    # If it's a list, group by symbol
    tax_lots_by_symbol = {}
    if isinstance(tax_lots_data, list):
        for lot in tax_lots_data:
            symbol = lot.get('symbol')
            if symbol:
                if symbol not in tax_lots_by_symbol:
                    tax_lots_by_symbol[symbol] = []
                tax_lots_by_symbol[symbol].append(lot)
    
    return tax_lots_by_symbol

def get_helpful_portfolio_missing_error():
    """Generate a helpful error message when portfolio state is missing"""
    default_path = os.path.join(os.path.dirname(__file__), '..', 'portfolio-state-mcp-server', 'state', 'portfolio_state.json')
    state_file = os.getenv('PORTFOLIO_STATE_PATH', default_path)

    return {
        "error": "Portfolio state not found",
        "details": f"No portfolio data file found at: {state_file}",
        "possible_causes": [
            "Portfolio has not been imported yet",
            "Portfolio state file was deleted or moved",
            "PORTFOLIO_STATE_PATH environment variable points to wrong location"
        ],
        "suggested_actions": [
            "Import portfolio data using: /import-portfolio command",
            "Or use portfolio-state-server to import broker CSV",
            "Or verify PORTFOLIO_STATE_PATH environment variable"
        ],
        "next_steps": "Run '/import-portfolio' to import your portfolio from a broker CSV file",
        "confidence": 0.0
    }

async def get_portfolio_state():
    """Read portfolio state directly from JSON file with calculated fields"""
    import json
    from datetime import datetime

    try:
        # Read the portfolio state file - use environment variable or relative path
        default_path = os.path.join(os.path.dirname(__file__), '..', 'portfolio-state-mcp-server', 'state', 'portfolio_state.json')
        state_file = os.getenv('PORTFOLIO_STATE_PATH', default_path)

        with open(state_file, 'r') as f:
            data = json.load(f)

        # Calculate enriched fields if not present
        if 'total_value' not in data:
            data['total_value'] = sum(p.get('current_value', 0) for p in data.get('positions', []))

        if 'total_unrealized_gain' not in data:
            total_unrealized = 0
            for position in data.get('positions', []):
                if 'unrealized_gain' in position:
                    total_unrealized += position['unrealized_gain']
            data['total_unrealized_gain'] = total_unrealized

        # Add confidence score for compatibility
        data['confidence'] = 0.95

        logger.info(f"Successfully loaded portfolio state with {len(data.get('positions', []))} positions")
        return data

    except FileNotFoundError:
        logger.error(f"Portfolio state file not found at expected location")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing portfolio state JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading portfolio state: {e}")
        return None

def convert_portfolio_state_to_oracle_format(portfolio_state, current_prices=None):
    """Convert Portfolio State format to Oracle format"""
    
    # Extract tax lots
    tax_lots_list = []
    tax_lots_by_symbol = get_tax_lots_by_symbol(portfolio_state)
    for symbol, lots in tax_lots_by_symbol.items():
        for lot in lots:
            tax_lots_list.append({
                'tax_lot_id': lot['lot_id'],
                'identifier': symbol,
                'quantity': lot['quantity'],
                'cost_basis': lot['cost_basis'] / lot['quantity'] if lot['quantity'] > 0 else 0,
                'date': lot['purchase_date']
            })
    
    tax_lots_df = pd.DataFrame(tax_lots_list)
    
    # Extract unique symbols and their current prices
    symbols = list(tax_lots_by_symbol.keys())
    prices_list = []
    
    for symbol in symbols:
        if symbol in ['CASH', 'VMFXX', 'N/A']:
            continue
            
        # Get price from provided prices or calculate from cost basis
        if current_prices and symbol in current_prices:
            price = current_prices[symbol]
        else:
            lots = tax_lots_by_symbol.get(symbol, [])
            # Calculate average price from cost basis
            total_qty = sum(lot['quantity'] for lot in lots)
            total_cost = sum(lot['cost_basis'] for lot in lots)
            price = (total_cost / total_qty) if total_qty > 0 else 0
        
        prices_list.append({
            'identifier': symbol,
            'price': price
        })
    
    prices_df = pd.DataFrame(prices_list)
    
    # Calculate current portfolio value and weights for targets
    total_value = 0
    position_values = {}
    
    tax_lots_by_symbol = get_tax_lots_by_symbol(portfolio_state)
    for symbol, lots in tax_lots_by_symbol.items():
        if symbol in ['CASH', 'VMFXX', 'N/A']:
            continue
        
        total_quantity = sum(lot['quantity'] for lot in lots)
        # Calculate average price from cost basis
        total_cost = sum(lot['cost_basis'] for lot in lots)
        current_price = (total_cost / total_quantity) if total_quantity > 0 else 0
        position_value = total_quantity * current_price
        
        position_values[symbol] = position_value
        total_value += position_value
    
    # Create targets based on current allocations (maintain current weights)
    targets_list = []
    total_weight = 0
    
    for symbol, value in position_values.items():
        weight = value / total_value if total_value > 0 else 0
        targets_list.append({
            'asset_class': symbol,
            'target_weight': weight,
            'identifiers': [symbol]
        })
        total_weight += weight
    
    # Add cash target to make weights sum to 1.0
    cash_weight = max(0, 1.0 - total_weight)
    if cash_weight > 0:
        targets_list.append({
            'asset_class': 'CASH',
            'target_weight': cash_weight,
            'identifiers': ['CASH']
        })
    
    targets_df = pd.DataFrame(targets_list)
    
    # Check if there's CASH in the tax lots
    cash_lots = tax_lots_by_symbol.get('CASH', [])
    if cash_lots:
        cash = sum(lot.get('cost_basis', 0) for lot in cash_lots)
    else:
        # No explicit cash position - log warning but use 0
        logger.warning("No CASH position found in portfolio - using 0 cash for optimization")
        cash = 0.0
    
    return tax_lots_df, prices_df, targets_df, cash

@server.tool()
async def optimize_portfolio_for_taxes(
    ctx: Context,
    optimization_goal: str = "tax_aware_rebalance",
    target_allocations: Dict[str, float] = {},
    optimization_settings: Dict[str, Any] = {},
    withdrawal_amount: float = 0.0
) -> Dict[str, Any]:
    """
    Optimize portfolio using Oracle for tax-aware rebalancing and TLH.
    
    Args:
        optimization_goal: Type of optimization
            - "tax_aware_rebalance": Rebalance with tax considerations
            - "tax_loss_harvest": Focus on harvesting losses
            - "direct_index": Direct indexing strategy
            - "minimize_taxes": Minimize tax impact
            - "withdrawal": Optimize withdrawal for taxes
        target_allocations: Target weights by symbol (pass {} for defaults)
        optimization_settings: Oracle optimization parameters (pass {} for defaults)
        withdrawal_amount: Amount to withdraw (if any)
    
    Returns:
        Optimal trades with tax implications
    """
    try:
        if not ORACLE_AVAILABLE:
            return {
                "error": "Oracle not available",
                "suggestion": "Ensure Oracle is properly installed",
                "confidence": 0.0
            }
        
        # Get portfolio state
        portfolio_state = await get_portfolio_state()

        if not portfolio_state:
            return get_helpful_portfolio_missing_error()
        
        # Get tax lots grouped by symbol
        tax_lots_by_symbol = get_tax_lots_by_symbol(portfolio_state)
        
        # Convert to Oracle format
        tax_lots_df, prices_df, targets_df, cash = convert_portfolio_state_to_oracle_format(
            portfolio_state
        )
        
        # Override targets if provided
        if target_allocations:
            targets_list = []
            for symbol, weight in target_allocations.items():
                targets_list.append({
                    'asset_class': symbol,
                    'target_weight': weight,
                    'identifiers': [symbol]
                })
            targets_df = pd.DataFrame(targets_list)
        
        # Determine optimization type
        optimization_type_map = {
            "tax_aware_rebalance": OracleOptimizationType.TAX_AWARE,
            "tax_loss_harvest": OracleOptimizationType.PAIRS_TLH,
            "direct_index": OracleOptimizationType.DIRECT_INDEX,
            "minimize_taxes": OracleOptimizationType.TAX_AWARE,
            "withdrawal": OracleOptimizationType.TAX_AWARE,
            "buy_only": OracleOptimizationType.BUY_ONLY,
            "hold": OracleOptimizationType.HOLD
        }
        
        optimization_type = optimization_type_map.get(
            optimization_goal, 
            OracleOptimizationType.TAX_AWARE
        )
        
        # Create Oracle instance (expects datetime.date, not string)
        current_date = datetime.now().date()
        
        # Create tax rates DataFrame using TaxRateService
        # Get representative income (use portfolio value as proxy)
        portfolio_value = portfolio_value_service.get_portfolio_total_value(portfolio_state)
        representative_income = portfolio_value * 0.04  # Assume 4% withdrawal rate
        
        # Get actual tax rates from service
        st_federal = tax_rate_service.get_capital_gains_rate(representative_income, "Single", is_long_term=False)
        lt_federal = tax_rate_service.get_capital_gains_rate(representative_income, "Single", is_long_term=True)
        state_rate = tax_rate_service.get_state_rate(representative_income, "CA", "Single")  # Default to CA
        niit_rate = tax_rate_service.get_niit_rate(representative_income, "Single")
        
        tax_rates_df = pd.DataFrame({
            'gain_type': ['short_term', 'long_term', 'qualified_dividend'],
            'federal_rate': [st_federal, lt_federal, lt_federal],  # Qualified dividends taxed as LTCG
            'state_rate': [state_rate, state_rate, state_rate],
            'total_rate': [
                st_federal + state_rate + niit_rate,
                lt_federal + state_rate + niit_rate,
                lt_federal + state_rate + niit_rate
            ]
        })
        
        oracle = Oracle(
            current_date=current_date,
            recently_closed_lots=pd.DataFrame(),
            stock_restrictions=pd.DataFrame(),
            tax_rates=tax_rates_df
        )
        
        # Create strategy
        strategy = OracleStrategy(
            tax_lots=tax_lots_df,
            prices=prices_df,
            cash=cash,
            targets=targets_df,
            strategy_id="PORTFOLIO_1",
            optimization_type=optimization_type,
            deminimus_cash_target=0.01,  # 1% cash target
            withdrawal_amount=withdrawal_amount,
            enforce_wash_sale_prevention=True
        )
        
        # Add strategy to Oracle (Oracle expects a list of strategies)
        oracle.strategies = [strategy]
        strategy.set_oracle(oracle)
        
        # Initialize wash sale restrictions
        oracle.initialize_wash_sale_restrictions(
            percentage_protection_from_inadvertent_wash_sales=0.003
        )
        
        # Default optimization settings
        default_settings = {
            "weight_tax": 1.0,
            "weight_drift": 1.0,
            "weight_transaction": 0.1,
            "weight_factor_model": 0.0,
            "weight_cash_drag": 1.0,
            "rebalance_threshold": 0.005,  # 0.5% threshold
            "buy_threshold": 0.0025,
            "holding_time_days": 0,
            "should_tlh": True,
            "tlh_min_loss_threshold": 0.015,  # 1.5% loss threshold
            "range_min_weight_multiplier": 0.5,
            "range_max_weight_multiplier": 2.0,
            "min_notional": 10,  # $10 minimum trade
            "rank_penalty_factor": 0.0,
            "trade_rounding": 2
        }
        
        # Adjust settings based on goal
        if optimization_goal == "tax_loss_harvest":
            default_settings["weight_tax"] = 2.0
            default_settings["weight_drift"] = 0.1
            default_settings["tlh_min_loss_threshold"] = 0.01  # Lower threshold
        elif optimization_goal == "minimize_taxes":
            default_settings["weight_tax"] = 3.0
            default_settings["weight_drift"] = 0.5
        elif optimization_goal == "withdrawal":
            default_settings["weight_tax"] = 2.0
            default_settings["weight_cash_drag"] = 0.0
        
        # Merge with user settings
        if optimization_settings:
            default_settings.update(optimization_settings)
        
        # Run optimization
        results, netted_trades = oracle.compute_optimal_trades_for_all_strategies(
            settings={
                "strategies": {
                    "PORTFOLIO_1": default_settings
                }
            }
        )
        
        # Process results
        strategy_result = results.get("PORTFOLIO_1", (None, False, {}, pd.DataFrame()))
        
        # Unpack the tuple result
        if isinstance(strategy_result, tuple):
            status, should_trade, trade_summary, trades = strategy_result
        else:
            # Fallback if format is different
            status = strategy_result.get("status", None)
            should_trade = strategy_result.get("should_trade", False)
            trade_summary = strategy_result.get("trade_summary", {})
            trades = strategy_result.get("trades", pd.DataFrame())
        
        if not should_trade:
            # Calculate total value from tax_lots_by_symbol
            total_value = sum(lot['quantity'] * (lot['cost_basis']/lot['quantity'] if lot['quantity'] > 0 else 0) 
                            for lots in tax_lots_by_symbol.values() for lot in lots)
            
            return {
                "optimization_status": "NO_TRADES_NEEDED",
                "message": "Portfolio is already optimally positioned",
                "current_state": {
                    "total_value": total_value,
                    "num_positions": len(tax_lots_by_symbol)
                },
                "confidence": 0.95
            }
        
        # Format trades for output
        formatted_trades = []
        total_tax_impact = 0
        total_proceeds = 0
        total_cost = 0
        
        # Convert DataFrame trades to list of dicts if needed
        if isinstance(trades, pd.DataFrame):
            trade_list = trades.to_dict('records') if not trades.empty else []
        else:
            trade_list = trades if trades else []
        
        for trade in trade_list:
            trade_type = trade.get("trade_type", "")
            quantity = trade.get("quantity", 0)
            identifier = trade.get("identifier", "")
            
            # Get current price
            price = prices_df[prices_df['identifier'] == identifier]['price'].iloc[0] if not prices_df.empty else 0
            
            # Calculate trade value
            trade_value = abs(quantity * price)
            
            # Estimate tax impact for sells
            tax_impact = 0
            if trade_type == "SELL" and "tax_lot_id" in trade:
                # Find the lot being sold
                lot_info = tax_lots_df[tax_lots_df['tax_lot_id'] == trade['tax_lot_id']].iloc[0]
                gain = (price - lot_info['cost_basis']) * quantity
                
                # Check if long-term or short-term
                purchase_date = pd.to_datetime(lot_info['date'])
                days_held = (pd.Timestamp.now() - purchase_date).days
                is_long_term = days_held > 365
                
                # Use actual tax rates from service
                portfolio_value = portfolio_value_service.get_portfolio_total_value(portfolio_state)
                representative_income = portfolio_value * 0.04
                
                tax_estimate = tax_rate_service.estimate_tax_on_sale(
                    gain=gain,
                    income=representative_income,
                    filing_status="Single",
                    state="CA",
                    is_long_term=is_long_term
                )
                tax_impact = tax_estimate['total_tax']
                
                total_tax_impact += tax_impact
                total_proceeds += trade_value
            else:
                total_cost += trade_value
            
            formatted_trades.append({
                "symbol": identifier,
                "action": trade_type,
                "quantity": abs(quantity),
                "estimated_value": trade_value,
                "tax_impact": tax_impact,
                "tax_lot_id": trade.get("tax_lot_id", "N/A")
            })
        
        # Trade summary is already unpacked above
        
        result = {
            "optimization_status": "SUCCESS",
            "optimization_goal": optimization_goal,
            "trades_recommended": len(formatted_trades),
            "trades": formatted_trades,
            "summary": {
                "total_buy_value": total_cost,
                "total_sell_value": total_proceeds,
                "net_cash_flow": total_proceeds - total_cost,
                "estimated_tax_impact": total_tax_impact,
                "effective_tax_rate": (total_tax_impact / total_proceeds * 100) if total_proceeds > 0 else 0
            },
            "oracle_metrics": {
                "tax_cost": trade_summary.get("tax_cost", 0),
                "drift_cost": trade_summary.get("drift_cost", 0),
                "spread_costs": trade_summary.get("spread_costs", 0),
                "overall_cost": trade_summary.get("overall", 0)
            },
            "netted_trades": [
                {
                    "symbol": trade.get("identifier"),
                    "net_quantity": trade.get("quantity"),
                    "action": "BUY" if trade.get("quantity", 0) > 0 else "SELL"
                }
                for trade in netted_trades
            ],
            "confidence": 0.92,
            "metadata": {
                "optimization_date": datetime.now().isoformat(),
                "oracle_status": pulp.LpStatus[status] if status is not None else "Unknown",
                "settings_used": default_settings
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Portfolio optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "confidence": 0.0
        }

@server.tool()
async def find_tax_loss_harvesting_pairs(
    ctx: Context,
    correlation_threshold: float = 0.95,
    min_loss_threshold: float = 100.0
) -> Dict[str, Any]:
    """
    Find tax loss harvesting pairs in the portfolio.
    Identifies correlated assets that can be swapped for TLH.
    
    Args:
        correlation_threshold: Minimum correlation to consider as a pair
        min_loss_threshold: Minimum loss amount to consider
    
    Returns:
        TLH pair recommendations
    """
    try:
        # Get portfolio state
        portfolio_state = await get_portfolio_state()

        if not portfolio_state:
            return get_helpful_portfolio_missing_error()
        
        # Find positions with losses
        loss_positions = []
        
        # Get tax lots - handle both dict and list formats
        tax_lots_data = portfolio_state.get('tax_lots', [])
        
        # If it's a list, group by symbol
        tax_lots_by_symbol = {}
        if isinstance(tax_lots_data, list):
            for lot in tax_lots_data:
                symbol = lot.get('symbol')
                if symbol:
                    if symbol not in tax_lots_by_symbol:
                        tax_lots_by_symbol[symbol] = []
                    tax_lots_by_symbol[symbol].append(lot)
        elif isinstance(tax_lots_data, dict):
            tax_lots_by_symbol = tax_lots_data
        
        for symbol, lots in tax_lots_by_symbol.items():
            # Calculate total unrealized gain/loss for this position
            total_quantity = sum(lot['quantity'] for lot in lots)
            total_cost_basis = sum(lot['cost_basis'] for lot in lots)
            
            # Skip if no quantity
            if total_quantity == 0:
                continue
            
            # Check if positions data has unrealized gains calculated
            positions = portfolio_state.get('positions', [])
            position_data = None
            for pos in positions:
                if isinstance(pos, dict) and pos.get('symbol') == symbol:
                    position_data = pos
                    break
            
            # Use position data if available, otherwise aggregate from lots
            if position_data and 'unrealized_gain' in position_data:
                unrealized_gain = position_data['unrealized_gain']
            else:
                # Aggregate unrealized gains from individual lots
                unrealized_gain = sum(lot.get('unrealized_gain', 0) for lot in lots)
            
            # Only add if there's a loss greater than threshold
            if unrealized_gain < -min_loss_threshold:
                loss_positions.append({
                    'symbol': symbol,
                    'unrealized_loss': abs(unrealized_gain),
                    'cost_basis': total_cost_basis,
                    'quantity': total_quantity,
                    'asset_type': lots[0].get('asset_type', 'equity') if lots else 'equity'
                })
        
        # Define common TLH pairs (ETFs that track similar indices)
        common_pairs = {
            'VOO': ['SPY', 'IVV'],  # S&P 500 ETFs
            'SPY': ['VOO', 'IVV'],
            'IVV': ['VOO', 'SPY'],
            'VTI': ['ITOT', 'SCHB'],  # Total market ETFs
            'ITOT': ['VTI', 'SCHB'],
            'SCHB': ['VTI', 'ITOT'],
            'VEA': ['IEFA', 'SCHF'],  # International developed
            'IEFA': ['VEA', 'SCHF'],
            'SCHF': ['VEA', 'IEFA'],
            'VWO': ['IEMG', 'EEM'],  # Emerging markets
            'IEMG': ['VWO', 'EEM'],
            'EEM': ['VWO', 'IEMG'],
            'QQQ': ['QQQM', 'ONEQ'],  # Nasdaq 100
            'DIA': ['MDY', 'RSP'],  # Large cap alternatives
            'VIG': ['SCHD', 'DVY'],  # Dividend ETFs
            'SCHD': ['VIG', 'DVY'],
        }
        
        # Find TLH opportunities
        tlh_opportunities = []
        
        for position in loss_positions:
            symbol = position['symbol']
            
            # Check if we have known pairs
            if symbol in common_pairs:
                for alternative in common_pairs[symbol]:
                    # Check if we don't already own the alternative
                    if alternative not in portfolio_state.get('tax_lots', {}):
                        tlh_opportunities.append({
                            'current_holding': symbol,
                            'suggested_replacement': alternative,
                            'unrealized_loss': position['unrealized_loss'],
                            'tax_benefit_estimate': position['unrealized_loss'] * tax_rate_service.get_capital_gains_rate(
                                portfolio_value_service.get_portfolio_total_value(portfolio_state) * 0.04,
                                "Single",
                                is_long_term=False
                            ),
                            'asset_type': position['asset_type'],
                            'correlation_estimate': 0.98  # Default high correlation for known ETF pairs
                        })
        
        # Sort by tax benefit
        tlh_opportunities.sort(key=lambda x: x['tax_benefit_estimate'], reverse=True)
        
        # Calculate total harvesting potential
        total_losses = sum(p['unrealized_loss'] for p in loss_positions)
        # Use actual tax rate for benefit calculation
        portfolio_value = portfolio_value_service.get_portfolio_total_value(portfolio_state)
        representative_income = portfolio_value * 0.04
        avg_tax_rate = tax_rate_service.get_combined_capital_gains_rate(
            representative_income, "Single", "CA", is_long_term=False
        )
        total_tax_benefit = total_losses * avg_tax_rate
        
        result = {
            "tlh_summary": {
                "positions_with_losses": len(loss_positions),
                "total_harvestable_losses": total_losses,
                "estimated_tax_savings": total_tax_benefit,
                "opportunities_found": len(tlh_opportunities)
            },
            "loss_positions": loss_positions[:10],  # Top 10
            "tlh_pairs": tlh_opportunities[:10],  # Top 10 opportunities
            "recommendations": [],
            "warnings": [],
            "confidence": 0.88
        }
        
        # Add recommendations
        if tlh_opportunities:
            result["recommendations"].append({
                "action": "Execute Tax Loss Harvesting",
                "priority": "HIGH" if total_losses > 5000 else "MEDIUM",
                "description": f"Harvest ${total_losses:,.0f} in losses for ${total_tax_benefit:,.0f} tax savings",
                "top_swaps": [
                    f"Swap {opp['current_holding']} for {opp['suggested_replacement']}"
                    for opp in tlh_opportunities[:3]
                ]
            })
        
        # Add wash sale warning
        result["warnings"].append({
            "type": "WASH_SALE",
            "message": "Ensure 31+ days between selling and repurchasing substantially identical securities",
            "affected_symbols": [p['symbol'] for p in loss_positions[:5]]
        })
        
        return result
        
    except Exception as e:
        logger.error(f"TLH pair finding failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

@server.tool()
async def simulate_withdrawal_tax_impact(
    ctx: Context,
    withdrawal_amount: float,
    optimization_method: str = "minimize_tax"
) -> Dict[str, Any]:
    """
    Simulate the tax impact of different withdrawal strategies.
    
    Args:
        withdrawal_amount: Amount to withdraw from portfolio
        optimization_method: Method for withdrawal
            - "minimize_tax": Minimize tax impact
            - "proportional": Sell proportionally
            - "harvest_losses": Prioritize loss harvesting
            - "long_term_only": Only sell long-term holdings
    
    Returns:
        Withdrawal simulation with tax implications
    """
    try:
        # Get portfolio state
        portfolio_state = await get_portfolio_state()

        if not portfolio_state:
            return get_helpful_portfolio_missing_error()
        
        # Calculate total portfolio value using PortfolioValueService
        total_value = portfolio_value_service.get_portfolio_total_value(portfolio_state)
        
        if withdrawal_amount > total_value * 0.95:
            return {
                "error": f"Withdrawal amount ${withdrawal_amount:,.0f} exceeds 95% of portfolio value ${total_value:,.0f}",
                "confidence": 0.0
            }
        
        # Prepare for Oracle optimization
        if ORACLE_AVAILABLE:
            # Note: Can't call other tools from within a tool directly
            # Would need to refactor to use shared functions
            # For now, skip Oracle optimization in withdrawal simulation
            pass
        
        # Fallback: Simple withdrawal simulation
        withdrawal_trades = []
        remaining_amount = withdrawal_amount
        total_tax = 0
        
        # Sort lots based on method
        all_lots = []
        tax_lots_by_symbol = get_tax_lots_by_symbol(portfolio_state)
        for symbol, lots in tax_lots_by_symbol.items():
            for lot in lots:
                lot['symbol'] = symbol
                all_lots.append(lot)
        
        if optimization_method == "minimize_tax":
            # Prefer long-term gains and losses
            all_lots.sort(key=lambda x: (
                not x.get('is_long_term', False),
                x.get('unrealized_gain', 0)
            ))
        elif optimization_method == "harvest_losses":
            # Sell losses first
            all_lots.sort(key=lambda x: x.get('unrealized_gain', 0))
        elif optimization_method == "long_term_only":
            # Only long-term holdings
            all_lots = [lot for lot in all_lots if lot.get('is_long_term', False)]
            all_lots.sort(key=lambda x: x.get('unrealized_gain', 0))
        else:  # proportional
            # Sort by value
            all_lots.sort(key=lambda x: x.get('current_value', 0), reverse=True)
        
        # Simulate sales
        for lot in all_lots:
            if remaining_amount <= 0:
                break
            
            # Calculate lot value using PortfolioValueService
            try:
                lot_value = portfolio_value_service.get_lot_current_value(lot)
            except ValueError:
                # If we can't get current value, skip this lot
                logger.warning(f"Could not get value for lot {lot.get('lot_id')}")
                continue
            
            if lot_value <= 0:
                continue
            
            # Determine how much to sell
            sell_value = min(lot_value, remaining_amount)
            sell_ratio = sell_value / lot_value
            
            # Calculate actual gain using PortfolioValueService
            gain = portfolio_value_service.get_lot_unrealized_gain(lot) * sell_ratio
            
            # Calculate tax using actual rates from TaxRateService
            representative_income = total_value * 0.04
            tax_estimate = tax_rate_service.estimate_tax_on_sale(
                gain=gain,
                income=representative_income,
                filing_status="Single",
                state="CA",
                is_long_term=lot.get('is_long_term', False)
            )
            tax = tax_estimate['total_tax']
            
            withdrawal_trades.append({
                'symbol': lot['symbol'],
                'lot_id': lot['lot_id'],
                'sell_value': sell_value,
                'gain_loss': gain,
                'tax': tax,
                'is_long_term': lot.get('is_long_term', False),
                'effective_tax_rate': (tax / gain * 100) if gain > 0 else 0
            })
            
            total_tax += tax
            remaining_amount -= sell_value
        
        result = {
            "withdrawal_summary": {
                "requested_amount": withdrawal_amount,
                "achievable_amount": withdrawal_amount - remaining_amount,
                "withdrawal_pct": (withdrawal_amount / total_value * 100),
                "optimization_method": optimization_method
            },
            "withdrawal_trades": withdrawal_trades[:20],  # Top 20 trades
            "tax_implications": {
                "estimated_tax": total_tax,
                "effective_tax_rate": (total_tax / (withdrawal_amount - remaining_amount) * 100) if (withdrawal_amount - remaining_amount) > 0 else 0,
                "after_tax_proceeds": (withdrawal_amount - remaining_amount) - total_tax,
                "federal_portion": total_tax * 0.7,  # Rough estimate
                "state_portion": total_tax * 0.25,
                "niit_portion": total_tax * 0.05
            },
            "comparison": {
                "method_used": optimization_method,
                "tax_cost": total_tax,
                "trades_required": len(withdrawal_trades)
            },
            "confidence": 0.85
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Withdrawal simulation failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

if __name__ == "__main__":
    server.run()