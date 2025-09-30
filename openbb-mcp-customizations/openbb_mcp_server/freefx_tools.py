"""Free FX (foreign exchange) rate tools.

Provides FX quotes and conversion using free providers:
- Frankfurter (ECB official rates, daily, no API key required)
- Alpha Vantage (intraday fallback for majors)
"""

import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from shared.http_client import BaseHTTPTool, ProviderError
from shared.provider_router import ProviderRouter, register_router

logger = logging.getLogger(__name__)


class FrankfurterFetcher:
    """Fetch FX rates from Frankfurter (ECB official rates)."""

    def __init__(self):
        self.client = BaseHTTPTool(
            provider_name="frankfurter",
            base_url="https://api.frankfurter.app",
            timeout=15.0,
            cache_ttl=3600  # 1-hour cache (daily rates)
        )

    async def fetch_latest(self, base: str = "USD", symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Fetch latest FX rates.

        Args:
            base: Base currency (default USD)
            symbols: Target currencies (if None, returns all)

        Returns:
            Dict with rate data
        """
        try:
            params = {"from": base.upper()}
            if symbols:
                params["to"] = ",".join([s.upper() for s in symbols])

            data = await self.client.get("/latest", params=params)

            # Transform to standard format
            rates = []
            for currency, rate in data.get("rates", {}).items():
                rates.append({
                    "base": base.upper(),
                    "currency": currency,
                    "rate": rate,
                    "date": data.get("date"),
                    "asof": f"{data.get('date')}T00:00:00Z"
                })

            return {
                "rates": rates,
                "base": base.upper(),
                "date": data.get("date"),
                "asof": f"{data.get('date')}T00:00:00Z",
                "source": "frankfurter",
                "provider": "ecb"
            }

        except Exception as e:
            logger.error(f"Frankfurter fetch failed: {e}")
            raise ProviderError(f"Frankfurter error: {e}")

    async def fetch_historical(
        self,
        base: str,
        target: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch historical FX rates.

        Args:
            base: Base currency
            target: Target currency
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to today

        Returns:
            Dict with historical rate data
        """
        try:
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            params = {
                "from": base.upper(),
                "to": target.upper()
            }

            # Frankfurter endpoint: /{start_date}..{end_date}
            data = await self.client.get(f"/{start_date}..{end_date}", params=params)

            # Transform to time series
            series = []
            for date, rates in data.get("rates", {}).items():
                if target.upper() in rates:
                    series.append({
                        "date": date,
                        "rate": rates[target.upper()],
                        "asof": f"{date}T00:00:00Z"
                    })

            # Sort by date
            series.sort(key=lambda x: x["date"])

            return {
                "base": base.upper(),
                "target": target.upper(),
                "series": series,
                "start_date": start_date,
                "end_date": end_date,
                "source": "frankfurter",
                "provider": "ecb"
            }

        except Exception as e:
            logger.error(f"Frankfurter historical fetch failed: {e}")
            raise ProviderError(f"Frankfurter error: {e}")

    async def convert(
        self,
        from_currency: str,
        to_currency: str,
        amount: float = 1.0,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert amount between currencies.

        Args:
            from_currency: Source currency
            to_currency: Target currency
            amount: Amount to convert (default 1.0)
            date: Optional date (YYYY-MM-DD), defaults to latest

        Returns:
            Dict with conversion result
        """
        try:
            params = {
                "from": from_currency.upper(),
                "to": to_currency.upper(),
                "amount": amount
            }

            # Use specific date or latest
            endpoint = f"/{date}" if date else "/latest"
            data = await self.client.get(endpoint, params=params)

            # When amount is supplied, Frankfurter's rates field contains the converted value
            # We need to derive the per-unit rate by dividing by the amount
            converted_value = data.get("rates", {}).get(to_currency.upper())

            if converted_value is not None:
                # Frankfurter returns the converted amount (not per-unit rate)
                converted = converted_value
                # Derive per-unit rate: converted / amount
                rate = converted_value / amount if amount != 0 else None
            else:
                converted = None
                rate = None

            return {
                "from_currency": from_currency.upper(),
                "to_currency": to_currency.upper(),
                "amount": amount,
                "rate": rate,  # Per-unit exchange rate
                "converted": converted,  # Total converted amount
                "date": data.get("date"),
                "asof": f"{data.get('date')}T00:00:00Z",
                "source": "frankfurter",
                "provider": "ecb"
            }

        except Exception as e:
            logger.error(f"Frankfurter conversion failed: {e}")
            raise ProviderError(f"Frankfurter error: {e}")


# Initialize router for FX rates
def _init_fx_router():
    """Initialize the FX rate router."""
    router = ProviderRouter("fx_rate")

    # Frankfurter as primary (no key required, ECB official)
    frankfurter = FrankfurterFetcher()
    router.add_provider(
        "frankfurter",
        frankfurter.fetch_latest,
        primary=True
    )
    logger.info("Frankfurter registered as primary FX provider (ECB official)")

    # TODO: Add Alpha Vantage as fallback for intraday rates
    # Requires different endpoint structure (FX_INTRADAY)

    register_router("fx_rate", router)
    return router


# Initialize on module import
_fx_router = _init_fx_router()

# Module-level singleton fetcher to prevent socket leaks
_frankfurter_fetcher = FrankfurterFetcher()


# MCP tool wrappers
async def mcp_fx_quote(
    base: str = "USD",
    currencies: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for fetching FX quotes.

    Args:
        base: Base currency (default USD)
        currencies: List of target currencies (if None, returns all)

    Returns:
        Dict containing rate data
    """
    try:
        result = await _fx_router.execute(base=base, symbols=currencies)

        # Flatten response
        data = result.get("data", {})

        response = {
            "rates": data.get("rates", []),
            "base": data.get("base"),
            "date": data.get("date"),
            "asof": data.get("asof"),
            "source": result.get("source"),
            "provider": data.get("provider"),
            "provenance": result.get("provenance", {})
        }

        # Add note about ECB end-of-day pricing
        response["provenance"]["note"] = "Rates reflect ECB official daily fixes (end-of-day)"

        return response

    except Exception as e:
        logger.error(f"Error fetching FX quotes: {e}")
        return {
            "error": str(e),
            "base": base,
            "currencies": currencies
        }


async def mcp_fx_convert(
    from_currency: str,
    to_currency: str,
    amount: float = 1.0,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for currency conversion.

    Args:
        from_currency: Source currency code (e.g., 'USD')
        to_currency: Target currency code (e.g., 'EUR')
        amount: Amount to convert (default 1.0)
        date: Optional date (YYYY-MM-DD), uses latest if not specified

    Returns:
        Dict containing conversion result
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _frankfurter_fetcher.convert(from_currency, to_currency, amount, date)

        return result

    except Exception as e:
        logger.error(f"Error converting {from_currency} to {to_currency}: {e}")
        return {
            "error": str(e),
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": amount
        }


async def mcp_fx_historical(
    base: str,
    target: str,
    start_date: str,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for historical FX rates.

    Args:
        base: Base currency code
        target: Target currency code
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        Dict containing historical rate series
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _frankfurter_fetcher.fetch_historical(base, target, start_date, end_date)

        # Limit series to 500 points max (about 1.5 years daily)
        if len(result.get("series", [])) > 500:
            logger.warning(f"FX historical series truncated from {len(result['series'])} to 500 points")
            result["series"] = result["series"][-500:]
            result["truncated"] = True
            result["points_returned"] = 500

        return result

    except Exception as e:
        logger.error(f"Error fetching FX historical: {e}")
        return {
            "error": str(e),
            "base": base,
            "target": target,
            "start_date": start_date
        }