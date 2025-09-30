"""Free global macro data tools.

Provides macroeconomic indicators using free providers:
- World Bank Indicators API (no key required)
- IMF IFS/WEO APIs (no key required)
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from shared.http_client import BaseHTTPTool, ProviderError

logger = logging.getLogger(__name__)


class WorldBankFetcher:
    """Fetch macro indicators from World Bank."""

    def __init__(self):
        self.client = BaseHTTPTool(
            provider_name="worldbank",
            base_url="https://api.worldbank.org/v2",
            timeout=30.0,
            cache_ttl=3600  # 1-hour cache
        )

    async def fetch_indicator(
        self,
        indicator: str,
        countries: List[str],
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch indicator data for countries.

        Args:
            indicator: Indicator ID (e.g., 'NY.GDP.MKTP.CD')
            countries: List of country codes (ISO 2 or 3 letter)
            start_year: Start year (default: current year - 5)
            end_year: End year (default: current year)

        Returns:
            Dict with indicator data
        """
        try:
            # Default date range
            if not start_year:
                start_year = datetime.now().year - 5
            if not end_year:
                end_year = datetime.now().year

            # Format countries (max 20)
            if len(countries) > 20:
                logger.warning(f"Country list truncated from {len(countries)} to 20")
                countries = countries[:20]

            country_str = ";".join([c.upper() for c in countries])

            # World Bank API format: /countries/{countries}/indicators/{indicator}
            params = {
                "format": "json",
                "date": f"{start_year}:{end_year}",
                "per_page": 1000  # Max records
            }

            data = await self.client.get(
                f"/country/{country_str}/indicator/{indicator}",
                params=params
            )

            # World Bank returns [metadata, data]
            if not isinstance(data, list) or len(data) < 2:
                raise ProviderError("Invalid World Bank API response format")

            metadata = data[0]
            records = data[1] if len(data) > 1 else []

            # Transform to standard format
            series = []
            for record in records:
                if record.get("value") is not None:
                    series.append({
                        "country": record.get("country", {}).get("value"),
                        "country_code": record.get("countryiso3code"),
                        "year": record.get("date"),
                        "value": record.get("value"),
                        "indicator": indicator
                    })

            return {
                "indicator": indicator,
                "indicator_name": metadata.get("value") if isinstance(metadata, dict) else None,
                "countries": countries,
                "data": series,
                "start_year": start_year,
                "end_year": end_year,
                "source": "worldbank",
                "provider": "worldbank",
                "total_records": len(series)
            }

        except Exception as e:
            logger.error(f"World Bank fetch failed for {indicator}: {e}")
            raise ProviderError(f"World Bank error: {e}")


class IMFFetcher:
    """Fetch macro data from IMF (IFS/WEO)."""

    def __init__(self):
        self.client = BaseHTTPTool(
            provider_name="imf",
            base_url="https://www.imf.org/external/datamapper/api/v1",
            timeout=30.0,
            cache_ttl=3600
        )

    async def fetch_series(
        self,
        indicator: str,
        countries: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch IMF indicator data.

        Args:
            indicator: Indicator code (e.g., 'NGDP_RPCH' for real GDP growth)
            countries: Optional list of ISO country codes

        Returns:
            Dict with indicator data
        """
        try:
            # IMF DataMapper API format: /{indicator}
            data = await self.client.get(f"/{indicator}")

            if not isinstance(data, dict):
                raise ProviderError("Invalid IMF API response")

            # Extract values for requested countries
            values_data = data.get("values", {}).get(indicator, {})

            series = []
            for country_code, country_data in values_data.items():
                # Filter by requested countries if specified
                if countries and country_code not in [c.upper() for c in countries]:
                    continue

                for year, value in country_data.items():
                    if value is not None:
                        try:
                            series.append({
                                "country_code": country_code,
                                "year": int(year),
                                "value": float(value),
                                "indicator": indicator
                            })
                        except (ValueError, TypeError):
                            continue

            # Sort by country and year
            series.sort(key=lambda x: (x["country_code"], x["year"]))

            return {
                "indicator": indicator,
                "countries_requested": countries,
                "data": series,
                "source": "imf",
                "provider": "imf",
                "total_records": len(series)
            }

        except Exception as e:
            logger.error(f"IMF fetch failed for {indicator}: {e}")
            raise ProviderError(f"IMF error: {e}")


# Module-level singleton fetchers to prevent socket leaks
_worldbank_fetcher = WorldBankFetcher()
_imf_fetcher = IMFFetcher()


# MCP tool wrappers
async def mcp_economy_wb_indicator(
    indicator: str,
    countries: List[str],
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for World Bank indicators.

    Args:
        indicator: World Bank indicator ID
        countries: List of country codes (ISO 2 or 3 letter)
        start_year: Start year (optional, defaults to current - 5)
        end_year: End year (optional, defaults to current)

    Returns:
        Dict containing indicator data

    Example indicators:
        - NY.GDP.MKTP.CD: GDP (current US$)
        - FP.CPI.TOTL.ZG: Inflation, consumer prices (annual %)
        - SL.UEM.TOTL.ZS: Unemployment, total (% of labor force)
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _worldbank_fetcher.fetch_indicator(indicator, countries, start_year, end_year)

        # Apply ResponseLimiter logic (max 500 records)
        if len(result.get("data", [])) > 500:
            logger.warning(f"World Bank data truncated from {len(result['data'])} to 500 records")
            result["data"] = result["data"][:500]
            result["truncated"] = True

        return result

    except Exception as e:
        logger.error(f"Error fetching World Bank indicator {indicator}: {e}")
        return {
            "error": str(e),
            "indicator": indicator,
            "countries": countries
        }


async def mcp_economy_imf_series(
    indicator: str,
    countries: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for IMF indicators.

    Args:
        indicator: IMF indicator code
        countries: Optional list of country codes (ISO 3 letter)

    Returns:
        Dict containing indicator data

    Example indicators:
        - NGDP_RPCH: Real GDP growth (%)
        - PCPIPCH: Inflation rate (%)
        - LUR: Unemployment rate (%)
    """
    try:
        # Use module-level singleton to avoid socket leaks
        result = await _imf_fetcher.fetch_series(indicator, countries)

        # Apply ResponseLimiter logic (max 500 records)
        if len(result.get("data", [])) > 500:
            logger.warning(f"IMF data truncated from {len(result['data'])} to 500 records")
            result["data"] = result["data"][:500]
            result["truncated"] = True

        return result

    except Exception as e:
        logger.error(f"Error fetching IMF indicator {indicator}: {e}")
        return {
            "error": str(e),
            "indicator": indicator,
            "countries": countries
        }