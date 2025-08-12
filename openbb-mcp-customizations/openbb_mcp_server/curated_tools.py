"""Curated list of OpenBB tools for MCP server.

This module defines a fixed set of 44 essential tools that provide comprehensive
financial analysis capabilities while minimizing context consumption.

IMPORTANT PARAMETER GUIDELINES FOR TOOLS:
- news_company: Use limit=20 with yfinance provider
- etf_equity_exposure: Use sector ETFs (XLK, XLF) not broad market (SPY)
- fixedincome_government_treasury_rates: Use provider="federal_reserve" not FMP
- equity_ownership_form_13f: Use provider="sec" for free access
- equity_ownership_insider_trading: Use provider="sec" for free access

PREFERRED PROVIDERS:
- equity_estimates_consensus: Use provider="yfinance" (free)
- equity_fundamental_*: Use provider="yfinance" (free)
- equity_ownership_*: Use provider="sec" (free)
- fixedincome_government_*: Use provider="federal_reserve" (free)

REMOVED TOOLS (26 noise/redundant):
Macro noise: economy_fred_series, economy_fred_search, economy_indicators, 
             economy_country_profile, economy_composite_leading_indicator,
             economy_survey_bls_search, economy_survey_bls_series,
             economy_direction_of_trade, economy_balance_of_payments, economy_gdp_forecast
News noise: news_world
Equity screeners: equity_search, equity_discovery_gainers, equity_discovery_growth_tech,
                 equity_discovery_undervalued_large_caps, equity_price_quote
ETF duplicates: etf_search, etf_countries, etf_info, etf_price_performance, etf_historical
Fixed income: fixedincome_bond_indices, fixedincome_mortgage_indices,
             fixedincome_yield_curve, fixedincome_spreads

ADDED TOOLS (10 high-ROI SEC/EDGAR and shorts tools):
SEC Core: regulators_sec_filing_headers, regulators_sec_htm_file, regulators_sec_rss_litigation,
         regulators_sec_cik_map, regulators_sec_symbol_map, regulators_sec_institutions_search
XBRL: equity_compare_company_facts, equity_fundamental_management_discussion_analysis
Shorts: equity_shorts_fails_to_deliver (SEC), equity_shorts_short_interest (FINRA - free),
        equity_shorts_short_volume (Stockgrid - free)

Updated: 2025-08-12 - Total of 44 curated tools with free shorts data providers installed
"""

# Immutable set of curated tools - these are the ONLY tools that will be available
CURATED_TOOLS = frozenset({
    # Economy Tools (5 canonical tools only)
    "economy_cpi",
    "economy_unemployment",
    "economy_interest_rates",
    "economy_gdp_real",
    "economy_gdp_nominal",
    # Optional (off by default): economy_house_price_index, economy_retail_prices
    
    # Equity Tools (11 tools - fundamentals, ownership, prices)
    # Prices & Performance
    "equity_price_historical",
    "equity_price_performance",
    
    # Fundamental Analysis (using yfinance provider)
    "equity_fundamental_balance",
    "equity_fundamental_income",
    "equity_fundamental_cash",
    "equity_fundamental_dividends",
    "equity_fundamental_metrics",
    "equity_fundamental_multiples",
    "equity_fundamental_management_discussion_analysis",  # MD&A extractor from SEC filings
    
    # Company Research
    "equity_profile",
    "equity_estimates_consensus",
    # "equity_analyst_estimates",  # Removed - doesn't exist as endpoint
    
    # Ownership & Filings (SEC provider)
    "equity_ownership_insider_trading",  # Use provider='sec'
    "equity_ownership_form_13f",  # Use provider='sec'
    "equity_discovery_filings",  # FMP for ticker-first discovery
    
    # Shorts & Market Frictions (SEC/FINRA/Stockgrid data)
    "equity_shorts_fails_to_deliver",  # FTD data from SEC
    "equity_shorts_short_interest",  # Short interest from FINRA (free)
    "equity_shorts_short_volume",  # Short volume from Stockgrid (free)
    
    # XBRL & Company Facts
    "equity_compare_company_facts",  # SEC companyfacts API
    
    # SEC/EDGAR Tools (6 new regulatory/filings tools)
    "regulators_sec_filing_headers",  # Fast form classification
    "regulators_sec_htm_file",  # Source HTML for LLM parsing
    "regulators_sec_rss_litigation",  # Enforcement & litigation feed
    "regulators_sec_cik_map",  # CIK/Symbol mapping
    "regulators_sec_symbol_map",  # Symbol/CIK mapping  
    "regulators_sec_institutions_search",  # Find institutional CIKs
    
    # Fixed Income Tools (4 canonical tools)
    "fixedincome_government_treasury_rates",  # Keep for LLM access
    "fixedincome_government_yield_curve",
    "fixedincome_spreads_tcm",
    "fixedincome_spreads_treasury_effr",
    
    # ETF Tools (3 essential tools only)
    "etf_holdings",
    "etf_sectors",  # Sector breakdown
    "etf_equity_exposure",  # Individual stock exposure
    
    # Index Tools (1 tool)
    "index_price_historical",
    
    # Derivatives Tools (2 tools)
    "derivatives_options_chains",
    "derivatives_futures_curve",
    
    # News Tools (1 tool - company specific only)
    "news_company",  # Keep for issuer-specific headlines
    
    # Currency Tools (1 tool)
    "currency_price_historical",
    
    # Commodity Tools (1 tool)
    "commodity_price_spot",
    
    # Cryptocurrency Tools (1 tool)
    "crypto_price_historical",
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

# Blocklist of removed tools
BLOCKLIST = frozenset({
    # Macro noise
    "economy_fred_series", "economy_fred_search", "economy_indicators",
    "economy_country_profile", "economy_composite_leading_indicator",
    "economy_survey_bls_search", "economy_survey_bls_series",
    "economy_direction_of_trade", "economy_balance_of_payments", "economy_gdp_forecast",
    "economy_survey_nonfarm_payrolls", "economy_retail_prices", "economy_house_price_index",
    
    # News noise
    "news_world", "news_market",
    
    # Equity screeners/duplicates
    "equity_search", "equity_discovery_gainers", "equity_discovery_growth_tech",
    "equity_discovery_undervalued_large_caps", "equity_price_quote", "equity_shock",
    
    # ETF duplicates
    "etf_search", "etf_countries", "etf_info", "etf_price_performance", "etf_historical",
    
    # Fixed income duplicates
    "fixedincome_yield_curve", "fixedincome_spreads",
    "fixedincome_bond_indices", "fixedincome_mortgage_indices",
})

# Provider overrides to ensure free access
PROVIDER_OVERRIDES = {
    "equity_fundamental_balance": "yfinance",
    "equity_fundamental_income": "yfinance",
    "equity_fundamental_cash": "yfinance",
    "equity_fundamental_dividends": "yfinance",
    "equity_fundamental_metrics": "yfinance",
    "equity_fundamental_multiples": "yfinance",
    "equity_ownership_insider_trading": "sec",
    "equity_ownership_form_13f": "sec",
    "equity_estimates_consensus": "yfinance",
    "fixedincome_government_treasury_rates": "federal_reserve",
    "fixedincome_government_yield_curve": "federal_reserve",
}

# Parameter defaults for tools
PARAMETER_DEFAULTS = {
    "economy_cpi": {"country": "united_states"},
    "equity_ownership_form_13f": {"provider": "sec"},
    "equity_ownership_insider_trading": {"provider": "sec"},
    "news_company": {"limit": 20, "provider": "yfinance"},
    "fixedincome_government_treasury_rates": {"provider": "federal_reserve"},
    "etf_equity_exposure": {"limit": 100},
}