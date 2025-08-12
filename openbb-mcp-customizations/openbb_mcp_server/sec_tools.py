"""SEC/EDGAR tool wrappers for OpenBB MCP server.

This module provides direct SEC API wrappers for tools not available in standard OpenBB API.
These tools provide authoritative, free access to SEC filings and regulatory data.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

# SEC API base URLs
SEC_API_BASE = "https://data.sec.gov"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives"

# User agent required by SEC
USER_AGENT = "OpenBB-MCP-Server/1.0 (contact@example.com)"


async def edgar_fetch_submissions(cik: str) -> Dict[str, Any]:
    """Fetch SEC submissions for a company by CIK.
    
    Args:
        cik: Central Index Key (10-digit with leading zeros)
        
    Returns:
        Dict containing company submissions data
    """
    # Ensure CIK is 10 digits with leading zeros
    cik = str(cik).zfill(10)
    
    url = f"{SEC_API_BASE}/submissions/CIK{cik}.json"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def edgar_fetch_companyfacts(cik: str) -> Dict[str, Any]:
    """Fetch XBRL company facts from SEC.
    
    Args:
        cik: Central Index Key (10-digit with leading zeros)
        
    Returns:
        Dict containing XBRL facts for the company
    """
    # Ensure CIK is 10 digits with leading zeros
    cik = str(cik).zfill(10)
    
    url = f"{SEC_API_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def sec_rss_parser(feed_type: str = "litigation") -> List[Dict[str, Any]]:
    """Parse SEC RSS feeds for various content types.
    
    Args:
        feed_type: Type of RSS feed ('litigation', 'news', 'speeches')
        
    Returns:
        List of parsed RSS items
    """
    import xml.etree.ElementTree as ET
    
    feed_urls = {
        "litigation": "https://www.sec.gov/rss/litigation/litreleases.xml",
        "news": "https://www.sec.gov/news/pressreleases.rss",
        "speeches": "https://www.sec.gov/news/speeches-statements.rss",
    }
    
    if feed_type not in feed_urls:
        raise ValueError(f"Invalid feed_type. Must be one of: {list(feed_urls.keys())}")
    
    url = feed_urls[feed_type]
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0
        )
        response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(response.text)
        
        items = []
        for item in root.findall(".//item"):
            parsed_item = {
                "title": item.findtext("title", ""),
                "link": item.findtext("link", ""),
                "description": item.findtext("description", ""),
                "pub_date": item.findtext("pubDate", ""),
                "guid": item.findtext("guid", ""),
            }
            items.append(parsed_item)
        
        return items


async def get_cik_from_ticker(ticker: str) -> Optional[str]:
    """Get CIK from ticker symbol using SEC ticker mapping.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        CIK as string, or None if not found
    """
    url = f"{SEC_API_BASE}/files/company_tickers.json"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0
        )
        response.raise_for_status()
        
        tickers_data = response.json()
        
        # Search for ticker in the data
        ticker_upper = ticker.upper()
        for company in tickers_data.values():
            if company.get("ticker") == ticker_upper:
                return str(company.get("cik_str", "")).zfill(10)
        
        return None


async def get_ticker_from_cik(cik: str) -> Optional[str]:
    """Get ticker symbol from CIK.
    
    Args:
        cik: Central Index Key
        
    Returns:
        Ticker symbol, or None if not found
    """
    url = f"{SEC_API_BASE}/files/company_tickers.json"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0
        )
        response.raise_for_status()
        
        tickers_data = response.json()
        
        # Search for CIK in the data
        cik_int = int(str(cik).lstrip("0"))
        for company in tickers_data.values():
            if company.get("cik_str") == cik_int:
                return company.get("ticker")
        
        return None


async def search_institutions(query: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Search for institutional investors by name.
    
    Args:
        query: Search query for institution name
        limit: Maximum number of results
        
    Returns:
        List of matching institutions with CIKs
    """
    # This would typically query the SEC's institutional investor database
    # For now, return a placeholder implementation
    # In production, this would search the 13F filer database
    
    logger.warning("Institution search is a placeholder implementation")
    return [
        {
            "name": f"Institution matching '{query}'",
            "cik": "0000000000",
            "note": "Placeholder - implement actual SEC institution search"
        }
    ]


async def fetch_filing_header(accession_number: str) -> Dict[str, Any]:
    """Fetch filing header information by accession number.
    
    Args:
        accession_number: SEC accession number (e.g., "0000950103-24-000001")
        
    Returns:
        Dict containing filing header information
    """
    # Remove hyphens from accession number for URL
    acc_no_dash = accession_number.replace("-", "")
    
    # Construct header URL
    url = f"{SEC_ARCHIVES_BASE}/edgar/data/{acc_no_dash}-index-headers.html"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0
        )
        response.raise_for_status()
        
        # Parse header information (simplified)
        # In production, would parse the HTML properly
        return {
            "accession_number": accession_number,
            "url": url,
            "content_preview": response.text[:500],
            "note": "Full header parsing to be implemented"
        }


async def fetch_filing_html(accession_number: str, file_name: Optional[str] = None) -> str:
    """Fetch filing HTML content by accession number.
    
    Args:
        accession_number: SEC accession number
        file_name: Optional specific file within the filing
        
    Returns:
        HTML content of the filing
    """
    # Remove hyphens from accession number
    acc_no_dash = accession_number.replace("-", "")
    
    # Get first 10 digits for CIK directory
    cik_part = acc_no_dash[:10]
    
    if file_name:
        url = f"{SEC_ARCHIVES_BASE}/edgar/data/{cik_part}/{acc_no_dash}/{file_name}"
    else:
        # Default to main filing document
        url = f"{SEC_ARCHIVES_BASE}/edgar/data/{cik_part}/{acc_no_dash}/{accession_number}.htm"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0
        )
        response.raise_for_status()
        return response.text


# MCP tool wrapper functions that can be registered with the OpenBB MCP server
async def mcp_edgar_filings(
    symbol: str,
    form_type: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """MCP wrapper for fetching SEC filings by symbol.
    
    Args:
        symbol: Stock ticker symbol
        form_type: Optional form type filter (e.g., "10-K", "8-K")
        limit: Maximum number of filings to return
        
    Returns:
        Dict containing filing information
    """
    try:
        # Get CIK from ticker
        cik = await get_cik_from_ticker(symbol)
        if not cik:
            return {"error": f"Could not find CIK for symbol {symbol}"}
        
        # Fetch submissions
        submissions = await edgar_fetch_submissions(cik)
        
        # Extract recent filings
        recent_filings = submissions.get("filings", {}).get("recent", {})
        
        # Filter by form type if specified
        filings = []
        forms = recent_filings.get("form", [])
        dates = recent_filings.get("filingDate", [])
        accessions = recent_filings.get("accessionNumber", [])
        
        for i in range(min(len(forms), limit)):
            if form_type and forms[i] != form_type:
                continue
            
            filings.append({
                "form": forms[i],
                "filing_date": dates[i] if i < len(dates) else None,
                "accession_number": accessions[i] if i < len(accessions) else None,
            })
            
            if len(filings) >= limit:
                break
        
        return {
            "symbol": symbol,
            "cik": cik,
            "company_name": submissions.get("name", ""),
            "filings": filings
        }
        
    except Exception as e:
        logger.error(f"Error fetching filings for {symbol}: {e}")
        return {"error": str(e)}


async def mcp_company_facts(
    symbol: str,
    facts: Optional[List[str]] = None
) -> Dict[str, Any]:
    """MCP wrapper for fetching XBRL company facts.
    
    Args:
        symbol: Stock ticker symbol
        facts: Optional list of specific facts to retrieve
        
    Returns:
        Dict containing company facts
    """
    try:
        # Get CIK from ticker
        cik = await get_cik_from_ticker(symbol)
        if not cik:
            return {"error": f"Could not find CIK for symbol {symbol}"}
        
        # Fetch company facts
        company_facts = await edgar_fetch_companyfacts(cik)
        
        # Extract specific facts if requested
        if facts:
            filtered_facts = {}
            for fact in facts:
                if fact in company_facts.get("facts", {}).get("us-gaap", {}):
                    filtered_facts[fact] = company_facts["facts"]["us-gaap"][fact]
            
            return {
                "symbol": symbol,
                "cik": cik,
                "entity_name": company_facts.get("entityName", ""),
                "facts": filtered_facts
            }
        
        return {
            "symbol": symbol,
            "cik": cik,
            "entity_name": company_facts.get("entityName", ""),
            "facts": company_facts.get("facts", {})
        }
        
    except Exception as e:
        logger.error(f"Error fetching company facts for {symbol}: {e}")
        return {"error": str(e)}