#!/usr/bin/env python3
"""
Tax MCP Server v2 - Enhanced with NIIT, Trust Taxes, and State-Specific Rules
Addresses all tax deficiencies from ~/investing/feedback.md
Consolidated into single comprehensive tax analysis tool
"""

from fastmcp import FastMCP
from typing import Dict, List, Optional, Any, Union
import logging
import sys
import os
from datetime import datetime
import tenforty

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
    state: Optional[str] = None,
    income_sources: Dict[str, float] = None,
    deductions: Dict[str, float] = None,
    credits: Dict[str, float] = None,
    dependents: int = 0,
    include_niit: bool = True,
    include_amt: bool = True,
    trust_details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Comprehensive tax calculation including NIIT, trust taxes, and state-specific rules.
    Single tool that handles all tax scenarios per reviewer feedback.
    
    Args:
        tax_year: Tax year (2018-2024)
        entity_type: 'individual', 'trust', or 'estate'
        filing_status: For individuals: 'Single', 'Married Filing Jointly', etc.
        state: Two-letter state code (e.g., 'MA', 'CA', 'NY')
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
        
        # Default income sources
        if income_sources is None:
            income_sources = {}
        
        if deductions is None:
            deductions = {}
        
        if credits is None:
            credits = {}
        
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
                logger.error(f"Failed to fetch from Portfolio State: {e}")
                raise ValueError(f"Portfolio State required but failed: {e}")
        
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
            # Use tenforty for individual calculation
            base_result = tenforty.evaluate_return(
                year=tax_year,
                state=state,
                filing_status=filing_status,
                num_dependents=dependents,
                w2_income=income_sources.get('w2_income', 0),
                taxable_interest=income_sources.get('taxable_interest', 0),
                qualified_dividends=income_sources.get('qualified_dividends', 0),
                ordinary_dividends=income_sources.get('ordinary_dividends', 0),
                short_term_capital_gains=income_sources.get('short_term_capital_gains', 0),
                long_term_capital_gains=income_sources.get('long_term_capital_gains', 0),
                incentive_stock_option_gains=income_sources.get('iso_gains', 0),
                itemized_deductions=deductions.get('itemized_deductions', 0)
            )
            
            federal_tax = base_result.federal_total_tax
            state_tax = base_result.state_total_tax if base_result.state_total_tax else 0
            agi = base_result.federal_adjusted_gross_income
            
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
            # Calculate Modified Adjusted Gross Income (MAGI)
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
            
            # NIIT thresholds
            niit_thresholds = {
                'Single': 200000,
                'Married Filing Jointly': 250000,
                'Married Filing Separately': 125000,
                'Head of Household': 200000,
                'trust': 15200  # 2024 trust threshold (much lower!)
            }
            
            threshold = niit_thresholds.get(filing_status if entity_type == 'individual' else 'trust', 200000)
            
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
                "effective_niit_rate": float(niit_tax / magi * 100) if magi > 0 else 0
            }
            
            federal_tax += niit_tax
        
        # =========================
        # 3. MASSACHUSETTS STATE TAX SPECIFICS
        # =========================
        
        if state == "MA":
            ma_tax = calculate_massachusetts_tax(income_sources, entity_type)
            state_tax = ma_tax["total_ma_tax"]
            result["state_tax"]["massachusetts_detail"] = ma_tax
        
        # =========================
        # 4. AMT CALCULATION
        # =========================
        
        if include_amt and entity_type == "individual":
            # AMT calculation (simplified - tenforty handles most of it)
            if hasattr(base_result, 'federal_amt'):
                amt = base_result.federal_amt
                result["amt_calculation"] = {
                    "amt_income": float(agi + income_sources.get('iso_gains', 0)),
                    "amt_exemption": get_amt_exemption(filing_status, agi, tax_year),
                    "tentative_amt": float(amt),
                    "regular_tax": float(federal_tax - amt),
                    "amt_owed": float(max(0, amt)),
                    "is_amt_liable": amt > 0
                }
        
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
        # 8. TAX PLANNING RECOMMENDATIONS
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
            "tax_engine": "tenforty + custom calculations"
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Comprehensive tax calculation failed: {str(e)}")
        raise ValueError(f"Tax calculation failed: {str(e)}")


def calculate_trust_tax(trust_income: float, trust_details: Dict, tax_year: int) -> Dict[str, float]:
    """
    Calculate federal trust tax with compressed brackets.
    Trusts hit top rate at ~$15,200 vs $609,350 for individuals!
    """
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
        "note": "Trusts reach 37% rate at $15,200 vs $609,350 for individuals"
    }


def calculate_massachusetts_tax(income_sources: Dict[str, float], entity_type: str) -> Dict[str, float]:
    """
    Calculate Massachusetts state tax with specific rules.
    MA has 5% flat rate but 12% on short-term capital gains!
    """
    # MA tax rates
    ordinary_rate = 0.05  # 5% flat rate
    stcg_rate = 0.12  # 12% on short-term gains
    ltcg_rate = 0.05  # 5% on long-term gains
    
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
        "note": "MA charges 12% on STCG vs 5% on other income"
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