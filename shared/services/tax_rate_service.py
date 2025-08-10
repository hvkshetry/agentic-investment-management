#!/usr/bin/env python3
"""
Tax Rate Service - Single source of truth for tax calculations
Uses tenforty when available, provides fallback calculations
Eliminates hardcoded tax rates throughout the system
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import tenforty
try:
    import tenforty
    TENFORTY_AVAILABLE = True
except ImportError:
    TENFORTY_AVAILABLE = False
    logger.warning("tenforty not available - using fallback tax brackets")

class TaxRateService:
    """Centralized service for all tax rate calculations"""
    
    def __init__(self):
        self.tenforty_available = TENFORTY_AVAILABLE
        
        # 2024 Federal tax brackets for fallback
        self.federal_brackets_2024 = {
            "Single": [
                (11600, 0.10),    # Up to $11,600
                (47150, 0.12),    # $11,601 to $47,150
                (100525, 0.22),   # $47,151 to $100,525
                (191950, 0.24),   # $100,526 to $191,950
                (243725, 0.32),   # $191,951 to $243,725
                (609350, 0.35),   # $243,726 to $609,350
                (float('inf'), 0.37)  # Over $609,350
            ],
            "Married/Joint": [
                (23200, 0.10),    # Up to $23,200
                (94300, 0.12),    # $23,201 to $94,300
                (201050, 0.22),   # $94,301 to $201,050
                (383900, 0.24),   # $201,051 to $383,900
                (487450, 0.32),   # $383,901 to $487,450
                (731200, 0.35),   # $487,451 to $731,200
                (float('inf'), 0.37)  # Over $731,200
            ]
        }
        
        # Capital gains tax rates (simplified)
        self.ltcg_brackets_2024 = {
            "Single": [
                (47025, 0.00),    # 0% bracket
                (518900, 0.15),   # 15% bracket
                (float('inf'), 0.20)  # 20% bracket
            ],
            "Married/Joint": [
                (94050, 0.00),    # 0% bracket
                (583750, 0.15),   # 15% bracket
                (float('inf'), 0.20)  # 20% bracket
            ]
        }
        
        # NIIT threshold (Net Investment Income Tax)
        self.niit_threshold = {
            "Single": 200000,
            "Married/Joint": 250000
        }
        self.niit_rate = 0.038  # 3.8%
        
        # State tax rates (simplified)
        self.state_rates = {
            "CA": 0.093,  # California top rate (approximate)
            "NY": 0.0882, # New York top rate
            "MA": 0.05,   # Massachusetts flat rate
            "TX": 0.00,   # No state income tax
            "FL": 0.00,   # No state income tax
            "WA": 0.00,   # No state income tax
            "NV": 0.00,   # No state income tax
            "WY": 0.00,   # No state income tax
            "SD": 0.00,   # No state income tax
            "AK": 0.00,   # No state income tax
            "TN": 0.00,   # No state income tax (as of 2023)
            "NH": 0.00,   # No wage income tax
        }
    
    def get_federal_marginal_rate(
        self, 
        income: float, 
        filing_status: str = "Single",
        year: int = 2024
    ) -> float:
        """
        Get federal marginal tax rate for given income
        Uses tenforty if available, otherwise uses bracket tables
        """
        if self.tenforty_available and year >= 2020:
            try:
                # Use tenforty for accurate calculation
                result = tenforty.evaluate_return(
                    year=year,
                    filing_status=filing_status,
                    w2_income=income
                )
                return result.federal_tax_bracket / 100.0
            except Exception as e:
                logger.warning(f"tenforty calculation failed: {e}, using fallback")
        
        # Fallback to bracket tables
        brackets = self.federal_brackets_2024.get(filing_status, self.federal_brackets_2024["Single"])
        
        for threshold, rate in brackets:
            if income <= threshold:
                return rate
        
        return 0.37  # Top rate
    
    def get_federal_effective_rate(
        self,
        income: float,
        filing_status: str = "Single",
        year: int = 2024,
        deductions: float = 0
    ) -> float:
        """Calculate federal effective tax rate"""
        if self.tenforty_available and year >= 2020:
            try:
                result = tenforty.evaluate_return(
                    year=year,
                    filing_status=filing_status,
                    w2_income=income,
                    itemized_deductions=deductions if deductions > 0 else None
                )
                return result.federal_effective_tax_rate / 100.0
            except Exception as e:
                logger.warning(f"tenforty calculation failed: {e}, using fallback")
        
        # Simplified fallback calculation
        taxable_income = max(0, income - deductions)
        tax = self.calculate_federal_tax(taxable_income, filing_status)
        return tax / income if income > 0 else 0
    
    def calculate_federal_tax(
        self,
        taxable_income: float,
        filing_status: str = "Single"
    ) -> float:
        """Calculate total federal tax owed"""
        brackets = self.federal_brackets_2024.get(filing_status, self.federal_brackets_2024["Single"])
        
        tax = 0
        prev_threshold = 0
        
        for threshold, rate in brackets:
            if taxable_income <= prev_threshold:
                break
            
            taxable_in_bracket = min(taxable_income, threshold) - prev_threshold
            tax += taxable_in_bracket * rate
            prev_threshold = threshold
            
            if taxable_income <= threshold:
                break
        
        return tax
    
    def get_capital_gains_rate(
        self,
        income: float,
        filing_status: str = "Single",
        is_long_term: bool = True
    ) -> float:
        """
        Get capital gains tax rate
        Returns rate as decimal (0.15 for 15%)
        """
        if not is_long_term:
            # Short-term gains taxed as ordinary income
            return self.get_federal_marginal_rate(income, filing_status)
        
        # Long-term capital gains rates
        brackets = self.ltcg_brackets_2024.get(filing_status, self.ltcg_brackets_2024["Single"])
        
        for threshold, rate in brackets:
            if income <= threshold:
                return rate
        
        return 0.20  # Top LTCG rate
    
    def get_niit_rate(self, income: float, filing_status: str = "Single") -> float:
        """
        Get Net Investment Income Tax rate (3.8% for high earners)
        Returns 0.038 if income exceeds threshold, 0 otherwise
        """
        threshold = self.niit_threshold.get(filing_status, self.niit_threshold["Single"])
        return self.niit_rate if income > threshold else 0.0
    
    def get_state_rate(
        self,
        income: float,
        state: str,
        filing_status: str = "Single",
        year: int = 2024
    ) -> float:
        """
        Get state income tax rate
        Uses tenforty for CA, MA, NY if available
        """
        if not state or state == "None":
            return 0.0
        
        state = state.upper()
        
        # Try tenforty for supported states
        if self.tenforty_available and state in ["CA", "MA", "NY"] and year >= 2020:
            try:
                result = tenforty.evaluate_return(
                    year=year,
                    state=state,
                    filing_status=filing_status,
                    w2_income=income
                )
                if hasattr(result, 'state_tax_bracket'):
                    return result.state_tax_bracket / 100.0
            except Exception as e:
                logger.warning(f"tenforty state calculation failed: {e}, using fallback")
        
        # Fallback to simplified rates
        return self.state_rates.get(state, 0.05)  # Default 5% if unknown state
    
    def get_combined_capital_gains_rate(
        self,
        income: float,
        filing_status: str = "Single",
        state: str = None,
        is_long_term: bool = True
    ) -> float:
        """
        Get combined federal + state + NIIT rate for capital gains
        This is what should be used for tax impact calculations
        """
        federal_rate = self.get_capital_gains_rate(income, filing_status, is_long_term)
        state_rate = self.get_state_rate(income, state, filing_status) if state else 0
        niit_rate = self.get_niit_rate(income, filing_status)
        
        # Combined rate (not perfectly accurate due to deductibility, but close)
        return federal_rate + state_rate + niit_rate
    
    def estimate_tax_on_sale(
        self,
        gain: float,
        income: float,
        filing_status: str = "Single",
        state: str = None,
        is_long_term: bool = True
    ) -> Dict[str, float]:
        """
        Estimate tax on a capital gain
        Returns breakdown of federal, state, NIIT, and total tax
        """
        federal_rate = self.get_capital_gains_rate(income, filing_status, is_long_term)
        federal_tax = gain * federal_rate
        
        state_rate = self.get_state_rate(income + gain, state, filing_status) if state else 0
        state_tax = gain * state_rate
        
        niit_rate = self.get_niit_rate(income + gain, filing_status)
        niit_tax = gain * niit_rate
        
        return {
            "federal_tax": federal_tax,
            "federal_rate": federal_rate,
            "state_tax": state_tax,
            "state_rate": state_rate,
            "niit_tax": niit_tax,
            "niit_rate": niit_rate,
            "total_tax": federal_tax + state_tax + niit_tax,
            "effective_rate": (federal_tax + state_tax + niit_tax) / gain if gain > 0 else 0
        }

# Singleton instance
_tax_rate_service = None

def get_tax_rate_service() -> TaxRateService:
    """Get or create the singleton TaxRateService instance"""
    global _tax_rate_service
    if _tax_rate_service is None:
        _tax_rate_service = TaxRateService()
    return _tax_rate_service