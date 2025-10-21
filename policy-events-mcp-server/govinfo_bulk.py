"""
Simple GovInfo API client for bulk data retrieval.
No filtering - returns all data for LLM to analyze.
"""
import httpx
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class GovInfoBulkClient:
    """Lightweight GovInfo API client"""

    BASE_URL = "https://api.govinfo.gov"

    def __init__(self):
        self.api_key = os.getenv("GOVINFO_API_KEY")
        self.session = None

    def _validate_api_key(self):
        """Validate that API key is configured"""
        if not self.api_key:
            raise ValueError(
                "Missing GOVINFO_API_KEY environment variable. "
                "Get your free API key at https://www.govinfo.gov/api-signup/"
            )
        
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def get_federal_rules(
        self,
        days_back: int = 30,
        days_ahead: int = 30,
        max_results: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get all Federal Register documents in date range.
        Returns minimal metadata for LLM analysis.
        """
        self._validate_api_key()

        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)

        rules = []
        
        # Calculate date range
        start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end_date = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        # First get the FR packages for the date range
        endpoint = f"/published/{start_date}/{end_date}"
        params = {
            "collection": "FR",
            "offsetMark": "*",
            "pageSize": 20,  # Get up to 20 days of FR issues
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
            
        try:
            response = await self.session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            # For each FR package, get its granules (individual rules/notices)
            for package in data.get("packages", []):
                package_id = package.get("packageId", "")
                
                # Only process daily FR issues (format FR-YYYY-MM-DD)
                if not (package_id and package_id.startswith("FR-") and len(package_id.split("-")) == 4):
                    continue
                
                # Get granules for this FR issue
                granules_endpoint = f"/packages/{package_id}/granules"
                granules_params = {
                    "offsetMark": "*",
                    "pageSize": 100  # Get up to 100 documents per day
                }
                if self.api_key:
                    granules_params["api_key"] = self.api_key
                
                try:
                    granules_response = await self.session.get(
                        f"{self.BASE_URL}{granules_endpoint}",
                        params=granules_params
                    )
                    
                    if granules_response.status_code == 200:
                        granules_data = granules_response.json()
                        
                        for granule in granules_data.get("granules", []):
                            title = granule.get("title", "")
                            
                            # Determine rule type from title
                            rule_type = "Other"
                            title_lower = title.lower()
                            if "proposed rule" in title_lower:
                                rule_type = "Proposed Rule"
                            elif "final rule" in title_lower:
                                rule_type = "Final Rule"
                            elif "notice" in title_lower:
                                rule_type = "Notice"
                            
                            # Extract agency from title (usually at beginning)
                            agency = "Unknown Agency"
                            if "-" in title:
                                agency = title.split("-")[0].strip()
                            
                            rules.append({
                                "document_number": granule.get("granuleId", ""),
                                "title": title[:200],  # Limit title length
                                "agency": agency,
                                "rule_type": rule_type,
                                "publication_date": package.get("dateIssued", ""),
                                "fr_url": granule.get("granuleLink", ""),
                                "package_id": package_id  # Store parent package for detail retrieval
                            })
                            
                            if len(rules) >= max_results:
                                break
                                
                except Exception as e:
                    logger.warning(f"Error fetching granules for {package_id}: {e}")
                    continue
                
                if len(rules) >= max_results:
                    break
                        
            logger.info(f"Retrieved {len(rules)} Federal Register documents")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Federal Register documents: {e}")
            raise ValueError(
                f"GovInfo API error: {e.response.status_code}. "
                f"Verify your GOVINFO_API_KEY is valid at https://www.govinfo.gov/api-signup/"
            )
        except Exception as e:
            logger.error(f"Error fetching Federal Register documents: {e}")
            raise ValueError(f"Failed to fetch Federal Register documents from GovInfo: {str(e)}")

        return rules[:max_results]
    
    async def _get_package_summary(self, package_id: str) -> Dict[str, Any]:
        """Get summary for a specific package"""
        try:
            endpoint = f"/packages/{package_id}/summary"
            params = {}
            if self.api_key:
                params["api_key"] = self.api_key
                
            response = await self.session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            logger.error(f"Error fetching package summary for {package_id}: {e}")
            
        return {}
    
    def _extract_agency(self, summary: Dict[str, Any]) -> str:
        """Extract agency name from package summary"""
        # Try various fields
        agency = summary.get("agency", "")
        if not agency:
            agency = summary.get("issuingAgency", "")
        if not agency:
            # Try to extract from title
            title = summary.get("title", "")
            if "EPA" in title:
                agency = "Environmental Protection Agency"
            elif "SEC" in title:
                agency = "Securities and Exchange Commission"
            elif "FDA" in title:
                agency = "Food and Drug Administration"
            else:
                agency = "Unknown Agency"
        return agency
    
    def _determine_rule_type(self, summary: Dict[str, Any]) -> str:
        """Determine if proposed, final, or notice"""
        doc_type = summary.get("documentType", "").lower()
        title = summary.get("title", "").lower()
        
        if "proposed" in doc_type or "proposed" in title:
            return "Proposed Rule"
        elif "final" in doc_type or "final" in title:
            return "Final Rule"
        elif "notice" in doc_type or "notice" in title:
            return "Notice"
        else:
            return "Other"
    
    async def get_rule_details(
        self,
        document_numbers: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Get full details for specific rules identified by LLM.
        Enhanced to fetch content from Federal Register API when available.
        Document numbers can be either:
        - Granule IDs (e.g., "2025-15325")
        - Package IDs with granule (e.g., "FR-2025-08-12:2025-15325")
        """
        self._validate_api_key()

        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)

        detailed_rules = []
        
        for doc_num in document_numbers:
            try:
                # Check if we have package_id:granule_id format
                if ":" in doc_num:
                    package_id, granule_id = doc_num.split(":", 1)
                else:
                    # If no package ID, try Federal Register API directly
                    granule_id = doc_num
                    
                    # Try to fetch from Federal Register API
                    fr_api_url = f"https://www.federalregister.gov/api/v1/documents/{granule_id}"
                    
                    try:
                        fr_response = await self.session.get(fr_api_url)
                        
                        if fr_response.status_code == 200:
                            fr_data = fr_response.json()
                            
                            detailed_rules.append({
                                "document_number": granule_id,
                                "title": fr_data.get("title", ""),
                                "agency": ", ".join(fr_data.get("agencies", [])) if fr_data.get("agencies") else "Unknown",
                                "rule_type": fr_data.get("type", "Unknown"),
                                "publication_date": fr_data.get("publication_date", ""),
                                "effective_date": fr_data.get("effective_on", ""),
                                "comment_close_date": fr_data.get("comments_close_on", ""),
                                "abstract": fr_data.get("abstract", ""),
                                "summary": fr_data.get("abstract", "") or fr_data.get("action", ""),
                                "significant": fr_data.get("significant", False),
                                "cfr_references": fr_data.get("cfr_references", []),
                                "docket_ids": fr_data.get("docket_ids", []),
                                "pdf_link": fr_data.get("pdf_url", ""),
                                "html_link": fr_data.get("html_url", ""),
                                "fr_url": fr_data.get("html_url", f"https://www.federalregister.gov/d/{granule_id}")
                            })
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to fetch from Federal Register API: {e}")
                    
                    # Fallback if Federal Register API fails
                    detailed_rules.append({
                        "document_number": granule_id,
                        "title": f"Federal Register Document {granule_id}",
                        "agency": "Various",
                        "rule_type": "See document",
                        "publication_date": "Recent",
                        "effective_date": "See document for effective date",
                        "comment_close_date": "See document for comment deadline",
                        "summary": f"Document {granule_id} from Federal Register. For full details, visit federalregister.gov",
                        "pdf_link": f"https://www.federalregister.gov/documents/search?conditions%5Bterm%5D={granule_id}",
                        "text_link": "",
                        "fr_url": f"https://www.federalregister.gov/d/{granule_id}"
                    })
                    continue
                
                # If we have the package ID, get the granule summary
                endpoint = f"/packages/{package_id}/granules/{granule_id}/summary"
                params = {}
                if self.api_key:
                    params["api_key"] = self.api_key
                    
                response = await self.session.get(
                    f"{self.BASE_URL}{endpoint}",
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    detailed_rules.append({
                        "document_number": granule_id,
                        "title": data.get("title", ""),
                        "agency": data.get("agencies", ["Unknown"])[0] if data.get("agencies") else "Unknown",
                        "rule_type": data.get("documentType", "Unknown"),
                        "publication_date": data.get("dateIssued", ""),
                        "effective_date": data.get("effectiveDate", ""),
                        "comment_close_date": self._extract_comment_date(data),
                        "summary": data.get("abstract", "") or data.get("summary", ""),
                        "pdf_link": data.get("download", {}).get("pdfLink", ""),
                        "text_link": data.get("download", {}).get("txtLink", ""),
                        "fr_url": data.get("detailsLink", "")
                    })
                else:
                    # Fallback if API call fails
                    detailed_rules.append({
                        "document_number": granule_id,
                        "title": f"Federal Register Document {granule_id}",
                        "agency": "See document",
                        "rule_type": "See document",
                        "publication_date": "Recent",
                        "fr_url": f"https://www.federalregister.gov/d/{granule_id}"
                    })
                    
            except Exception as e:
                logger.error(f"Error fetching details for {doc_num}: {e}")
                continue
                
        return detailed_rules
    
    def _extract_comment_date(self, summary: Dict[str, Any]) -> Optional[str]:
        """Extract comment close date if present"""
        # This might be in various fields or in the text
        # Simple check for now
        if "commentCloseDate" in summary:
            return summary["commentCloseDate"]
        
        # Could parse from summary text if needed
        summary_text = summary.get("summary", "").lower()
        if "comments must be received" in summary_text or "comment period" in summary_text:
            # Would need more sophisticated parsing
            return "See document for comment deadline"
            
        return None