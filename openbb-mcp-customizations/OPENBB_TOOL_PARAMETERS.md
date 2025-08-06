# OpenBB MCP Curated Tools - Parameter Guide

## Tools Requiring Date Parameters

These tools MUST include date parameters to avoid exceeding token limits:

### 1. economy_balance_of_payments
```python
# Required parameter:
start_date="2024-01-01"  # Use a date within the last year
```

### 2. fixedincome_government_treasury_rates
```python
# Required parameters:
start_date="2024-07-01"  # Start of date range
end_date="2024-12-31"    # End of date range (6-12 months recommended)
provider="federal_reserve"  # or "fmp"
```

## Tools Requiring Careful Parameter Usage

### economy_survey_bls_search
To avoid token limit issues, use specific parameters:
```python
# Good practice - specific query with filters:
obb.economy.survey.bls_search(
    category="cpi",                # Always specify a category
    query="gasoline;seattle",      # Use specific keywords with ; as AND
    include_extras=False,          # Reduce output size
    include_code_map=False         # Reduce output size
)

# Available categories:
# cpi, pce, ppi, ip, jolts, nfp, cps, lfs, wages, ec, sla, bed, tu
```

## Tools with Special Provider Requirements

### BLS Tools (Bureau of Labor Statistics)
```python
# economy_survey_bls_series
# Must use proper BLS series ID format:
series_id="CUUR0000SA0"  # CPI example
# NOT FRED series IDs like "UNRATE"
```

### Working Provider Recommendations

#### Economy Tools
- GDP tools: Use `provider="oecd"` or `provider="econdb"`
- CPI: Use `provider="fred"` or `provider="oecd"`
- FRED tools: Use `provider="fred"`
- Unemployment: Use `provider="oecd"`

#### Equity Tools
- Fundamentals: Use `provider="yfinance"`
- Price data: Use `provider="yfinance"`
- Insider trading: Use `provider="sec"`
- Company search: Use `provider="sec"`

#### Fixed Income Tools
- Yield curve: Works without date restrictions
- Other tools: See date parameter requirements above

## Free Alternatives Reference

| Premium Tool | Free Alternative | Provider |
|--------------|------------------|----------|
| equity_compare_peers | equity_discovery_filings | sec |
| equity_fundamental_ratios | equity_fundamental_multiples | yfinance |
| equity_ownership_institutional | equity_ownership_form_13f | sec |
| economy_risk_premium | Use economy_fred_series to calculate | fred |

## Deprecated Tools Removed

The following tools have been removed as they are deprecated or redundant:

| Removed Tool | Alternative | Notes |
|--------------|-------------|--------|
| economy_long_term_interest_rate | economy_interest_rates(duration="long") | Deprecated in v4.3 |
| economy_short_term_interest_rate | economy_interest_rates(duration="short") | Deprecated in v4.3 |
| fixedincome_rate_effr | economy_fred_series("EFFR") | Use FRED series directly |
| fixedincome_rate_sofr | economy_fred_series("SOFR") | Use FRED series directly |

## Common FRED Series for economy_fred_series

### Interest Rates
- DGS1, DGS2, DGS10, DGS30 - Treasury yields
- FEDFUNDS - Federal funds rate
- SOFR - Secured overnight financing rate
- MORTGAGE30US - 30-year mortgage rate

### Economic Indicators
- GDP, GDPC1 - Gross domestic product
- CPIAUCSL - Consumer price index
- UNRATE - Unemployment rate
- PAYEMS - Nonfarm payrolls
- HOUST - Housing starts

### Market Indicators
- VIXCLS - VIX volatility index
- DEXUSEU - USD/EUR exchange rate
- GOLDAMGBD228NLBM - Gold price
- DCOILWTICO - WTI crude oil price
- T10Y2Y - 10Y-2Y Treasury spread

### Money Supply
- M1SL - M1 money supply
- M2SL - M2 money supply
- BOGMBASE - Monetary base

## Trade Analysis Tools Parameters

### economy_direction_of_trade
- **provider**: imf (required)
- **country**: ISO codes or names (e.g., "us", "china", "united_states")
- **counterpart**: Trading partners (e.g., "world", "eu", "china,mexico")
- **direction**: "exports", "imports", "balance", or "all"
- **frequency**: "annual", "quarterly", "monthly"
- **start_date/end_date**: Date range for analysis
- Example: Track US-China bilateral trade monthly

### economy_export_destinations
- **provider**: econdb (required)
- **country**: ISO code (e.g., "us", "de", "jp")
- Returns top export partners with percentage shares

### economy_indicators
- **provider**: imf or econdb
- **symbol**: 
  - For IMF: Use presets like "gold_reserves", "fsi_core", "irfcl_top_lines"
  - For EconDB: Use indicators like "GDP", "CPI", "MAIN"
- **country**: ISO codes, can be multiple (e.g., "us,china,jp")
- **frequency**: Data frequency preference
- For IMF data, supports Financial Soundness Indicators

### economy_country_profile
- **provider**: econdb (required)
- **country**: Full name or ISO code (e.g., "united_states" or "us")
- **latest**: true for current data only, false for full history

### economy_port_volume
- **provider**: econdb or imf
- **port_code**: Specific ports (e.g., "rotterdam,singapore")
- Returns TEU (Twenty-foot Equivalent Unit) volumes and average dwelling times

## Tips for Optimal Usage

1. Always specify date ranges for the four tools that require them
2. Use 1-year ranges for most analyses to balance data volume with context
3. For BLS tools, use proper BLS series IDs, not FRED equivalents
4. When a tool fails with a provider, try alternative providers listed above
5. For risk premium calculations, use economy_fred_series to get component rates and calculate spreads manually
6. For trade analysis, use bilateral flows to track specific trade relationships
7. Monitor port volumes as leading indicators of trade disruptions