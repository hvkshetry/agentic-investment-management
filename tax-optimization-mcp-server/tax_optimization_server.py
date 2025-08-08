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

# Add required paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))
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
    print(f"Oracle import error: {e}")

# Import confidence scoring
from confidence_scoring import ConfidenceScorer

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

async def get_portfolio_state():
    """Connect to Portfolio State Server and get current portfolio state with tax lots"""
    try:
        state_file = "/home/hvksh/investing/portfolio-state-mcp-server/state/portfolio_state.json"
        
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            return state_data
        else:
            logger.warning("Portfolio state file not found")
            return None
            
    except Exception as e:
        logger.error(f"Error reading portfolio state: {e}")
        return None

def convert_portfolio_state_to_oracle_format(portfolio_state, current_prices=None):
    """Convert Portfolio State format to Oracle format"""
    
    # Extract tax lots
    tax_lots_list = []
    for symbol, lots in portfolio_state.get('tax_lots', {}).items():
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
    symbols = list(portfolio_state.get('tax_lots', {}).keys())
    prices_list = []
    
    for symbol in symbols:
        if symbol in ['CASH', 'VMFXX', 'N/A']:
            continue
            
        # Get price from first lot or use provided prices
        if current_prices and symbol in current_prices:
            price = current_prices[symbol]
        else:
            lots = portfolio_state['tax_lots'][symbol]
            price = lots[0]['current_price'] if lots else 0
        
        prices_list.append({
            'identifier': symbol,
            'price': price
        })
    
    prices_df = pd.DataFrame(prices_list)
    
    # Calculate current portfolio value and weights for targets
    total_value = 0
    position_values = {}
    
    for symbol, lots in portfolio_state.get('tax_lots', {}).items():
        if symbol in ['CASH', 'VMFXX', 'N/A']:
            continue
        
        total_quantity = sum(lot['quantity'] for lot in lots)
        current_price = lots[0]['current_price'] if lots else 0
        position_value = total_quantity * current_price
        
        position_values[symbol] = position_value
        total_value += position_value
    
    # Create targets based on current allocations (maintain current weights)
    targets_list = []
    for symbol, value in position_values.items():
        weight = value / total_value if total_value > 0 else 0
        targets_list.append({
            'asset_class': symbol,
            'target_weight': weight,
            'identifiers': [symbol]
        })
    
    # Add cash target if needed
    targets_list.append({
        'asset_class': 'CASH',
        'target_weight': 0.01,  # 1% cash target
        'identifiers': ['CASH']
    })
    
    targets_df = pd.DataFrame(targets_list)
    
    # Calculate current cash (simplified - would need actual cash balance)
    cash = 10000.0  # Default cash amount
    
    return tax_lots_df, prices_df, targets_df, cash

@server.tool()
async def optimize_portfolio_for_taxes(
    ctx: Context,
    optimization_goal: str = "tax_aware_rebalance",
    target_allocations: Optional[Dict[str, float]] = None,
    optimization_settings: Optional[Dict[str, Any]] = None,
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
        target_allocations: Optional target weights by symbol
        optimization_settings: Oracle optimization parameters
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
            return {
                "error": "Unable to read portfolio state",
                "confidence": 0.0
            }
        
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
        
        # Create Oracle instance
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Create tax rates DataFrame with required columns
        tax_rates_df = pd.DataFrame({
            'gain_type': ['short_term', 'long_term'],
            'federal_rate': [0.25, 0.15],
            'state_rate': [0.05, 0.05],  # Simplified state rates
            'total_rate': [0.30, 0.20]  # Combined federal + state
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
        
        # Add strategy to Oracle
        oracle.strategies = {"PORTFOLIO_1": strategy}
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
        strategy_result = results.get("PORTFOLIO_1", {})
        
        if not strategy_result.get("should_trade", False):
            return {
                "optimization_status": "NO_TRADES_NEEDED",
                "message": "Portfolio is already optimally positioned",
                "current_state": {
                    "total_value": sum(lot['current_value'] for lots in portfolio_state['tax_lots'].values() for lot in lots),
                    "num_positions": len(portfolio_state['tax_lots'])
                },
                "confidence": 0.95
            }
        
        # Format trades for output
        formatted_trades = []
        total_tax_impact = 0
        total_proceeds = 0
        total_cost = 0
        
        for trade in strategy_result.get("trades", []):
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
                
                if days_held > 365:
                    tax_impact = gain * 0.15  # Long-term rate
                else:
                    tax_impact = gain * 0.25  # Short-term rate
                
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
        
        # Get trade summary
        trade_summary = strategy_result.get("trade_summary", {})
        
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
                "oracle_status": strategy_result.get("status", "Unknown"),
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
            return {
                "error": "Unable to read portfolio state",
                "confidence": 0.0
            }
        
        # Find positions with losses
        loss_positions = []
        
        for symbol, lots in portfolio_state.get('tax_lots', {}).items():
            total_loss = sum(lot.get('unrealized_gain', 0) for lot in lots if lot.get('unrealized_gain', 0) < 0)
            
            if abs(total_loss) >= min_loss_threshold:
                loss_positions.append({
                    'symbol': symbol,
                    'unrealized_loss': abs(total_loss),
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
                            'tax_benefit_estimate': position['unrealized_loss'] * 0.25,
                            'asset_type': position['asset_type'],
                            'correlation_estimate': 0.98  # High correlation for index ETFs
                        })
        
        # Sort by tax benefit
        tlh_opportunities.sort(key=lambda x: x['tax_benefit_estimate'], reverse=True)
        
        # Calculate total harvesting potential
        total_losses = sum(p['unrealized_loss'] for p in loss_positions)
        total_tax_benefit = total_losses * 0.25  # Rough estimate
        
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
            return {
                "error": "Unable to read portfolio state",
                "confidence": 0.0
            }
        
        # Calculate total portfolio value
        total_value = 0
        for symbol, lots in portfolio_state.get('tax_lots', {}).items():
            for lot in lots:
                total_value += lot.get('current_value', 0)
        
        if withdrawal_amount > total_value * 0.95:
            return {
                "error": f"Withdrawal amount ${withdrawal_amount:,.0f} exceeds 95% of portfolio value ${total_value:,.0f}",
                "confidence": 0.0
            }
        
        # Prepare for Oracle optimization
        if ORACLE_AVAILABLE:
            # Use Oracle for optimal withdrawal
            optimization_settings = {
                "weight_tax": 3.0 if optimization_method == "minimize_tax" else 1.0,
                "weight_drift": 0.5,
                "weight_transaction": 0.1,
                "should_tlh": optimization_method == "harvest_losses",
                "tlh_min_loss_threshold": 0.01 if optimization_method == "harvest_losses" else 0.02
            }
            
            # Call the tool properly using the context
            result_data = await optimize_portfolio_for_taxes(
                ctx,
                optimization_goal="withdrawal",
                withdrawal_amount=withdrawal_amount,
                optimization_settings=optimization_settings
            )
            oracle_result = result_data
            
            if "error" not in oracle_result:
                return {
                    "withdrawal_summary": {
                        "requested_amount": withdrawal_amount,
                        "withdrawal_pct": (withdrawal_amount / total_value * 100),
                        "optimization_method": optimization_method
                    },
                    "oracle_optimization": oracle_result,
                    "tax_implications": {
                        "estimated_tax": oracle_result['summary']['estimated_tax_impact'],
                        "effective_rate": oracle_result['summary']['effective_tax_rate'],
                        "after_tax_proceeds": withdrawal_amount - oracle_result['summary']['estimated_tax_impact']
                    },
                    "confidence": oracle_result.get('confidence', 0.9)
                }
        
        # Fallback: Simple withdrawal simulation
        withdrawal_trades = []
        remaining_amount = withdrawal_amount
        total_tax = 0
        
        # Sort lots based on method
        all_lots = []
        for symbol, lots in portfolio_state.get('tax_lots', {}).items():
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
            
            lot_value = lot.get('current_value', 0)
            if lot_value <= 0:
                continue
            
            # Determine how much to sell
            sell_value = min(lot_value, remaining_amount)
            sell_ratio = sell_value / lot_value
            
            # Calculate tax
            gain = lot.get('unrealized_gain', 0) * sell_ratio
            if lot.get('is_long_term', False):
                tax = max(0, gain * 0.15)
            else:
                tax = max(0, gain * 0.25)
            
            withdrawal_trades.append({
                'symbol': lot['symbol'],
                'lot_id': lot['lot_id'],
                'sell_value': sell_value,
                'gain_loss': gain,
                'tax': tax,
                'is_long_term': lot.get('is_long_term', False)
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
                "total_tax": total_tax,
                "effective_tax_rate": (total_tax / withdrawal_amount * 100) if withdrawal_amount > 0 else 0,
                "after_tax_proceeds": withdrawal_amount - total_tax
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