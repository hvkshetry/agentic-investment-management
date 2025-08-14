# Concentration Analysis with MCP Tools

## How Agents Should Use MCP Tools for Look-Through Analysis

### 1. Getting ETF Holdings

When analyzing concentration risk, agents should use the MCP ETF holdings tool:

```python
# For each ETF in the portfolio
for symbol in etf_symbols:
    # Get actual holdings using MCP tool
    holdings_response = mcp__openbb-curated__etf_holdings(
        symbol=symbol,
        limit=100  # Get top 100 holdings
    )
    
    # Process the holdings data
    from orchestrator.position_lookthrough import PositionLookthrough
    analyzer = PositionLookthrough()
    
    # Convert MCP response to holdings dictionary
    holdings_dict = analyzer.get_fund_holdings_from_mcp(symbol, holdings_response)
```

### 2. Getting Fund Categories

For mutual fund categorization, use the equity_profile tool:

```python
# Get fund metadata including category
profile_response = mcp__openbb-curated__equity_profile(
    symbol="VWIUX",
    provider="yfinance"
)

# Extract category from response
from orchestrator.symbol_resolver import SymbolResolver
resolver = SymbolResolver()
category = resolver.get_fund_category_from_mcp("VWIUX", profile_response)
```

### 3. Complete Concentration Analysis Workflow

```python
# Step 1: Get portfolio from state server
portfolio_state = mcp__portfolio-state-server__get_portfolio_state()

# Step 2: Extract positions and weights
positions = {}
for holding in portfolio_state["positions"]:
    symbol = holding["symbol"]
    weight = holding["weight"]
    positions[symbol] = weight

# Step 3: Identify ETFs and get their holdings
from orchestrator.position_lookthrough import PositionLookthrough
analyzer = PositionLookthrough(concentration_limit=0.10)

etf_holdings = {}
for symbol, weight in positions.items():
    if analyzer.is_fund(symbol):
        # Get ETF holdings using MCP
        holdings_data = mcp__openbb-curated__etf_holdings(
            symbol=symbol,
            limit=100
        )
        
        # Process and store
        etf_holdings[symbol] = analyzer.get_fund_holdings_from_mcp(
            symbol, 
            holdings_data
        )

# Step 4: Calculate true concentration with look-through
company_exposure = {}
for symbol, weight in positions.items():
    if symbol in etf_holdings:
        # ETF - aggregate underlying holdings
        for holding_symbol, holding_weight in etf_holdings[symbol].items():
            exposure = weight * holding_weight
            if holding_symbol in company_exposure:
                company_exposure[holding_symbol] += exposure
            else:
                company_exposure[holding_symbol] = exposure
    else:
        # Direct holding
        if symbol in company_exposure:
            company_exposure[symbol] += weight
        else:
            company_exposure[symbol] = weight

# Step 5: Check concentration limits
violations = []
for symbol, concentration in company_exposure.items():
    if concentration > 0.10:  # 10% limit
        violations.append({
            "symbol": symbol,
            "concentration": concentration,
            "excess": concentration - 0.10
        })

# Step 6: Generate report
if violations:
    print(f"❌ FAILED: {len(violations)} companies exceed 10% limit")
    for v in violations:
        print(f"  {v['symbol']}: {v['concentration']:.2%}")
else:
    print("✅ PASSED: No concentration violations")
```

## Agent Instructions

### For Risk Analyst

When performing concentration analysis:

1. **Always use MCP tools** for ETF holdings:
   ```python
   mcp__openbb-curated__etf_holdings(symbol="VTI", limit=100)
   ```

2. **Aggregate exposures** across all holdings (direct + ETF underlying)

3. **Apply 10% limit** to individual companies, not ETFs themselves

### For Gate Validator

When validating concentration gates:

1. **Distinguish between funds and stocks**:
   - ETFs/Mutual Funds: Can exceed 10% (they're diversified)
   - Individual Stocks: Must stay under 10%

2. **Perform look-through analysis**:
   - Get ETF holdings from MCP tools
   - Calculate aggregate exposure to each company
   - Flag violations only for single-company concentrations

### For Portfolio Manager

When optimizing portfolios:

1. **Consider hidden concentrations**:
   - Multiple ETFs may hold the same stocks
   - Check aggregate exposure after optimization

2. **Use MCP tools for validation**:
   ```python
   # After proposing new weights
   for etf in proposed_etfs:
       holdings = mcp__openbb-curated__etf_holdings(symbol=etf, limit=50)
       # Check for concentration buildup
   ```

## MCP Tool References

### ETF Holdings
- **Tool**: `mcp__openbb-curated__etf_holdings`
- **Parameters**: 
  - `symbol`: ETF ticker (required)
  - `limit`: Number of holdings to return (default 10, max 100)
- **Returns**: List of holdings with symbols and weights

### Fund/Equity Profile
- **Tool**: `mcp__openbb-curated__equity_profile`
- **Parameters**:
  - `symbol`: Ticker symbol (required)
  - `provider`: Data provider (use "yfinance")
- **Returns**: Profile data including category for funds

### ETF Sectors
- **Tool**: `mcp__openbb-curated__etf_sectors`
- **Parameters**:
  - `symbol`: ETF ticker (required)
- **Returns**: Sector breakdown of ETF holdings

### ETF Equity Exposure
- **Tool**: `mcp__openbb-curated__etf_equity_exposure`
- **Parameters**:
  - `symbol`: ETF ticker (required)
  - `limit`: Number of exposures to return
- **Returns**: Top equity exposures in the ETF

## Implementation Notes

1. **Caching**: Holdings are cached to avoid repeated API calls
2. **Fallback**: If MCP tools fail, use approximate holdings
3. **Validation**: Always validate symbols before analysis
4. **Performance**: Process ETFs in parallel when possible