"""
Pydantic models for Portfolio MCP Server
Provides strong typing and validation for all MCP tool inputs and outputs
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Dict, Any, List, Optional, Union, Literal
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class OptimizationObjective(str, Enum):
    """Portfolio optimization objectives"""
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    MAX_DIVERSIFICATION = "max_diversification"
    MIN_CVaR = "min_cvar"
    TARGET_RETURN = "target_return"
    TARGET_RISK = "target_risk"


class RiskMeasure(str, Enum):
    """Risk measures for optimization"""
    VARIANCE = "variance"
    STANDARD_DEVIATION = "std"
    CVAR = "cvar"
    VAR = "var"
    MAX_DRAWDOWN = "max_drawdown"
    SEMI_VARIANCE = "semi_variance"
    ENTROPY = "entropy"
    ULCER_INDEX = "ulcer_index"


class RebalancingStrategy(str, Enum):
    """Portfolio rebalancing strategies"""
    THRESHOLD = "threshold"
    PERIODIC = "periodic"
    TACTICAL = "tactical"
    STRATEGIC = "strategic"
    DYNAMIC = "dynamic"


class ConstraintType(str, Enum):
    """Portfolio constraint types"""
    LONG_ONLY = "long_only"
    MARKET_NEUTRAL = "market_neutral"
    BOX = "box"
    GROUP = "group"
    TURNOVER = "turnover"
    CONCENTRATION = "concentration"


class CovarianceMethod(str, Enum):
    """Covariance estimation methods"""
    SAMPLE = "sample"
    SHRINKAGE = "shrinkage"
    LEDOIT_WOLF = "ledoit_wolf"
    OAS = "oas"
    EXPONENTIAL = "exponential"
    ROBUST = "robust"


# ============================================================================
# BASE MODELS
# ============================================================================

class AssetConstraintModel(BaseModel):
    """Constraints for individual assets"""
    min_weight: float = Field(default=0.0, ge=0, le=1, description="Minimum weight")
    max_weight: float = Field(default=1.0, ge=0, le=1, description="Maximum weight")
    target_weight: Optional[float] = Field(None, ge=0, le=1, description="Target weight")
    
    @model_validator(mode='after')
    def validate_weights(self):
        if self.min_weight > self.max_weight:
            raise ValueError("min_weight must be <= max_weight")
        if self.target_weight is not None:
            if self.target_weight < self.min_weight or self.target_weight > self.max_weight:
                raise ValueError("target_weight must be between min_weight and max_weight")
        return self


class OptimizationConstraintsModel(BaseModel):
    """Portfolio optimization constraints"""
    constraint_type: ConstraintType = Field(
        default=ConstraintType.LONG_ONLY,
        description="Type of portfolio constraints"
    )
    min_position_size: float = Field(
        default=0.01,
        ge=0,
        le=1,
        description="Minimum position size"
    )
    max_position_size: float = Field(
        default=0.40,
        ge=0,
        le=1,
        description="Maximum position size"
    )
    max_positions: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum number of positions"
    )
    sector_limits: Optional[Dict[str, float]] = Field(
        None,
        description="Sector exposure limits"
    )
    asset_constraints: Optional[Dict[str, AssetConstraintModel]] = Field(
        None,
        description="Individual asset constraints"
    )
    
    model_config = ConfigDict(use_enum_values=True)


class PortfolioMetricsModel(BaseModel):
    """Portfolio performance metrics"""
    expected_return: float = Field(..., description="Expected annual return")
    volatility: float = Field(..., ge=0, description="Annual volatility")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    max_drawdown: float = Field(..., le=0, description="Maximum drawdown")
    var_95: float = Field(..., ge=0, description="95% Value at Risk")
    cvar_95: float = Field(..., ge=0, description="95% Conditional VaR")
    calmar_ratio: float = Field(..., description="Calmar ratio")
    diversification_ratio: float = Field(..., gt=0, description="Diversification ratio")


class EfficientFrontierPointModel(BaseModel):
    """Point on the efficient frontier"""
    expected_return: float = Field(..., description="Expected return")
    volatility: float = Field(..., ge=0, description="Portfolio volatility")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    weights: List[float] = Field(..., description="Asset weights")


class RebalancingTradeModel(BaseModel):
    """Rebalancing trade details"""
    asset_index: int = Field(..., ge=0, description="Asset index")
    asset_symbol: Optional[str] = Field(None, description="Asset symbol")
    current_shares: float = Field(..., description="Current shares held")
    target_shares: float = Field(..., description="Target shares")
    shares_to_trade: float = Field(..., description="Shares to buy/sell (positive=buy)")
    trade_value: float = Field(..., description="Dollar value of trade")
    trade_cost: float = Field(..., ge=0, description="Estimated transaction cost")


# ============================================================================
# REQUEST MODELS (for portfolio_mcp_server.py)
# ============================================================================

class OptimizeSharpeRatioRequest(BaseModel):
    """Request for optimize_sharpe_ratio"""
    returns: List[List[float]] = Field(
        ...,
        min_length=2,
        description="2D list where each row is an asset's return series"
    )
    risk_free_rate: float = Field(
        default=0.04,
        ge=0,
        le=0.2,
        description="Annual risk-free rate"
    )
    
    @field_validator('returns')
    def validate_returns(cls, v):
        """Ensure all return series have same length"""
        if v:
            first_len = len(v[0])
            if first_len < 20:
                raise ValueError("Need at least 20 return observations")
            for i, series in enumerate(v):
                if len(series) != first_len:
                    raise ValueError(f"All return series must have same length")
        return v


class OptimizeMinVarianceRequest(BaseModel):
    """Request for optimize_min_variance"""
    returns: List[List[float]] = Field(
        ...,
        min_length=2,
        description="2D list where each row is an asset's return series"
    )
    target_return: Optional[float] = Field(
        None,
        description="Optional target return constraint"
    )


class CalculateRiskParityRequest(BaseModel):
    """Request for calculate_risk_parity"""
    returns: List[List[float]] = Field(
        ...,
        min_length=2,
        description="2D list where each row is an asset's return series"
    )


class GenerateEfficientFrontierRequest(BaseModel):
    """Request for generate_efficient_frontier"""
    returns: List[List[float]] = Field(
        ...,
        min_length=2,
        description="2D list where each row is an asset's return series"
    )
    n_portfolios: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Number of portfolios on the frontier"
    )


class CalculatePortfolioMetricsRequest(BaseModel):
    """Request for calculate_portfolio_metrics"""
    weights: List[float] = Field(
        ...,
        min_length=1,
        description="Portfolio weights for each asset"
    )
    returns: List[List[float]] = Field(
        ...,
        min_length=1,
        description="2D list where each row is an asset's return series"
    )
    benchmark_returns: Optional[List[float]] = Field(
        None,
        description="Optional benchmark return series"
    )
    
    @field_validator('weights')
    def validate_weights(cls, v, info):
        """Ensure weights sum to 1"""
        total = sum(v)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1, got {total}")
        return v


class RebalancePortfolioRequest(BaseModel):
    """Request for rebalance_portfolio"""
    current_weights: List[float] = Field(
        ...,
        min_length=1,
        description="Current portfolio weights"
    )
    target_weights: List[float] = Field(
        ...,
        min_length=1,
        description="Target portfolio weights"
    )
    portfolio_value: float = Field(
        ...,
        gt=0,
        description="Total portfolio value"
    )
    prices: List[float] = Field(
        ...,
        min_length=1,
        description="Current asset prices"
    )
    min_trade_size: float = Field(
        default=100.0,
        ge=0,
        description="Minimum trade size in dollars"
    )
    
    @model_validator(mode='after')
    def validate_consistency(self):
        """Ensure all lists have same length"""
        lengths = [
            len(self.current_weights),
            len(self.target_weights),
            len(self.prices)
        ]
        if len(set(lengths)) > 1:
            raise ValueError("current_weights, target_weights, and prices must have same length")
        return self


# ============================================================================
# REQUEST MODELS (for portfolio_mcp_server_v3.py)
# ============================================================================

class OptimizationConfigModel(BaseModel):
    """Configuration for advanced portfolio optimization"""
    objective: OptimizationObjective = Field(
        default=OptimizationObjective.MAX_SHARPE,
        description="Optimization objective"
    )
    risk_measure: RiskMeasure = Field(
        default=RiskMeasure.VARIANCE,
        description="Risk measure to use"
    )
    constraints: OptimizationConstraintsModel = Field(
        default_factory=OptimizationConstraintsModel,
        description="Optimization constraints"
    )
    covariance_method: CovarianceMethod = Field(
        default=CovarianceMethod.LEDOIT_WOLF,
        description="Covariance estimation method"
    )
    lookback_days: int = Field(
        default=252,
        ge=60,
        le=1260,
        description="Historical data lookback period in days"
    )
    confidence_level: float = Field(
        default=0.95,
        ge=0.9,
        le=0.99,
        description="Confidence level for risk metrics"
    )
    risk_free_rate: float = Field(
        default=0.04,
        ge=0,
        le=0.2,
        description="Annual risk-free rate"
    )
    target_return: Optional[float] = Field(
        None,
        description="Target return for constrained optimization"
    )
    target_volatility: Optional[float] = Field(
        None,
        ge=0,
        description="Target volatility for constrained optimization"
    )
    regularization: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="L2 regularization parameter"
    )
    
    model_config = ConfigDict(use_enum_values=True)


class OptimizePortfolioAdvancedRequest(BaseModel):
    """Request for optimize_portfolio_advanced (v3)"""
    tickers: List[str] = Field(
        ...,
        min_length=2,
        description="List of ticker symbols"
    )
    optimization_config: OptimizationConfigModel = Field(
        default_factory=OptimizationConfigModel,
        description="Optimization configuration"
    )


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class OptimizeSharpeRatioResponse(BaseModel):
    """Response for optimize_sharpe_ratio"""
    optimal_weights: List[float] = Field(..., description="Optimal portfolio weights")
    expected_return: float = Field(..., description="Expected annual return")
    volatility: float = Field(..., ge=0, description="Annual volatility")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    asset_contributions: List[float] = Field(..., description="Return contribution by asset")


class OptimizeMinVarianceResponse(BaseModel):
    """Response for optimize_min_variance"""
    optimal_weights: List[float] = Field(..., description="Optimal portfolio weights")
    expected_return: float = Field(..., description="Expected annual return")
    volatility: float = Field(..., ge=0, description="Minimum volatility achieved")
    risk_contributions: List[float] = Field(..., description="Risk contribution by asset")


class CalculateRiskParityResponse(BaseModel):
    """Response for calculate_risk_parity"""
    risk_parity_weights: List[float] = Field(..., description="Risk parity weights")
    risk_contributions: List[float] = Field(..., description="Risk contribution by asset")
    total_risk: float = Field(..., ge=0, description="Total portfolio risk")
    diversification_ratio: float = Field(..., gt=0, description="Diversification ratio")


class GenerateEfficientFrontierResponse(BaseModel):
    """Response for generate_efficient_frontier"""
    frontier_portfolios: List[EfficientFrontierPointModel] = Field(
        ...,
        description="Portfolios on the efficient frontier"
    )
    max_sharpe_portfolio: EfficientFrontierPointModel = Field(
        ...,
        description="Maximum Sharpe ratio portfolio"
    )
    min_variance_portfolio: EfficientFrontierPointModel = Field(
        ...,
        description="Minimum variance portfolio"
    )
    tangency_portfolio: Optional[EfficientFrontierPointModel] = Field(
        None,
        description="Tangency portfolio"
    )


class CalculatePortfolioMetricsResponse(BaseModel):
    """Response for calculate_portfolio_metrics"""
    metrics: PortfolioMetricsModel = Field(..., description="Portfolio metrics")
    risk_decomposition: Dict[str, float] = Field(..., description="Risk decomposition")
    performance_attribution: Optional[Dict[str, float]] = Field(
        None,
        description="Performance attribution vs benchmark"
    )


class RebalancePortfolioResponse(BaseModel):
    """Response for rebalance_portfolio"""
    trades: List[RebalancingTradeModel] = Field(..., description="Required trades")
    total_turnover: float = Field(..., ge=0, description="Total turnover amount")
    estimated_costs: float = Field(..., ge=0, description="Total estimated transaction costs")
    tracking_error: float = Field(..., ge=0, description="Tracking error to target")
    rebalancing_urgency: str = Field(..., description="Urgency level (low/medium/high)")


class OptimizePortfolioAdvancedResponse(BaseModel):
    """Response for optimize_portfolio_advanced (v3)"""
    optimal_weights: Dict[str, float] = Field(..., description="Optimal weights by ticker")
    metrics: PortfolioMetricsModel = Field(..., description="Portfolio metrics")
    risk_contributions: Dict[str, float] = Field(..., description="Risk contribution by ticker")
    optimization_details: Dict[str, Any] = Field(..., description="Optimization details")
    backtesting_results: Optional[Dict[str, Any]] = Field(
        None,
        description="Backtesting results if requested"
    )
    alternative_portfolios: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Alternative portfolio suggestions"
    )


# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())