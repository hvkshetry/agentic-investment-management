#!/usr/bin/env python3
"""
Tax MCP Server - Provides tax calculation tools via Model Context Protocol
Uses tenforty library for US federal and state tax calculations
"""

from fastmcp import FastMCP
from typing import Dict, List, Optional, Any
import logging
import tenforty

# Configure logging to stderr only (critical for stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Defaults to stderr
)
logger = logging.getLogger("tax-server")

# Initialize FastMCP server
server = FastMCP("Tax Server")

# Implementation functions (regular Python functions that can be called directly)
def _calculate_tax_liability_impl(
    year: int = 2024,
    state: Optional[str] = None,
    filing_status: str = "Single",
    num_dependents: int = 0,
    w2_income: float = 0.0,
    taxable_interest: float = 0.0,
    qualified_dividends: float = 0.0,
    ordinary_dividends: float = 0.0,
    short_term_capital_gains: float = 0.0,
    long_term_capital_gains: float = 0.0,
    incentive_stock_option_gains: float = 0.0,
    itemized_deductions: float = 0.0
) -> Dict[str, Any]:
    """Implementation for tax liability calculation."""
    try:
        # Calculate using tenforty
        result = tenforty.evaluate_return(
            year=year,
            state=state,
            filing_status=filing_status,
            num_dependents=num_dependents,
            w2_income=w2_income,
            taxable_interest=taxable_interest,
            qualified_dividends=qualified_dividends,
            ordinary_dividends=ordinary_dividends,
            short_term_capital_gains=short_term_capital_gains,
            long_term_capital_gains=long_term_capital_gains,
            incentive_stock_option_gains=incentive_stock_option_gains,
            itemized_deductions=itemized_deductions
        )
        
        # Calculate gross income
        gross_income = (
            w2_income + 
            taxable_interest +
            ordinary_dividends + 
            qualified_dividends +
            short_term_capital_gains + 
            long_term_capital_gains +
            incentive_stock_option_gains
        )
        
        return {
            "federal_tax": result.federal_total_tax,
            "state_tax": result.state_total_tax if result.state_total_tax else 0.0,
            "total_tax": result.total_tax,
            "federal_effective_rate": result.federal_effective_tax_rate,
            "state_effective_rate": result.state_effective_tax_rate if result.state_effective_tax_rate else 0.0,
            "federal_marginal_rate": result.federal_tax_bracket,
            "federal_amt": result.federal_amt,
            "is_amt_liable": result.federal_amt > 0,
            "gross_income": gross_income,
            "federal_agi": result.federal_adjusted_gross_income,
            "federal_taxable_income": result.federal_taxable_income,
            "after_tax_income": gross_income - result.total_tax,
            "tax_breakdown": {
                "ordinary_income_tax": result.federal_total_tax - result.federal_amt,
                "amt": result.federal_amt,
                "state_tax": result.state_total_tax if result.state_total_tax else 0.0,
                "total": result.total_tax
            }
        }
    except Exception as e:
        logger.error(f"Tax calculation failed: {str(e)}")
        raise ValueError(f"Tax calculation failed: {str(e)}")

@server.tool()
async def calculate_tax_liability(
    year: int = 2024,
    state: Optional[str] = None,
    filing_status: str = "Single",
    num_dependents: int = 0,
    w2_income: float = 0.0,
    taxable_interest: float = 0.0,
    qualified_dividends: float = 0.0,
    ordinary_dividends: float = 0.0,
    short_term_capital_gains: float = 0.0,
    long_term_capital_gains: float = 0.0,
    incentive_stock_option_gains: float = 0.0,
    itemized_deductions: float = 0.0
) -> Dict[str, Any]:
    """
    Calculate complete tax liability for a scenario.
    
    Args:
        year: Tax year (2018-2024)
        state: Two-letter state code (e.g., "CA", "NY")
        filing_status: Filing status ("Single", "Married Filing Jointly", etc.)
        num_dependents: Number of dependents
        w2_income: W2 wage income
        taxable_interest: Taxable interest income
        qualified_dividends: Qualified dividend income
        ordinary_dividends: Ordinary dividend income
        short_term_capital_gains: Short-term capital gains
        long_term_capital_gains: Long-term capital gains
        incentive_stock_option_gains: ISO gains
        itemized_deductions: Total itemized deductions
    
    Returns:
        Dictionary with tax calculations including federal, state, AMT, and breakdown
    """
    return _calculate_tax_liability_impl(
        year=year,
        state=state,
        filing_status=filing_status,
        num_dependents=num_dependents,
        w2_income=w2_income,
        taxable_interest=taxable_interest,
        qualified_dividends=qualified_dividends,
        ordinary_dividends=ordinary_dividends,
        short_term_capital_gains=short_term_capital_gains,
        long_term_capital_gains=long_term_capital_gains,
        incentive_stock_option_gains=incentive_stock_option_gains,
        itemized_deductions=itemized_deductions
    )

@server.tool()
async def optimize_tax_harvest(
    positions: List[Dict[str, Any]], 
    target_loss_amount: float = 3000.0
) -> Dict[str, Any]:
    """
    Optimize tax loss harvesting strategy.
    
    Args:
        positions: List of position dictionaries with 'symbol', 'shares', and 'unrealized_gain'
        target_loss_amount: Target amount of losses to harvest (default $3000)
    
    Returns:
        Dictionary with harvest plan, total losses, and tax savings estimate
    """
    # Filter positions with losses
    loss_positions = [
        p for p in positions 
        if p.get('unrealized_gain', 0) < 0
    ]
    
    # Sort by loss amount
    loss_positions.sort(key=lambda x: x['unrealized_gain'])
    
    harvest_plan = []
    total_harvested = 0.0
    
    for position in loss_positions:
        if total_harvested >= target_loss_amount:
            break
            
        loss_amount = abs(position['unrealized_gain'])
        harvest_amount = min(loss_amount, target_loss_amount - total_harvested)
        
        harvest_plan.append({
            "symbol": position['symbol'],
            "shares_to_sell": position['shares'] * (harvest_amount / loss_amount),
            "loss_amount": harvest_amount,
            "wash_sale_until": "30 days from sale"
        })
        total_harvested += harvest_amount
    
    return {
        "harvest_plan": harvest_plan,
        "total_loss_harvested": total_harvested,
        "tax_savings_estimate": total_harvested * 0.25,  # Assume 25% rate
        "wash_sale_warnings": [p['symbol'] for p in harvest_plan]
    }

@server.tool()
async def compare_tax_scenarios(
    scenarios: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Compare multiple tax scenarios for optimization.
    
    Args:
        scenarios: List of scenario dictionaries with tax parameters
    
    Returns:
        List of scenario results sorted by after-tax income
    """
    results = []
    
    for i, scenario in enumerate(scenarios):
        # Extract description if provided, then remove non-tax parameters
        description = scenario.pop('name', scenario.pop('description', f"Scenario {i+1}"))
        
        # Filter scenario to only include valid tax parameters
        valid_params = {
            'year', 'state', 'filing_status', 'num_dependents',
            'w2_income', 'taxable_interest', 'qualified_dividends',
            'ordinary_dividends', 'short_term_capital_gains',
            'long_term_capital_gains', 'incentive_stock_option_gains',
            'itemized_deductions'
        }
        
        # Create filtered scenario with only valid parameters
        tax_params = {k: v for k, v in scenario.items() if k in valid_params}
        
        # Call implementation function with filtered parameters
        tax_result = _calculate_tax_liability_impl(**tax_params)
        results.append({
            "scenario_id": i,
            "description": description,
            "total_tax": tax_result["total_tax"],
            "after_tax_income": tax_result["after_tax_income"],
            "effective_rate": tax_result["federal_effective_rate"],
            "result": tax_result
        })
    
    # Sort by after-tax income (highest first)
    results.sort(key=lambda x: x['after_tax_income'], reverse=True)
    
    return results

@server.tool()
async def estimate_quarterly_payments(
    ytd_income: Dict[str, float],
    prior_year_tax: float,
    payments_made: float = 0.0,
    current_quarter: int = 2
) -> Dict[str, Any]:
    """
    Calculate required quarterly estimated tax payments.
    
    Args:
        ytd_income: Year-to-date income by type
        prior_year_tax: Total tax from prior year
        payments_made: Estimated payments already made this year
        current_quarter: Current quarter (1-4)
    
    Returns:
        Dictionary with payment schedule and safe harbor calculations
    """
    # Project annual income
    months_elapsed = current_quarter * 3
    
    # Map common income aliases to tax calculation parameters
    income_mapping = {
        'wages': 'w2_income',
        'salary': 'w2_income',
        'interest': 'taxable_interest',
        'dividends': 'ordinary_dividends',
        'capital_gains': 'short_term_capital_gains'
    }
    
    projected_annual = {}
    for income_type, amount in ytd_income.items():
        # Use mapping if available, otherwise use original key
        mapped_key = income_mapping.get(income_type, income_type)
        projected_annual[mapped_key] = (amount / months_elapsed) * 12
    
    # Ensure we have default values for required parameters
    tax_params = {
        'year': 2024,
        'filing_status': 'Single',
        'w2_income': 0.0,
        'taxable_interest': 0.0,
        'ordinary_dividends': 0.0,
        'qualified_dividends': 0.0,
        'short_term_capital_gains': 0.0,
        'long_term_capital_gains': 0.0,
        'incentive_stock_option_gains': 0.0,
        'itemized_deductions': 0.0
    }
    
    # Update with projected values
    tax_params.update(projected_annual)
    
    # Calculate projected tax using implementation function
    projected_tax = _calculate_tax_liability_impl(**tax_params)
    
    # IRS safe harbor: 90% current year or 100% prior year (110% if high income)
    safe_harbor = min(
        projected_tax["total_tax"] * 0.9,
        prior_year_tax * 1.0  # Use 1.1 if AGI > $150k
    )
    
    # Calculate remaining payments
    remaining_required = safe_harbor - payments_made
    quarters_left = 4 - current_quarter + 1
    
    quarterly_payment = remaining_required / quarters_left if quarters_left > 0 else 0
    
    return {
        "projected_annual_tax": projected_tax["total_tax"],
        "safe_harbor_amount": safe_harbor,
        "payments_made": payments_made,
        "remaining_required": remaining_required,
        "quarterly_payment": quarterly_payment,
        "payment_schedule": {
            "Q1": quarterly_payment if current_quarter <= 1 else 0,
            "Q2": quarterly_payment if current_quarter <= 2 else 0,
            "Q3": quarterly_payment if current_quarter <= 3 else 0,
            "Q4": quarterly_payment if current_quarter <= 4 else 0
        }
    }

@server.tool()
async def analyze_bracket_impact(
    base_scenario: Dict[str, Any],
    additional_income: float,
    income_type: str = "ordinary"
) -> Dict[str, Any]:
    """
    Analyze marginal tax impact of additional income.
    
    Args:
        base_scenario: Base tax scenario parameters
        additional_income: Amount of additional income to analyze
        income_type: Type of income ("ordinary", "ltcg", "stcg")
    
    Returns:
        Dictionary with marginal tax analysis
    """
    # Calculate base tax using implementation function
    base_result = _calculate_tax_liability_impl(**base_scenario)
    
    # Create scenario with additional income
    modified_scenario = base_scenario.copy()
    if income_type == "ordinary":
        modified_scenario["w2_income"] = modified_scenario.get("w2_income", 0) + additional_income
    elif income_type == "ltcg":
        modified_scenario["long_term_capital_gains"] = modified_scenario.get("long_term_capital_gains", 0) + additional_income
    elif income_type == "stcg":
        modified_scenario["short_term_capital_gains"] = modified_scenario.get("short_term_capital_gains", 0) + additional_income
    
    # Calculate new tax using implementation function
    new_result = _calculate_tax_liability_impl(**modified_scenario)
    
    # Calculate marginal impact
    marginal_tax = new_result["total_tax"] - base_result["total_tax"]
    marginal_rate = (marginal_tax / additional_income) * 100 if additional_income > 0 else 0
    
    return {
        "additional_income": additional_income,
        "income_type": income_type,
        "marginal_tax": marginal_tax,
        "marginal_rate": marginal_rate,
        "new_bracket": new_result["federal_marginal_rate"],
        "old_bracket": base_result["federal_marginal_rate"],
        "bracket_changed": new_result["federal_marginal_rate"] != base_result["federal_marginal_rate"],
        "amt_triggered": new_result["is_amt_liable"] and not base_result["is_amt_liable"]
    }

if __name__ == "__main__":
    # Run the server with stdio transport
    logger.info("Starting Tax MCP Server v2.0 with FastMCP")
    server.run(transport="stdio")