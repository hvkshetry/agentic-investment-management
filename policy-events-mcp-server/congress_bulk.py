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

class CongressBulkClient:
    """Lightweight Congress.gov API client"""
    
    BASE_URL = "https://api.congress.gov/v3"
    
    def __init__(self):
        self.api_key = os.getenv("CONGRESS_API_KEY")
        self.session = None
        
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
            
        except Exception as e:
            logger.error(f"Error fetching bills: {e}")
            # Return empty list on error - fail gracefully
            return []
            
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
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)
            
        hearings = []
        
        # Get hearings from both chambers
        for chamber in ["house", "senate"]:
            endpoint = f"/committee-meeting/118/{chamber}"
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
                
                # Extract minimal hearing info
                for meeting in data.get("committeeMeetings", []):
                    hearings.append({
                        "event_id": meeting.get("eventId"),
                        "chamber": chamber.title(),
                        "title": meeting.get("title", ""),
                        "committee": meeting.get("committees", [{}])[0].get("name", "") if meeting.get("committees") else "",
                        "date": meeting.get("date", ""),
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
                
                # Assume current congress (118)
                endpoint = f"/bill/118/{bill_type}/{bill_number}"
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
                committees_endpoint = f"/bill/118/{bill_type}/{bill_number}/committees"
                committees_response = await self.session.get(
                    f"{self.BASE_URL}{committees_endpoint}",
                    params=params
                )
                committees_data = committees_response.json() if committees_response.status_code == 200 else {}
                
                # Get text/summary
                text_endpoint = f"/bill/118/{bill_type}/{bill_number}/text"
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
                    "congress_url": f"https://www.congress.gov/bill/118th-congress/{bill_type.replace('res', '-resolution')}/{bill_number}"
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
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)
            
        detailed_hearings = []
        
        for event_id in event_ids:
            # Try both chambers since we don't know which one
            for chamber in ["house", "senate"]:
                try:
                    endpoint = f"/committee-meeting/118/{chamber}/{event_id}"
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
                            "url": f"https://www.congress.gov/committee-meeting/118/{chamber}/{event_id}"
                        })
                        break  # Found in this chamber, don't check the other
                        
                except Exception as e:
                    logger.error(f"Error fetching details for {event_id} in {chamber}: {e}")
                    continue
                    
        return detailed_hearings