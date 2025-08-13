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
            
        except Exception as e:
            logger.error(f"Error fetching Federal Register documents: {e}")
            return []
            
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
        Document numbers can be either:
        - Granule IDs (e.g., "2025-15325") 
        - Package IDs with granule (e.g., "FR-2025-08-12:2025-15325")
        """
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)
            
        detailed_rules = []
        
        for doc_num in document_numbers:
            try:
                # Check if we have package_id:granule_id format
                if ":" in doc_num:
                    package_id, granule_id = doc_num.split(":", 1)
                else:
                    # Try to find the package by searching recent FR issues
                    # This is a fallback - ideally the LLM should pass package_id:granule_id
                    granule_id = doc_num
                    
                    # Search recent FR packages to find which one contains this granule
                    # For now, construct a direct link as we can't easily search
                    detailed_rules.append({
                        "document_number": granule_id,
                        "title": f"Federal Register Document {granule_id}",
                        "agency": "Various",
                        "rule_type": "See document",
                        "publication_date": "Recent",
                        "effective_date": "See document for effective date",
                        "comment_close_date": "See document for comment deadline",
                        "summary": f"Document {granule_id} from Federal Register. For full details, search federalregister.gov",
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