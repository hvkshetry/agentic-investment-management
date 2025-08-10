"""Curated list of OpenBB tools for MCP server.

This module defines a fixed set of 58 essential tools that provide comprehensive
financial analysis capabilities while minimizing context consumption.

IMPORTANT PARAMETER GUIDELINES FOR TOOLS:
- economy_direction_of_trade: Use country="us" (not "all"), frequency="annual", limit=100
- economy_balance_of_payments: Always include start_date
- news_world/news_company: Use limit=20 with yfinance provider
- etf_equity_exposure: Use sector ETFs (XLK, XLF) not broad market (SPY)
- equity_discovery_gainers: Use limit=50 to manage response size
- economy_fred_series: NEVER use limit parameter, use date ranges instead
- fixedincome_government_treasury_rates: Use provider="federal_reserve" not FMP

PREFERRED PROVIDERS:
- equity_estimates_consensus: Use provider="yfinance" (free)
- equity_fundamental_income: Use provider="yfinance" or "polygon" (both free)
- equity_ownership_insider_trading: Use provider="sec" (free)

REMOVED TOOLS (5 unfixable):
- economy_export_destinations: EconDB API broken, returns HTML
- economy_port_volume: EconDB API structure error
- derivatives_options_unusual: Requires paid intrinio API
- derivatives_options_snapshots: Requires paid intrinio API  
- equity_fundamental_trailing_dividend_yield: Requires paid tiingo API

Updated: 2025-08-10 - Reduced from 60 to 58 tools (removed unused index_constituents, index_available)
"""

# Immutable set of curated tools - these are the ONLY tools that will be available
CURATED_TOOLS = frozenset({
    # Economy Tools (18 tools - all working with proper parameters)
    # GDP & Growth
    "economy_gdp_real",
    "economy_gdp_nominal", 
    "economy_gdp_forecast",
    
    # Inflation & Prices
    "economy_cpi",
    "economy_retail_prices",
    "economy_house_price_index",
    
    # Interest Rates & Money (excluding non-working money_measures)
    "economy_interest_rates",
    
    # Employment & Trade
    "economy_unemployment",
    "economy_balance_of_payments",  # Requires date parameters
    "economy_survey_nonfarm_payrolls",  # Added as free alternative
    
    # FRED & BLS Access
    "economy_fred_series",
    "economy_fred_search",
    "economy_survey_bls_series",
    "economy_survey_bls_search",
    
    # Leading Indicators
    "economy_composite_leading_indicator",
    
    # Trade & International Analysis (3 tools - removed broken EconDB tools)
    "economy_direction_of_trade",  # Bilateral trade flows (IMF) - use specific params
    "economy_indicators",  # IMF/EconDB indicators including reserves
    "economy_country_profile",  # Country economic overview (EconDB)
    
    # Equity Tools (16 tools - mix of working and free alternatives)
    # Search & Quotes
    "equity_search",
    "equity_price_quote",
    "equity_price_historical",
    "equity_price_performance",  # Added free tool
    
    # Fundamental Analysis (using free alternatives)
    "equity_fundamental_balance",
    "equity_fundamental_income",
    "equity_fundamental_cash",
    "equity_fundamental_dividends",
    "equity_fundamental_metrics",
    "equity_fundamental_multiples",  # Free alternative to ratios
    
    # Company Research (using free alternatives)
    "equity_profile",
    "equity_estimates_consensus",
    "equity_discovery_filings",  # Free alternative to compare_peers
    # New discovery/screening tools (YFinance provider)
    "equity_discovery_gainers",  # Top gaining stocks
    "equity_discovery_undervalued_large_caps",  # Value screening
    "equity_discovery_growth_tech",  # Growth stock screening
    
    # Ownership Data (using free alternatives)
    "equity_ownership_insider_trading",
    "equity_ownership_form_13f",  # Free alternative to institutional
    
    # Fixed Income Tools (6 tools - all working with parameters)
    "fixedincome_government_treasury_rates",  # Requires date parameters
    "fixedincome_government_yield_curve",
    "fixedincome_spreads_tcm",  # Free alternative to treasury_yield
    "fixedincome_spreads_treasury_effr",  # Correct name
    # New fixed income indices (FRED provider)
    "fixedincome_bond_indices",  # Bond market indices
    "fixedincome_mortgage_indices",  # Mortgage rate indices
    
    # ETF Tools (8 tools - all working)
    "etf_search",
    "etf_info",
    "etf_holdings",
    "etf_price_performance",
    "etf_historical",
    # New ETF portfolio analysis tools (FMP provider)
    "etf_sectors",  # Sector breakdown of ETF holdings
    "etf_countries",  # Geographic exposure analysis
    "etf_equity_exposure",  # Individual stock exposure in ETFs
    
    # Index Tools (1 tool - removed unused)
    "index_price_historical",
    
    # Derivatives Tools (2 tools - removed paid-only intrinio tools)
    "derivatives_options_chains",
    "derivatives_futures_curve",  # Futures curve analysis (YFinance)
    
    # News Tools (2 tools - with corrected names)
    "news_world",  # Corrected from news_general
    "news_company",
    
    # Currency Tools (1 tool - removed non-existent)
    "currency_price_historical",
    
    # Commodity Tools (1 tool - with corrected name)
    "commodity_price_spot",  # Corrected from commodity_price_historical
    
    # Cryptocurrency Tools (1 tool - new)
    "crypto_price_historical",  # Cryptocurrency prices (YFinance/FMP)
})

def is_curated_tool(tool_name: str) -> bool:
    """Check if a tool is in the curated list.
    
    Args:
        tool_name: The name of the tool to check
        
    Returns:
        True if the tool is in the curated list, False otherwise
    """
    return tool_name in CURATED_TOOLS

def get_curated_tools_count() -> int:
    """Get the total number of curated tools.
    
    Returns:
        The number of tools in the curated list
    """
    return len(CURATED_TOOLS)