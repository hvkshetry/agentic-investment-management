# Data Dependencies Summary for MCP Servers

## Overview
The Risk, Portfolio, and Tax MCP servers rely on several external data sources, primarily through the shared `MarketDataPipeline` class.

## Primary Data Sources

### 1. Portfolio State Server
- **Source**: Local state (portfolio_state.json)
- **Data**: Current holdings, tax lots, purchase prices
- **Price Updates**: Yahoo Finance (via yfinance library)
- **Frequency**: Cached for 5 minutes per symbol

### 2. Market Data Pipeline (shared by Risk & Portfolio servers)

#### Equity Price Data
- **Primary Source**: OpenBB (if available) with yfinance provider
- **Fallback**: Direct yfinance API calls
- **Data Fetched**:
  - Historical daily prices (Close, Open, High, Low, Volume)
  - Default lookback: 504 days (2 years) for portfolio optimization
  - Default lookback: 252 days (1 year) for risk analysis
- **Processing**:
  - Calculates daily returns
  - Handles missing data imputation
  - Performs data quality scoring

#### Risk-Free Rate
- **Source**: OpenBB via FRED (Federal Reserve Economic Data)
- **Data**: US Treasury rates (3m, 1y, 5y, 10y, 30y)
- **Default**: 10-year Treasury rate
- **Fallback**: NONE - fails if OpenBB unavailable (no synthetic fallback)

#### Covariance Estimation (for optimization)
- **Methods**:
  1. Sample covariance (raw historical)
  2. Ledoit-Wolf shrinkage (via scikit-learn)
  3. Exponentially weighted covariance (60-day span)
- **Purpose**: Robust portfolio optimization

## Data Flow by Server

### Risk MCP Server (`risk_mcp_server_v3.py`)
```python
External Data Inputs:
1. Historical prices: data_pipeline.prepare_for_optimization(tickers, lookback_days=504)
   - Source: OpenBB/yfinance
   - Returns: prices, returns, covariance matrices
   
2. Risk-free rate: data_pipeline.get_risk_free_rate('10y')
   - Source: OpenBB/FRED
   - Used for: Sharpe ratio, Sortino ratio calculations
   
3. Current positions: portfolio_state_client.get_positions()
   - Source: Portfolio State Server (which fetches from yfinance)
```

### Portfolio MCP Server (`portfolio_mcp_server_v3.py`)
```python
External Data Inputs:
1. Historical prices: data_pipeline.prepare_for_optimization(tickers, lookback_days=756)
   - Source: OpenBB/yfinance
   - Default: 3 years of data
   - Returns: prices, returns, expected returns, covariance matrices
   
2. Risk-free rate: data_pipeline.get_risk_free_rate('10y')
   - Source: OpenBB/FRED
   - Used for: Sharpe optimization, efficient frontier
   
3. Current positions: portfolio_state_client.get_positions()
   - Source: Portfolio State Server
```

### Tax MCP Server (`tax_mcp_server_v2.py`)
```python
External Data Inputs:
1. Tax lots: portfolio_state_client.get_tax_lots()
   - Source: Portfolio State Server
   - No direct market data fetching
   
2. Current positions: portfolio_state_client.get_positions(fetch_prices=False)
   - Note: Explicitly avoids fetching prices to reduce API calls
   
3. Tax calculations: tenforty library
   - Source: Internal tax calculation library
   - No external API calls
```

## Data Caching Strategy

### Portfolio State Server
- **Price Cache**: 5 minutes (300 seconds) TTL
- **Stored in**: `shared/cache/market_data_cache.json`
- **Format**: `{symbol: {value, timestamp}}`

### Market Data Pipeline
- **No built-in cache** - fetches fresh data each call
- **Recommendation**: Implement caching for historical data

## External Library Dependencies

### Required for Data Fetching
```python
# Core dependencies
yfinance         # Yahoo Finance data
openbb           # OpenBB platform (for treasury rates)
pandas           # Data manipulation
numpy            # Numerical operations
scipy            # Statistical functions

# For robust estimation
scikit-learn     # Ledoit-Wolf covariance shrinkage
statsmodels      # Stationarity tests (ADF)

# For tax calculations
tenforty         # Federal/state tax calculations
```

## API Rate Limits & Considerations

### Yahoo Finance (via yfinance)
- No official rate limits but throttling may occur
- Best practice: Batch requests, use 5-minute cache
- Mutual funds: Use 5-day period for better compatibility

### OpenBB/FRED
- FRED API: 120 requests per minute
- OpenBB handles rate limiting internally
- Treasury rates updated daily (no need for frequent fetches)

## Data Quality Checks

The MarketDataPipeline performs:
1. **Sample size adequacy** (min 252 days recommended)
2. **Missing data detection** (<1% threshold)
3. **Stationarity tests** (ADF test on returns)
4. **Outlier detection** (MAD-based, 3σ threshold)
5. **Condition number** check for covariance matrix

## Summary

**Primary external data sources:**
1. **Yahoo Finance** (via yfinance): All equity/ETF/mutual fund prices
2. **OpenBB/FRED**: US Treasury rates for risk-free rate
3. **No other external APIs** are used

**Data fetching frequency:**
- Portfolio State: On-demand with 5-minute cache
- Risk/Portfolio analysis: Fresh fetch for each analysis
- Tax calculations: No market data needed (uses stored tax lots)

**Critical dependencies:**
- OpenBB is REQUIRED for risk-free rates (no fallback)
- yfinance is REQUIRED for equity prices (OpenBB uses it as provider)
- Both libraries must be installed for full functionality