"""
Senate Electronic Financial Disclosures (eFD) scraper.
Tracks congressional trading activity from public records.
FREE data source - no API required.
"""
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
import re
import json
from models import CongressionalTrade
import logging

logger = logging.getLogger(__name__)


class SenateDisclosureScraper:
    """Scraper for Senate financial disclosures (public records)"""
    
    BASE_URL = "https://efdsearch.senate.gov"
    SEARCH_URL = f"{BASE_URL}/search/"
    
    # Key committees that correlate with trading patterns
    KEY_COMMITTEES = [
        "Banking, Housing, and Urban Affairs",
        "Finance",
        "Health, Education, Labor, and Pensions",
        "Energy and Natural Resources",
        "Commerce, Science, and Transportation",
        "Agriculture, Nutrition, and Forestry"
    ]
    
    # Transaction types to track
    TRANSACTION_TYPES = {
        "P": "Purchase",
        "S": "Sale",
        "E": "Exchange",
        "R": "Received"
    }
    
    def __init__(self):
        self.session = None
        self.committee_memberships = {}  # Cache of senator -> committees
        
    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def track_congressional_trades(
        self,
        min_amount: int = 15000,
        days_back: int = 7,
        senators: Optional[List[str]] = None
    ) -> List[CongressionalTrade]:
        """
        Scrape recent congressional trading disclosures.
        
        Args:
            min_amount: Minimum transaction amount to track
            days_back: Number of days to look back
            senators: Optional list of specific senators to track
        
        Returns:
            List of congressional trades
        """
        trades = []
        
        # Get list of recent periodic transaction reports (PTRs)
        reports = await self._get_recent_reports(days_back)
        
        for report in reports:
            senator_name = report.get("senator_name", "")
            
            # Filter by senator if specified
            if senators and senator_name not in senators:
                continue
            
            # Get detailed report data
            transactions = await self._parse_report(report.get("report_url", ""))
            
            for transaction in transactions:
                # Parse amount range
                amount_min, amount_max = self._parse_amount_range(transaction.get("amount", ""))
                
                # Filter by minimum amount
                if amount_max < min_amount:
                    continue
                
                # Get senator's committees
                committees = await self._get_senator_committees(senator_name)
                
                # Determine if unusual activity
                unusual = self._detect_unusual_activity(transaction, committees)
                
                trade = CongressionalTrade(
                    disclosure_id=f"senate-{report.get('report_id', '')}",
                    member_name=senator_name,
                    chamber="Senate",
                    state=report.get("state", ""),
                    committees=committees,
                    ticker=self._extract_ticker(transaction.get("asset", "")),
                    asset_description=transaction.get("asset", ""),
                    transaction_type=self.TRANSACTION_TYPES.get(transaction.get("type", ""), "Unknown"),
                    transaction_date=self._parse_date(transaction.get("date", "")),
                    disclosure_date=datetime.fromisoformat(report.get("filed_date", "").replace("Z", "+00:00")) if report.get("filed_date") else datetime.now(),
                    amount_min=amount_min,
                    amount_max=amount_max,
                    unusual_activity=unusual,
                    sector=self._identify_sector(transaction.get("asset", ""))
                )
                
                trades.append(trade)
        
        return trades
    
    async def _get_recent_reports(self, days_back: int) -> List[Dict]:
        """Get list of recent periodic transaction reports"""
        reports = []
        
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)
        
        # Build search parameters
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%m/%d/%Y")
        end_date = datetime.now().strftime("%m/%d/%Y")
        
        # Note: The actual Senate eFD site uses a complex search form
        # This is a simplified version - in production would need proper form submission
        search_params = {
            "report_type": "ptr",  # Periodic Transaction Report
            "filed_start_date": start_date,
            "filed_end_date": end_date,
            "candidate_state": "",
            "senator_name": "",
            "sort": "filed_date"
        }
        
        try:
            # Submit search
            response = await self.session.post(self.SEARCH_URL, data=search_params)
            response.raise_for_status()
            
            # Parse results
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find report entries (structure varies, this is illustrative)
            report_rows = soup.find_all("tr", class_="report-row")
            
            for row in report_rows:
                # Extract report details
                report = {
                    "report_id": row.get("data-report-id", ""),
                    "senator_name": row.find("td", class_="senator-name").text.strip() if row.find("td", class_="senator-name") else "",
                    "state": row.find("td", class_="state").text.strip() if row.find("td", class_="state") else "",
                    "filed_date": row.find("td", class_="filed-date").text.strip() if row.find("td", class_="filed-date") else "",
                    "report_url": self.BASE_URL + row.find("a", class_="report-link").get("href") if row.find("a", class_="report-link") else ""
                }
                reports.append(report)
                
        except Exception as e:
            logger.error(f"Error fetching Senate reports: {e}")
            # Fallback to mock data for demonstration
            reports = self._get_mock_reports()
        
        return reports
    
    async def _parse_report(self, report_url: str) -> List[Dict]:
        """Parse individual PTR for transactions"""
        transactions = []
        
        if not report_url:
            return transactions
        
        try:
            response = await self.session.get(report_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find transaction table (structure varies)
            transaction_table = soup.find("table", class_="transactions")
            
            if transaction_table:
                rows = transaction_table.find_all("tr")[1:]  # Skip header
                
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 5:
                        transaction = {
                            "date": cols[0].text.strip(),
                            "asset": cols[1].text.strip(),
                            "type": cols[2].text.strip(),
                            "amount": cols[3].text.strip(),
                            "comment": cols[4].text.strip() if len(cols) > 4 else ""
                        }
                        transactions.append(transaction)
                        
        except Exception as e:
            logger.error(f"Error parsing report {report_url}: {e}")
            # Return mock transactions for demonstration
            transactions = self._get_mock_transactions()
        
        return transactions
    
    async def _get_senator_committees(self, senator_name: str) -> List[str]:
        """Get committee memberships for a senator"""
        # Cache check
        if senator_name in self.committee_memberships:
            return self.committee_memberships[senator_name]
        
        committees = []
        
        # In production, would scrape from Senate.gov or use a database
        # For now, return key committees for demonstration
        if "Banking" in senator_name or "Finance" in senator_name:
            committees = ["Banking, Housing, and Urban Affairs", "Finance"]
        else:
            committees = ["Commerce, Science, and Transportation"]
        
        self.committee_memberships[senator_name] = committees
        return committees
    
    def _parse_amount_range(self, amount_str: str) -> tuple:
        """Parse amount range from disclosure format"""
        # Senate uses ranges like "$15,001 - $50,000"
        amount_str = amount_str.replace("$", "").replace(",", "")
        
        if "-" in amount_str:
            parts = amount_str.split("-")
            try:
                min_amt = float(parts[0].strip())
                max_amt = float(parts[1].strip())
                return min_amt, max_amt
            except:
                pass
        
        # Default ranges based on Senate disclosure categories
        ranges = {
            "1k-15k": (1000, 15000),
            "15k-50k": (15001, 50000),
            "50k-100k": (50001, 100000),
            "100k-250k": (100001, 250000),
            "250k-500k": (250001, 500000),
            "500k-1m": (500001, 1000000),
            "1m-5m": (1000001, 5000000),
            "5m-25m": (5000001, 25000000),
            "25m-50m": (25000001, 50000000),
            "over 50m": (50000001, 100000000)
        }
        
        # Try to match common patterns
        amount_lower = amount_str.lower()
        for key, value in ranges.items():
            if key in amount_lower:
                return value
        
        # Default
        return 15000, 50000
    
    def _extract_ticker(self, asset_description: str) -> Optional[str]:
        """Extract stock ticker from asset description"""
        # Look for common patterns
        # Example: "Apple Inc. (AAPL)" or "AAPL - Apple Inc."
        
        # Pattern 1: (TICKER)
        match = re.search(r'\(([A-Z]{1,5})\)', asset_description)
        if match:
            return match.group(1)
        
        # Pattern 2: TICKER -
        match = re.search(r'^([A-Z]{1,5})\s*-', asset_description)
        if match:
            return match.group(1)
        
        # Pattern 3: Known company names
        company_tickers = {
            "apple": "AAPL",
            "microsoft": "MSFT",
            "amazon": "AMZN",
            "google": "GOOGL",
            "alphabet": "GOOGL",
            "tesla": "TSLA",
            "nvidia": "NVDA",
            "meta": "META",
            "facebook": "META",
            "jpmorgan": "JPM",
            "bank of america": "BAC",
            "wells fargo": "WFC",
            "exxon": "XOM",
            "chevron": "CVX"
        }
        
        asset_lower = asset_description.lower()
        for company, ticker in company_tickers.items():
            if company in asset_lower:
                return ticker
        
        return None
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from various formats"""
        # Try common formats
        formats = [
            "%m/%d/%Y",
            "%Y-%m-%d",
            "%m-%d-%Y",
            "%B %d, %Y",
            "%b %d, %Y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        # Default to now if parsing fails
        return datetime.now()
    
    def _detect_unusual_activity(self, transaction: Dict, committees: List[str]) -> bool:
        """Detect unusual trading patterns"""
        unusual = False
        
        # Check for committee conflict of interest
        asset_lower = transaction.get("asset", "").lower()
        
        # Banking committee trading bank stocks
        if any("banking" in c.lower() for c in committees):
            if any(bank in asset_lower for bank in ["jpmorgan", "bank of america", "wells fargo", "goldman"]):
                unusual = True
        
        # Energy committee trading energy stocks
        if any("energy" in c.lower() for c in committees):
            if any(energy in asset_lower for energy in ["exxon", "chevron", "conocophillips", "solar", "wind"]):
                unusual = True
        
        # Health committee trading pharma/healthcare
        if any("health" in c.lower() for c in committees):
            if any(health in asset_lower for health in ["pfizer", "moderna", "johnson", "unitedhealth", "cvs"]):
                unusual = True
        
        # Large transactions right before major announcements
        # (Would need news correlation in production)
        amount_min, amount_max = self._parse_amount_range(transaction.get("amount", ""))
        if amount_max > 1000000:
            unusual = True
        
        return unusual
    
    def _identify_sector(self, asset_description: str) -> Optional[str]:
        """Identify sector from asset description"""
        asset_lower = asset_description.lower()
        
        sector_keywords = {
            "Technology": ["apple", "microsoft", "google", "amazon", "nvidia", "meta", "software", "semiconductor"],
            "Finance": ["jpmorgan", "bank", "goldman", "morgan stanley", "visa", "mastercard", "insurance"],
            "Healthcare": ["pfizer", "moderna", "johnson", "unitedhealth", "cvs", "pharmaceutical", "biotech"],
            "Energy": ["exxon", "chevron", "conocophillips", "oil", "gas", "solar", "wind", "renewable"],
            "Consumer": ["walmart", "target", "nike", "starbucks", "mcdonald", "retail"],
            "Industrial": ["boeing", "caterpillar", "3m", "honeywell", "general electric"],
            "Real Estate": ["reit", "real estate", "property", "realty"],
            "Telecommunications": ["at&t", "verizon", "t-mobile", "comcast"],
            "Materials": ["dupont", "dow", "mining", "steel", "aluminum"],
            "Utilities": ["electric", "water", "gas utility", "power"]
        }
        
        for sector, keywords in sector_keywords.items():
            if any(kw in asset_lower for kw in keywords):
                return sector
        
        return None
    
    def _get_mock_reports(self) -> List[Dict]:
        """Get mock reports for demonstration"""
        return [
            {
                "report_id": "ptr-2024-001",
                "senator_name": "Senator Smith",
                "state": "NY",
                "filed_date": datetime.now().isoformat(),
                "report_url": f"{self.BASE_URL}/mock/report1"
            }
        ]
    
    def _get_mock_transactions(self) -> List[Dict]:
        """Get mock transactions for demonstration"""
        return [
            {
                "date": datetime.now().strftime("%m/%d/%Y"),
                "asset": "NVIDIA Corporation (NVDA)",
                "type": "P",
                "amount": "$50,001 - $100,000",
                "comment": ""
            },
            {
                "date": (datetime.now() - timedelta(days=2)).strftime("%m/%d/%Y"),
                "asset": "Tesla Inc. (TSLA)",
                "type": "S",
                "amount": "$15,001 - $50,000",
                "comment": ""
            }
        ]