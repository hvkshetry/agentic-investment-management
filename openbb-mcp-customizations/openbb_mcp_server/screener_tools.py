"""Free equity screener tools.

Provides equity screening using free providers:
- FMP (Financial Modeling Prep, limited free tier)
"""

import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from shared.http_client import BaseHTTPTool, ProviderError

logger = logging.getLogger(__name__)


class FMPScreenerFetcher:
    """Fetch screener results from FMP."""

    def __init__(self):
        self.api_key = os.getenv("FMP_API_KEY")
        if not self.api_key:
            logger.warning("FMP_API_KEY not set - FMP screener unavailable")

        self.client = BaseHTTPTool(
            provider_name="fmp",
            base_url="https://financialmodelingprep.com/api/v3",
            timeout=30.0,
            cache_ttl=3600  # 1-hour cache
        )

    async def screen_stocks(
        self,
        market_cap_min: Optional[float] = None,
        market_cap_max: Optional[float] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        beta_min: Optional[float] = None,
        beta_max: Optional[float] = None,
        volume_min: Optional[int] = None,
        dividend_min: Optional[float] = None,
        is_etf: bool = False,
        is_actively_trading: bool = True,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        exchange: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Screen stocks with filters.

        Args:
            market_cap_min: Minimum market cap
            market_cap_max: Maximum market cap
            price_min: Minimum price
            price_max: Maximum price
            beta_min: Minimum beta
            beta_max: Maximum beta
            volume_min: Minimum volume
            dividend_min: Minimum dividend yield (%)
            is_etf: Filter for ETFs only
            is_actively_trading: Filter for actively trading stocks
            sector: Sector filter
            industry: Industry filter
            country: Country filter (e.g., 'US')
            exchange: Exchange filter (e.g., 'NASDAQ', 'NYSE')
            limit: Max results (default 50)

        Returns:
            Dict with screener results
        """
        if not self.api_key:
            raise ProviderError("FMP API key not configured")

        try:
            # Build query parameters
            params = {"apikey": self.api_key, "limit": limit}

            if market_cap_min:
                params["marketCapMoreThan"] = int(market_cap_min)
            if market_cap_max:
                params["marketCapLowerThan"] = int(market_cap_max)
            if price_min:
                params["priceMoreThan"] = price_min
            if price_max:
                params["priceLowerThan"] = price_max
            if beta_min:
                params["betaMoreThan"] = beta_min
            if beta_max:
                params["betaLowerThan"] = beta_max
            if volume_min:
                params["volumeMoreThan"] = volume_min
            if dividend_min:
                params["dividendMoreThan"] = dividend_min
            if is_etf:
                params["isEtf"] = "true"
            if is_actively_trading:
                params["isActivelyTrading"] = "true"
            if sector:
                params["sector"] = sector
            if industry:
                params["industry"] = industry
            if country:
                params["country"] = country
            if exchange:
                params["exchange"] = exchange

            # FMP screener endpoint
            data = await self.client.get("/stock-screener", params=params)

            if not isinstance(data, list):
                raise ProviderError("Invalid FMP screener response format")

            # Transform to standard format
            results = []
            for stock in data[:limit]:  # Enforce limit
                results.append({
                    "symbol": stock.get("symbol"),
                    "name": stock.get("companyName"),
                    "sector": stock.get("sector"),
                    "industry": stock.get("industry"),
                    "market_cap": stock.get("marketCap"),
                    "price": stock.get("price"),
                    "beta": stock.get("beta"),
                    "volume": stock.get("volume"),
                    "dividend_yield": stock.get("lastAnnualDividend"),
                    "exchange": stock.get("exchangeShortName"),
                    "country": stock.get("country")
                })

            return {
                "results": results,
                "count": len(results),
                "filters": {
                    "market_cap_min": market_cap_min,
                    "market_cap_max": market_cap_max,
                    "price_min": price_min,
                    "price_max": price_max,
                    "beta_min": beta_min,
                    "beta_max": beta_max,
                    "volume_min": volume_min,
                    "dividend_min": dividend_min,
                    "sector": sector,
                    "industry": industry,
                    "country": country,
                    "exchange": exchange
                },
                "source": "fmp",
                "provider": "fmp"
            }

        except Exception as e:
            logger.error(f"FMP screener failed: {e}")
            raise ProviderError(f"FMP error: {e}")


# Module-level singleton fetcher to prevent socket leaks
_fmp_screener_fetcher = FMPScreenerFetcher()


# MCP tool wrapper
async def mcp_equity_screener(
    market_cap_min: Optional[float] = None,
    market_cap_max: Optional[float] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    beta_min: Optional[float] = None,
    beta_max: Optional[float] = None,
    volume_min: Optional[int] = None,
    dividend_min: Optional[float] = None,
    is_etf: bool = False,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    exchange: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    MCP wrapper for equity screener.

    Args:
        market_cap_min: Minimum market cap (USD)
        market_cap_max: Maximum market cap (USD)
        price_min: Minimum stock price
        price_max: Maximum stock price
        beta_min: Minimum beta (volatility)
        beta_max: Maximum beta
        volume_min: Minimum trading volume
        dividend_min: Minimum dividend yield (%)
        is_etf: Filter for ETFs only
        sector: Sector filter (e.g., 'Technology', 'Healthcare')
        industry: Industry filter
        country: Country code (e.g., 'US', 'CN')
        exchange: Exchange (e.g., 'NASDAQ', 'NYSE')
        limit: Max results (default 50, max 100)

    Returns:
        Dict containing screened stocks with metadata

    Example:
        # Find large-cap tech stocks
        mcp_equity_screener(
            market_cap_min=10_000_000_000,
            sector="Technology",
            limit=20
        )
    """
    try:
        # Enforce 100-item cap (as per ResponseLimiter)
        limit = min(limit, 100)

        # Use module-level singleton to avoid socket leaks
        result = await _fmp_screener_fetcher.screen_stocks(
            market_cap_min=market_cap_min,
            market_cap_max=market_cap_max,
            price_min=price_min,
            price_max=price_max,
            beta_min=beta_min,
            beta_max=beta_max,
            volume_min=volume_min,
            dividend_min=dividend_min,
            is_etf=is_etf,
            sector=sector,
            industry=industry,
            country=country,
            exchange=exchange,
            limit=limit
        )

        return result

    except Exception as e:
        logger.error(f"Error running equity screener: {e}")
        return {
            "error": str(e),
            "filters": {
                "market_cap_min": market_cap_min,
                "sector": sector,
                "industry": industry
            }
        }
