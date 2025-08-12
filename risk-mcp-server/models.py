"""
Pydantic models for Risk MCP Server
Provides strong typing and validation for all MCP tool inputs and outputs
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Dict, Any, List, Optional, Union, Literal
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class TreasuryMaturity(str, Enum):
    """Treasury maturity options"""
    THREE_MONTH = "3m"
    ONE_YEAR = "1y"
    FIVE_YEAR = "5y"
    TEN_YEAR = "10y"
    THIRTY_YEAR = "30y"


class RiskMetricType(str, Enum):
    """Types of risk metrics"""
    VAR = "VaR"
    CVAR = "CVaR"
    SHARPE = "sharpe_ratio"
    SORTINO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    VOLATILITY = "volatility"
    BETA = "beta"
    ALPHA = "alpha"
    INFORMATION_RATIO = "information_ratio"
    TRACKING_ERROR = "tracking_error"


class StressScenarioType(str, Enum):
    """Pre-defined stress test scenarios"""
    MARKET_CRASH = "market_crash"
    INTEREST_RATE_SHOCK = "interest_rate_shock"
    INFLATION_SPIKE = "inflation_spike"
    CREDIT_CRISIS = "credit_crisis"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    CUSTOM = "custom"


# ============================================================================
# BASE MODELS
# ============================================================================

class RiskMetricsModel(BaseModel):
    """Comprehensive risk metrics"""
    volatility: float = Field(..., ge=0, description="Annualized volatility")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    max_drawdown: float = Field(..., le=0, description="Maximum drawdown (negative)")
    calmar_ratio: float = Field(..., description="Calmar ratio")
    beta: Optional[float] = Field(None, description="Beta vs benchmark")
    alpha: Optional[float] = Field(None, description="Alpha vs benchmark")
    tracking_error: Optional[float] = Field(None, ge=0, description="Tracking error vs benchmark")
    information_ratio: Optional[float] = Field(None, description="Information ratio")
    skewness: float = Field(..., description="Skewness of returns")
    kurtosis: float = Field(..., description="Excess kurtosis of returns")
    
    model_config = ConfigDict(use_enum_values=True)


class VaRMetricsModel(BaseModel):
    """Value at Risk metrics"""
    var: float = Field(..., ge=0, description="Value at Risk (positive value represents loss)")
    cvar: float = Field(..., ge=0, description="Conditional VaR (Expected Shortfall)")
    confidence: float = Field(..., ge=0, le=1, description="Confidence level")
    time_horizon: int = Field(..., ge=1, description="Time horizon in days")
    method: str = Field(..., description="Calculation method used")


class ComponentVaRModel(BaseModel):
    """Component VaR for individual assets"""
    asset_index: int = Field(..., ge=0, description="Asset index in portfolio")
    component_var: float = Field(..., ge=0, description="Component VaR contribution")
    marginal_var: float = Field(..., description="Marginal VaR")
    percentage_contribution: float = Field(..., ge=0, le=100, description="Percentage of total VaR")


class StressTestScenarioModel(BaseModel):
    """Stress test scenario definition"""
    name: str = Field(..., description="Scenario name")
    type: StressScenarioType = Field(..., description="Scenario type")
    shocks: Dict[str, float] = Field(..., description="Asset-specific shocks")
    market_shock: Optional[float] = Field(None, description="Overall market shock")
    duration_days: Optional[int] = Field(None, ge=1, description="Scenario duration")
    probability: Optional[float] = Field(None, ge=0, le=1, description="Scenario probability")
    
    model_config = ConfigDict(use_enum_values=True)


class StressTestResultModel(BaseModel):
    """Stress test result for a scenario"""
    scenario_name: str = Field(..., description="Scenario name")
    portfolio_loss: float = Field(..., description="Portfolio loss (negative value)")
    portfolio_return: float = Field(..., description="Portfolio return under scenario")
    asset_impacts: List[float] = Field(..., description="Impact on each asset")
    var_impact: float = Field(..., description="Impact on VaR")
    worst_asset: Optional[int] = Field(None, description="Index of worst performing asset")
    best_asset: Optional[int] = Field(None, description="Index of best performing asset")


class CorrelationMatrixModel(BaseModel):
    """Correlation matrix with metadata"""
    matrix: List[List[float]] = Field(..., description="Correlation matrix")
    eigenvalues: List[float] = Field(..., description="Eigenvalues of correlation matrix")
    condition_number: float = Field(..., gt=0, description="Condition number")
    max_correlation: float = Field(..., ge=-1, le=1, description="Maximum correlation")
    min_correlation: float = Field(..., ge=-1, le=1, description="Minimum correlation")
    average_correlation: float = Field(..., ge=-1, le=1, description="Average correlation")


# ============================================================================
# REQUEST MODELS (for risk_mcp_server.py)
# ============================================================================

class CalculateVaRRequest(BaseModel):
    """Request for calculate_var"""
    returns: List[float] = Field(
        ..., 
        min_length=20,
        description="List of historical returns (minimum 20 data points)"
    )
    confidence: float = Field(
        default=0.95,
        ge=0.5,
        le=0.999,
        description="Confidence level (e.g., 0.95 for 95%)"
    )
    time_horizon: int = Field(
        default=1,
        ge=1,
        le=252,
        description="Time horizon in days"
    )


class CalculatePortfolioVaRRequest(BaseModel):
    """Request for calculate_portfolio_var"""
    returns: List[List[float]] = Field(
        ...,
        min_length=1,
        description="2D list where each row is an asset's return series"
    )
    weights: List[float] = Field(
        ...,
        min_length=1,
        description="Portfolio weights (must sum to 1)"
    )
    confidence: float = Field(
        default=0.95,
        ge=0.5,
        le=0.999,
        description="Confidence level"
    )
    time_horizon: int = Field(
        default=1,
        ge=1,
        le=252,
        description="Time horizon in days"
    )
    
    @field_validator('weights')
    def validate_weights(cls, v):
        """Ensure weights sum to approximately 1"""
        total = sum(v)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1, got {total}")
        return v
    
    @field_validator('returns')
    def validate_returns_shape(cls, v):
        """Ensure all return series have same length"""
        if v:
            first_len = len(v[0])
            for i, series in enumerate(v):
                if len(series) != first_len:
                    raise ValueError(f"All return series must have same length. Series {i} has {len(series)}, expected {first_len}")
        return v


class StressTestPortfolioRequest(BaseModel):
    """Request for stress_test_portfolio"""
    returns: List[List[float]] = Field(
        ...,
        description="2D list of asset returns"
    )
    weights: List[float] = Field(
        ...,
        description="Portfolio weights"
    )
    scenarios: List[StressTestScenarioModel] = Field(
        ...,
        min_length=1,
        description="List of stress test scenarios"
    )


class CalculateCorrelationMatrixRequest(BaseModel):
    """Request for calculate_correlation_matrix"""
    returns: List[List[float]] = Field(
        ...,
        min_length=2,
        description="2D list where each row is an asset's return series"
    )


class CalculateRiskMetricsRequest(BaseModel):
    """Request for calculate_risk_metrics"""
    returns: List[float] = Field(
        ...,
        min_length=20,
        description="List of returns"
    )
    benchmark_returns: Optional[List[float]] = Field(
        None,
        description="Optional benchmark returns for relative metrics"
    )
    risk_free_rate: float = Field(
        default=0.04,
        ge=0,
        le=0.2,
        description="Annual risk-free rate"
    )


class MonteCarloVaRRequest(BaseModel):
    """Request for monte_carlo_var"""
    mean_return: float = Field(
        ...,
        description="Expected return (annualized)"
    )
    volatility: float = Field(
        ...,
        gt=0,
        description="Volatility (annualized)"
    )
    portfolio_value: float = Field(
        ...,
        gt=0,
        description="Portfolio value"
    )
    time_horizon: int = Field(
        default=1,
        ge=1,
        le=252,
        description="Time horizon in days"
    )
    confidence: float = Field(
        default=0.95,
        ge=0.5,
        le=0.999,
        description="Confidence level"
    )
    n_simulations: int = Field(
        default=10000,
        ge=1000,
        le=1000000,
        description="Number of Monte Carlo simulations"
    )


class CalculateComponentVaRRequest(BaseModel):
    """Request for calculate_component_var"""
    returns: List[List[float]] = Field(
        ...,
        description="2D list of asset returns"
    )
    weights: List[float] = Field(
        ...,
        description="Portfolio weights"
    )
    confidence: float = Field(
        default=0.95,
        ge=0.5,
        le=0.999,
        description="Confidence level"
    )


# ============================================================================
# REQUEST MODELS (for risk_mcp_server_v3.py)
# ============================================================================

class AnalyzePortfolioRiskRequest(BaseModel):
    """Request for analyze_portfolio_risk (v3)"""
    tickers: List[str] = Field(
        ...,
        min_length=1,
        description="List of ticker symbols"
    )
    weights: List[float] = Field(
        ...,
        min_length=1,
        description="Portfolio weights (must sum to 1)"
    )
    analysis_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Analysis options"
    )
    
    @field_validator('weights')
    def validate_weights(cls, v, info):
        """Ensure weights match tickers and sum to 1"""
        if 'tickers' in info.data:
            if len(v) != len(info.data['tickers']):
                raise ValueError(f"Number of weights ({len(v)}) must match number of tickers ({len(info.data['tickers'])})")
        total = sum(v)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1, got {total}")
        return v


class GetRiskFreeRateRequest(BaseModel):
    """Request for get_risk_free_rate"""
    maturity: TreasuryMaturity = Field(
        default=TreasuryMaturity.TEN_YEAR,
        description="Treasury maturity"
    )
    
    model_config = ConfigDict(use_enum_values=True)


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class CalculateVaRResponse(BaseModel):
    """Response for calculate_var"""
    var: float = Field(..., ge=0, description="Value at Risk")
    cvar: float = Field(..., ge=0, description="Conditional VaR")
    confidence: float = Field(..., description="Confidence level used")
    time_horizon: int = Field(..., description="Time horizon in days")
    method: str = Field(default="historical", description="Method used")


class CalculatePortfolioVaRResponse(BaseModel):
    """Response for calculate_portfolio_var"""
    portfolio_var: float = Field(..., ge=0, description="Portfolio VaR")
    portfolio_cvar: float = Field(..., ge=0, description="Portfolio CVaR")
    confidence: float = Field(..., description="Confidence level")
    time_horizon: int = Field(..., description="Time horizon")
    portfolio_volatility: float = Field(..., ge=0, description="Portfolio volatility")


class StressTestPortfolioResponse(BaseModel):
    """Response for stress_test_portfolio"""
    results: List[StressTestResultModel] = Field(..., description="Results for each scenario")
    worst_scenario: str = Field(..., description="Name of worst scenario")
    best_scenario: str = Field(..., description="Name of best scenario")
    average_loss: float = Field(..., description="Average loss across scenarios")


class CalculateCorrelationMatrixResponse(BaseModel):
    """Response for calculate_correlation_matrix"""
    correlation_matrix: List[List[float]] = Field(..., description="Correlation matrix")
    eigenvalues: List[float] = Field(..., description="Eigenvalues")
    condition_number: float = Field(..., gt=0, description="Condition number")
    max_correlation: float = Field(..., description="Maximum correlation")
    min_correlation: float = Field(..., description="Minimum correlation")


class CalculateRiskMetricsResponse(BaseModel):
    """Response for calculate_risk_metrics"""
    volatility: float = Field(..., ge=0, description="Annualized volatility")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    max_drawdown: float = Field(..., le=0, description="Maximum drawdown")
    calmar_ratio: float = Field(..., description="Calmar ratio")
    skewness: float = Field(..., description="Skewness")
    kurtosis: float = Field(..., description="Excess kurtosis")
    beta: Optional[float] = Field(None, description="Beta vs benchmark")
    alpha: Optional[float] = Field(None, description="Alpha vs benchmark")
    tracking_error: Optional[float] = Field(None, description="Tracking error")
    information_ratio: Optional[float] = Field(None, description="Information ratio")


class MonteCarloVaRResponse(BaseModel):
    """Response for monte_carlo_var"""
    var: float = Field(..., ge=0, description="Value at Risk")
    cvar: float = Field(..., ge=0, description="Conditional VaR")
    expected_return: float = Field(..., description="Expected portfolio return")
    expected_value: float = Field(..., gt=0, description="Expected portfolio value")
    worst_case: float = Field(..., description="Worst case loss")
    best_case: float = Field(..., description="Best case gain")
    confidence: float = Field(..., description="Confidence level")
    simulations: int = Field(..., description="Number of simulations run")


class CalculateComponentVaRResponse(BaseModel):
    """Response for calculate_component_var"""
    total_var: float = Field(..., ge=0, description="Total portfolio VaR")
    component_vars: List[ComponentVaRModel] = Field(..., description="Component VaR for each asset")
    diversification_benefit: float = Field(..., description="Diversification benefit")


class AnalyzePortfolioRiskResponse(BaseModel):
    """Response for analyze_portfolio_risk (v3)"""
    var_metrics: VaRMetricsModel = Field(..., description="VaR and CVaR metrics")
    risk_metrics: RiskMetricsModel = Field(..., description="Comprehensive risk metrics")
    correlation_analysis: CorrelationMatrixModel = Field(..., description="Correlation analysis")
    stress_test_results: Optional[List[StressTestResultModel]] = Field(None, description="Stress test results")
    component_risk: Optional[CalculateComponentVaRResponse] = Field(None, description="Component risk analysis")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")


class GetRiskFreeRateResponse(BaseModel):
    """Response for get_risk_free_rate"""
    rate: float = Field(..., ge=0, description="Risk-free rate (annualized)")
    maturity: str = Field(..., description="Treasury maturity")
    date: str = Field(..., description="Date of rate quote")
    source: str = Field(default="FRED", description="Data source")


# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())