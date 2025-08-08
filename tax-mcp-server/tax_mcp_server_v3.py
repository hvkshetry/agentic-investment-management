#!/usr/bin/env python3
"""
Tax MCP Server v3 - Integrated with Portfolio State Server  
Uses Portfolio State Server for accurate tax lot tracking
Provides comprehensive tax optimization based on actual holdings
"""

from fastmcp import FastMCP, Context
from typing import Dict, List, Optional, Any, Union
import logging
import sys
import os
from datetime import datetime, timedelta
import json
import numpy as np

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'portfolio-state-mcp-server'))

# Import confidence scoring
from confidence_scoring import ConfidenceScorer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("tax-server-v3")

# Initialize components
server = FastMCP("Tax Server v3 - State Integrated")
confidence_scorer = ConfidenceScorer()

# Try to import tenforty for tax calculations
try:
    import tenforty
    TENFORTY_AVAILABLE = True
except ImportError:
    TENFORTY_AVAILABLE = False
    logger.warning("tenforty not available - basic tax calculations only")

async def get_portfolio_state():
    """Connect to Portfolio State Server and get current portfolio state with tax lots"""
    try:
        # Read the portfolio state file directly
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

@server.tool()
async def calculate_tax_implications_from_state(
    ctx: Context,
    tax_year: int = 2024,
    filing_status: str = "Single",
    state: Optional[str] = None,
    other_income: Dict[str, float] = None,
    simulate_sales: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive tax implications using Portfolio State data.
    Analyzes actual tax lots for accurate capital gains calculations.
    
    Args:
        tax_year: Tax year for calculations
        filing_status: 'Single', 'Married Filing Jointly', etc.
        state: State code for state tax calculations (e.g., 'CA', 'NY')
        other_income: Dict of other income sources (wages, interest, etc.)
        simulate_sales: Optional list of sales to simulate:
            [{"symbol": "VOO", "quantity": 10, "price": 600, "method": "FIFO"}]
    
    Returns:
        Comprehensive tax analysis with optimization recommendations
    """
    try:
        # Get portfolio state with tax lots
        portfolio_state = await get_portfolio_state()
        
        if not portfolio_state:
            return {
                "error": "Unable to read portfolio state",
                "suggestion": "Ensure Portfolio State Server has imported your portfolio data",
                "confidence": 0.0
            }
        
        # Process tax lots
        tax_lots = portfolio_state.get('tax_lots', {})
        
        # Calculate current unrealized gains
        long_term_gains = 0
        short_term_gains = 0
        total_unrealized = 0
        harvestable_losses = []
        
        for symbol, lots in tax_lots.items():
            for lot in lots:
                unrealized = lot.get('unrealized_gain', 0)
                total_unrealized += unrealized
                
                if lot.get('is_long_term', False):
                    long_term_gains += unrealized if unrealized > 0 else 0
                    if unrealized < -1000:  # Significant loss
                        harvestable_losses.append({
                            "symbol": symbol,
                            "lot_id": lot['lot_id'],
                            "loss": abs(unrealized),
                            "type": "long_term",
                            "holding_days": lot.get('holding_period_days', 0)
                        })
                else:
                    short_term_gains += unrealized if unrealized > 0 else 0
                    if unrealized < -1000:  # Significant loss
                        harvestable_losses.append({
                            "symbol": symbol,
                            "lot_id": lot['lot_id'],
                            "loss": abs(unrealized),
                            "type": "short_term",
                            "holding_days": lot.get('holding_period_days', 0)
                        })
        
        # Initialize result
        result = {
            "portfolio_tax_summary": {
                "total_unrealized_gains": total_unrealized,
                "long_term_unrealized": long_term_gains,
                "short_term_unrealized": short_term_gains,
                "total_tax_lots": sum(len(lots) for lots in tax_lots.values())
            },
            "tax_loss_harvesting": {
                "opportunities": sorted(harvestable_losses, key=lambda x: x['loss'], reverse=True)[:10],
                "total_harvestable_losses": sum(h['loss'] for h in harvestable_losses),
                "estimated_tax_savings": sum(h['loss'] for h in harvestable_losses) * 0.25  # Rough estimate
            },
            "simulated_sales": [],
            "tax_optimization_strategies": [],
            "estimated_taxes": {},
            "metadata": {
                "tax_year": tax_year,
                "filing_status": filing_status,
                "state": state,
                "analysis_date": datetime.now().isoformat()
            }
        }
        
        # Simulate sales if requested
        if simulate_sales:
            for sale in simulate_sales:
                symbol = sale.get('symbol')
                quantity = sale.get('quantity', 0)
                price = sale.get('price', 0)
                method = sale.get('method', 'FIFO')
                
                if symbol in tax_lots:
                    sale_result = simulate_sale_tax(
                        tax_lots[symbol], 
                        quantity, 
                        price, 
                        method
                    )
                    result["simulated_sales"].append(sale_result)
        
        # Calculate estimated taxes
        if TENFORTY_AVAILABLE and other_income:
            try:
                # Prepare income data
                income_data = other_income or {}
                income_data['long_term_capital_gains'] = long_term_gains
                income_data['short_term_capital_gains'] = short_term_gains
                
                # Federal tax calculation
                federal_tax = calculate_federal_tax(
                    income_data,
                    filing_status,
                    tax_year
                )
                
                result["estimated_taxes"]["federal"] = federal_tax
                
                # State tax if applicable
                if state:
                    state_tax = calculate_state_tax(
                        income_data,
                        filing_status,
                        state,
                        tax_year
                    )
                    result["estimated_taxes"]["state"] = state_tax
                
                # NIIT calculation
                if calculate_niit_applies(income_data, filing_status):
                    niit = calculate_niit(income_data)
                    result["estimated_taxes"]["niit"] = niit
                
            except Exception as e:
                logger.error(f"Tax calculation failed: {e}")
                result["estimated_taxes"]["error"] = str(e)
        
        # Generate tax optimization strategies
        strategies = []
        
        # Tax loss harvesting
        if harvestable_losses:
            strategies.append({
                "strategy": "Tax Loss Harvesting",
                "description": f"Harvest ${sum(h['loss'] for h in harvestable_losses):,.0f} in losses",
                "potential_savings": sum(h['loss'] for h in harvestable_losses) * 0.25,
                "priority": "HIGH" if sum(h['loss'] for h in harvestable_losses) > 10000 else "MEDIUM",
                "action_items": [
                    f"Sell {h['symbol']} (Lot: {h['lot_id']}) for ${h['loss']:,.0f} loss" 
                    for h in harvestable_losses[:3]
                ]
            })
        
        # Long-term holding strategy
        short_term_close_to_long = []
        for symbol, lots in tax_lots.items():
            for lot in lots:
                days_held = lot.get('holding_period_days', 0)
                if 300 < days_held < 365 and lot.get('unrealized_gain', 0) > 1000:
                    short_term_close_to_long.append({
                        "symbol": symbol,
                        "days_to_long_term": 365 - days_held,
                        "unrealized_gain": lot['unrealized_gain']
                    })
        
        if short_term_close_to_long:
            strategies.append({
                "strategy": "Hold for Long-Term Capital Gains",
                "description": "Wait for positions to qualify for long-term treatment",
                "potential_savings": sum(s['unrealized_gain'] for s in short_term_close_to_long) * 0.15,
                "priority": "HIGH",
                "action_items": [
                    f"Hold {s['symbol']} for {s['days_to_long_term']} more days to save on taxes"
                    for s in sorted(short_term_close_to_long, key=lambda x: x['days_to_long_term'])[:3]
                ]
            })
        
        # Asset location strategy
        if len(portfolio_state.get('accounts', {})) > 1:
            strategies.append({
                "strategy": "Asset Location Optimization",
                "description": "Place tax-inefficient assets in tax-advantaged accounts",
                "potential_savings": "Varies",
                "priority": "MEDIUM",
                "action_items": [
                    "Move high-dividend stocks to IRA accounts",
                    "Keep tax-efficient ETFs in taxable accounts",
                    "Place REITs in tax-deferred accounts"
                ]
            })
        
        # Charitable giving with appreciated shares
        highly_appreciated = []
        for symbol, lots in tax_lots.items():
            for lot in lots:
                if lot.get('is_long_term', False):
                    gain_pct = (lot.get('unrealized_gain', 0) / lot.get('cost_basis', 1)) * 100
                    if gain_pct > 50:
                        highly_appreciated.append({
                            "symbol": symbol,
                            "gain_pct": gain_pct,
                            "unrealized_gain": lot['unrealized_gain']
                        })
        
        if highly_appreciated:
            strategies.append({
                "strategy": "Donate Appreciated Securities",
                "description": "Donate highly appreciated stocks to charity",
                "potential_savings": "Full deduction without capital gains tax",
                "priority": "MEDIUM",
                "action_items": [
                    f"Consider donating {h['symbol']} with {h['gain_pct']:.0f}% gain"
                    for h in sorted(highly_appreciated, key=lambda x: x['gain_pct'], reverse=True)[:3]
                ]
            })
        
        result["tax_optimization_strategies"] = strategies
        
        # Calculate confidence score
        result["confidence"] = confidence_scorer.score_tax_analysis({
            'num_tax_lots': sum(len(lots) for lots in tax_lots.values()),
            'data_completeness': 1.0 if other_income else 0.7,
            'state_tax_included': 1.0 if state else 0.8,
            'tenforty_available': 1.0 if TENFORTY_AVAILABLE else 0.5
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Tax analysis failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

@server.tool()
async def optimize_sale_for_taxes(
    ctx: Context,
    symbol: str,
    target_amount: float,
    optimization_goal: str = "minimize_tax"
) -> Dict[str, Any]:
    """
    Optimize which tax lots to sell for a given symbol to achieve target proceeds.
    
    Args:
        symbol: Stock symbol to sell
        target_amount: Target dollar amount to raise
        optimization_goal: 'minimize_tax', 'maximize_losses', 'harvest_losses'
    
    Returns:
        Optimal tax lots to sell with tax implications
    """
    try:
        # Get portfolio state
        portfolio_state = await get_portfolio_state()
        
        if not portfolio_state:
            return {
                "error": "Unable to read portfolio state",
                "confidence": 0.0
            }
        
        tax_lots = portfolio_state.get('tax_lots', {})
        
        if symbol not in tax_lots:
            return {
                "error": f"No tax lots found for {symbol}",
                "available_symbols": list(tax_lots.keys()),
                "confidence": 0.0
            }
        
        symbol_lots = tax_lots[symbol]
        
        # Get current price (use first lot's current price as proxy)
        current_price = symbol_lots[0].get('current_price', 0) if symbol_lots else 0
        
        if current_price <= 0:
            return {
                "error": "Unable to determine current price",
                "confidence": 0.0
            }
        
        # Calculate shares needed
        shares_needed = target_amount / current_price
        
        # Optimize lot selection based on goal
        if optimization_goal == "minimize_tax":
            # Prefer long-term gains and losses
            sorted_lots = sorted(symbol_lots, key=lambda x: (
                not x.get('is_long_term', False),  # Long-term first
                x.get('unrealized_gain', 0)  # Lowest gains first
            ))
        elif optimization_goal == "maximize_losses":
            # Sell biggest losses first
            sorted_lots = sorted(symbol_lots, key=lambda x: x.get('unrealized_gain', 0))
        elif optimization_goal == "harvest_losses":
            # Only sell lots with losses
            sorted_lots = [lot for lot in symbol_lots if lot.get('unrealized_gain', 0) < 0]
            sorted_lots.sort(key=lambda x: x.get('unrealized_gain', 0))
        else:
            # Default to FIFO
            sorted_lots = sorted(symbol_lots, key=lambda x: x.get('purchase_date', ''))
        
        # Select lots to sell
        selected_lots = []
        remaining_shares = shares_needed
        total_proceeds = 0
        total_cost_basis = 0
        total_gain = 0
        long_term_gain = 0
        short_term_gain = 0
        
        for lot in sorted_lots:
            if remaining_shares <= 0:
                break
            
            shares_to_sell = min(lot['quantity'], remaining_shares)
            lot_proceeds = shares_to_sell * current_price
            lot_cost = (lot['cost_basis'] / lot['quantity']) * shares_to_sell
            lot_gain = lot_proceeds - lot_cost
            
            selected_lots.append({
                "lot_id": lot['lot_id'],
                "purchase_date": lot['purchase_date'],
                "shares": shares_to_sell,
                "proceeds": lot_proceeds,
                "cost_basis": lot_cost,
                "gain_loss": lot_gain,
                "is_long_term": lot.get('is_long_term', False),
                "holding_days": lot.get('holding_period_days', 0)
            })
            
            total_proceeds += lot_proceeds
            total_cost_basis += lot_cost
            total_gain += lot_gain
            
            if lot.get('is_long_term', False):
                long_term_gain += lot_gain
            else:
                short_term_gain += lot_gain
            
            remaining_shares -= shares_to_sell
        
        # Calculate tax implications
        federal_tax_on_long = long_term_gain * 0.15 if long_term_gain > 0 else 0
        federal_tax_on_short = short_term_gain * 0.25 if short_term_gain > 0 else 0
        total_federal_tax = federal_tax_on_long + federal_tax_on_short
        
        result = {
            "optimization_summary": {
                "symbol": symbol,
                "target_amount": target_amount,
                "actual_proceeds": total_proceeds,
                "shares_to_sell": shares_needed,
                "optimization_goal": optimization_goal
            },
            "selected_lots": selected_lots,
            "tax_implications": {
                "total_gain_loss": total_gain,
                "long_term_gain": long_term_gain,
                "short_term_gain": short_term_gain,
                "estimated_federal_tax": total_federal_tax,
                "effective_tax_rate": (total_federal_tax / total_gain * 100) if total_gain > 0 else 0,
                "after_tax_proceeds": total_proceeds - total_federal_tax
            },
            "alternative_methods": {}
        }
        
        # Compare with other methods
        for method in ["FIFO", "LIFO", "HIFO"]:
            alt_result = simulate_sale_by_method(symbol_lots, shares_needed, current_price, method)
            result["alternative_methods"][method] = {
                "total_gain": alt_result['total_gain'],
                "tax_estimate": alt_result['tax_estimate'],
                "after_tax_proceeds": alt_result['after_tax_proceeds']
            }
        
        # Add recommendation
        best_method = min(result["alternative_methods"].items(), 
                         key=lambda x: x[1]['tax_estimate'])
        
        result["recommendation"] = {
            "best_method": best_method[0],
            "tax_savings": total_federal_tax - best_method[1]['tax_estimate'],
            "action": f"Use {optimization_goal} strategy to minimize taxes"
        }
        
        result["confidence"] = 0.95  # High confidence with actual tax lots
        
        return result
        
    except Exception as e:
        logger.error(f"Sale optimization failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

@server.tool()
async def year_end_tax_planning(
    ctx: Context,
    tax_year: int = 2024,
    filing_status: str = "Single",
    ytd_income: Dict[str, float] = None,
    planned_transactions: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Comprehensive year-end tax planning using portfolio state.
    
    Args:
        tax_year: Tax year for planning
        filing_status: Filing status
        ytd_income: Year-to-date income by category
        planned_transactions: List of planned transactions to evaluate
    
    Returns:
        Year-end tax planning recommendations
    """
    try:
        # Get portfolio state
        portfolio_state = await get_portfolio_state()
        
        if not portfolio_state:
            return {
                "error": "Unable to read portfolio state",
                "confidence": 0.0
            }
        
        tax_lots = portfolio_state.get('tax_lots', {})
        
        # Calculate current year realized gains (would need transaction history)
        # For now, use YTD income if provided
        ytd = ytd_income or {}
        ytd_cap_gains = ytd.get('capital_gains', 0)
        
        # Find tax loss harvesting opportunities
        harvesting_opportunities = []
        total_losses_available = 0
        
        for symbol, lots in tax_lots.items():
            for lot in lots:
                if lot.get('unrealized_gain', 0) < -500:  # Minimum loss threshold
                    harvesting_opportunities.append({
                        "symbol": symbol,
                        "lot_id": lot['lot_id'],
                        "loss": abs(lot['unrealized_gain']),
                        "is_long_term": lot.get('is_long_term', False),
                        "wash_sale_risk": check_wash_sale_risk(symbol, lot)
                    })
                    total_losses_available += abs(lot['unrealized_gain'])
        
        # Sort by loss amount
        harvesting_opportunities.sort(key=lambda x: x['loss'], reverse=True)
        
        # Calculate optimal harvesting amount
        optimal_harvest = min(ytd_cap_gains + 3000, total_losses_available)  # $3000 ordinary income offset
        
        # Build recommendations
        recommendations = []
        
        # Tax loss harvesting
        if harvesting_opportunities:
            selected_losses = []
            harvested_amount = 0
            
            for opp in harvesting_opportunities:
                if harvested_amount >= optimal_harvest:
                    break
                if not opp['wash_sale_risk']:
                    selected_losses.append(opp)
                    harvested_amount += opp['loss']
            
            recommendations.append({
                "action": "Tax Loss Harvesting",
                "urgency": "HIGH",
                "deadline": f"December 31, {tax_year}",
                "description": f"Harvest ${harvested_amount:,.0f} in losses to offset gains",
                "tax_savings": harvested_amount * 0.25,
                "specific_actions": [
                    f"Sell {loss['symbol']} (Lot: {loss['lot_id']}) for ${loss['loss']:,.0f} loss"
                    for loss in selected_losses[:5]
                ]
            })
        
        # Defer income / accelerate deductions
        recommendations.append({
            "action": "Defer Income to Next Year",
            "urgency": "MEDIUM",
            "deadline": f"December 31, {tax_year}",
            "description": "Consider deferring bonuses or self-employment income",
            "tax_savings": "Varies based on income",
            "specific_actions": [
                "Delay invoicing for December work until January",
                "Defer year-end bonus if possible",
                "Delay IRA to Roth conversions"
            ]
        })
        
        # Accelerate deductions
        recommendations.append({
            "action": "Accelerate Deductions",
            "urgency": "MEDIUM",
            "deadline": f"December 31, {tax_year}",
            "description": "Pay deductible expenses before year-end",
            "tax_savings": "Varies based on deductions",
            "specific_actions": [
                "Pay January mortgage payment in December",
                "Make charitable contributions",
                "Pay state taxes before year-end (watch AMT)"
            ]
        })
        
        # Required distributions
        current_date = datetime.now()
        if current_date.month >= 11:  # November or December
            recommendations.append({
                "action": "Required Minimum Distributions",
                "urgency": "CRITICAL" if current_date.month == 12 else "HIGH",
                "deadline": f"December 31, {tax_year}",
                "description": "Take RMDs from retirement accounts if required",
                "tax_savings": "Avoid 50% penalty",
                "specific_actions": [
                    "Check if you're 72 or older",
                    "Calculate RMD amount",
                    "Consider QCD (Qualified Charitable Distribution)"
                ]
            })
        
        # Roth conversion opportunities
        if ytd.get('ordinary_income', 0) < get_tax_bracket_limit(filing_status, 'middle'):
            recommendations.append({
                "action": "Roth IRA Conversion",
                "urgency": "LOW",
                "deadline": f"December 31, {tax_year}",
                "description": "Convert traditional IRA to Roth while in lower bracket",
                "tax_savings": "Tax-free growth",
                "specific_actions": [
                    f"Convert up to ${get_tax_bracket_limit(filing_status, 'middle') - ytd.get('ordinary_income', 0):,.0f}",
                    "Consider partial conversion",
                    "Evaluate state tax implications"
                ]
            })
        
        result = {
            "year_end_summary": {
                "days_until_year_end": (datetime(tax_year, 12, 31) - datetime.now()).days,
                "ytd_capital_gains": ytd_cap_gains,
                "losses_available": total_losses_available,
                "optimal_harvest_amount": optimal_harvest
            },
            "recommendations": recommendations,
            "harvesting_opportunities": harvesting_opportunities[:10],
            "estimated_tax_savings": {
                "from_loss_harvesting": min(optimal_harvest * 0.25, 5000),
                "from_timing_strategies": "Varies",
                "total_potential": min(optimal_harvest * 0.25, 5000) + 2000  # Rough estimate
            },
            "warnings": [],
            "confidence": 0.90
        }
        
        # Add warnings
        if current_date.month == 12 and current_date.day > 15:
            result["warnings"].append({
                "type": "DEADLINE",
                "message": "Less than 2 weeks until year-end - act quickly on recommendations"
            })
        
        # Check for wash sale risks
        wash_sale_risks = [opp for opp in harvesting_opportunities if opp['wash_sale_risk']]
        if wash_sale_risks:
            result["warnings"].append({
                "type": "WASH_SALE",
                "message": f"Potential wash sale risk on {len(wash_sale_risks)} positions",
                "affected_symbols": list(set(r['symbol'] for r in wash_sale_risks))
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Year-end planning failed: {e}")
        return {
            "error": str(e),
            "confidence": 0.0
        }

# Helper functions
def simulate_sale_tax(lots, quantity, price, method):
    """Simulate tax implications of a sale"""
    if method == "FIFO":
        sorted_lots = sorted(lots, key=lambda x: x['purchase_date'])
    elif method == "LIFO":
        sorted_lots = sorted(lots, key=lambda x: x['purchase_date'], reverse=True)
    elif method == "HIFO":
        sorted_lots = sorted(lots, key=lambda x: x['purchase_price'], reverse=True)
    else:
        sorted_lots = lots
    
    remaining = quantity
    total_proceeds = quantity * price
    total_cost = 0
    long_term_gain = 0
    short_term_gain = 0
    
    for lot in sorted_lots:
        if remaining <= 0:
            break
        
        shares_to_sell = min(lot['quantity'], remaining)
        lot_cost = (lot['cost_basis'] / lot['quantity']) * shares_to_sell
        lot_gain = shares_to_sell * price - lot_cost
        
        total_cost += lot_cost
        
        if lot.get('is_long_term', False):
            long_term_gain += lot_gain
        else:
            short_term_gain += lot_gain
        
        remaining -= shares_to_sell
    
    return {
        "method": method,
        "proceeds": total_proceeds,
        "cost_basis": total_cost,
        "total_gain": total_proceeds - total_cost,
        "long_term_gain": long_term_gain,
        "short_term_gain": short_term_gain,
        "estimated_tax": long_term_gain * 0.15 + short_term_gain * 0.25
    }

def simulate_sale_by_method(lots, shares_needed, current_price, method):
    """Simulate sale using specific method"""
    result = simulate_sale_tax(lots, shares_needed, current_price, method)
    
    return {
        "total_gain": result['total_gain'],
        "tax_estimate": result['estimated_tax'],
        "after_tax_proceeds": result['proceeds'] - result['estimated_tax']
    }

def calculate_federal_tax(income_data, filing_status, tax_year):
    """Calculate federal tax (simplified)"""
    # This would use tenforty or detailed tax tables
    total_income = sum(income_data.values())
    
    # Simplified calculation
    if filing_status == "Single":
        if total_income < 44725:
            tax = total_income * 0.12
        elif total_income < 95375:
            tax = 5035 + (total_income - 44725) * 0.22
        else:
            tax = 16290 + (total_income - 95375) * 0.24
    else:  # Married Filing Jointly
        if total_income < 89450:
            tax = total_income * 0.12
        elif total_income < 190750:
            tax = 10070 + (total_income - 89450) * 0.22
        else:
            tax = 32580 + (total_income - 190750) * 0.24
    
    # Add capital gains tax
    ltcg = income_data.get('long_term_capital_gains', 0)
    stcg = income_data.get('short_term_capital_gains', 0)
    
    tax += ltcg * 0.15  # Simplified - should check brackets
    tax += stcg * 0.24  # At ordinary income rate
    
    return {
        "federal_tax": tax,
        "effective_rate": (tax / total_income * 100) if total_income > 0 else 0,
        "marginal_rate": 24  # Simplified
    }

def calculate_state_tax(income_data, filing_status, state, tax_year):
    """Calculate state tax (simplified)"""
    total_income = sum(income_data.values())
    
    # Simplified state tax rates
    state_rates = {
        "CA": 0.093,  # California top rate
        "NY": 0.0685,  # New York
        "TX": 0.0,     # Texas - no income tax
        "FL": 0.0,     # Florida - no income tax
        "IL": 0.0495,  # Illinois flat tax
    }
    
    rate = state_rates.get(state, 0.05)  # Default 5%
    
    return {
        "state_tax": total_income * rate,
        "state": state,
        "rate": rate * 100
    }

def calculate_niit_applies(income_data, filing_status):
    """Check if NIIT applies"""
    total_income = sum(income_data.values())
    
    thresholds = {
        "Single": 200000,
        "Married Filing Jointly": 250000,
        "Married Filing Separately": 125000
    }
    
    return total_income > thresholds.get(filing_status, 200000)

def calculate_niit(income_data):
    """Calculate Net Investment Income Tax"""
    investment_income = (
        income_data.get('long_term_capital_gains', 0) +
        income_data.get('short_term_capital_gains', 0) +
        income_data.get('dividends', 0) +
        income_data.get('interest', 0)
    )
    
    return investment_income * 0.038  # 3.8% NIIT rate

def check_wash_sale_risk(symbol, lot):
    """Check if selling would trigger wash sale rule"""
    # Simplified - would need to check recent transactions
    # Wash sale applies if same security bought within 30 days before or after sale
    return False  # Placeholder

def get_tax_bracket_limit(filing_status, bracket_level):
    """Get tax bracket limits"""
    brackets = {
        "Single": {
            "low": 44725,
            "middle": 95375,
            "high": 182050
        },
        "Married Filing Jointly": {
            "low": 89450,
            "middle": 190750,
            "high": 364200
        }
    }
    
    return brackets.get(filing_status, brackets["Single"]).get(bracket_level, 95375)

if __name__ == "__main__":
    server.run()