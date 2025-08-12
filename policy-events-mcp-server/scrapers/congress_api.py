"""
Congress.gov API v3 client for tracking material bills, hearings, and nominations.
Free tier: 5,000 requests per hour
"""
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from models import CongressionalBill, CommitteeMeeting, KeyNomination, BillStatus
import os
import logging

logger = logging.getLogger(__name__)


class CongressAPIClient:
    """Client for Congress.gov API v3"""
    
    BASE_URL = "https://api.congress.gov/v3"
    
    # Key committees for investment impact
    KEY_COMMITTEES = {
        "house": [
            "hsif00",  # Energy and Commerce
            "hsba00",  # Financial Services (Banking)
            "hswm00",  # Ways and Means (Tax)
            "hsap00",  # Appropriations
            "hsbu00",  # Budget
        ],
        "senate": [
            "ssfi00",  # Finance
            "ssbk00",  # Banking, Housing, Urban Affairs
            "sseg00",  # Energy and Natural Resources
            "ssap00",  # Appropriations
            "ssbu00",  # Budget
            "sshr00",  # Health, Education, Labor, Pensions
        ]
    }
    
    # Key witness types for hearings
    KEY_WITNESS_POSITIONS = [
        "federal reserve", "fed chair", "fed governor",
        "secretary", "ceo", "chief executive",
        "commissioner", "administrator", "director"
    ]
    
    # Key nomination positions
    KEY_POSITIONS = [
        "Federal Reserve", "Board of Governors",
        "Securities and Exchange Commission",
        "Commodity Futures Trading Commission",
        "Treasury", "Commerce", "Energy"
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CONGRESS_API_KEY", "DEMO_KEY")
        self.session = None
        
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict:
        """Make authenticated request to Congress.gov API"""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)
        
        params = params or {}
        params["api_key"] = self.api_key
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = await self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Congress API request failed: {e}")
            raise
    
    async def track_material_bills(
        self,
        congress: Optional[int] = None,
        days_back: int = 7,
        limit: int = 100
    ) -> List[CongressionalBill]:
        """
        Track material bills from key committees.
        
        Args:
            congress: Congress number (defaults to current)
            days_back: Number of days to look back
            limit: Maximum results
        
        Returns:
            List of material bills with scores
        """
        if not congress:
            # Current congress (118th as of 2024)
            congress = 118
        
        bills = []
        
        # Fetch recent bills
        endpoint = f"/bill/{congress}"
        params = {
            "format": "json",
            "limit": limit,
            "offset": 0
        }
        
        data = await self._make_request(endpoint, params)
        
        for bill_item in data.get("bills", []):
            # Get detailed bill info
            bill_endpoint = f"/bill/{congress}/{bill_item['type'].lower()}/{bill_item['number']}"
            bill_data = await self._make_request(bill_endpoint)
            bill_detail = bill_data.get("bill", {})
            
            # Check if from key committee
            committees = []
            for committee in bill_detail.get("committees", {}).get("item", []):
                committees.append(committee.get("systemCode", ""))
            
            # Calculate materiality
            is_material = any(c in self.KEY_COMMITTEES["house"] + self.KEY_COMMITTEES["senate"] 
                             for c in committees)
            
            if is_material:
                # Map status
                latest_action = bill_detail.get("latestAction", {})
                status = self._map_bill_status(latest_action.get("text", ""))
                
                bill = CongressionalBill(
                    bill_id=f"{bill_item['type']}-{bill_item['number']}",
                    congress=congress,
                    title=bill_detail.get("title", ""),
                    summary=None,  # Would need separate call for summary
                    sponsor=bill_detail.get("sponsors", [{}])[0].get("fullName") if bill_detail.get("sponsors") else None,
                    committees=committees,
                    status=status,
                    status_date=datetime.fromisoformat(latest_action.get("actionDate", "").replace("Z", "+00:00")) if latest_action.get("actionDate") else datetime.now(),
                    affected_sectors=self._identify_sectors(bill_detail.get("title", "")),
                    materiality_score=self._calculate_bill_materiality(bill_detail),
                    last_action=latest_action.get("text"),
                    url=f"https://www.congress.gov/bill/{congress}th-congress/{bill_item['type'].lower().replace('res', '-resolution')}/{bill_item['number']}"
                )
                bills.append(bill)
        
        return bills
    
    async def monitor_key_hearings(
        self,
        congress: Optional[int] = None,
        days_ahead: int = 30,
        chamber: Optional[str] = None
    ) -> List[CommitteeMeeting]:
        """
        Monitor upcoming committee hearings with key witnesses.
        
        Args:
            congress: Congress number
            days_ahead: Days to look ahead
            chamber: 'house', 'senate', or None for both
        
        Returns:
            List of material hearings
        """
        if not congress:
            congress = 118
        
        meetings = []
        chambers = [chamber] if chamber else ["house", "senate"]
        
        for ch in chambers:
            endpoint = f"/committee-meeting/{congress}/{ch}"
            params = {
                "format": "json",
                "limit": 100
            }
            
            data = await self._make_request(endpoint, params)
            
            for meeting_item in data.get("committeeMeetings", []):
                # Get detailed meeting info
                event_id = meeting_item.get("eventId")
                meeting_endpoint = f"/committee-meeting/{congress}/{ch}/{event_id}"
                meeting_data = await self._make_request(meeting_endpoint)
                meeting_detail = meeting_data.get("committeeMeeting", {})
                
                # Check for key witnesses
                witnesses = meeting_detail.get("witnesses", [])
                key_officials = self._identify_key_officials(witnesses)
                
                if key_officials or self._is_key_committee_meeting(meeting_detail):
                    meeting = CommitteeMeeting(
                        event_id=str(event_id),
                        congress=congress,
                        chamber=ch.title(),
                        committee=meeting_detail.get("committees", [{}])[0].get("name", "") if meeting_detail.get("committees") else "",
                        title=meeting_detail.get("title", ""),
                        meeting_date=datetime.fromisoformat(meeting_detail.get("date", "").replace("Z", "+00:00")) if meeting_detail.get("date") else datetime.now(),
                        meeting_type=meeting_detail.get("type", "Hearing"),
                        witnesses=[{"name": w.get("name", ""), "position": w.get("position", "")} 
                                 for w in witnesses],
                        key_officials=key_officials,
                        topics=self._extract_topics(meeting_detail.get("title", "")),
                        affected_sectors=self._identify_sectors(meeting_detail.get("title", "")),
                        materiality_score=self._calculate_hearing_materiality(meeting_detail, key_officials),
                        documents_url=f"https://www.congress.gov/committee-meeting/{congress}/{ch}/{event_id}"
                    )
                    meetings.append(meeting)
        
        return meetings
    
    async def monitor_key_nominations(
        self,
        congress: Optional[int] = None,
        days_back: int = 30
    ) -> List[KeyNomination]:
        """
        Monitor nominations for key financial/regulatory positions.
        
        Args:
            congress: Congress number
            days_back: Days to look back
        
        Returns:
            List of key nominations
        """
        if not congress:
            congress = 118
        
        nominations = []
        endpoint = f"/nomination/{congress}"
        params = {
            "format": "json",
            "limit": 100
        }
        
        data = await self._make_request(endpoint, params)
        
        for nom_item in data.get("nominations", []):
            # Get detailed nomination info
            nom_endpoint = f"/nomination/{congress}/{nom_item['number']}"
            if nom_item.get("part"):
                nom_endpoint += f"/{nom_item['part']}"
            
            nom_data = await self._make_request(nom_endpoint)
            nom_detail = nom_data.get("nomination", {})
            
            # Check if key position
            position = nom_detail.get("description", "")
            if any(key_pos.lower() in position.lower() for key_pos in self.KEY_POSITIONS):
                nomination = KeyNomination(
                    nomination_id=f"{congress}-{nom_item['number']}",
                    nominee_name=nom_detail.get("nominee", {}).get("name", "") if nom_detail.get("nominee") else "Unknown",
                    position=position,
                    agency=self._extract_agency(position),
                    submission_date=datetime.fromisoformat(nom_detail.get("receivedDate", "").replace("Z", "+00:00")) if nom_detail.get("receivedDate") else datetime.now(),
                    committee=nom_detail.get("committee", {}).get("name") if nom_detail.get("committee") else None,
                    hearing_date=None,  # Would need to check hearings
                    confirmation_date=datetime.fromisoformat(nom_detail.get("confirmedDate", "").replace("Z", "+00:00")) if nom_detail.get("confirmedDate") else None,
                    status=nom_detail.get("latestAction", {}).get("text", "") if nom_detail.get("latestAction") else "Pending",
                    policy_implications=self._assess_policy_implications(position),
                    affected_sectors=self._identify_sectors_from_position(position),
                    materiality_score=self._calculate_nomination_materiality(position)
                )
                nominations.append(nomination)
        
        return nominations
    
    def _map_bill_status(self, action_text: str) -> BillStatus:
        """Map action text to bill status"""
        action_lower = action_text.lower()
        if "became public law" in action_lower or "signed by president" in action_lower:
            return BillStatus.ENACTED
        elif "vetoed" in action_lower:
            return BillStatus.VETOED
        elif "passed senate" in action_lower:
            return BillStatus.PASSED_SENATE
        elif "passed house" in action_lower:
            return BillStatus.PASSED_HOUSE
        elif "reported" in action_lower:
            return BillStatus.REPORTED
        elif "referred to" in action_lower or "committee" in action_lower:
            return BillStatus.IN_COMMITTEE
        else:
            return BillStatus.INTRODUCED
    
    def _identify_sectors(self, text: str) -> List[str]:
        """Identify affected sectors from text"""
        sectors = []
        text_lower = text.lower()
        
        sector_keywords = {
            "Technology": ["technology", "tech", "digital", "cyber", "artificial intelligence", "ai"],
            "Finance": ["bank", "financial", "credit", "securities", "investment"],
            "Healthcare": ["health", "medical", "drug", "pharmaceutical", "medicare", "medicaid"],
            "Energy": ["energy", "oil", "gas", "renewable", "climate", "emission"],
            "Defense": ["defense", "military", "national security"],
            "Real Estate": ["housing", "real estate", "mortgage"],
            "Retail": ["retail", "consumer", "commerce"],
            "Transportation": ["transportation", "airline", "railroad", "shipping"]
        }
        
        for sector, keywords in sector_keywords.items():
            if any(kw in text_lower for kw in keywords):
                sectors.append(sector)
        
        return sectors
    
    def _calculate_bill_materiality(self, bill_data: Dict) -> float:
        """Calculate materiality score for a bill (0-10)"""
        score = 0.0
        
        # Committee importance
        committees = bill_data.get("committees", {}).get("item", [])
        for committee in committees:
            if committee.get("systemCode") in self.KEY_COMMITTEES["house"] + self.KEY_COMMITTEES["senate"]:
                score += 2.0
        
        # Bill type (bills more material than resolutions)
        bill_type = bill_data.get("type", "")
        if bill_type in ["HR", "S"]:
            score += 1.0
        
        # Status progression
        latest_action = bill_data.get("latestAction", {}).get("text", "").lower()
        if "passed" in latest_action:
            score += 2.0
        elif "reported" in latest_action:
            score += 1.0
        
        # Title keywords
        title = bill_data.get("title", "").lower()
        material_keywords = ["tax", "appropriation", "budget", "reform", "act of 2024", "emergency"]
        if any(kw in title for kw in material_keywords):
            score += 2.0
        
        return min(score, 10.0)
    
    def _identify_key_officials(self, witnesses: List[Dict]) -> List[str]:
        """Identify key officials from witness list"""
        key_officials = []
        for witness in witnesses:
            position = witness.get("position", "").lower()
            if any(key_pos in position for key_pos in self.KEY_WITNESS_POSITIONS):
                key_officials.append(witness.get("name", ""))
        return key_officials
    
    def _is_key_committee_meeting(self, meeting_data: Dict) -> bool:
        """Check if meeting is from a key committee"""
        committees = meeting_data.get("committees", [])
        for committee in committees:
            if committee.get("systemCode") in self.KEY_COMMITTEES["house"] + self.KEY_COMMITTEES["senate"]:
                return True
        return False
    
    def _extract_topics(self, title: str) -> List[str]:
        """Extract topics from meeting title"""
        # Simple keyword extraction
        topics = []
        keywords = ["monetary policy", "interest rates", "inflation", "fiscal", "budget", 
                   "regulation", "oversight", "investigation", "reform"]
        title_lower = title.lower()
        for kw in keywords:
            if kw in title_lower:
                topics.append(kw.title())
        return topics
    
    def _calculate_hearing_materiality(self, meeting_data: Dict, key_officials: List[str]) -> float:
        """Calculate materiality score for a hearing"""
        score = 0.0
        
        # Key officials present
        score += len(key_officials) * 2.0
        
        # Key committee
        if self._is_key_committee_meeting(meeting_data):
            score += 2.0
        
        # Meeting type
        if meeting_data.get("type") == "Hearing":
            score += 1.0
        
        # Title keywords
        title = meeting_data.get("title", "").lower()
        if any(kw in title for kw in ["federal reserve", "monetary", "sec", "treasury"]):
            score += 3.0
        
        return min(score, 10.0)
    
    def _extract_agency(self, position: str) -> str:
        """Extract agency from position description"""
        for agency in ["Federal Reserve", "SEC", "CFTC", "Treasury", "Commerce", "Energy"]:
            if agency.lower() in position.lower():
                return agency
        return "Unknown"
    
    def _assess_policy_implications(self, position: str) -> List[str]:
        """Assess policy implications of a nomination"""
        implications = []
        position_lower = position.lower()
        
        if "federal reserve" in position_lower:
            implications.append("Monetary policy direction")
            implications.append("Interest rate decisions")
        elif "sec" in position_lower:
            implications.append("Securities regulation")
            implications.append("Market structure")
        elif "treasury" in position_lower:
            implications.append("Fiscal policy")
            implications.append("Tax policy")
        
        return implications
    
    def _identify_sectors_from_position(self, position: str) -> List[str]:
        """Identify affected sectors from government position"""
        sectors = []
        position_lower = position.lower()
        
        if "federal reserve" in position_lower:
            sectors.extend(["Finance", "Real Estate"])
        elif "sec" in position_lower or "cftc" in position_lower:
            sectors.append("Finance")
        elif "energy" in position_lower:
            sectors.append("Energy")
        elif "commerce" in position_lower:
            sectors.extend(["Technology", "Retail"])
        
        return sectors
    
    def _calculate_nomination_materiality(self, position: str) -> float:
        """Calculate materiality score for a nomination"""
        score = 5.0  # Base score for any key nomination
        
        position_lower = position.lower()
        if "chair" in position_lower or "governor" in position_lower:
            score += 3.0
        elif "commissioner" in position_lower:
            score += 2.0
        
        if "federal reserve" in position_lower:
            score += 2.0
        
        return min(score, 10.0)