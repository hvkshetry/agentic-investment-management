"""Free analyst estimates and recommendations tools.

Provides analyst data using free providers:
- Finnhub (consensus estimates, price targets)
- FMP (analyst recommendations history)
"""

import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from shared.http_client import BaseHTTPTool, ProviderError
from shared.provider_router import ProviderRouter, register_router

logger = logging.getLogger(__name__)


class FinnhubAnalystFetcher:
    """Fetch analyst data from Finnhub."""

    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            logger.warning("FINNHUB_API_KEY not set - Finnhub analyst data unavailable")

        self.client = BaseHTTPTool(
            provider_name="finnhub",
            base_url="https://finnhub.io/api/v1",
            timeout=20.0,
            cache_ttl=3600  # 1-hour cache
        )

    async def fetch_price_target(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch analyst price target consensus.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with price target data
        """
        if not self.api_key:
            raise ProviderError("Finnhub API key not configured")

        try:
            data = await self.client.get(
                "/stock/price-target",
                params={"symbol": symbol, "token": self.api_key}
            )

            # Transform to standard format
            return {
                "symbol": symbol,
                "target_high": data.get("targetHigh"),
                "target_low": data.get("targetLow"),
                "target_mean": data.get("targetMean"),
                "target_median": data.get("targetMedian"),
                "last_updated": data.get("lastUpdated"),
                "source": "finnhub",
                "provider": "finnhub"
            }

        except Exception as e:
            logger.error(f"Finnhub price target fetch failed for {symbol}: {e}")
            raise ProviderError(f"Finnhub error: {e}")

    async def fetch_recommendations(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch analyst recommendation trends.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with recommendation data
        """
        if not self.api_key:
            raise ProviderError("Finnhub API key not configured")

        try:
            data = await self.client.get(
                "/stock/recommendation",
                params={"symbol": symbol, "token": self.api_key}
            )

            if not isinstance(data, list):
                raise ProviderError("Invalid Finnhub recommendations response")

            # Transform to standard format
            recommendations = []
            for rec in data[:12]:  # Last 12 months
                recommendations.append({
                    "period": rec.get("period"),
                    "strong_buy": rec.get("strongBuy", 0),
                    "buy": rec.get("buy", 0),
                    "hold": rec.get("hold", 0),
                    "sell": rec.get("sell", 0),
                    "strong_sell": rec.get("strongSell", 0)
                })

            return {
                "symbol": symbol,
                "recommendations": recommendations,
                "source": "finnhub",
                "provider": "finnhub"
            }

        except Exception as e:
            logger.error(f"Finnhub recommendations fetch failed for {symbol}: {e}")
            raise ProviderError(f"Finnhub error: {e}")


class FMPAnalystFetcher:
    """Fetch analyst data from FMP."""

    def __init__(self):
        self.api_key = os.getenv("FMP_API_KEY")
        if not self.api_key:
            logger.warning("FMP_API_KEY not set - FMP analyst data unavailable")

        self.client = BaseHTTPTool(
            provider_name="fmp",
            base_url="https://financialmodelingprep.com/api/v3",
            timeout=20.0,
            cache_ttl=3600
        )

    async def fetch_estimates(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch analyst earnings estimates.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with earnings estimates
        """
        if not self.api_key:
            raise ProviderError("FMP API key not configured")

        try:
            data = await self.client.get(
                f"/analyst-estimates/{symbol}",
                params={"apikey": self.api_key}
            )

            if not isinstance(data, list):
                raise ProviderError("Invalid FMP estimates response")

            # Transform to standard format
            estimates = []
            for est in data[:8]:  # Next 8 quarters
                estimates.append({
                    "date": est.get("date"),
                    "estimated_revenue": est.get("estimatedRevenueLow"),
                    "estimated_revenue_high": est.get("estimatedRevenueHigh"),
                    "estimated_revenue_avg": est.get("estimatedRevenueAvg"),
                    "estimated_eps": est.get("estimatedEpsAvg"),
                    "estimated_ebitda": est.get("estimatedEbitdaAvg"),
                    "number_analysts": est.get("numberAnalystEstimatedRevenue")
                })

            return {
                "symbol": symbol,
                "estimates": estimates,
                "source": "fmp",
                "provider": "fmp"
            }

        except Exception as e:
            logger.error(f"FMP estimates fetch failed for {symbol}: {e}")
            raise ProviderError(f"FMP error: {e}")


# Module-level singleton fetchers to prevent socket leaks
_finnhub_analyst_fetcher = FinnhubAnalystFetcher()
_fmp_analyst_fetcher = FMPAnalystFetcher()


# Initialize router for price targets
def _init_price_target_router():
    """Initialize the price target router."""
    router = ProviderRouter("price_target")

    # Finnhub as primary if available
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    if finnhub_key:
        router.add_provider(
            "finnhub",
            _finnhub_analyst_fetcher.fetch_price_target,
            primary=True
        )
        logger.info("Finnhub registered as primary price target provider")

    register_router("price_target", router)
    return router


# Initialize on module import
_price_target_router = _init_price_target_router()


# MCP tool wrappers
async def mcp_analyst_price_target(symbol: str) -> Dict[str, Any]:
    """
    MCP wrapper for analyst price targets.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'TSLA')

    Returns:
        Dict containing:
            - target_high: Highest price target
            - target_low: Lowest price target
            - target_mean: Average price target
            - target_median: Median price target
            - last_updated: Last update date
    """
    try:
        result = await _price_target_router.execute(symbol=symbol)

        # Flatten response
        data = result.get("data", {})

        response = {
            "symbol": symbol,
            "target_high": data.get("target_high"),
            "target_low": data.get("target_low"),
            "target_mean": data.get("target_mean"),
            "target_median": data.get("target_median"),
            "last_updated": data.get("last_updated"),
            "source": result.get("source"),
            "provider": data.get("provider"),
            "provenance": result.get("provenance", {})
        }

        return response

    except Exception as e:
        logger.error(f"Error fetching price target for {symbol}: {e}")
        return {
            "error": str(e),
            "symbol": symbol
        }


async def mcp_analyst_recommendations(symbol: str) -> Dict[str, Any]:
    """
    MCP wrapper for analyst recommendations.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dict containing recommendation trends (buy/hold/sell counts by period)
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _finnhub_analyst_fetcher.fetch_recommendations(symbol)

        # Limit to 12 periods max
        if len(result.get("recommendations", [])) > 12:
            result["recommendations"] = result["recommendations"][:12]
            result["truncated"] = True

        return result

    except Exception as e:
        logger.error(f"Error fetching recommendations for {symbol}: {e}")
        return {
            "error": str(e),
            "symbol": symbol
        }


async def mcp_analyst_estimates(symbol: str) -> Dict[str, Any]:
    """
    MCP wrapper for analyst earnings estimates.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dict containing earnings estimates for upcoming quarters
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _fmp_analyst_fetcher.fetch_estimates(symbol)

        # Limit to 8 quarters max
        if len(result.get("estimates", [])) > 8:
            result["estimates"] = result["estimates"][:8]
            result["truncated"] = True

        return result

    except Exception as e:
        logger.error(f"Error fetching estimates for {symbol}: {e}")
        return {
            "error": str(e),
            "symbol": symbol
        }