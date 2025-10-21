# MCP Tools Guide for AI Agents

## Overview
This guide provides comprehensive documentation for AI agents (Claude, Gemini, etc.) to effectively use the investment management MCP servers. Each server specializes in different aspects of portfolio management with validated inputs and outputs.

## Quick Reference: MCP Tool Names

### Portfolio State Server
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__portfolio-state-server__import_broker_csv`
- `mcp__portfolio-state-server__update_market_prices`
- `mcp__portfolio-state-server__simulate_sale`
- `mcp__portfolio-state-server__get_tax_loss_harvesting_opportunities`
- `mcp__portfolio-state-server__record_transaction`

### Portfolio Optimization Server
- `mcp__portfolio-optimization-server__optimize_portfolio_advanced`

### Risk Server
- `mcp__risk-server__analyze_portfolio_risk` (includes stress testing)
- `mcp__risk-server__get_risk_free_rate`

### Tax Server
- `mcp__tax-server__calculate_comprehensive_tax`

### Tax Optimization Server
- `mcp__tax-optimization-server__optimize_portfolio_for_taxes`
- `mcp__tax-optimization-server__find_tax_loss_harvesting_pairs`
- `mcp__tax-optimization-server__simulate_withdrawal_tax_impact`

### ❌ NON-EXISTENT TOOLS (Do not use)
- `mcp__risk-server__stress_test_portfolio` - Stress testing is part of `analyze_portfolio_risk`

### ✅ Critical Usage Notes
1. **Native Python types required**: All MCP tools need native Python types, NOT JSON strings
   - ✅ CORRECT: `tickers=["SPY", "AGG"], weights=[0.5, 0.5]`
   - ❌ WRONG: `tickers="[\"SPY\", \"AGG\"]", weights="[0.5, 0.5]"`

2. **Standard workflow pattern**:
   - Start with `get_portfolio_state` to get current holdings
   - Extract tickers and weights from the state response
   - Pass these to optimization/risk tools as native lists
   - Write results to session directory `./runs/<timestamp>/`

3. **Stress testing**: Use `analyze_portfolio_risk` with `analysis_options={"include_stress_test": True}`

---

## Available MCP Servers

### 1. Portfolio State Server (`portfolio-state-mcp-server`)
**Purpose**: Manages portfolio positions, tax lots, and transaction history

#### Tools:

##### `get_portfolio_state`
Get complete portfolio state with all positions and tax lots.
```python
# Request
properties: Optional[Dict] = None  # Compatibility parameter, can be ignored

# Response
{
  "positions": [...],      # List of positions with tax lots
  "summary": {...},        # Portfolio summary statistics
  "asset_allocation": [...], # Asset allocation breakdown
  "last_updated": "2024-01-15T10:30:00Z"
}
```

##### `import_broker_csv`
Import portfolio data from broker CSV files.
```python
# Request
broker: str              # "vanguard", "ubs", "fidelity", "schwab", etc.
csv_content: str        # CSV file content as string
account_id: str = "default"  # Account identifier

# Response
{
  "status": "success",
  "imported_count": 15,
  "symbols": ["AAPL", "GOOGL", ...],
  "total_value": 250000.00
}
```

##### `update_market_prices`
Update current market prices for portfolio positions.
```python
# Request
prices: Dict[str, float]  # {"AAPL": 155.50, "GOOGL": 2800.00}

# Response
{
  "status": "success",
  "updated_count": 2,
  "portfolio_value": 275000.00,
  "total_gain_loss": 25000.00
}
```

##### `simulate_sale`
Simulate a sale to calculate tax implications.
```python
# Request
symbol: str              # Stock symbol
quantity: float          # Shares to sell
sale_price: float        # Price per share
cost_basis_method: str = "FIFO"  # "FIFO", "LIFO", "HIFO", "AVERAGE"

# Response
{
  "proceeds": 15500.00,
  "cost_basis": 14000.00,
  "realized_gain": 1500.00,
  "tax_implications": {...},
  "lots_sold": [...]
}
```

##### `get_tax_loss_harvesting_opportunities`
Identify tax loss harvesting opportunities.
```python
# Request
min_loss_threshold: float = 1000.0  # Minimum loss to consider
exclude_recent_days: int = 31       # Wash sale prevention

# Response
{
  "opportunities": [...],
  "total_potential_loss": -5000.00,
  "total_tax_savings": 1500.00
}
```

##### `record_transaction`
Record a buy or sell transaction.
```python
# Request
transaction_type: str    # "buy" or "sell"
symbol: str             # Stock symbol
quantity: float         # Number of shares
price: float           # Price per share
date: str              # "YYYY-MM-DD"
account_id: str = "default"
broker: str = "unknown"

# Response
{
  "status": "success",
  "transaction_id": "txn_abc123",
  "total_value": 15000.00
}
```

### 2. Risk Server (`risk-mcp-server`)
**Purpose**: Comprehensive risk analysis and portfolio metrics

#### Tools:

##### `analyze_portfolio_risk` (v3 - Recommended)
Professional-grade portfolio risk analysis in a single call.
```python
# Request
tickers: List[str]       # ["AAPL", "GOOGL", "MSFT"]
weights: List[float]     # [0.4, 0.3, 0.3] - must sum to 1
analysis_options: Dict = {
  "include_stress_test": True,
  "include_component_risk": True
}

# Response
{
  "var_metrics": {...},
  "risk_metrics": {...},
  "correlation_analysis": {...},
  "stress_test_results": [...],
  "component_risk": {...}
}
```

##### `calculate_var`
Calculate Value at Risk and Conditional VaR.
```python
# Request
returns: List[float]     # Historical returns (min 20 points)
confidence: float = 0.95 # Confidence level
time_horizon: int = 1    # Days

# Response
{
  "var": 0.025,          # 2.5% potential loss
  "cvar": 0.035,         # Expected loss beyond VaR
  "confidence": 0.95,
  "time_horizon": 1
}
```

##### `stress_test_portfolio`
Run stress test scenarios on portfolio.
```python
# Request
returns: List[List[float]]  # Asset returns
weights: List[float]        # Portfolio weights
scenarios: List[Dict]       # Stress scenarios

# Response
{
  "results": [...],
  "worst_scenario": "market_crash",
  "average_loss": -0.15
}
```

##### `calculate_risk_metrics`
Calculate comprehensive risk metrics.
```python
# Request
returns: List[float]
benchmark_returns: Optional[List[float]] = None
risk_free_rate: float = 0.04

# Response
{
  "volatility": 0.15,
  "sharpe_ratio": 0.8,
  "sortino_ratio": 1.2,
  "max_drawdown": -0.25,
  "calmar_ratio": 0.5
}
```

### 3. Tax Server (`tax-mcp-server`)
**Purpose**: Tax calculations, optimization, and planning

#### Tools:

##### `calculate_tax_liability`
Calculate comprehensive tax liability.
```python
# Request
year: int = 2024
state: Optional[str] = "CA"
filing_status: str = "Single"
w2_income: float = 150000.0
qualified_dividends: float = 5000.0
long_term_capital_gains: float = 10000.0

# Response
{
  "breakdown": {
    "federal_tax": 35000.00,
    "state_tax": 12000.00,
    "total_tax": 47000.00,
    "effective_rate": 0.285
  },
  "after_tax_income": 118000.00,
  "tax_savings_opportunities": [...]
}
```

##### `optimize_tax_harvest`
Optimize tax loss harvesting strategy.
```python
# Request
positions: List[Dict]    # Positions with unrealized gains/losses
target_loss_amount: float = 3000.0

# Response
{
  "recommended_harvests": [...],
  "total_loss_harvested": -3000.00,
  "estimated_tax_savings": 900.00,
  "wash_sale_positions": []
}
```

##### `estimate_quarterly_payments`
Calculate required quarterly estimated tax payments.
```python
# Request
ytd_income: Dict[str, float]
prior_year_tax: float
payments_made: float = 0.0
current_quarter: int = 2

# Response
{
  "quarterly_schedule": [...],
  "total_required": 15000.00,
  "remaining_due": 7500.00,
  "penalty_risk": False
}
```

### 4. Portfolio Optimization Server (`portfolio-mcp-server`)
**Purpose**: Portfolio construction and optimization

#### Tools:

##### `optimize_portfolio_advanced` (v3 - Recommended)
Professional-grade portfolio optimization.
```python
# Request
tickers: List[str]
optimization_config: {
  "objective": "max_sharpe",  # or "min_variance", "risk_parity"
  "risk_measure": "variance",
  "constraints": {
    "min_position_size": 0.01,
    "max_position_size": 0.40
  },
  "lookback_days": 252,
  "risk_free_rate": 0.04
}

# Response
{
  "optimal_weights": {"AAPL": 0.35, "GOOGL": 0.30, ...},
  "metrics": {...},
  "risk_contributions": {...},
  "optimization_details": {...}
}
```

##### `optimize_sharpe_ratio`
Optimize portfolio to maximize Sharpe ratio.
```python
# Request
returns: List[List[float]]  # Asset returns
risk_free_rate: float = 0.04

# Response
{
  "optimal_weights": [0.4, 0.3, 0.3],
  "expected_return": 0.12,
  "volatility": 0.15,
  "sharpe_ratio": 0.8
}
```

##### `generate_efficient_frontier`
Generate efficient frontier portfolios.
```python
# Request
returns: List[List[float]]
n_portfolios: int = 50

# Response
{
  "frontier_portfolios": [...],
  "max_sharpe_portfolio": {...},
  "min_variance_portfolio": {...}
}
```

##### `rebalance_portfolio`
Calculate rebalancing trades.
```python
# Request
current_weights: List[float]
target_weights: List[float]
portfolio_value: float
prices: List[float]
min_trade_size: float = 100.0

# Response
{
  "trades": [...],
  "total_turnover": 5000.00,
  "estimated_costs": 50.00,
  "rebalancing_urgency": "medium"
}
```

## Best Practices for AI Agents

### 1. Input Validation
All servers now use Pydantic models for validation. Common errors:
- **Weights must sum to 1**: Portfolio weights should total 1.0 (100%)
- **Minimum data points**: Most statistical functions need at least 20 data points
- **Date format**: Always use "YYYY-MM-DD" format
- **Positive values**: Prices, quantities, and portfolio values must be positive

### 2. Error Handling
```python
# All errors follow this format:
{
  "error": "validation_error",
  "message": "Weights must sum to 1",
  "details": {...}
}
```

### 3. Workflow Examples

#### Complete Portfolio Analysis Workflow
```python
# 1. Get current portfolio state
portfolio = get_portfolio_state()

# 2. Update market prices
update_market_prices({"AAPL": 155.50, "GOOGL": 2800.00})

# 3. Analyze risk
risk_analysis = analyze_portfolio_risk(
  tickers=["AAPL", "GOOGL"],
  weights=[0.6, 0.4]
)

# 4. Check for tax loss harvesting
harvesting = get_tax_loss_harvesting_opportunities()

# 5. Calculate tax implications
tax_liability = calculate_tax_liability(
  w2_income=150000,
  long_term_capital_gains=harvesting["total_potential_loss"]
)
```

#### Portfolio Optimization Workflow
```python
# 1. Get historical data (from data sources)
tickers = ["SPY", "AGG", "GLD", "VNQ"]

# 2. Optimize portfolio
optimization = optimize_portfolio_advanced(
  tickers=tickers,
  optimization_config={
    "objective": "max_sharpe",
    "constraints": {
      "min_position_size": 0.05,
      "max_position_size": 0.40
    }
  }
)

# 3. Calculate rebalancing trades
trades = rebalance_portfolio(
  current_weights=[0.25, 0.25, 0.25, 0.25],
  target_weights=optimization["optimal_weights"],
  portfolio_value=100000,
  prices=[450, 105, 180, 85]
)

# 4. Simulate tax impact
for trade in trades["trades"]:
  if trade["shares_to_trade"] < 0:  # Selling
    simulate_sale(
      symbol=trade["asset_symbol"],
      quantity=abs(trade["shares_to_trade"]),
      sale_price=trade["price"]
    )
```

### 4. Common Pitfalls to Avoid

1. **Don't forget wash sale rules**: When harvesting losses, check `exclude_recent_days` parameter
2. **Account for transaction costs**: Use `min_trade_size` to avoid excessive small trades
3. **Validate data consistency**: Ensure return series have same length for all assets
4. **Check market hours**: Some tools may need market data during trading hours
5. **Handle missing data**: Some brokers may not provide all fields in CSV imports

### 5. Performance Tips

1. **Batch operations**: Update multiple prices in a single call
2. **Cache results**: Risk metrics don't change frequently
3. **Use v3 endpoints**: They're optimized for comprehensive analysis
4. **Minimize API calls**: Get all needed data in one `analyze_portfolio_risk` call

## Validation Rules Summary

### Common Validations Across All Servers:
- **Dates**: Must be "YYYY-MM-DD" format, cannot be future dates
- **Weights**: Must sum to 1.0 ± 0.001
- **Prices**: Must be positive (> 0)
- **Quantities**: Must be positive for buys, can be negative for sells
- **Returns**: Minimum 20 data points for statistical validity
- **Confidence**: Between 0.5 and 0.999
- **Tax rates**: Between 0 and 1

### Server-Specific Validations:
- **Portfolio State**: Symbols must be non-empty strings
- **Risk**: Return series must have consistent lengths
- **Tax**: Filing status must be valid enum value
- **Portfolio**: Lookback days minimum 60, maximum 1260

## Support and Troubleshooting

### Common Error Messages and Solutions:

1. **"Weights must sum to 1"**
   - Ensure portfolio weights add up to exactly 1.0
   - Example: [0.4, 0.3, 0.3] ✓ vs [0.4, 0.3, 0.2] ✗

2. **"Need at least 20 return observations"**
   - Provide more historical data points
   - Check data source for sufficient history

3. **"Transaction date cannot be in the future"**
   - Use today's date or earlier
   - Check system clock synchronization

4. **"Price for {symbol} must be positive"**
   - Verify market data feed
   - Check for data quality issues

5. **"All return series must have same length"**
   - Align data series to same time period
   - Handle missing data appropriately

## Version Information
- Portfolio State Server: v1.0 with Pydantic validation
- Risk Server: v3.0 with comprehensive analysis
- Tax Server: v2.0 with entity support
- Portfolio Server: v3.0 with advanced optimization

Last Updated: 2024-01-15