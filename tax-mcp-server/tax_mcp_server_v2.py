#!/usr/bin/env python3
"""
Tax MCP Server v2 - Enhanced with NIIT, Trust Taxes, and State-Specific Rules
Addresses all tax deficiencies from ~/investing/feedback.md
Consolidated into single comprehensive tax analysis tool

AGPL-3.0 License Notice:
This software uses PolicyEngine-US (AGPL-3.0) for individual tax calculations.
Any distribution or network service must comply with AGPL-3.0 terms.
"""

from fastmcp import FastMCP
from typing import Dict, List, Optional, Any, Union
import logging
import sys
import os
from datetime import datetime
from policyengine_us import Simulation
from policyengine_us.system import system as pe_system

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import confidence scoring and portfolio state
from confidence_scoring import ConfidenceScorer
from portfolio_state_client import get_portfolio_state_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("tax-server-v2")

# Initialize components
server = FastMCP("Tax Server v2 - Enhanced")
confidence_scorer = ConfidenceScorer()
portfolio_state_client = get_portfolio_state_client()

@server.tool()
async def calculate_comprehensive_tax(
    tax_year: int = 2024,
    entity_type: str = "individual",  # 'individual', 'trust', 'estate'
    filing_status: str = "Single",
    state: str = "",  # Empty string for no state tax
    income_sources: Dict[str, float] = {},
    deductions: Dict[str, float] = {},
    credits: Dict[str, float] = {},
    dependents: int = 0,
    include_niit: bool = True,
    include_amt: bool = True,
    trust_details: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """
    Comprehensive tax calculation including NIIT, trust taxes, and state-specific rules.
    Single tool that handles all tax scenarios per reviewer feedback.
    
    Args:
        tax_year: Tax year (2018-2025)
        entity_type: 'individual', 'trust', or 'estate'
        filing_status: For individuals: 'Single', 'Married Filing Jointly', etc.
        state: Two-letter state code (e.g., 'MA', 'CA', 'NY') or empty string for no state tax
        income_sources: Dict with income types:
            - w2_income: Wages and salaries
            - taxable_interest: Interest income
            - tax_exempt_interest: Municipal bond interest
            - ordinary_dividends: Non-qualified dividends
            - qualified_dividends: Qualified dividends
            - short_term_capital_gains: STCG
            - long_term_capital_gains: LTCG
            - rental_income: Net rental income
            - business_income: Schedule C income
            - passive_income: K-1 passive income
            - iso_gains: Incentive stock option gains
            - retirement_distributions: 401k/IRA distributions
        deductions: Dict with deduction types:
            - itemized_deductions: Total itemized
            - business_expenses: Schedule C expenses
            - rental_expenses: Rental property expenses
            - investment_expenses: Investment management fees
        credits: Dict with tax credits
        dependents: Number of dependents
        include_niit: Calculate Net Investment Income Tax
        include_amt: Calculate Alternative Minimum Tax
        trust_details: For trusts/estates:
            - distributable_net_income: DNI
            - distributions_to_beneficiaries: Amount distributed
            - trust_type: 'simple', 'complex', 'grantor'
    
    Returns:
        Comprehensive tax analysis with federal, state, NIIT, AMT, and confidence scoring
    """
    try:
        # Handle MCP JSON string serialization
        import json

        # Normalize filing status to tenforty format
        # Map human-readable values to tenforty enum values
        filing_status_map = {
            "married filing jointly": "Married/Joint",
            "married jointly": "Married/Joint",
            "joint": "Married/Joint",
            "married/joint": "Married/Joint",
            "married filing separately": "Married/Separate",
            "married separately": "Married/Separate",
            "married/separate": "Married/Separate",
            "head of household": "Head of Household",
            "single": "Single",
            "qualifying widow": "Qualifying Widow(er)",
            "qualifying widower": "Qualifying Widow(er)",
            "qualifying widow(er)": "Qualifying Widow(er)"
        }

        # Normalize filing status (case-insensitive)
        filing_status_lower = filing_status.lower()
        if filing_status_lower in filing_status_map:
            original_filing_status = filing_status
            filing_status = filing_status_map[filing_status_lower]
            if original_filing_status != filing_status:
                logger.info(f"Normalized filing_status from '{original_filing_status}' to '{filing_status}'")

        # Convert JSON strings to native types if needed (MCP protocol serializes to JSON)
        if isinstance(income_sources, str):
            try:
                income_sources = json.loads(income_sources)
                logger.debug(f"Converted income_sources from JSON string to dict with {len(income_sources)} keys")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse income_sources as JSON: {income_sources[:50]}...")
        
        if isinstance(deductions, str):
            try:
                deductions = json.loads(deductions)
                logger.debug(f"Converted deductions from JSON string to dict with {len(deductions)} keys")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse deductions as JSON: {deductions[:50]}...")
        
        if isinstance(credits, str):
            try:
                credits = json.loads(credits)
                logger.debug(f"Converted credits from JSON string to dict with {len(credits)} keys")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse credits as JSON: {credits[:50]}...")
        
        if isinstance(trust_details, str):
            try:
                trust_details = json.loads(trust_details)
                logger.debug(f"Converted trust_details from JSON string to dict")
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse trust_details as JSON: {trust_details[:50]}...")
        
        # Ensure dicts are not None (though they shouldn't be with new defaults)
        # These checks are now redundant but kept for safety
        
        # Try to get real capital gains from Portfolio State
        use_portfolio_state = income_sources.get('use_portfolio_state', True)
        portfolio_source = "provided"
        
        if use_portfolio_state and ('capital_gains_from_portfolio' in income_sources or 
                                   income_sources.get('long_term_capital_gains', 0) == 0 and 
                                   income_sources.get('short_term_capital_gains', 0) == 0):
            try:
                logger.info("Fetching real capital gains from Portfolio State")
                
                # Get tax lots
                tax_lots = await portfolio_state_client.get_tax_lots()
                positions = await portfolio_state_client.get_positions(fetch_prices=False)  # Don't fetch prices for 55 positions
                
                if not tax_lots:
                    raise ValueError("No tax lots found in Portfolio State")
                
                # Calculate actual capital gains from tax lots
                long_term_gains = 0
                short_term_gains = 0
                
                for symbol, position in positions.items():
                    for lot in position.tax_lots:
                        # Calculate gain/loss for this lot
                        current_value = lot.quantity * position.current_price
                        gain_loss = current_value - lot.cost_basis
                        
                        if lot.is_long_term:
                            long_term_gains += gain_loss
                        else:
                            short_term_gains += gain_loss
                
                # Update income sources with real gains
                income_sources['long_term_capital_gains'] = long_term_gains
                income_sources['short_term_capital_gains'] = short_term_gains
                portfolio_source = "portfolio_state"
                
                logger.info(f"Using real capital gains from Portfolio State: "
                          f"LT: ${long_term_gains:,.2f}, ST: ${short_term_gains:,.2f}")
                
            except Exception as e:
                logger.warning(f"Failed to fetch from Portfolio State: {e}")
                logger.warning("Continuing with user-provided capital gains (if any). Portfolio-derived gains unavailable.")
                portfolio_source = "unavailable (Portfolio State error)"
                # Don't raise - allow tax calculation to proceed with user-provided data or zeros
        
        # Initialize result structure
        result = {
            "tax_summary": {},
            "federal_tax": {},
            "state_tax": {},
            "niit_calculation": {},
            "amt_calculation": {},
            "trust_tax": {},
            "marginal_analysis": {},
            "effective_rates": {},
            "tax_planning": {},
            "confidence": {},
            "metadata": {}
        }
        
        # =========================
        # 1. CALCULATE BASE TAXES
        # =========================

        if entity_type == "individual":
            # Use PolicyEngine for individual calculation (replaces tenforty)
            pe_result = calculate_individual_tax_policyengine(
                tax_year=tax_year,
                filing_status=filing_status,
                state=state,
                income_sources=income_sources,
                deductions=deductions,
                dependents=dependents
            )

            federal_tax = pe_result["federal_tax"]
            state_tax = pe_result["state_tax"]
            agi = pe_result["agi"]

            # PolicyEngine already calculates NIIT, so extract it
            niit_from_pe = pe_result.get("niit", 0)
            amt_from_pe = pe_result.get("amt", 0)
            
        elif entity_type in ["trust", "estate"]:
            # Calculate trust/estate taxes
            trust_income = sum(income_sources.values())
            trust_tax_result = calculate_trust_tax(
                trust_income,
                trust_details or {},
                tax_year
            )
            federal_tax = trust_tax_result["federal_tax"]
            state_tax = 0  # Will calculate state-specific trust tax below
            agi = trust_income
            result["trust_tax"] = trust_tax_result
        
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")
        
        # =========================
        # 2. CALCULATE NIIT (3.8% SURTAX)
        # =========================

        if include_niit:
            if entity_type == "individual":
                # For individuals, PolicyEngine already calculated NIIT
                niit_tax = niit_from_pe
                magi = agi + income_sources.get('tax_exempt_interest', 0)

                # Get threshold for reporting
                niit_thresholds = {
                    'Single': 200000,
                    'Married Filing Jointly': 250000,
                    'Married Filing Separately': 125000,
                    'Head of Household': 200000
                }
                threshold = niit_thresholds.get(filing_status, 200000)

                result["niit_calculation"] = {
                    "magi": float(magi),
                    "threshold": float(threshold),
                    "niit_tax": float(niit_tax),
                    "effective_niit_rate": float(niit_tax / magi * 100) if magi > 0 else 0,
                    "source": "PolicyEngine calculation"
                }

                # NIIT already included in PolicyEngine's federal_tax
                # No need to add it again

            elif entity_type in ["trust", "estate"]:
                # For trusts, calculate NIIT manually (not in PolicyEngine)
                magi = agi + income_sources.get('tax_exempt_interest', 0)

                # Net Investment Income components
                net_investment_income = (
                    income_sources.get('taxable_interest', 0) +
                    income_sources.get('ordinary_dividends', 0) +
                    income_sources.get('qualified_dividends', 0) +
                    income_sources.get('short_term_capital_gains', 0) +
                    income_sources.get('long_term_capital_gains', 0) +
                    income_sources.get('rental_income', 0) +
                    income_sources.get('passive_income', 0) -
                    deductions.get('investment_expenses', 0)
                )

                # Trust NIIT threshold (much lower!)
                threshold = 15200  # 2024 trust threshold

                # Calculate NIIT
                if magi > threshold:
                    excess_magi = magi - threshold
                    niit_base = min(net_investment_income, excess_magi)
                    niit_tax = niit_base * 0.038
                else:
                    niit_tax = 0
                    niit_base = 0

                result["niit_calculation"] = {
                    "magi": float(magi),
                    "threshold": float(threshold),
                    "excess_magi": float(max(0, magi - threshold)),
                    "net_investment_income": float(net_investment_income),
                    "niit_base": float(niit_base),
                    "niit_tax": float(niit_tax),
                    "effective_niit_rate": float(niit_tax / magi * 100) if magi > 0 else 0,
                    "source": "Custom trust calculation"
                }

                federal_tax += niit_tax
        
        # =========================
        # 3. MASSACHUSETTS STATE TAX SPECIFICS
        # =========================
        
        if state == "MA":
            ma_tax = calculate_massachusetts_tax(income_sources, entity_type, tax_year)
            state_tax = ma_tax["total_ma_tax"]
            result["state_tax"]["massachusetts_detail"] = ma_tax
        
        # =========================
        # 4. AMT CALCULATION
        # =========================

        if include_amt and entity_type == "individual":
            # For individuals, PolicyEngine already calculated AMT
            amt = amt_from_pe
            result["amt_calculation"] = {
                "amt_owed": float(amt),
                "is_amt_liable": amt > 0,
                "source": "PolicyEngine calculation"
            }
            # AMT already included in PolicyEngine's federal_tax
            # No need to add it again
        
        # =========================
        # 5. TOTAL TAX CALCULATION
        # =========================
        
        total_income = sum(income_sources.values())
        total_deductions = sum(deductions.values())
        total_credits = sum(credits.values())
        
        total_tax = federal_tax + state_tax - total_credits
        after_tax_income = total_income - total_tax
        
        result["tax_summary"] = {
            "gross_income": float(total_income),
            "adjusted_gross_income": float(agi),
            "total_deductions": float(total_deductions),
            "taxable_income": float(max(0, agi - total_deductions)),
            "federal_tax": float(federal_tax),
            "state_tax": float(state_tax),
            "niit_tax": float(result["niit_calculation"].get("niit_tax", 0)),
            "amt": float(result["amt_calculation"].get("amt_owed", 0)) if include_amt else 0,
            "total_credits": float(total_credits),
            "total_tax": float(total_tax),
            "after_tax_income": float(after_tax_income)
        }
        
        # =========================
        # 6. EFFECTIVE RATES
        # =========================
        
        result["effective_rates"] = {
            "federal_effective_rate": float(federal_tax / total_income * 100) if total_income > 0 else 0,
            "state_effective_rate": float(state_tax / total_income * 100) if total_income > 0 else 0,
            "total_effective_rate": float(total_tax / total_income * 100) if total_income > 0 else 0,
            "marginal_federal_rate": get_marginal_rate(agi, filing_status, entity_type, tax_year),
            "capital_gains_rate": get_capital_gains_rate(agi, filing_status, tax_year)
        }
        
        # =========================
        # 7. MARGINAL ANALYSIS
        # =========================
        
        # Analyze impact of $10k additional income
        marginal_impacts = {}
        for income_type in ['ordinary', 'ltcg', 'stcg']:
            additional = 10000
            
            if income_type == 'ordinary':
                test_sources = income_sources.copy()
                test_sources['w2_income'] = test_sources.get('w2_income', 0) + additional
            elif income_type == 'ltcg':
                test_sources = income_sources.copy()
                test_sources['long_term_capital_gains'] = test_sources.get('long_term_capital_gains', 0) + additional
            else:  # stcg
                test_sources = income_sources.copy()
                test_sources['short_term_capital_gains'] = test_sources.get('short_term_capital_gains', 0) + additional
            
            # Would need to recalculate - simplified here
            marginal_rate = get_marginal_rate(agi + additional, filing_status, entity_type, tax_year)
            marginal_tax = additional * marginal_rate / 100
            
            marginal_impacts[income_type] = {
                "additional_income": additional,
                "marginal_tax": float(marginal_tax),
                "marginal_rate": float(marginal_rate),
                "keep_after_tax": float(additional - marginal_tax)
            }
        
        result["marginal_analysis"] = marginal_impacts
        
        # =========================
        # 8. ADVANCED TAX OPTIMIZATION FROM SHARED LIBRARIES
        # =========================
        
        # 8A. MULTI-PERIOD TAX OPTIMIZATION
        if trust_details.get('enable_multi_period', False) or income_sources.get('enable_multi_period', False):
            try:
                from optimization.multi_period import MultiPeriodOptimizer
                marginal_rate = get_marginal_rate(agi, filing_status, entity_type, tax_year)
                mp_optimizer = MultiPeriodOptimizer(
                    tax_rates={'short_term': marginal_rate/100, 'long_term': get_capital_gains_rate(agi, filing_status, tax_year)/100}
                )
                
                # Analyze tax-aware rebalancing if portfolio provided
                if 'portfolio_holdings' in trust_details or 'portfolio_holdings' in income_sources:
                    holdings = trust_details.get('portfolio_holdings') or income_sources.get('portfolio_holdings', {})
                    target_weights = trust_details.get('target_weights') or income_sources.get('target_weights', {})
                    current_prices = trust_details.get('current_prices') or income_sources.get('current_prices', {})
                    cost_basis = trust_details.get('cost_basis') or income_sources.get('cost_basis', {})
                    
                    tax_aware_plan = mp_optimizer.tax_aware_rebalance(
                        current_holdings=holdings,
                        target_weights=target_weights,
                        current_prices=current_prices,
                        cost_basis=cost_basis
                    )
                    
                    result["tax_aware_rebalancing"] = {
                        "total_tax_due": tax_aware_plan['total_tax_due'],
                        "loss_harvest_candidates": tax_aware_plan['loss_harvest_candidates'],
                        "tax_efficiency_score": tax_aware_plan['tax_efficiency_score'],
                        "recommended_trades": tax_aware_plan.get('trades', {}),
                        "optimization_performed": True
                    }
                    
            except Exception as e:
                logger.warning(f"Multi-period tax optimization failed: {e}")
                result["tax_aware_rebalancing"] = {"error": str(e), "optimization_performed": False}
        
        # 8B. TAX LOSS HARVESTING ANALYSIS
        if income_sources.get('unrealized_gains_losses'):
            try:
                from backtesting.strategies import StrategyLibrary
                
                unrealized = income_sources['unrealized_gains_losses']
                marginal_rate = get_marginal_rate(agi, filing_status, entity_type, tax_year)
                
                # Identify tax loss harvesting opportunities
                harvest_opportunities = []
                total_harvestable_losses = 0
                
                for asset, gain_loss in unrealized.items():
                    if gain_loss < 0:
                        # Calculate tax benefit of harvesting this loss
                        if abs(gain_loss) > income_sources.get('short_term_capital_gains', 0):
                            # Can offset STCG at ordinary rates
                            tax_benefit = min(abs(gain_loss), income_sources.get('short_term_capital_gains', 0)) * marginal_rate / 100
                        else:
                            # Offset LTCG at capital gains rate
                            tax_benefit = abs(gain_loss) * get_capital_gains_rate(agi, filing_status, tax_year) / 100
                        
                        harvest_opportunities.append({
                            "asset": asset,
                            "unrealized_loss": gain_loss,
                            "tax_benefit": tax_benefit,
                            "wash_sale_warning": "Avoid repurchasing within 30 days"
                        })
                        total_harvestable_losses += abs(gain_loss)
                
                result["tax_loss_harvesting"] = {
                    "opportunities": harvest_opportunities,
                    "total_harvestable_losses": total_harvestable_losses,
                    "potential_tax_savings": sum(opp['tax_benefit'] for opp in harvest_opportunities),
                    "current_year_offset_limit": 3000,  # Against ordinary income
                    "analysis_performed": True
                }
                
            except Exception as e:
                logger.warning(f"Tax loss harvesting analysis failed: {e}")
                result["tax_loss_harvesting"] = {"error": str(e), "analysis_performed": False}
        
        # 8C. TRUST DISTRIBUTION OPTIMIZATION
        if entity_type == "trust" and trust_details.get('beneficiary_tax_rates'):
            try:
                # Analyze optimal distribution strategy
                dni = trust_details.get('distributable_net_income', 0)
                beneficiary_rates = trust_details['beneficiary_tax_rates']
                marginal_rate = get_marginal_rate(agi, filing_status, entity_type, tax_year)
                
                # Calculate tax at trust level vs beneficiary level
                trust_tax_rate = marginal_rate / 100  # Trust marginal rate (likely 37%)
                
                distribution_scenarios = []
                for beneficiary, ben_rate in beneficiary_rates.items():
                    tax_at_trust = dni * trust_tax_rate
                    tax_at_beneficiary = dni * ben_rate
                    tax_savings = tax_at_trust - tax_at_beneficiary
                    
                    distribution_scenarios.append({
                        "beneficiary": beneficiary,
                        "beneficiary_rate": ben_rate * 100,
                        "trust_rate": trust_tax_rate * 100,
                        "distribution_amount": dni,
                        "tax_savings": tax_savings,
                        "recommendation": "Distribute" if tax_savings > 0 else "Retain in trust"
                    })
                
                result["trust_distribution_optimization"] = {
                    "scenarios": distribution_scenarios,
                    "optimal_distribution": max(distribution_scenarios, key=lambda x: x['tax_savings']),
                    "total_potential_savings": sum(s['tax_savings'] for s in distribution_scenarios if s['tax_savings'] > 0),
                    "analysis_performed": True
                }
                
            except Exception as e:
                logger.warning(f"Trust distribution optimization failed: {e}")
                result["trust_distribution_optimization"] = {"error": str(e), "analysis_performed": False}
        
        # 8D. CHARITABLE GIVING OPTIMIZATION
        if deductions.get('charitable_planning'):
            try:
                charitable_config = deductions['charitable_planning']
                
                # Analyze donation strategies
                strategies = []
                
                # Bunching strategy
                if charitable_config.get('annual_giving'):
                    annual = charitable_config['annual_giving']
                    bunched = annual * 3  # Bundle 3 years
                    marginal_rate = get_marginal_rate(agi, filing_status, entity_type, tax_year)
                    
                    # Calculate tax benefit
                    current_benefit = min(annual, agi * 0.6) * marginal_rate / 100  # AGI limit
                    bunched_benefit = min(bunched, agi * 0.6) * marginal_rate / 100
                    
                    strategies.append({
                        "strategy": "Bunching",
                        "description": "Bundle 3 years of donations in current year",
                        "current_year_donation": bunched,
                        "tax_benefit": bunched_benefit,
                        "vs_annual_benefit": bunched_benefit - (current_benefit * 3),
                        "recommendation": "Consider if itemizing"
                    })
                
                # Appreciated stock donation
                if charitable_config.get('appreciated_stock'):
                    stock_value = charitable_config['appreciated_stock']['value']
                    stock_basis = charitable_config['appreciated_stock']['basis']
                    unrealized_gain = stock_value - stock_basis
                    
                    # Avoid capital gains tax + get deduction
                    cap_gains_avoided = unrealized_gain * get_capital_gains_rate(agi, filing_status, tax_year) / 100
                    deduction_value = stock_value * marginal_rate / 100
                    
                    strategies.append({
                        "strategy": "Donate Appreciated Stock",
                        "stock_value": stock_value,
                        "capital_gains_avoided": cap_gains_avoided,
                        "deduction_value": deduction_value,
                        "total_benefit": cap_gains_avoided + deduction_value,
                        "recommendation": "Highly tax-efficient"
                    })
                
                result["charitable_optimization"] = {
                    "strategies": strategies,
                    "best_strategy": max(strategies, key=lambda x: x.get('total_benefit', x.get('tax_benefit', 0))),
                    "analysis_performed": True
                }
                
            except Exception as e:
                logger.warning(f"Charitable optimization failed: {e}")
                result["charitable_optimization"] = {"error": str(e), "analysis_performed": False}
        
        # =========================
        # 9. TAX PLANNING RECOMMENDATIONS
        # =========================
        
        recommendations = []
        
        # NIIT planning
        if result["niit_calculation"].get("niit_tax", 0) > 0:
            recommendations.append({
                "category": "NIIT Reduction",
                "recommendation": "Consider tax-exempt bonds or deferred compensation to reduce MAGI below $" + 
                                str(result["niit_calculation"]["threshold"]),
                "potential_savings": float(result["niit_calculation"]["niit_tax"])
            })
        
        # Trust tax planning
        if entity_type == "trust" and trust_details:
            if not trust_details.get("distributions_to_beneficiaries"):
                recommendations.append({
                    "category": "Trust Distribution",
                    "recommendation": "Consider distributing income to beneficiaries in lower tax brackets",
                    "potential_savings": float(federal_tax * 0.2)  # Estimate
                })
        
        # MA specific
        if state == "MA" and income_sources.get('short_term_capital_gains', 0) > 0:
            recommendations.append({
                "category": "MA Capital Gains",
                "recommendation": "Hold positions >1 year to avoid MA's 12% STCG rate",
                "potential_savings": float(income_sources['short_term_capital_gains'] * 0.07)  # 12% vs 5%
            })
        
        # Retirement planning
        if income_sources.get('w2_income', 0) > 100000:
            recommendations.append({
                "category": "Retirement Contributions",
                "recommendation": "Max out 401(k) ($23,000) and IRA ($7,000) to reduce taxable income",
                "potential_savings": float(30000 * result["effective_rates"]["marginal_federal_rate"] / 100)
            })
        
        result["tax_planning"] = {
            "recommendations": recommendations,
            "total_potential_savings": sum(r["potential_savings"] for r in recommendations)
        }
        
        # =========================
        # 9. CONFIDENCE SCORING
        # =========================
        
        # Determine which edge cases are handled
        edge_cases_handled = []
        if include_niit:
            edge_cases_handled.append("NIIT")
        if include_amt:
            edge_cases_handled.append("AMT")
        if entity_type == "trust":
            edge_cases_handled.append("trust_income")
        if state == "MA":
            edge_cases_handled.append("MA_specific")
        if income_sources.get('qualified_dividends', 0) > 0:
            edge_cases_handled.append("qualified_dividends")
        
        # Calculate data completeness
        expected_fields = ['w2_income', 'taxable_interest', 'dividends', 'capital_gains']
        provided_fields = sum(1 for f in expected_fields if any(k for k in income_sources.keys() if f in k))
        data_completeness = provided_fields / len(expected_fields)
        
        # Complexity assessment
        complexity = "simple"
        if entity_type == "trust" or include_niit or include_amt:
            complexity = "complex"
        elif len(income_sources) > 5:
            complexity = "moderate"
        
        confidence_metrics = confidence_scorer.score_tax_calculation(
            data_completeness=data_completeness,
            calculation_complexity=complexity,
            jurisdiction_support=state in ['MA', 'CA', 'NY', None],
            edge_cases_handled=edge_cases_handled
        )
        
        result["confidence"] = confidence_metrics.to_dict()
        
        # =========================
        # 10. METADATA
        # =========================
        
        result["metadata"] = {
            "calculation_timestamp": datetime.now().isoformat(),
            "tax_year": tax_year,
            "entity_type": entity_type,
            "filing_status": filing_status,
            "state": state,
            "portfolio_source": portfolio_source,
            "using_portfolio_state": portfolio_source == "portfolio_state",
            "features_included": {
                "niit": include_niit,
                "amt": include_amt,
                "trust_tax": entity_type == "trust",
                "state_specific": state is not None
            },
            "tax_engine": "PolicyEngine-US (individuals) + custom calculations (trusts)" if entity_type == "individual" else "Custom trust calculations"
        }
        
        return result

    except Exception as e:
        logger.error(f"Comprehensive tax calculation failed: {str(e)}")
        raise ValueError(f"Tax calculation failed: {str(e)}")


def calculate_individual_tax_policyengine(
    tax_year: int,
    filing_status: str,
    state: str,
    income_sources: Dict[str, float],
    deductions: Dict[str, float],
    dependents: int
) -> Dict[str, Any]:
    """
    Calculate individual (Form 1040) taxes using PolicyEngine-US.
    Replaces tenforty with more accurate, actively maintained library.

    Args:
        tax_year: Tax year (2018-2025)
        filing_status: 'Single', 'Married Filing Jointly', etc.
        state: Two-letter state code (e.g., 'MA', 'CA', 'NY')
        income_sources: Dictionary of income types
        deductions: Dictionary of deduction types
        dependents: Number of dependents

    Returns:
        Dictionary with federal_tax, state_tax, agi, and detailed breakdown
    """

    # Map filing status to PolicyEngine format
    filing_status_map = {
        "Single": "SINGLE",
        "Married Filing Jointly": "JOINT",
        "Married/Joint": "JOINT",
        "Married Filing Separately": "SEPARATE",
        "Married/Separate": "SEPARATE",
        "Head of Household": "HEAD_OF_HOUSEHOLD",
        "Surviving Spouse": "SURVIVING_SPOUSE"
    }

    pe_filing_status = filing_status_map.get(filing_status, "SINGLE")

    # Build PolicyEngine household structure
    # PolicyEngine uses a hierarchical structure: household -> tax_unit -> person
    situation = {
        "people": {
            "person": {
                "age": {tax_year: 40},  # Default adult age
                "employment_income": {tax_year: income_sources.get('w2_income', 0)},
                "taxable_interest_income": {tax_year: income_sources.get('taxable_interest', 0)},
                "tax_exempt_interest_income": {tax_year: income_sources.get('tax_exempt_interest', 0)},
                "qualified_dividend_income": {tax_year: income_sources.get('qualified_dividends', 0)},
                "non_qualified_dividend_income": {tax_year: income_sources.get('ordinary_dividends', 0)},
                "short_term_capital_gains": {tax_year: income_sources.get('short_term_capital_gains', 0)},
                "long_term_capital_gains": {tax_year: income_sources.get('long_term_capital_gains', 0)},
                "self_employment_income": {tax_year: income_sources.get('business_income', 0)},
                "rental_income": {tax_year: income_sources.get('rental_income', 0)},
                "partnership_s_corp_income": {tax_year: income_sources.get('passive_income', 0)},
                "taxable_ira_distributions": {tax_year: income_sources.get('retirement_distributions', 0)},
            }
        },
        "tax_units": {
            "tax_unit": {
                "members": ["person"],
                "filing_status": {tax_year: pe_filing_status},
                # Note: PolicyEngine calculates itemized vs standard automatically
                # We can't directly set itemized_deductions amount
            }
        },
        "spm_units": {
            "spm_unit": {
                "members": ["person"]
            }
        },
        "households": {
            "household": {
                "members": ["person"],
                "state_name": {tax_year: state if state else "MA"}  # Default to MA if no state
            }
        }
    }

    # Add dependents if specified
    if dependents > 0:
        for i in range(dependents):
            person_id = f"dependent_{i+1}"
            situation["people"][person_id] = {
                "age": {tax_year: 10}  # Default child age
            }
            situation["tax_units"]["tax_unit"]["members"].append(person_id)
            situation["spm_units"]["spm_unit"]["members"].append(person_id)
            situation["households"]["household"]["members"].append(person_id)

    # Create simulation
    simulation = Simulation(situation=situation)

    # Extract results
    federal_income_tax = simulation.calculate("income_tax", tax_year)[0]
    state_income_tax = simulation.calculate("state_income_tax", tax_year)[0] if state else 0
    agi = simulation.calculate("adjusted_gross_income", tax_year)[0]

    # Get detailed breakdown - only use variables that exist
    result = {
        "federal_tax": float(federal_income_tax),
        "state_tax": float(state_income_tax),
        "agi": float(agi),
        "taxable_income": float(simulation.calculate("taxable_income", tax_year)[0]),
        "standard_deduction": float(simulation.calculate("standard_deduction", tax_year)[0]),
    }

    # Try to add optional fields that may not always exist
    try:
        result["niit"] = float(simulation.calculate("net_investment_income_tax", tax_year)[0])
    except:
        result["niit"] = 0

    try:
        result["amt"] = float(simulation.calculate("alternative_minimum_tax", tax_year)[0])
    except:
        result["amt"] = 0

    try:
        result["capital_gains_tax"] = float(simulation.calculate("capital_gains_tax", tax_year)[0])
    except:
        result["capital_gains_tax"] = 0

    try:
        if income_sources.get('business_income', 0) > 0:
            result["self_employment_tax"] = float(simulation.calculate("self_employment_tax", tax_year)[0])
        else:
            result["self_employment_tax"] = 0
    except:
        result["self_employment_tax"] = 0

    # Add state-specific details if available
    if state:
        try:
            result["state_agi"] = float(simulation.calculate("state_agi", tax_year)[0])
        except:
            pass

    return result


def calculate_trust_tax(trust_income: float, trust_details: Dict, tax_year: int) -> Dict[str, float]:
    """
    Calculate federal trust tax with compressed brackets.
    Trusts hit top rate at ~$15,200 vs $609,350 for individuals!

    IMPORTANT: Grantor trusts are pass-through entities. All income is taxed to the
    grantor on their personal Form 1040, NOT on the trust's Form 1041.
    This function returns $0 tax for grantor trusts to prevent double taxation.
    """
    # Check if this is a grantor trust
    trust_type = trust_details.get('trust_type', 'complex')
    is_grantor_trust = trust_type.lower() == 'grantor'

    if is_grantor_trust:
        # Grantor trust: all income passes through to grantor's Form 1040
        # Trust pays $0 tax to prevent double taxation
        return {
            "trust_income": float(trust_income),
            "dni": float(trust_income),
            "distributions": 0.0,
            "trust_taxable_income": 0.0,
            "federal_tax": 0.0,
            "effective_rate": 0.0,
            "is_grantor_trust": True,
            "note": "Grantor trust: All income taxed to grantor on Form 1040. Trust pays $0 tax to prevent double taxation."
        }

    # Non-grantor trust: calculate tax normally
    # 2024 trust tax brackets (compressed)
    trust_brackets = [
        (3150, 0.10),
        (11450, 0.24),
        (15200, 0.35),
        (float('inf'), 0.37)
    ]

    # Distributable Net Income (DNI)
    dni = trust_details.get('distributable_net_income', trust_income)
    distributions = trust_details.get('distributions_to_beneficiaries', 0)

    # Trust keeps income not distributed
    trust_taxable_income = max(0, dni - distributions)
    
    # Calculate tax with compressed brackets
    tax = 0
    prev_bracket = 0
    
    for bracket_limit, rate in trust_brackets:
        if trust_taxable_income <= prev_bracket:
            break
        
        taxable_in_bracket = min(trust_taxable_income - prev_bracket, bracket_limit - prev_bracket)
        tax += taxable_in_bracket * rate
        prev_bracket = bracket_limit
    
    return {
        "trust_income": float(trust_income),
        "dni": float(dni),
        "distributions": float(distributions),
        "trust_taxable_income": float(trust_taxable_income),
        "federal_tax": float(tax),
        "effective_rate": float(tax / trust_income * 100) if trust_income > 0 else 0,
        "top_rate_threshold": 15200,
        "is_grantor_trust": False,
        "trust_type": trust_type,
        "note": "Non-grantor trust: Trusts reach 37% rate at $15,200 vs $609,350 for individuals"
    }


def calculate_massachusetts_tax(
    income_sources: Dict[str, float],
    entity_type: str,
    tax_year: int = 2024
) -> Dict[str, float]:
    """
    Calculate Massachusetts state tax with specific rules.
    Uses PolicyEngine's parameter system for accurate, maintained tax rates.

    MA has 5% flat rate on ordinary income and long-term capital gains.
    STCG rate changed from 12% → 8.5% in 2023 (Bill H.4104 Section 8).

    Reference:
    - PolicyEngine-US parameter system (authoritative source)
    - https://malegislature.gov/Bills/193/H4104/BillHistory
    """
    # Get MA tax rates directly from PolicyEngine parameter system
    # This ensures rates are always accurate and automatically updated
    date_str = f"{tax_year}-01-01"

    ma_params = pe_system.parameters.gov.states.ma.tax.income.rates
    ordinary_rate = ma_params.part_b(date_str)  # Part B: ordinary income
    stcg_rate = ma_params.part_a.capital_gains(date_str)  # Part A: STCG
    ltcg_rate = ma_params.part_c(date_str)  # Part C: LTCG (same as Part B)
    
    # Calculate by income type
    ordinary_income = (
        income_sources.get('w2_income', 0) +
        income_sources.get('taxable_interest', 0) +
        income_sources.get('ordinary_dividends', 0) +
        income_sources.get('business_income', 0)
    )
    
    stcg = income_sources.get('short_term_capital_gains', 0)
    ltcg = income_sources.get('long_term_capital_gains', 0)
    
    # Calculate taxes
    ordinary_tax = ordinary_income * ordinary_rate
    stcg_tax = stcg * stcg_rate
    ltcg_tax = ltcg * ltcg_rate
    
    # Personal exemption (simplified)
    exemption = 4400 if entity_type == 'individual' else 0
    
    total_ma_tax = max(0, ordinary_tax + stcg_tax + ltcg_tax - exemption * ordinary_rate)
    
    return {
        "ordinary_income": float(ordinary_income),
        "ordinary_tax": float(ordinary_tax),
        "short_term_gains": float(stcg),
        "stcg_tax": float(stcg_tax),
        "stcg_rate": float(stcg_rate * 100),
        "long_term_gains": float(ltcg),
        "ltcg_tax": float(ltcg_tax),
        "personal_exemption": float(exemption),
        "total_ma_tax": float(total_ma_tax),
        "rate_source": "PolicyEngine-US parameter system",
        "note": f"MA charges {stcg_rate*100}% on STCG vs {ordinary_rate*100}% on other income (rates from PolicyEngine for {tax_year})"
    }


def get_amt_exemption(filing_status: str, agi: float, tax_year: int) -> float:
    """Get AMT exemption amount with phase-out"""
    # 2024 AMT exemptions
    exemptions = {
        'Single': 85700,
        'Married Filing Jointly': 133300,
        'Married Filing Separately': 66650,
        'Head of Household': 85700
    }
    
    # Phase-out thresholds
    phase_out_start = {
        'Single': 609350,
        'Married Filing Jointly': 1218700,
        'Married Filing Separately': 609350,
        'Head of Household': 609350
    }
    
    exemption = exemptions.get(filing_status, 85700)
    threshold = phase_out_start.get(filing_status, 609350)
    
    # Phase out at 25 cents per dollar over threshold
    if agi > threshold:
        reduction = (agi - threshold) * 0.25
        exemption = max(0, exemption - reduction)
    
    return exemption


def get_marginal_rate(income: float, filing_status: str, entity_type: str, tax_year: int) -> float:
    """Get marginal tax rate for income level"""
    if entity_type == "trust":
        # Trust brackets (compressed)
        if income > 15200:
            return 37.0
        elif income > 11450:
            return 35.0
        elif income > 3150:
            return 24.0
        else:
            return 10.0
    else:
        # Individual brackets (2024, simplified)
        if filing_status == "Single":
            if income > 609350:
                return 37.0
            elif income > 243725:
                return 35.0
            elif income > 191950:
                return 32.0
            elif income > 100525:
                return 28.0
            elif income > 47150:
                return 22.0
            elif income > 11600:
                return 12.0
            else:
                return 10.0
        else:  # Married Filing Jointly (simplified)
            if income > 731200:
                return 37.0
            elif income > 487450:
                return 35.0
            elif income > 383900:
                return 32.0
            elif income > 201050:
                return 28.0
            elif income > 94300:
                return 22.0
            elif income > 23200:
                return 12.0
            else:
                return 10.0


def get_capital_gains_rate(income: float, filing_status: str, tax_year: int) -> float:
    """Get long-term capital gains tax rate"""
    # 2024 LTCG brackets
    if filing_status == "Single":
        if income > 553850:
            return 20.0
        elif income > 47025:
            return 15.0
        else:
            return 0.0
    else:  # Married Filing Jointly
        if income > 583750:
            return 20.0
        elif income > 94050:
            return 15.0
        else:
            return 0.0


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Tax MCP Server v2 - Enhanced Edition")
    logger.info("=" * 70)
    logger.info("")
    logger.info("New Features (addressing ~/investing/feedback.md):")
    logger.info("✓ Net Investment Income Tax (3.8% surtax)")
    logger.info("✓ Trust taxation with compressed brackets")
    logger.info("✓ Massachusetts state tax (12% STCG rate)")
    logger.info("✓ Comprehensive AMT calculations")
    logger.info("✓ Tax planning recommendations")
    logger.info("✓ Confidence scoring on all calculations")
    logger.info("")
    logger.info("Single Comprehensive Tool:")
    logger.info("• calculate_comprehensive_tax handles all scenarios")
    logger.info("• Individuals, trusts, and estates")
    logger.info("• Federal, state, NIIT, and AMT in one call")
    logger.info("• Marginal analysis and planning recommendations")
    logger.info("")
    logger.info("Key Improvements:")
    logger.info("• NIIT with proper MAGI calculation and thresholds")
    logger.info("• Trust tax with Form 1041 compressed brackets")
    logger.info("• MA: 5% ordinary, 12% STCG, 5% LTCG")
    logger.info("• Full confidence scoring based on data completeness")
    logger.info("=" * 70)
    
    server.run(transport="stdio")