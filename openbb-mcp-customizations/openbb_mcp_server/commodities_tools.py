"""Free commodities pricing tools.

Provides commodities data using free providers:
- EIA (U.S. Energy Information Administration - official, no key required)
- LBMA (London Bullion Market Association - gold/silver prices)
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from shared.http_client import BaseHTTPTool, ProviderError

logger = logging.getLogger(__name__)


class LBMAFetcher:
    """Fetch precious metals prices from LBMA."""

    def __init__(self):
        self.client = BaseHTTPTool(
            provider_name="lbma",
            base_url="https://prices.lbma.org.uk",
            timeout=20.0,
            cache_ttl=3600  # 1-hour cache (daily prices)
        )

    async def fetch_gold_price(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch gold prices from LBMA.

        Args:
            start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
            end_date: End date (YYYY-MM-DD), defaults to today

        Returns:
            Dict with gold price data
        """
        try:
            # Default date range to last 30 days
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            # LBMA API endpoint for gold
            data = await self.client.get(
                "/json/gold_am.json",
                params={}
            )

            if not isinstance(data, list):
                raise ProviderError("Invalid LBMA gold response format")

            # Transform to standard format
            prices = []
            for entry in data:
                date_str = entry.get("d")
                if not date_str:
                    continue

                # Filter by date range
                if date_str < start_date or date_str > end_date:
                    continue

                prices.append({
                    "date": date_str,
                    "price_usd": entry.get("v", [None])[0],  # USD per troy ounce
                    "asof": f"{date_str}T00:00:00Z"
                })

            # Sort by date
            prices.sort(key=lambda x: x["date"])

            return {
                "commodity": "gold",
                "unit": "USD per troy ounce",
                "prices": prices,
                "start_date": start_date,
                "end_date": end_date,
                "source": "lbma",
                "provider": "lbma"
            }

        except Exception as e:
            logger.error(f"LBMA gold fetch failed: {e}")
            raise ProviderError(f"LBMA error: {e}")

    async def fetch_silver_price(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch silver prices from LBMA.

        Args:
            start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
            end_date: End date (YYYY-MM-DD), defaults to today

        Returns:
            Dict with silver price data
        """
        try:
            # Default date range to last 30 days
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            # LBMA API endpoint for silver
            data = await self.client.get(
                "/json/silver.json",
                params={}
            )

            if not isinstance(data, list):
                raise ProviderError("Invalid LBMA silver response format")

            # Transform to standard format
            prices = []
            for entry in data:
                date_str = entry.get("d")
                if not date_str:
                    continue

                # Filter by date range
                if date_str < start_date or date_str > end_date:
                    continue

                prices.append({
                    "date": date_str,
                    "price_usd": entry.get("v", [None])[0],  # USD per troy ounce
                    "asof": f"{date_str}T00:00:00Z"
                })

            # Sort by date
            prices.sort(key=lambda x: x["date"])

            return {
                "commodity": "silver",
                "unit": "USD per troy ounce",
                "prices": prices,
                "start_date": start_date,
                "end_date": end_date,
                "source": "lbma",
                "provider": "lbma"
            }

        except Exception as e:
            logger.error(f"LBMA silver fetch failed: {e}")
            raise ProviderError(f"LBMA error: {e}")


# Module-level singleton fetcher to prevent socket leaks
_lbma_fetcher = LBMAFetcher()


# MCP tool wrappers
async def mcp_commodity_gold(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for gold prices from LBMA.

    Args:
        start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        end_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        Dict containing:
            - prices: List of daily gold prices (USD per troy ounce)
            - date range
            - source metadata

    Note:
        LBMA provides official London Gold Fix prices.
        Prices are typically updated daily.
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _lbma_fetcher.fetch_gold_price(start_date, end_date)

        # Limit to 500 data points max
        if len(result.get("prices", [])) > 500:
            logger.warning(f"Gold price data truncated from {len(result['prices'])} to 500 points")
            result["prices"] = result["prices"][-500:]
            result["truncated"] = True

        return result

    except Exception as e:
        logger.error(f"Error fetching gold prices: {e}")
        return {
            "error": str(e),
            "commodity": "gold",
            "start_date": start_date,
            "end_date": end_date
        }


async def mcp_commodity_silver(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for silver prices from LBMA.

    Args:
        start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        end_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        Dict containing:
            - prices: List of daily silver prices (USD per troy ounce)
            - date range
            - source metadata

    Note:
        LBMA provides official London Silver Fix prices.
        Prices are typically updated daily.
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _lbma_fetcher.fetch_silver_price(start_date, end_date)

        # Limit to 500 data points max
        if len(result.get("prices", [])) > 500:
            logger.warning(f"Silver price data truncated from {len(result['prices'])} to 500 points")
            result["prices"] = result["prices"][-500:]
            result["truncated"] = True

        return result

    except Exception as e:
        logger.error(f"Error fetching silver prices: {e}")
        return {
            "error": str(e),
            "commodity": "silver",
            "start_date": start_date,
            "end_date": end_date
        }


async def mcp_commodity_oil_wti(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for WTI crude oil prices.

    Args:
        start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        end_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        Dict containing WTI crude oil price data

    Note:
        This requires EIA API integration which needs an API key.
        Implementation placeholder - would use EIA's open data API.
        For now, returns a not implemented error.
    """
    return {
        "error": "EIA API integration requires API key (not implemented in free tier)",
        "commodity": "wti_crude",
        "note": "Consider using Alpha Vantage's WTI_CRUDE function as alternative"
    }


async def mcp_commodity_natural_gas(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for natural gas prices.

    Args:
        start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        end_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        Dict containing natural gas price data

    Note:
        This requires EIA API integration which needs an API key.
        Implementation placeholder - would use EIA's open data API.
        For now, returns a not implemented error.
    """
    return {
        "error": "EIA API integration requires API key (not implemented in free tier)",
        "commodity": "natural_gas",
        "note": "Consider using Alpha Vantage's NATURAL_GAS function as alternative"
    }