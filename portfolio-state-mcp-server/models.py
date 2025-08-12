"""
Pydantic models for Portfolio State MCP Server
Provides strong typing and validation for all MCP tool inputs and outputs
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Dict, Any, List, Optional, Union, Literal
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class CostBasisMethod(str, Enum):
    """Cost basis calculation methods"""
    FIFO = "FIFO"  # First In First Out
    LIFO = "LIFO"  # Last In First Out
    HIFO = "HIFO"  # Highest In First Out
    AVERAGE = "AVERAGE"  # Average Cost
    SPECIFIC = "SPECIFIC"  # Specific Lot Identification


class AssetType(str, Enum):
    """Asset type classification"""
    EQUITY = "equity"
    BOND = "bond"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    OPTION = "option"
    CASH = "cash"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    REIT = "reit"


class TransactionType(str, Enum):
    """Transaction types"""
    BUY = "buy"
    SELL = "sell"


class BrokerType(str, Enum):
    """Supported brokers"""
    VANGUARD = "vanguard"
    UBS = "ubs"
    FIDELITY = "fidelity"
    SCHWAB = "schwab"
    ETRADE = "etrade"
    TD_AMERITRADE = "td_ameritrade"
    ROBINHOOD = "robinhood"
    INTERACTIVE_BROKERS = "interactive_brokers"
    UNKNOWN = "unknown"


# ============================================================================
# BASE MODELS
# ============================================================================

class TaxLotModel(BaseModel):
    """Tax lot with immutable historical data"""
    lot_id: str = Field(..., description="Unique identifier for the tax lot")
    symbol: str = Field(..., description="Stock ticker symbol")
    quantity: float = Field(..., gt=0, description="Number of shares in this lot")
    purchase_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Purchase date (YYYY-MM-DD)")
    purchase_price: float = Field(..., gt=0, description="Price per share at purchase")
    cost_basis: float = Field(..., gt=0, description="Total cost basis for this lot")
    holding_period_days: int = Field(default=0, ge=0, description="Days held")
    is_long_term: bool = Field(default=False, description="Whether holding qualifies for long-term capital gains")
    asset_type: AssetType = Field(default=AssetType.EQUITY, description="Type of asset")
    account_id: str = Field(default="default", description="Account identifier")
    broker: str = Field(default="unknown", description="Broker name")
    
    model_config = ConfigDict(use_enum_values=True)


class PositionModel(BaseModel):
    """Aggregated position across all tax lots"""
    symbol: str = Field(..., description="Stock ticker symbol")
    total_quantity: float = Field(..., gt=0, description="Total shares held")
    average_cost: float = Field(..., gt=0, description="Average cost per share")
    total_cost_basis: float = Field(..., gt=0, description="Total cost basis")
    current_price: float = Field(..., ge=0, description="Current market price per share")
    current_value: float = Field(..., ge=0, description="Current market value")
    unrealized_gain: float = Field(..., description="Unrealized gain/loss")
    unrealized_return: float = Field(..., description="Unrealized return percentage")
    asset_type: AssetType = Field(..., description="Type of asset")
    tax_lots: List[TaxLotModel] = Field(..., description="Individual tax lots")
    
    model_config = ConfigDict(use_enum_values=True)


class TaxImplicationModel(BaseModel):
    """Tax implications of a transaction"""
    short_term_gain: float = Field(..., description="Short-term capital gain/loss")
    long_term_gain: float = Field(..., description="Long-term capital gain/loss")
    total_gain: float = Field(..., description="Total capital gain/loss")
    federal_tax: float = Field(..., description="Estimated federal tax")
    state_tax: float = Field(..., description="Estimated state tax")
    total_tax: float = Field(..., description="Total estimated tax")
    net_proceeds: float = Field(..., description="Net proceeds after tax")
    effective_tax_rate: float = Field(..., ge=0, le=1, description="Effective tax rate")


class SoldLotModel(BaseModel):
    """Details of a sold tax lot"""
    lot_id: str = Field(..., description="Tax lot identifier")
    quantity_sold: float = Field(..., gt=0, description="Shares sold from this lot")
    purchase_date: str = Field(..., description="Original purchase date")
    purchase_price: float = Field(..., gt=0, description="Original purchase price")
    sale_price: float = Field(..., gt=0, description="Sale price per share")
    cost_basis: float = Field(..., gt=0, description="Cost basis of sold shares")
    proceeds: float = Field(..., gt=0, description="Sale proceeds")
    gain_loss: float = Field(..., description="Realized gain/loss")
    holding_period_days: int = Field(..., ge=0, description="Days held")
    is_long_term: bool = Field(..., description="Whether qualifies for long-term treatment")


class HarvestingOpportunityModel(BaseModel):
    """Tax loss harvesting opportunity"""
    symbol: str = Field(..., description="Stock ticker symbol")
    total_shares: float = Field(..., gt=0, description="Total shares available to harvest")
    current_price: float = Field(..., gt=0, description="Current market price")
    total_loss: float = Field(..., lt=0, description="Total unrealized loss")
    short_term_loss: float = Field(..., le=0, description="Short-term loss component")
    long_term_loss: float = Field(..., le=0, description="Long-term loss component")
    tax_savings: float = Field(..., ge=0, description="Estimated tax savings")
    eligible_lots: List[TaxLotModel] = Field(..., description="Tax lots eligible for harvesting")
    wash_sale_risk: bool = Field(default=False, description="Whether there's wash sale risk")


# ============================================================================
# REQUEST MODELS
# ============================================================================

class GetPortfolioStateRequest(BaseModel):
    """Request for getting portfolio state"""
    properties: Optional[Union[str, Dict]] = Field(
        default=None, 
        description="Optional parameters (for compatibility)"
    )


class ImportBrokerCSVRequest(BaseModel):
    """Request for importing broker CSV data"""
    broker: str = Field(
        ..., 
        description="Broker name (vanguard, ubs, fidelity, schwab, etc.)"
    )
    csv_content: str = Field(
        ..., 
        min_length=1,
        description="CSV file content as string"
    )
    account_id: str = Field(
        default="default", 
        description="Account identifier"
    )
    
    @field_validator('broker')
    def validate_broker(cls, v):
        """Validate broker name"""
        valid_brokers = [b.value for b in BrokerType]
        if v.lower() not in valid_brokers:
            # Allow it but log warning
            return v.lower()
        return v.lower()


class UpdateMarketPricesRequest(BaseModel):
    """Request for updating market prices"""
    prices: Dict[str, float] = Field(
        ..., 
        min_length=1,
        description="Dictionary of symbol to current price mappings"
    )
    
    @field_validator('prices')
    def validate_prices(cls, v):
        """Ensure all prices are positive"""
        for symbol, price in v.items():
            if price <= 0:
                raise ValueError(f"Price for {symbol} must be positive, got {price}")
        return v


class SimulateSaleRequest(BaseModel):
    """Request for simulating a sale"""
    symbol: str = Field(
        ..., 
        min_length=1,
        description="Stock symbol to sell"
    )
    quantity: float = Field(
        ..., 
        gt=0,
        description="Number of shares to sell"
    )
    sale_price: float = Field(
        ..., 
        gt=0,
        description="Price per share for the sale"
    )
    cost_basis_method: CostBasisMethod = Field(
        default=CostBasisMethod.FIFO,
        description="Method for selecting lots (FIFO, LIFO, HIFO, AVERAGE)"
    )
    
    model_config = ConfigDict(use_enum_values=True)


class GetTaxLossHarvestingRequest(BaseModel):
    """Request for getting tax loss harvesting opportunities"""
    min_loss_threshold: float = Field(
        default=1000.0,
        ge=0,
        description="Minimum loss amount to consider"
    )
    exclude_recent_days: int = Field(
        default=31,
        ge=0,
        description="Exclude lots purchased within this many days (wash sale)"
    )


class RecordTransactionRequest(BaseModel):
    """Request for recording a transaction"""
    transaction_type: TransactionType = Field(
        ...,
        description="Type of transaction (buy or sell)"
    )
    symbol: str = Field(
        ..., 
        min_length=1,
        description="Stock ticker symbol"
    )
    quantity: float = Field(
        ..., 
        gt=0,
        description="Number of shares"
    )
    price: float = Field(
        ..., 
        gt=0,
        description="Price per share"
    )
    date: str = Field(
        ..., 
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Transaction date (YYYY-MM-DD)"
    )
    account_id: str = Field(
        default="default",
        description="Account identifier"
    )
    broker: str = Field(
        default="unknown",
        description="Broker name"
    )
    
    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('date')
    def validate_date(cls, v):
        """Ensure date is not in the future"""
        transaction_date = datetime.strptime(v, "%Y-%m-%d").date()
        if transaction_date > date.today():
            raise ValueError(f"Transaction date cannot be in the future: {v}")
        return v


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class PortfolioSummaryModel(BaseModel):
    """Portfolio summary statistics"""
    total_value: float = Field(..., ge=0, description="Total portfolio value")
    total_cost: float = Field(..., ge=0, description="Total cost basis")
    total_gain_loss: float = Field(..., description="Total unrealized gain/loss")
    total_return: float = Field(..., description="Total return percentage")
    position_count: int = Field(..., ge=0, description="Number of positions")
    total_tax_lots: int = Field(..., ge=0, description="Total number of tax lots")


class AssetAllocationModel(BaseModel):
    """Asset allocation breakdown"""
    asset_type: AssetType
    value: float = Field(..., ge=0)
    percentage: float = Field(..., ge=0, le=100)
    count: int = Field(..., ge=0)
    
    model_config = ConfigDict(use_enum_values=True)


class GetPortfolioStateResponse(BaseModel):
    """Response for get_portfolio_state"""
    positions: List[PositionModel] = Field(..., description="All portfolio positions")
    summary: PortfolioSummaryModel = Field(..., description="Portfolio summary")
    asset_allocation: List[AssetAllocationModel] = Field(..., description="Asset allocation breakdown")
    last_updated: str = Field(..., description="Last update timestamp")


class ImportBrokerCSVResponse(BaseModel):
    """Response for import_broker_csv"""
    status: Literal["success", "error"] = Field(..., description="Import status")
    message: str = Field(..., description="Status message")
    imported_count: int = Field(..., ge=0, description="Number of positions imported")
    symbols: List[str] = Field(..., description="List of imported symbols")
    total_value: float = Field(..., ge=0, description="Total value of imported positions")
    errors: List[str] = Field(default_factory=list, description="Any import errors")


class UpdateMarketPricesResponse(BaseModel):
    """Response for update_market_prices"""
    status: Literal["success", "error"] = Field(..., description="Update status")
    updated_count: int = Field(..., ge=0, description="Number of prices updated")
    portfolio_value: float = Field(..., ge=0, description="Updated portfolio value")
    total_gain_loss: float = Field(..., description="Updated total gain/loss")
    message: str = Field(..., description="Status message")


class SimulateSaleResponse(BaseModel):
    """Response for simulate_sale"""
    proceeds: float = Field(..., gt=0, description="Total sale proceeds")
    cost_basis: float = Field(..., gt=0, description="Total cost basis of sold shares")
    realized_gain: float = Field(..., description="Total realized gain/loss")
    tax_implications: TaxImplicationModel = Field(..., description="Tax implications")
    lots_sold: List[SoldLotModel] = Field(..., description="Details of lots sold")
    method_used: CostBasisMethod = Field(..., description="Cost basis method used")
    
    model_config = ConfigDict(use_enum_values=True)


class GetTaxLossHarvestingResponse(BaseModel):
    """Response for get_tax_loss_harvesting_opportunities"""
    opportunities: List[HarvestingOpportunityModel] = Field(..., description="Harvesting opportunities")
    total_potential_loss: float = Field(..., le=0, description="Total potential loss to harvest")
    total_tax_savings: float = Field(..., ge=0, description="Total estimated tax savings")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")


class RecordTransactionResponse(BaseModel):
    """Response for record_transaction"""
    status: Literal["success", "error"] = Field(..., description="Transaction status")
    message: str = Field(..., description="Status message")
    transaction_id: str = Field(..., description="Unique transaction identifier")
    symbol: str = Field(..., description="Stock symbol")
    quantity: float = Field(..., gt=0, description="Number of shares")
    total_value: float = Field(..., gt=0, description="Total transaction value")
    updated_position: Optional[PositionModel] = Field(None, description="Updated position after transaction")
    tax_lot_created: Optional[TaxLotModel] = Field(None, description="New tax lot (for buys)")
    realized_gain: Optional[float] = Field(None, description="Realized gain/loss (for sells)")


# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())