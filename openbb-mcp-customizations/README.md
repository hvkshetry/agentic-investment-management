# OpenBB MCP Server - Curated Tools Edition

## Overview

This is a modified version of the OpenBB MCP server that loads only a curated set of 60 essential financial tools, reducing context consumption by ~67% (from 184 to 60 tools). All tools use free data sources (FRED, yfinance, SEC, FINRA, ECB, OECD, IMF, EconDB) or FMP with the configured API key.

**Updated 2025-08-06**: Removed 5 unfixable tools after comprehensive testing.

## Changes Made

1. **Created `curated_tools.py`**: Defines a hardcoded, immutable set of tools with documentation
2. **Modified `main.py`**: 
   - Only enables tools in the curated list
   - Disables tool discovery features (available_categories, available_tools, activate_tools, deactivate_tools)
3. **Modified `settings.py`**: Forces `enable_tool_discovery = False`
4. **Modified `config.py`**: Ensures tool discovery cannot be re-enabled
5. **Added FMP API configuration**: Created `user_settings.json` with FMP API key for ETF analysis tools

## Important Tool Updates

### Corrected Tool Names
- `commodity_price_spot` (was: commodity_price_historical)
- `news_world` (was: news_general)
- `index_available` (was: index_market)
- `fixedincome_spreads_treasury_effr` (was: fixedincome_spreads_treasury_yield)

### Critical Parameter Guidelines
To avoid token limit errors and ensure proper functionality:
- `economy_direction_of_trade` - Use country="us", frequency="annual", limit=100
- `economy_balance_of_payments` - Always include start_date
- `news_company` - Use provider="yfinance" (no date/limit needed - auto-optimized to 50 articles)
- `etf_equity_exposure` - Use sector ETFs (XLK, XLF) not SPY
- `equity_discovery_gainers` - Use limit=50
- `economy_fred_series` - NEVER use limit parameter, use date ranges
- `fixedincome_government_treasury_rates` - Use provider="federal_reserve"

### Preferred Free Providers
- `equity_estimates_consensus` - Use provider="yfinance"
- `equity_fundamental_income` - Use provider="yfinance" or "polygon"
- `equity_ownership_insider_trading` - Use provider="sec"
- `equity_discovery_filings` - Recent SEC filings
- `equity_fundamental_multiples` - Valuation multiples
- `equity_ownership_form_13f` - 13F filings

## Curated Tools (60 total)

### Removed Tools (5 unfixable)
- `economy_export_destinations` - EconDB API broken
- `economy_port_volume` - EconDB API structure error
- `derivatives_options_unusual` - Requires paid intrinio API
- `derivatives_options_snapshots` - Requires paid intrinio API
- `equity_fundamental_trailing_dividend_yield` - Requires paid tiingo API

### Economy (18 tools)
- GDP: real, nominal, forecast
- Inflation: CPI, retail prices, house price index
- Rates: interest rates (unified function)
- Employment & Trade: unemployment, balance of payments, nonfarm payrolls
- Data Access: FRED series/search, BLS series/search
- Indicators: composite leading indicator
- **Trade & International Analysis (3 tools)**:
  - Direction of Trade: Bilateral merchandise trade flows (IMF)
  - Economic Indicators: International reserves, financial soundness (IMF/EconDB)
  - Country Profile: Comprehensive economic overview (EconDB)

### Equity (16 tools)
- Search & Quotes: search, price quote, historical, performance
- Fundamentals: balance, income, cash, dividends, metrics, multiples
- Research: profile, estimates consensus, discovery filings
- Screening: discovery gainers, undervalued large caps, growth tech
- Ownership: insider trading, form 13F

### Fixed Income (6 tools)
- Treasury rates, yield curve, TCM spreads, treasury-EFFR spreads
- Indices: bond indices, mortgage indices

### ETF (8 tools)
- Search, info, holdings, performance, historical
- Portfolio Analysis: sectors, countries, equity exposure (FMP provider)

### Index (3 tools)
- Historical prices, constituents, available indices

### Derivatives (2 tools)
- Options chains, futures curve

### News (2 tools)
- World news, company news

### Currency (1 tool)
- Historical prices

### Commodity (1 tool)
- Spot prices

### Cryptocurrency (1 tool)
- Historical prices (YFinance/FMP)

## API Configuration

All API keys are configured in `~/.openbb_platform/user_settings.json`. See `user_settings.json.example` for the required format.

Required API keys:
- **FRED API Key**: Free from https://fred.stlouisfed.org/docs/api/api_key.html
- **BLS API Key**: Free from https://www.bls.gov/developers/api_registration.htm
- **FMP API Key**: Free tier available from https://site.financialmodelingprep.com/developer/docs/

Note: While FRED and BLS are free public services, they still require API keys for access.

## Usage

1. Start the MCP server with:
   ```bash
   openbb-mcp --no-tool-discovery
   ```

2. Or configure your MCP client with the provided `mcp_config.json`:
   ```json
   {
     "transport": "stdio",
     "args": ["--no-tool-discovery"],
     "describe_responses": false
   }
   ```

## Benefits

- **67% reduction in context usage**: Only 60 tools instead of 184
- **Focused on free data sources**: yfinance, FRED, SEC, FINRA, IMF, EconDB
- **No dynamic tool management**: Consistent, predictable tool availability
- **Optimized for investment analysis**: All essential tools included
- **Trade analysis capabilities**: Monitor deglobalization and tariff impacts

## Trade Analysis Capabilities

The 5 new trade tools enable monitoring of:
- **Trade relationship shifts**: Track bilateral flows between specific countries
- **Supply chain vulnerabilities**: Identify export dependencies and concentration
- **Early warning indicators**: Port congestion and dwelling times signal disruptions
- **Financial stability**: Monitor international reserves and soundness indicators
- **Portfolio exposure**: Assess which trade corridors affect your investments

These tools are essential for investment advisory in an era of increasing trade tensions, tariffs, and supply chain restructuring.

## Notes

- Tool discovery is permanently disabled
- The curated tool list cannot be modified at runtime
- All tools are loaded at startup for maximum performance