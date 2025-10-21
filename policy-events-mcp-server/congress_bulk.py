"""
Simple Congress.gov API client for bulk data retrieval.
No filtering - returns all data for LLM to analyze.
"""
import httpx
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

def get_current_congress():
    """Calculate current Congress number based on date.
    
    Congress changes every 2 years on January 3rd.
    119th Congress: 2025-2026
    118th Congress: 2023-2024
    """
    current_date = datetime.now()
    current_year = current_date.year
    
    # Congress starts on January 3rd of odd years
    # If we're before January 3rd of an odd year, we're still in the previous congress
    if current_date.month == 1 and current_date.day < 3 and current_year % 2 == 1:
        effective_year = current_year - 1
    else:
        effective_year = current_year
    
    # Calculate congress number
    # First Congress was 1789-1791
    base_year = 1789
    base_congress = 1
    
    # Each Congress spans 2 years
    congress_number = base_congress + ((effective_year - base_year) // 2)
    
    return congress_number

class CongressBulkClient:
    """Lightweight Congress.gov API client"""

    BASE_URL = "https://api.congress.gov/v3"

    def __init__(self):
        self.api_key = os.getenv("CONGRESS_API_KEY")
        self.session = None

    def _validate_api_key(self):
        """Validate that API key is configured"""
        if not self.api_key:
            raise ValueError(
                "Missing CONGRESS_API_KEY environment variable. "
                "Get your free API key at https://api.congress.gov/sign-up/"
            )
        
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def get_recent_bills(
        self,
        days_back: int = 30,
        max_results: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get all recent bills without filtering.
        Returns minimal metadata for LLM analysis.
        """
        self._validate_api_key()

        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)

        bills = []
        
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        # Use the /bill endpoint with date filtering
        endpoint = "/bill"
        params = {
            "fromDateTime": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "toDateTime": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": min(max_results, 250),  # API max is 250
            "format": "json"
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
            
            # Extract minimal bill info
            for bill in data.get("bills", []):
                bills.append({
                    "bill_id": f"{bill.get('type', '')}-{bill.get('number', '')}",
                    "congress": bill.get("congress"),
                    "title": bill.get("title", ""),
                    "sponsor": bill.get("sponsor", {}).get("fullName", "") if bill.get("sponsor") else "",
                    "latest_action": bill.get("latestAction", {}).get("text", ""),
                    "action_date": bill.get("latestAction", {}).get("actionDate", ""),
                    "url": bill.get("url", "")
                })
                
            logger.info(f"Retrieved {len(bills)} bills from Congress.gov")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching bills: {e}")
            raise ValueError(
                f"Congress.gov API error: {e.response.status_code}. "
                f"Verify your CONGRESS_API_KEY is valid at https://api.congress.gov/sign-up/"
            )
        except Exception as e:
            logger.error(f"Error fetching bills: {e}")
            raise ValueError(f"Failed to fetch bills from Congress.gov: {str(e)}")

        return bills[:max_results]
    
    async def get_upcoming_hearings(
        self,
        days_ahead: int = 30,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all upcoming hearings without filtering.
        Returns minimal metadata for LLM analysis.
        """
        self._validate_api_key()

        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)

        hearings = []
        
        # Get hearings from both chambers
        current_congress = get_current_congress()
        for chamber in ["house", "senate"]:
            endpoint = f"/committee-meeting/{current_congress}/{chamber}"
            params = {
                "limit": min(max_results // 2, 100),  # Split between chambers
                "format": "json"
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
                
                # Extract minimal hearing info with enhanced metadata
                for meeting in data.get("committeeMeetings", []):
                    hearings.append({
                        "event_id": meeting.get("eventId"),
                        "chamber": chamber.title(),
                        "title": meeting.get("title", ""),
                        "committee": meeting.get("committees", [{}])[0].get("name", "") if meeting.get("committees") else "",
                        "date": meeting.get("date", ""),
                        "time": meeting.get("time", ""),  # Add time field
                        "location": meeting.get("location", ""),  # Add location
                        "congress": current_congress,  # Add congress number
                        "url": meeting.get("url", "")
                    })
                    
            except Exception as e:
                logger.error(f"Error fetching {chamber} hearings: {e}")
                # Continue with other chamber
                
        logger.info(f"Retrieved {len(hearings)} hearings from Congress.gov")
        return hearings[:max_results]
    
    async def get_bill_details(
        self,
        bill_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Get full details for specific bills identified by LLM.
        """
        self._validate_api_key()

        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)

        detailed_bills = []
        
        for bill_id in bill_ids:
            try:
                # Parse bill_id (format: "HR-1234" or "S-567")
                parts = bill_id.split("-")
                if len(parts) != 2:
                    continue
                    
                bill_type = parts[0].lower()
                bill_number = parts[1]
                
                # Use current congress dynamically
                current_congress = get_current_congress()
                endpoint = f"/bill/{current_congress}/{bill_type}/{bill_number}"
                params = {"format": "json"}
                
                if self.api_key:
                    params["api_key"] = self.api_key
                    
                response = await self.session.get(
                    f"{self.BASE_URL}{endpoint}",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                bill = data.get("bill", {})
                
                # Get committees
                committees_endpoint = f"/bill/{current_congress}/{bill_type}/{bill_number}/committees"
                committees_response = await self.session.get(
                    f"{self.BASE_URL}{committees_endpoint}",
                    params=params
                )
                committees_data = committees_response.json() if committees_response.status_code == 200 else {}
                
                # Get text/summary
                text_endpoint = f"/bill/{current_congress}/{bill_type}/{bill_number}/text"
                text_response = await self.session.get(
                    f"{self.BASE_URL}{text_endpoint}",
                    params=params
                )
                text_data = text_response.json() if text_response.status_code == 200 else {}
                
                detailed_bills.append({
                    "bill_id": bill_id,
                    "title": bill.get("title", ""),
                    "summary": bill.get("summary", {}).get("text", "") if bill.get("summary") else "",
                    "sponsor": bill.get("sponsors", [{}])[0] if bill.get("sponsors") else {},
                    "cosponsors_count": bill.get("cosponsors", {}).get("count", 0),
                    "committees": committees_data.get("committees", []),
                    "actions": bill.get("actions", {}).get("item", [])[:10] if bill.get("actions") else [],
                    "text_versions": text_data.get("textVersions", []),
                    "congress_url": f"https://www.congress.gov/bill/{current_congress}th-congress/{bill_type.replace('res', '-resolution')}/{bill_number}"
                })
                
            except Exception as e:
                logger.error(f"Error fetching details for {bill_id}: {e}")
                continue
                
        return detailed_bills
    
    async def get_hearing_details(
        self,
        event_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Get full details for specific hearings identified by LLM.
        """
        self._validate_api_key()

        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)

        detailed_hearings = []
        
        for event_id in event_ids:
            # Try both chambers since we don't know which one
            current_congress = get_current_congress()
            for chamber in ["house", "senate"]:
                try:
                    endpoint = f"/committee-meeting/{current_congress}/{chamber}/{event_id}"
                    params = {"format": "json"}
                    
                    if self.api_key:
                        params["api_key"] = self.api_key
                        
                    response = await self.session.get(
                        f"{self.BASE_URL}{endpoint}",
                        params=params
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        meeting = data.get("committeeMeeting", {})
                        
                        detailed_hearings.append({
                            "event_id": event_id,
                            "chamber": chamber.title(),
                            "title": meeting.get("title", ""),
                            "committees": meeting.get("committees", []),
                            "date": meeting.get("date", ""),
                            "type": meeting.get("type", ""),
                            "witnesses": meeting.get("witnesses", []),
                            "documents": meeting.get("documents", []),
                            "congress": current_congress,
                            "url": f"https://www.congress.gov/committee-meeting/{current_congress}/{chamber}/{event_id}"
                        })
                        break  # Found in this chamber, don't check the other
                        
                except Exception as e:
                    logger.error(f"Error fetching details for {event_id} in {chamber}: {e}")
                    continue
                    
        return detailed_hearings