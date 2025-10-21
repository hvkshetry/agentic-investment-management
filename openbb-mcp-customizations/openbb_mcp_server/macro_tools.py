"""Free global macro data tools.

Provides macroeconomic indicators using free providers:
- World Bank Indicators API (no key required)
- IMF IFS/WEO APIs (no key required)
"""

import json
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from importlib import resources

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
        self._country_map = self._load_iso_maps()

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

            allowed_countries: Optional[Set[str]] = None
            if countries:
                allowed_countries = self._normalize_country_codes(countries)

            series = []
            for country_code, country_data in values_data.items():
                # Filter by requested countries if specified
                if allowed_countries is not None and country_code.upper() not in allowed_countries:
                    continue

                for year, value in country_data.items():
                    if value is not None:
                        try:
                            entry = {
                                "country_code": country_code,
                                "year": int(year),
                                "value": float(value),
                                "indicator": indicator
                            }

                            country_info = self._country_map.get("iso3_to_info", {}).get(country_code.upper())
                            if country_info:
                                entry.setdefault("country", country_info["name"])
                                entry.setdefault("iso2", country_info.get("iso2"))

                            series.append(entry)
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

    def _load_iso_maps(self) -> Dict[str, Dict[str, Any]]:
        """Load helper maps for ISO code normalization."""
        iso2_to_name: Dict[str, str] = {}
        iso3_to_info: Dict[str, Dict[str, Any]] = {}
        iso2_to_iso3: Dict[str, str] = {}

        try:
            with resources.files("openbb_imf.assets").joinpath("imf_country_map.json").open(
                "r", encoding="utf-8"
            ) as handle:
                iso2_to_name = json.load(handle)
        except Exception as exc:
            logger.warning(f"Failed to load IMF ISO2 country map: {exc}")

        try:
            from openbb_imf.utils.constants import PORT_COUNTRIES  # type: ignore

            # Build reverse map name -> ISO3
            name_to_iso3 = {name.upper(): code.upper() for name, code in PORT_COUNTRIES.items()}

            for iso2, name in iso2_to_name.items():
                iso3 = name_to_iso3.get(name.upper())
                if iso3:
                    iso3_to_info[iso3] = {
                        "iso2": iso2.upper(),
                        "name": name
                    }
                    iso2_to_iso3[iso2.upper()] = iso3

            # Ensure ISO3 info is available for direct entries as well
            for name, iso3 in PORT_COUNTRIES.items():
                iso3 = iso3.upper()
                iso3_to_info.setdefault(iso3, {
                    "iso2": None,
                    "name": name
                })

        except Exception as exc:  # pragma: no cover - best effort enrichment
            logger.warning(f"Failed to build ISO3 enrichment map: {exc}")

        return {
            "iso2_to_name": {k.upper(): v for k, v in iso2_to_name.items()},
            "iso3_to_info": iso3_to_info,
            "iso2_to_iso3": iso2_to_iso3
        }

    def _normalize_country_codes(self, countries: List[str]) -> Set[str]:
        """Normalize requested codes to ISO3 as used by IMF datasets."""
        normalized: Set[str] = set()
        iso2_map = self._country_map.get("iso2_to_name", {})
        iso3_info = self._country_map.get("iso3_to_info", {})
        iso2_to_iso3 = self._country_map.get("iso2_to_iso3", {})

        for country in countries:
            if not country:
                continue

            code = country.upper()

            # Already ISO3
            if len(code) == 3 and code in iso3_info:
                normalized.add(code)
                continue

            # ISO2 -> ISO3 using lookup
            iso3 = iso2_to_iso3.get(code)
            if iso3:
                normalized.add(iso3)
                continue

            name = iso2_map.get(code)
            if name:
                info = next(
                    (iso for iso, data in iso3_info.items() if data.get("name", "").upper() == name.upper()),
                    None
                )
                if info:
                    normalized.add(info)
                    continue

            # Try using country name direct match
            info = next(
                (iso for iso, data in iso3_info.items() if data.get("name", "").upper() == code),
                None
            )
            if info:
                normalized.add(info)
                continue

            # Accept raw code (aggregates or already ISO3 but unknown to map)
            normalized.add(code)

        return normalized


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
