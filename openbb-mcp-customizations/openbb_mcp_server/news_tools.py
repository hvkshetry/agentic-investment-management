"""Free news and sentiment tools.

Provides news search using free providers:
- GDELT (global event database, no key required)
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from shared.http_client import BaseHTTPTool, ProviderError

logger = logging.getLogger(__name__)


class GDELTFetcher:
    """Fetch news from GDELT."""

    def __init__(self):
        self.client = BaseHTTPTool(
            provider_name="gdelt",
            base_url="https://api.gdeltproject.org/api/v2",
            timeout=30.0,
            cache_ttl=300  # 5-minute cache
        )

    async def search_news(
        self,
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        source_country: Optional[str] = None,
        theme: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search GDELT news articles.

        Args:
            query: Search query
            start_date: Start date (YYYY-MM-DD), defaults to 7 days ago
            end_date: End date (YYYY-MM-DD), defaults to today
            limit: Max articles (default 20, max 250)
            source_country: Optional country code filter
            theme: Optional GDELT theme filter

        Returns:
            Dict with articles and metadata
        """
        try:
            # Default date range to last 7 days
            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            # Ensure limit is within bounds
            limit = min(max(1, limit), 250)

            # Build GDELT query
            # Format: query AND sourcecountry:XX AND theme:YY
            gdelt_query = query
            if source_country:
                gdelt_query += f" AND sourcecountry:{source_country.upper()}"
            if theme:
                gdelt_query += f" AND theme:{theme}"

            # GDELT API uses different date format (YYYYMMDDHHMMSS)
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            params = {
                "query": gdelt_query,
                "mode": "artlist",
                "maxrecords": limit,
                "startdatetime": start_dt.strftime("%Y%m%d%H%M%S"),
                "enddatetime": end_dt.strftime("%Y%m%d235959"),
                "format": "json"
            }

            data = await self.client.get("/doc/doc", params=params)

            # GDELT returns {articles: [...]}
            if not isinstance(data, dict):
                raise ProviderError("Invalid GDELT response format")

            articles_raw = data.get("articles", [])

            # Transform to standard format
            articles = []
            for article in articles_raw[:limit]:  # Enforce limit
                # Parse tone (GDELT provides tone score)
                tone = article.get("tone")
                try:
                    tone_value = float(tone) if tone else None
                except (ValueError, TypeError):
                    tone_value = None

                # Normalize GDELT timestamp from YYYYMMDDHHMMSS to ISO 8601
                seendate_raw = article.get("seendate")
                datetime_iso = None
                if seendate_raw:
                    try:
                        # Parse YYYYMMDDHHMMSS format
                        dt = datetime.strptime(str(seendate_raw), "%Y%m%d%H%M%S")
                        datetime_iso = dt.isoformat() + "Z"
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse GDELT timestamp '{seendate_raw}': {e}")
                        datetime_iso = None

                articles.append({
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "source": article.get("domain"),
                    "datetime": datetime_iso,  # ISO 8601 format
                    "tone": tone_value,  # Negative = negative sentiment
                    "language": article.get("language"),
                    "country": article.get("sourcecountry")
                })

            return {
                "articles": articles,
                "query": query,
                "start_date": start_date,
                "end_date": end_date,
                "total_articles": len(articles),
                "source": "gdelt",
                "provider": "gdelt"
            }

        except Exception as e:
            logger.error(f"GDELT search failed for query '{query}': {e}")
            raise ProviderError(f"GDELT error: {e}")


# Module-level singleton fetcher to prevent socket leaks
_gdelt_fetcher = GDELTFetcher()


# MCP tool wrapper
async def mcp_news_search(
    query: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
    source_country: Optional[str] = None,
    theme: Optional[str] = None
) -> Dict[str, Any]:
    """
    MCP wrapper for news search.

    Args:
        query: Search query (keywords, company names, etc.)
        start_date: Start date (YYYY-MM-DD), defaults to 7 days ago
        end_date: End date (YYYY-MM-DD), defaults to today
        limit: Max articles to return (default 20, max 30)
        source_country: Optional country code filter (ISO 2-letter)
        theme: Optional GDELT theme (e.g., 'ECON_STOCKMARKET', 'GOV_CENTRAL_BANK')

    Returns:
        Dict containing articles with sentiment (tone) scores

    Example themes:
        - ECON_STOCKMARKET: Stock market news
        - ECON_INFLATIONPRICES: Inflation news
        - GOV_CENTRAL_BANK: Central bank policy
        - ENV_CLIMATECHANGE: Climate news
    """
    try:
        # Enforce 30-item cap (as per ResponseLimiter)
        limit = min(limit, 30)

        # Use module-level singleton to avoid socket leaks
        result = await _gdelt_fetcher.search_news(
            query=query,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            source_country=source_country,
            theme=theme
        )

        # Calculate average tone/sentiment
        articles = result.get("articles", [])
        tones = [a["tone"] for a in articles if a.get("tone") is not None]
        if tones:
            result["average_tone"] = sum(tones) / len(tones)
            result["sentiment"] = "positive" if result["average_tone"] > 0 else "negative" if result["average_tone"] < 0 else "neutral"
        else:
            result["average_tone"] = None
            result["sentiment"] = "unknown"

        return result

    except Exception as e:
        logger.error(f"Error searching news for '{query}': {e}")
        return {
            "error": str(e),
            "query": query
        }


async def mcp_news_search_company(
    company: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    MCP wrapper for company-specific news search.

    Args:
        company: Company name or ticker
        start_date: Start date (YYYY-MM-DD), defaults to 7 days ago
        end_date: End date (YYYY-MM-DD), defaults to today
        limit: Max articles (default 20)

    Returns:
        Dict containing company news with sentiment
    """
    try:
        # Add stock market theme to focus on financial news
        result = await mcp_news_search(
            query=company,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            theme="ECON_STOCKMARKET"
        )

        # Add company context
        result["company"] = company

        return result

    except Exception as e:
        logger.error(f"Error searching company news for '{company}': {e}")
        return {
            "error": str(e),
            "company": company
        }