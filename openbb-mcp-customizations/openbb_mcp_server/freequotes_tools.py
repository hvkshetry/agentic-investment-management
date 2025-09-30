"""Free real-time equity quotes tool wrappers.

Provides real-time and near-real-time equity quotes using free providers:
- Yahoo Finance (unofficial, primary)
- Alpha Vantage (fallback, 5/min rate limit)

Implements circuit breaker and failover logic for robustness.
"""

import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import asyncio

from shared.http_client import BaseHTTPTool, ProviderError, RateLimitError
from shared.provider_router import ProviderRouter, register_router, _throttler

logger = logging.getLogger(__name__)

# Feature flag for Yahoo unofficial API
ENABLE_YAHOO_UNOFFICIAL = os.getenv("ENABLE_YAHOO_UNOFFICIAL", "true").lower() == "true"


class YahooQuoteFetcher:
    """Fetch quotes from Yahoo Finance (unofficial API)."""

    def __init__(self):
        self.client = BaseHTTPTool(
            provider_name="yahoo",
            base_url="https://query2.finance.yahoo.com",
            timeout=15.0,
            cache_ttl=15  # 15-second cache for stale tolerance
        )

    async def fetch_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch quotes for multiple symbols.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dict with quote data and metadata
        """
        if not symbols:
            raise ValueError("symbols list cannot be empty")

        # Yahoo API uses comma-separated symbols
        symbol_str = ",".join(symbols)

        try:
            # Use v7 quote endpoint
            data = await self.client.get(
                "/v7/finance/quote",
                params={
                    "symbols": symbol_str,
                    "fields": "symbol,regularMarketPrice,regularMarketChange,regularMarketChangePercent,"
                              "regularMarketTime,currency,bid,ask,regularMarketPreviousClose,"
                              "regularMarketOpen,regularMarketDayHigh,regularMarketDayLow,regularMarketVolume",
                    "crumb": ""  # Sometimes required but often works without
                }
            )

            # Parse response
            if "quoteResponse" not in data or "result" not in data["quoteResponse"]:
                raise ProviderError("Invalid response format from Yahoo Finance")

            quotes = data["quoteResponse"]["result"]

            # Transform to standard format
            results = []
            for quote in quotes:
                # Convert Unix timestamp to ISO format
                timestamp = quote.get("regularMarketTime")
                if timestamp:
                    asof = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                else:
                    asof = datetime.now(timezone.utc).isoformat()

                results.append({
                    "symbol": quote.get("symbol"),
                    "last": quote.get("regularMarketPrice"),
                    "change": quote.get("regularMarketChange"),
                    "change_percent": quote.get("regularMarketChangePercent"),
                    "bid": quote.get("bid"),
                    "ask": quote.get("ask"),
                    "previous_close": quote.get("regularMarketPreviousClose"),
                    "open": quote.get("regularMarketOpen"),
                    "day_high": quote.get("regularMarketDayHigh"),
                    "day_low": quote.get("regularMarketDayLow"),
                    "volume": quote.get("regularMarketVolume"),
                    "currency": quote.get("currency", "USD"),
                    "asof": asof
                })

            # Find the newest quote timestamp for staleness checking
            newest_asof = None
            if results:
                for quote in results:
                    if quote.get("asof"):
                        if newest_asof is None or quote["asof"] > newest_asof:
                            newest_asof = quote["asof"]

            return {
                "quotes": results,
                "source": "yahoo_unofficial",
                "provider": "yahoo",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "asof": newest_asof  # Top-level timestamp for staleness check
            }

        except Exception as e:
            logger.error(f"Yahoo quote fetch failed: {e}")
            raise


class AlphaVantageQuoteFetcher:
    """Fetch quotes from Alpha Vantage (official, rate-limited)."""

    def __init__(self):
        self.api_key = os.getenv("ALPHAVANTAGE_API_KEY")
        if not self.api_key:
            logger.warning("ALPHAVANTAGE_API_KEY not set - Alpha Vantage quotes unavailable")

        self.client = BaseHTTPTool(
            provider_name="alpha_vantage",
            base_url="https://www.alphavantage.co",
            timeout=20.0,
            cache_ttl=60  # 1-minute cache
        )

    async def fetch_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch quotes for multiple symbols (sequential to respect rate limits).

        Args:
            symbols: List of ticker symbols

        Returns:
            Dict with quote data and metadata
        """
        if not self.api_key:
            raise ProviderError("Alpha Vantage API key not configured")

        if not symbols:
            raise ValueError("symbols list cannot be empty")

        # Alpha Vantage doesn't support batch AND has strict rate limits (5/min)
        # Only process first 5 symbols and flag the rest as skipped
        MAX_SYMBOLS = 5

        symbols_to_fetch = symbols[:MAX_SYMBOLS]
        skipped_symbols = symbols[MAX_SYMBOLS:] if len(symbols) > MAX_SYMBOLS else []

        quotes = []
        errors = []

        # Fetch sequentially to avoid blowing through quota
        # IMPORTANT: Manually check throttler for each sub-call to track actual API usage
        for symbol in symbols_to_fetch:
            try:
                # Check throttle before each individual request
                retry_after = await _throttler.acquire("alpha_vantage")
                if retry_after is not None:
                    logger.warning(f"Alpha Vantage throttled on symbol {symbol} (retry after {retry_after}s)")
                    errors.append({
                        "symbol": symbol,
                        "error": f"Rate limited (retry after {retry_after}s)",
                        "rate_limited": True
                    })
                    continue

                quote = await self._fetch_single_quote(symbol)
                quotes.append(quote)
            except Exception as e:
                logger.warning(f"Alpha Vantage quote failed for {symbol}: {e}")
                errors.append({"symbol": symbol, "error": str(e)})

        # Add skipped symbols to errors with clear message
        if skipped_symbols:
            logger.warning(f"Alpha Vantage: {len(skipped_symbols)} symbols skipped (limit: {MAX_SYMBOLS})")
            for symbol in skipped_symbols:
                errors.append({
                    "symbol": symbol,
                    "error": f"Symbol limit exceeded (max {MAX_SYMBOLS} per call)",
                    "skipped": True
                })

        if not quotes:
            raise ProviderError(f"All Alpha Vantage quote requests failed: {errors}")

        # Find the newest quote timestamp for staleness checking
        newest_asof = None
        if quotes:
            for quote in quotes:
                if quote.get("asof"):
                    if newest_asof is None or quote["asof"] > newest_asof:
                        newest_asof = quote["asof"]

        result = {
            "quotes": quotes,
            "source": "alpha_vantage",
            "provider": "alpha_vantage",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "asof": newest_asof,  # Top-level timestamp for staleness check
            "symbols_requested": len(symbols),
            "symbols_fetched": len(quotes),
            "symbols_skipped": len(skipped_symbols)
        }

        if errors:
            result["partial_errors"] = errors

        return result

    async def _fetch_single_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch a single quote from Alpha Vantage."""
        try:
            data = await self.client.get(
                "/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "apikey": self.api_key
                }
            )

            # Check for API errors
            if "Error Message" in data:
                raise ProviderError(f"Alpha Vantage error: {data['Error Message']}")
            if "Note" in data:
                # Rate limit message
                raise RateLimitError("Alpha Vantage rate limit reached")

            # Parse response
            if "Global Quote" not in data:
                raise ProviderError("Invalid response format from Alpha Vantage")

            quote = data["Global Quote"]

            # Transform to standard format
            return {
                "symbol": quote.get("01. symbol", symbol),
                "last": float(quote.get("05. price", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": float(quote.get("10. change percent", "0").replace("%", "")),
                "previous_close": float(quote.get("08. previous close", 0)),
                "open": float(quote.get("02. open", 0)),
                "day_high": float(quote.get("03. high", 0)),
                "day_low": float(quote.get("04. low", 0)),
                "volume": int(quote.get("06. volume", 0)),
                "currency": "USD",  # Alpha Vantage doesn't provide currency
                "asof": quote.get("07. latest trading day", datetime.now(timezone.utc).isoformat()[:10]) + "T00:00:00Z"
            }

        except (RateLimitError, ProviderError):
            raise
        except Exception as e:
            logger.error(f"Alpha Vantage quote fetch for {symbol} failed: {e}")
            raise ProviderError(f"Failed to fetch {symbol}: {e}")


# Initialize router for equity quotes
def _init_quote_router():
    """Initialize the equity quote router with failover."""
    router = ProviderRouter("equity_quote")

    # Add Yahoo as primary if enabled
    if ENABLE_YAHOO_UNOFFICIAL:
        yahoo_fetcher = YahooQuoteFetcher()
        router.add_provider(
            "yahoo",
            yahoo_fetcher.fetch_quotes,
            primary=True,
            max_stale_seconds=15
        )
        logger.info("Yahoo Finance registered as primary quote provider (unofficial)")
    else:
        logger.warning("Yahoo Finance disabled by feature flag")

    # Add Alpha Vantage as fallback if key available
    av_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if av_key:
        av_fetcher = AlphaVantageQuoteFetcher()
        router.add_provider(
            "alpha_vantage",
            av_fetcher.fetch_quotes,
            primary=not ENABLE_YAHOO_UNOFFICIAL,  # Primary only if Yahoo disabled
            skip_throttle=True  # Fetcher handles throttling internally to avoid double-counting
        )
        logger.info("Alpha Vantage registered as quote provider (fallback, internal throttling)")
    else:
        logger.warning("ALPHAVANTAGE_API_KEY not set - Alpha Vantage unavailable")

    register_router("equity_quote", router)
    return router


# Initialize on module import
_quote_router = _init_quote_router()


# MCP tool wrapper
async def mcp_marketdata_quote(
    symbols: List[str],
    max_stale_seconds: Optional[int] = 15
) -> Dict[str, Any]:
    """
    MCP wrapper for fetching real-time equity quotes.

    Args:
        symbols: List of ticker symbols (max 50)
        max_stale_seconds: Maximum acceptable data age in seconds

    Returns:
        Dict containing:
            - quotes: List of quote data
            - source: Provider that succeeded
            - provenance: Metadata about the data source
    """
    try:
        # Validate input
        if not symbols:
            return {"error": "symbols list cannot be empty"}

        if len(symbols) > 50:
            logger.warning(f"Symbol list truncated from {len(symbols)} to 50")
            symbols = symbols[:50]

        # Execute through router
        result = await _quote_router.execute(symbols=symbols)

        # Flatten the router response structure
        # Router returns: {data: {...}, source: "...", provenance: {...}}
        # We need to merge data and provenance at top level
        data = result.get("data", {})
        quotes = data.get("quotes", [])

        response = {
            "quotes": quotes,
            "source": result.get("source"),
            "provider": data.get("provider"),
            "fetched_at": data.get("fetched_at"),
            "provenance": result.get("provenance", {})
        }

        # Forward important metadata from the data layer
        if "asof" in data:
            response["asof"] = data["asof"]
        if "partial_errors" in data:
            response["partial_errors"] = data["partial_errors"]
        if "symbols_requested" in data:
            response["symbols_requested"] = data["symbols_requested"]
            response["symbols_fetched"] = data.get("symbols_fetched", len(quotes))
            response["symbols_skipped"] = data.get("symbols_skipped", 0)

        # Add disclaimer for unofficial sources
        if result.get("source") == "yahoo":
            response["provenance"]["disclaimer"] = (
                "Data sourced from unofficial Yahoo Finance API. "
                "For production use, consider official data providers."
            )

        return response

    except Exception as e:
        logger.error(f"Error fetching quotes for {symbols}: {e}")
        return {
            "error": str(e),
            "symbols": symbols,
            "details": "All quote providers failed or are unavailable"
        }


async def mcp_marketdata_quote_batch(
    symbols: List[str],
    batch_size: int = 20
) -> Dict[str, Any]:
    """
    MCP wrapper for fetching quotes in batches.

    Args:
        symbols: List of ticker symbols
        batch_size: Number of symbols per batch

    Returns:
        Dict containing combined results from all batches
    """
    try:
        if not symbols:
            return {"error": "symbols list cannot be empty"}

        # Split into batches
        batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]

        # Process batches
        all_quotes = []
        all_errors = []

        for i, batch in enumerate(batches):
            logger.info(f"Processing batch {i + 1}/{len(batches)} ({len(batch)} symbols)")

            result = await mcp_marketdata_quote(batch)

            if "error" in result:
                all_errors.append({
                    "batch": i + 1,
                    "symbols": batch,
                    "error": result["error"]
                })
            else:
                all_quotes.extend(result.get("quotes", []))

        return {
            "quotes": all_quotes,
            "total_symbols": len(symbols),
            "successful": len(all_quotes),
            "failed": len(symbols) - len(all_quotes),
            "errors": all_errors if all_errors else None,
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Error in batch quote fetch: {e}")
        return {
            "error": str(e),
            "total_symbols": len(symbols)
        }