"""SEC Filing Section Parser using edgar-crawler.

Wrapper around nlpaueb/edgar-crawler for extracting sections from SEC filings.
Handles 10-K, 10-Q, and 8-K filings including modern inline XBRL formats.
"""

import asyncio
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add edgar_crawler to path
EDGAR_CRAWLER_PATH = str(Path(__file__).parent.parent / "edgar_crawler")
if EDGAR_CRAWLER_PATH not in sys.path:
    sys.path.insert(0, EDGAR_CRAWLER_PATH)

from edgar_crawler.extract_items import ExtractItems
from edgar_crawler.item_lists import item_list_10k, item_list_10q, item_list_8k

from .sec_parsing_utils.text_chunker import chunk_text_by_tokens

logger = logging.getLogger(__name__)


def detect_filing_type(html_content: str) -> str:
    """Detect filing type from HTML content.

    Args:
        html_content: Raw HTML string

    Returns:
        Filing type: "10-K", "10-Q", or "8-K"
    """
    from bs4 import BeautifulSoup
    import re

    # Check for <TYPE> tag in SEC header
    type_match = re.search(r'<TYPE>([^\n]+)', html_content[:5000], re.IGNORECASE)
    if type_match:
        doc_type = type_match.group(1).strip()
        if '10-K' in doc_type.upper():
            return '10-K'
        elif '10-Q' in doc_type.upper():
            return '10-Q'
        elif '8-K' in doc_type.upper():
            return '8-K'

    # Check inline XBRL dei:DocumentType
    soup = BeautifulSoup(html_content, "html.parser")
    doc_type_tags = soup.find_all(['ix:nonnumeric', 'nonnumeric'],
                                   attrs={'name': re.compile('dei:documenttype', re.I)})
    if doc_type_tags:
        doc_type = doc_type_tags[0].get_text().strip()
        if '10-K' in doc_type.upper():
            return '10-K'
        elif '10-Q' in doc_type.upper():
            return '10-Q'
        elif '8-K' in doc_type.upper():
            return '8-K'

    # Check title tag
    title = soup.find('title')
    if title:
        title_text = title.get_text().upper()
        if '10-K' in title_text or '10K' in title_text:
            return '10-K'
        elif '10-Q' in title_text or '10Q' in title_text:
            return '10-Q'
        elif '8-K' in title_text:
            return '8-K'

    # Fallback to text search
    text_sample = soup.get_text()[:20000].upper()
    if 'FORM 10-K' in text_sample or 'ANNUAL REPORT' in text_sample:
        return '10-K'
    elif 'FORM 10-Q' in text_sample or 'QUARTERLY REPORT' in text_sample:
        return '10-Q'
    elif 'FORM 8-K' in text_sample or 'CURRENT REPORT' in text_sample:
        return '8-K'

    return '10-K'  # Default assumption


def normalize_section_name(section: str, filing_type: str) -> Optional[str]:
    """Normalize section name to edgar-crawler format.

    Args:
        section: User-provided section name (e.g., "Item 1A", "md&a")
        filing_type: Type of filing

    Returns:
        Normalized section name for edgar-crawler, or None if invalid
    """
    section_lower = section.lower().strip()

    # Remove "item " prefix if present
    section_clean = section.replace("Item ", "").replace("item ", "").strip()

    # Handle aliases
    if filing_type == "10-K":
        aliases = {
            "business": "1",
            "risk factors": "1A",
            "risks": "1A",
            "md&a": "7",
            "mda": "7",
            "management discussion": "7",
            "financial statements": "8",
            "financials": "8",
        }
        if section_lower in aliases:
            return aliases[section_lower]

        # Direct match (e.g., "1A", "7", etc.)
        if section_clean.upper() in item_list_10k:
            return section_clean.upper()

    elif filing_type == "10-Q":
        aliases = {
            "financial statements": "part_1__1",
            "md&a": "part_1__2",
            "mda": "part_1__2",
            "risks": "part_2__1A",
            "risk factors": "part_2__1A",
        }
        if section_lower in aliases:
            return aliases[section_lower]

        # Handle "Part I Item 1" or "part_1__1" format
        if section in item_list_10q:
            return section
        # Try parsing "Part I Item 2" format
        import re
        part_match = re.match(r'part\s*([12])\s*item\s*(\d+[a-z]?)', section_lower)
        if part_match:
            part_num, item_num = part_match.groups()
            return f"part_{part_num}__{item_num.upper()}"

    elif filing_type == "8-K":
        # Handle 8-K item numbers (e.g., "1.01", "2.02")
        if section_clean in item_list_8k:
            return section_clean

    return None


def extract_metadata_from_html(html_content: str, url: str) -> Dict[str, str]:
    """Extract filing metadata from HTML content and URL.

    Args:
        html_content: Raw HTML string
        url: SEC filing URL

    Returns:
        Dict with CIK, Company, Date, etc.
    """
    from bs4 import BeautifulSoup
    import re

    metadata = {}

    # Extract CIK from URL (e.g., /data/320193/... -> CIK is 320193)
    cik_match = re.search(r'/data/(\d+)/', url)
    metadata["CIK"] = cik_match.group(1) if cik_match else "0000000000"

    soup = BeautifulSoup(html_content, "html.parser")

    # Try to extract company name from title or XBRL
    title = soup.find('title')
    if title:
        metadata["Company"] = title.get_text().strip()[:100]
    else:
        metadata["Company"] = "Unknown"

    # Extract period of report from XBRL or default
    period_tags = soup.find_all(['ix:nonnumeric', 'nonnumeric'],
                                 attrs={'name': re.compile('dei:documentperiodenddate', re.I)})
    if period_tags:
        metadata["Period of Report"] = period_tags[0].get_text().strip()
    else:
        metadata["Period of Report"] = datetime.now().strftime("%Y-%m-%d")

    # Set defaults for other required fields
    metadata["SIC"] = "0000"
    metadata["State of Inc"] = ""
    metadata["State location"] = ""
    metadata["Fiscal Year End"] = "1231"
    metadata["html_index"] = url
    metadata["htm_file_link"] = url
    metadata["complete_text_file_link"] = url

    return metadata


def extract_items_from_html(
    html_content: str,
    filing_type: str,
    url: str,
    sections: Optional[List[str]] = None,
    filing_date: Optional[str] = None,
    include_tables: bool = False
) -> Dict[str, str]:
    """Extract sections from SEC filing HTML using edgar-crawler.

    Args:
        html_content: Raw HTML content
        filing_type: "10-K", "10-Q", or "8-K"
        url: SEC filing URL
        sections: List of section names to extract (None = all)
        filing_date: Filing date in YYYY-MM-DD format
        include_tables: Whether to include tables in extracted text

    Returns:
        Dict mapping section names to extracted text
    """
    # Create temp directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # edgar-crawler expects: raw_files_folder/<Type>/<filename>.htm
        raw_folder = Path(tmpdir) / "raw" / filing_type
        raw_folder.mkdir(parents=True)

        # Write HTML to file
        filing_path = raw_folder / "filing.htm"
        filing_path.write_text(html_content, encoding='utf-8')

        extracted_folder = Path(tmpdir) / "extracted"
        extracted_folder.mkdir()

        # Normalize section names to edgar-crawler format
        items_to_extract = None
        if sections:
            items_to_extract = []
            for sec in sections:
                normalized = normalize_section_name(sec, filing_type)
                if normalized:
                    items_to_extract.append(normalized)
                else:
                    logger.warning(f"Unknown section '{sec}' for {filing_type}")

        # Create ExtractItems instance
        extractor = ExtractItems(
            remove_tables=not include_tables,  # Honor include_tables parameter
            items_to_extract=items_to_extract,
            include_signature=False,
            raw_files_folder=str(raw_folder.parent),
            extracted_files_folder=str(extracted_folder),
            skip_extracted_filings=False
        )

        # Extract metadata from HTML and URL
        auto_metadata = extract_metadata_from_html(html_content, url)

        # Prepare complete filing metadata
        filing_metadata = {
            "Type": filing_type,
            "Date": filing_date or datetime.now().strftime("%Y-%m-%d"),
            "filename": "filing.htm",
            **auto_metadata  # Add all extracted metadata
        }

        # Determine items to extract based on filing type
        extractor.determine_items_to_extract(filing_metadata)

        # Extract items (note: method only takes filing_metadata, not path)
        result = extractor.extract_items(filing_metadata)

        return result


async def regulators_sec_section_extract(
    url: str,
    sections: Optional[List[str]] = None,
    max_tokens: int = 4500,
    include_tables: bool = False,
    use_cache: bool = True,
    max_chunks_per_section: int = 2
) -> Dict[str, Any]:
    """Extract specific sections from SEC HTML filings using edgar-crawler.

    This tool uses the nlpaueb/edgar-crawler library to parse SEC filings
    and extract requested sections. Handles both traditional HTML and modern
    inline XBRL formats.

    Args:
        url: Direct URL to SEC filing (.htm or .html file)
        sections: List of sections to extract (e.g., ["Item 1A", "Item 7"]).
                 If None, extracts all major sections. Supports aliases like "md&a".
        max_tokens: Maximum tokens per chunk (default: 4500)
        include_tables: Whether to include tables in extracted text (default: False)
        use_cache: Cache downloaded HTML for reuse (default: True)

    Returns:
        Dict with:
            - url: Filing URL
            - filing_type: Detected type (10-K, 10-Q, 8-K)
            - sections: List of extracted sections with chunks
            - metadata: Summary statistics

    Example:
        # Extract risk factors and MD&A from 10-K
        result = await regulators_sec_section_extract(
            url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
            sections=["Item 1A", "Item 7"]
        )
    """
    try:
        # Validate URL
        if not url or not url.startswith("http"):
            return {
                "error": "invalid_url",
                "message": "URL must be a valid HTTP/HTTPS URL"
            }

        if "sec.gov" not in url or (not url.endswith(".htm") and not url.endswith(".html")):
            return {
                "error": "invalid_url",
                "message": "URL must be a SEC.gov filing URL ending in .htm or .html"
            }

        # Download HTML (using OpenBB's caching)
        logger.info(f"Downloading filing from {url}")
        from openbb_sec.models.sec_filing import SecBaseFiling
        html_content = SecBaseFiling.download_file(url, False, use_cache)

        # Detect filing type
        filing_type = detect_filing_type(html_content)
        logger.info(f"Detected filing type: {filing_type}")

        # Extract sections using edgar-crawler (run in thread pool to not block event loop)
        logger.info(f"Extracting sections using edgar-crawler")
        extracted = await asyncio.to_thread(
            extract_items_from_html,
            html_content,
            filing_type,
            url,  # Pass URL for metadata extraction
            sections,
            None,  # filing_date
            include_tables  # Pass through include_tables parameter
        )

        if not extracted:
            return {
                "error": "no_sections_found",
                "message": f"Could not extract any sections from {filing_type} filing",
                "url": url,
                "filing_type": filing_type
            }

        # Format sections with chunking
        sections_output = []
        total_tokens = 0
        MAX_RESPONSE_TOKENS = 15000  # Conservative limit well below 25K MCP limit

        for section_name, text in extracted.items():
            if not text or section_name in ["cik", "company", "filing_type", "filing_date",
                                             "period_of_report", "sic", "state_of_inc",
                                             "state_location", "fiscal_year_end",
                                             "filing_html_index", "htm_filing_link",
                                             "complete_text_filing_link", "filename"]:
                continue  # Skip metadata fields

            # Check if adding this section would exceed limit
            if total_tokens > MAX_RESPONSE_TOKENS:
                logger.warning(f"Stopping extraction - reached {total_tokens} tokens (limit: {MAX_RESPONSE_TOKENS})")
                break

            # Chunk text
            chunks = chunk_text_by_tokens(text, max_tokens)

            # Limit chunks per section to prevent huge responses
            if len(chunks) > max_chunks_per_section:
                chunks = chunks[:max_chunks_per_section]
                status = "truncated"
                warning = f"Limited to first {max_chunks_per_section} chunks (of {len(chunk_text_by_tokens(text, max_tokens))} total)"
            else:
                status = "success"
                warning = None

            estimated_tokens = sum(c['tokens'] for c in chunks)

            # If this single section exceeds remaining budget, truncate chunks further
            remaining_budget = MAX_RESPONSE_TOKENS - total_tokens
            if estimated_tokens > remaining_budget:
                # Keep only chunks that fit in budget
                truncated_chunks = []
                chunk_tokens = 0
                for chunk in chunks:
                    if chunk_tokens + chunk['tokens'] <= remaining_budget:
                        truncated_chunks.append(chunk)
                        chunk_tokens += chunk['tokens']
                    else:
                        break

                if truncated_chunks:
                    result_entry = {
                        "section_name": section_name,
                        "text_length": len(text),
                        "estimated_tokens": chunk_tokens,
                        "chunks": truncated_chunks,
                        "status": "truncated",
                        "warning": f"Section truncated to {len(truncated_chunks)} chunks to stay within response limit"
                    }
                    sections_output.append(result_entry)
                    total_tokens += chunk_tokens
                break

            result_entry = {
                "section_name": section_name,
                "text_length": len(text),
                "estimated_tokens": estimated_tokens,
                "chunks": chunks,
                "status": status
            }
            if warning:
                result_entry["warning"] = warning

            sections_output.append(result_entry)
            total_tokens += estimated_tokens

        # Build response with truncation summary
        truncated_sections = [s["section_name"] for s in sections_output if s.get("status") == "truncated"]

        metadata = {
            "total_sections": len(sections_output),
            "successful_extractions": len(sections_output),
            "total_estimated_tokens": total_tokens,
            "extraction_engine": "edgar-crawler (nlpaueb)",
            "include_tables": include_tables
        }

        # Add truncation warning to metadata if any sections were truncated
        if truncated_sections:
            metadata["truncation_warning"] = f"{len(truncated_sections)} section(s) truncated: {', '.join(truncated_sections)}"
            metadata["truncated_sections"] = truncated_sections

        return {
            "url": url,
            "filing_type": filing_type,
            "sections": sections_output,
            "available_sections": list(extracted.keys()),
            "metadata": metadata
        }

    except Exception as e:
        logger.error(f"Error in regulators_sec_section_extract: {e}", exc_info=True)
        return {
            "error": "extraction_failed",
            "message": str(e),
            "url": url
        }
