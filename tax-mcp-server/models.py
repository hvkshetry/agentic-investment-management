"""
Pydantic models for Tax MCP Server
Provides strong typing and validation for all MCP tool inputs and outputs
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Dict, Any, List, Optional, Union, Literal
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class FilingStatus(str, Enum):
    """Tax filing status options"""
    SINGLE = "Single"
    MARRIED_FILING_JOINTLY = "MarriedFilingJointly"
    MARRIED_FILING_SEPARATELY = "MarriedFilingSeparately"
    HEAD_OF_HOUSEHOLD = "HeadOfHousehold"
    QUALIFYING_WIDOW = "QualifyingWidow"


class EntityType(str, Enum):
    """Tax entity types"""
    INDIVIDUAL = "individual"
    TRUST = "trust"
    ESTATE = "estate"
    CORPORATION = "corporation"
    PARTNERSHIP = "partnership"


class IncomeType(str, Enum):
    """Types of income for tax purposes"""
    ORDINARY = "ordinary"
    QUALIFIED_DIVIDEND = "qualified_dividend"
    SHORT_TERM_CAPITAL_GAIN = "short_term_capital_gain"
    LONG_TERM_CAPITAL_GAIN = "long_term_capital_gain"
    TAX_EXEMPT = "tax_exempt"
    BUSINESS = "business"
    RENTAL = "rental"
    RETIREMENT = "retirement"


class DeductionType(str, Enum):
    """Types of tax deductions"""
    STANDARD = "standard"
    ITEMIZED = "itemized"
    MORTGAGE_INTEREST = "mortgage_interest"
    STATE_LOCAL_TAX = "state_local_tax"
    CHARITABLE = "charitable"
    MEDICAL = "medical"
    BUSINESS_EXPENSE = "business_expense"


class TaxStrategy(str, Enum):
    """Tax optimization strategies"""
    TAX_LOSS_HARVESTING = "tax_loss_harvesting"
    BRACKET_MANAGEMENT = "bracket_management"
    DEDUCTION_BUNCHING = "deduction_bunching"
    ROTH_CONVERSION = "roth_conversion"
    CHARITABLE_GIVING = "charitable_giving"
    ESTATE_PLANNING = "estate_planning"


class StateCode(str, Enum):
    """US state codes for state tax calculations"""
    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"
    DC = "DC"


# ============================================================================
# BASE MODELS
# ============================================================================

class TaxBracketModel(BaseModel):
    """Tax bracket information"""
    bracket_min: float = Field(..., ge=0, description="Minimum income for bracket")
    bracket_max: Optional[float] = Field(None, description="Maximum income for bracket (None for top)")
    rate: float = Field(..., ge=0, le=1, description="Tax rate for bracket")
    tax_owed: float = Field(..., ge=0, description="Tax owed in this bracket")


class TaxablePositionModel(BaseModel):
    """Position with tax implications"""
    symbol: str = Field(..., min_length=1, description="Stock symbol")
    shares: float = Field(..., gt=0, description="Number of shares")
    cost_basis: float = Field(..., gt=0, description="Total cost basis")
    current_value: float = Field(..., ge=0, description="Current market value")
    unrealized_gain: float = Field(..., description="Unrealized gain/loss")
    purchase_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="Purchase date")
    is_long_term: bool = Field(default=False, description="Qualifies for long-term treatment")


class TaxScenarioModel(BaseModel):
    """Tax scenario for comparison"""
    scenario_name: str = Field(..., description="Scenario identifier")
    year: int = Field(..., ge=2020, le=2030, description="Tax year")
    filing_status: FilingStatus = Field(..., description="Filing status")
    state: Optional[str] = Field(None, description="State code for state tax")
    w2_income: float = Field(default=0, ge=0, description="W2 wages")
    business_income: float = Field(default=0, description="Business income")
    investment_income: Dict[str, float] = Field(default_factory=dict, description="Investment income by type")
    deductions: Dict[str, float] = Field(default_factory=dict, description="Deductions")
    credits: Dict[str, float] = Field(default_factory=dict, description="Tax credits")
    
    model_config = ConfigDict(use_enum_values=True)


class TaxHarvestingOpportunityModel(BaseModel):
    """Tax loss harvesting opportunity"""
    symbol: str = Field(..., description="Stock symbol")
    shares_to_sell: float = Field(..., gt=0, description="Shares to harvest")
    loss_amount: float = Field(..., lt=0, description="Loss to be realized")
    tax_savings: float = Field(..., ge=0, description="Estimated tax savings")
    wash_sale_risk: bool = Field(default=False, description="Risk of wash sale rule")
    replacement_symbol: Optional[str] = Field(None, description="Suggested replacement holding")


class QuarterlyPaymentModel(BaseModel):
    """Quarterly estimated tax payment"""
    quarter: int = Field(..., ge=1, le=4, description="Quarter number")
    due_date: str = Field(..., description="Payment due date")
    amount_due: float = Field(..., ge=0, description="Payment amount")
    safe_harbor_amount: float = Field(..., ge=0, description="Safe harbor payment")
    actual_amount: float = Field(..., ge=0, description="Actual estimated payment")


# ============================================================================
# REQUEST MODELS
# ============================================================================

class CalculateTaxLiabilityRequest(BaseModel):
    """Request for calculate_tax_liability"""
    year: int = Field(
        default=2024,
        ge=2020,
        le=2030,
        description="Tax year"
    )
    state: Optional[str] = Field(
        None,
        description="State code for state tax calculation"
    )
    filing_status: FilingStatus = Field(
        default=FilingStatus.SINGLE,
        description="Tax filing status"
    )
    num_dependents: int = Field(
        default=0,
        ge=0,
        description="Number of dependents"
    )
    w2_income: float = Field(
        default=0.0,
        ge=0,
        description="W2 wage income"
    )
    taxable_interest: float = Field(
        default=0.0,
        ge=0,
        description="Taxable interest income"
    )
    qualified_dividends: float = Field(
        default=0.0,
        ge=0,
        description="Qualified dividend income"
    )
    ordinary_dividends: float = Field(
        default=0.0,
        ge=0,
        description="Ordinary (non-qualified) dividends"
    )
    short_term_capital_gains: float = Field(
        default=0.0,
        description="Short-term capital gains/losses"
    )
    long_term_capital_gains: float = Field(
        default=0.0,
        description="Long-term capital gains/losses"
    )
    
    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('state')
    def validate_state(cls, v):
        """Validate state code"""
        if v and v not in [s.value for s in StateCode]:
            # Allow but log warning for unknown states
            pass
        return v


class OptimizeTaxHarvestRequest(BaseModel):
    """Request for optimize_tax_harvest"""
    positions: List[TaxablePositionModel] = Field(
        ...,
        min_length=1,
        description="List of positions to consider for harvesting"
    )
    target_loss_amount: float = Field(
        default=3000.0,
        gt=0,
        description="Target amount of losses to harvest"
    )


class CompareTaxScenariosRequest(BaseModel):
    """Request for compare_tax_scenarios"""
    scenarios: List[TaxScenarioModel] = Field(
        ...,
        min_length=2,
        description="List of scenarios to compare (minimum 2)"
    )


class EstimateQuarterlyPaymentsRequest(BaseModel):
    """Request for estimate_quarterly_payments"""
    ytd_income: Dict[str, float] = Field(
        ...,
        description="Year-to-date income by category"
    )
    prior_year_tax: float = Field(
        ...,
        ge=0,
        description="Prior year total tax liability"
    )
    payments_made: float = Field(
        default=0.0,
        ge=0,
        description="Estimated payments already made"
    )
    current_quarter: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Current quarter (1-4)"
    )
    
    @field_validator('ytd_income')
    def validate_income(cls, v):
        """Ensure all income values are non-negative"""
        for category, amount in v.items():
            if amount < 0 and category not in ['capital_losses', 'business_loss']:
                raise ValueError(f"Income category {category} cannot be negative")
        return v


class AnalyzeBracketImpactRequest(BaseModel):
    """Request for analyze_bracket_impact"""
    base_scenario: TaxScenarioModel = Field(
        ...,
        description="Base tax scenario"
    )
    additional_income: float = Field(
        ...,
        gt=0,
        description="Additional income to analyze"
    )
    income_type: IncomeType = Field(
        default=IncomeType.ORDINARY,
        description="Type of additional income"
    )
    
    model_config = ConfigDict(use_enum_values=True)


class CalculateComprehensiveTaxRequest(BaseModel):
    """Request for calculate_comprehensive_tax (v2)"""
    tax_year: int = Field(
        default=2024,
        ge=2020,
        le=2030,
        description="Tax year"
    )
    entity_type: EntityType = Field(
        default=EntityType.INDIVIDUAL,
        description="Tax entity type"
    )
    filing_status: FilingStatus = Field(
        default=FilingStatus.SINGLE,
        description="Filing status"
    )
    state: str = Field(
        default="",
        description="State code (empty for no state tax)"
    )
    income_sources: Dict[str, float] = Field(
        default_factory=dict,
        description="Income by source"
    )
    deductions: Dict[str, float] = Field(
        default_factory=dict,
        description="Deductions by type"
    )
    credits: Dict[str, float] = Field(
        default_factory=dict,
        description="Tax credits"
    )
    dependents: int = Field(
        default=0,
        ge=0,
        description="Number of dependents"
    )
    include_niit: bool = Field(
        default=True,
        description="Include Net Investment Income Tax"
    )
    include_amt: bool = Field(
        default=True,
        description="Include Alternative Minimum Tax"
    )
    
    model_config = ConfigDict(use_enum_values=True)


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class TaxLiabilityBreakdownModel(BaseModel):
    """Detailed tax liability breakdown"""
    gross_income: float = Field(..., description="Total gross income")
    adjusted_gross_income: float = Field(..., description="AGI")
    taxable_income: float = Field(..., description="Taxable income after deductions")
    federal_tax: float = Field(..., ge=0, description="Federal tax liability")
    state_tax: float = Field(..., ge=0, description="State tax liability")
    fica_tax: float = Field(..., ge=0, description="FICA taxes")
    medicare_tax: float = Field(..., ge=0, description="Medicare tax")
    niit_tax: float = Field(..., ge=0, description="Net Investment Income Tax")
    total_tax: float = Field(..., ge=0, description="Total tax liability")
    effective_rate: float = Field(..., ge=0, le=1, description="Effective tax rate")
    marginal_rate: float = Field(..., ge=0, le=1, description="Marginal tax rate")
    brackets: List[TaxBracketModel] = Field(..., description="Tax brackets applied")


class CalculateTaxLiabilityResponse(BaseModel):
    """Response for calculate_tax_liability"""
    breakdown: TaxLiabilityBreakdownModel = Field(..., description="Tax calculation breakdown")
    after_tax_income: float = Field(..., description="Income after all taxes")
    tax_savings_opportunities: List[str] = Field(..., description="Suggested tax savings strategies")
    warnings: List[str] = Field(default_factory=list, description="Tax calculation warnings")


class OptimizeTaxHarvestResponse(BaseModel):
    """Response for optimize_tax_harvest"""
    recommended_harvests: List[TaxHarvestingOpportunityModel] = Field(
        ...,
        description="Recommended positions to harvest"
    )
    total_loss_harvested: float = Field(..., le=0, description="Total losses to harvest")
    estimated_tax_savings: float = Field(..., ge=0, description="Total estimated tax savings")
    capital_loss_carryforward: float = Field(..., le=0, description="Losses to carry forward")
    wash_sale_positions: List[str] = Field(default_factory=list, description="Positions with wash sale risk")
    implementation_steps: List[str] = Field(..., description="Steps to implement harvesting")


class TaxScenarioComparisonModel(BaseModel):
    """Tax scenario comparison result"""
    scenario_name: str = Field(..., description="Scenario identifier")
    total_tax: float = Field(..., ge=0, description="Total tax liability")
    after_tax_income: float = Field(..., description="After-tax income")
    effective_rate: float = Field(..., ge=0, le=1, description="Effective tax rate")
    marginal_rate: float = Field(..., ge=0, le=1, description="Marginal tax rate")
    tax_savings: float = Field(..., description="Tax savings vs baseline")
    key_differences: List[str] = Field(..., description="Key differences from baseline")


class CompareTaxScenariosResponse(BaseModel):
    """Response for compare_tax_scenarios"""
    comparisons: List[TaxScenarioComparisonModel] = Field(..., description="Scenario comparisons")
    best_scenario: str = Field(..., description="Best scenario name")
    worst_scenario: str = Field(..., description="Worst scenario name")
    max_savings: float = Field(..., ge=0, description="Maximum possible tax savings")
    recommendations: List[str] = Field(..., description="Tax optimization recommendations")


class EstimateQuarterlyPaymentsResponse(BaseModel):
    """Response for estimate_quarterly_payments"""
    quarterly_schedule: List[QuarterlyPaymentModel] = Field(..., description="Payment schedule")
    total_required: float = Field(..., ge=0, description="Total estimated tax required")
    safe_harbor_total: float = Field(..., ge=0, description="Safe harbor total")
    remaining_due: float = Field(..., ge=0, description="Remaining amount due")
    penalty_risk: bool = Field(..., description="Risk of underpayment penalty")
    recommended_payment: float = Field(..., ge=0, description="Recommended next payment")


class BracketImpactAnalysisModel(BaseModel):
    """Tax bracket impact analysis"""
    current_bracket: float = Field(..., ge=0, le=1, description="Current marginal rate")
    new_bracket: float = Field(..., ge=0, le=1, description="New marginal rate")
    marginal_tax_on_income: float = Field(..., ge=0, description="Tax on additional income")
    effective_rate_change: float = Field(..., description="Change in effective rate")
    bracket_room: float = Field(..., ge=0, description="Room in current bracket")
    next_bracket_threshold: float = Field(..., ge=0, description="Income to next bracket")


class AnalyzeBracketImpactResponse(BaseModel):
    """Response for analyze_bracket_impact"""
    impact_analysis: BracketImpactAnalysisModel = Field(..., description="Bracket impact analysis")
    total_additional_tax: float = Field(..., ge=0, description="Total additional tax")
    after_tax_additional: float = Field(..., description="After-tax additional income")
    optimization_suggestions: List[str] = Field(..., description="Tax optimization suggestions")
    timing_recommendations: List[str] = Field(..., description="Income timing recommendations")


class ComprehensiveTaxResultModel(BaseModel):
    """Comprehensive tax calculation result"""
    federal_tax: TaxLiabilityBreakdownModel = Field(..., description="Federal tax breakdown")
    state_tax: Optional[TaxLiabilityBreakdownModel] = Field(None, description="State tax breakdown")
    total_combined_tax: float = Field(..., ge=0, description="Total federal + state tax")
    combined_effective_rate: float = Field(..., ge=0, le=1, description="Combined effective rate")
    amt_liability: Optional[float] = Field(None, description="AMT liability if applicable")
    strategies: List[TaxStrategy] = Field(..., description="Applicable tax strategies")
    
    model_config = ConfigDict(use_enum_values=True)


class CalculateComprehensiveTaxResponse(BaseModel):
    """Response for calculate_comprehensive_tax"""
    results: ComprehensiveTaxResultModel = Field(..., description="Tax calculation results")
    optimization_potential: float = Field(..., ge=0, description="Potential tax savings")
    planning_opportunities: List[str] = Field(..., description="Tax planning opportunities")
    compliance_notes: List[str] = Field(..., description="Compliance considerations")


# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())