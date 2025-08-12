"""
GovInfo API client for tracking Federal Register rules (proposed and final).
Focuses on binary events for options trading opportunities.
"""
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from models import FederalRule, RuleType, RINTracking
import os
import logging
import re

logger = logging.getLogger(__name__)


class GovInfoAPIClient:
    """Client for GovInfo API - Federal Register and regulatory documents"""
    
    BASE_URL = "https://api.govinfo.gov"
    
    # High-impact agencies for investment decisions
    KEY_AGENCIES = [
        "Securities and Exchange Commission",
        "Federal Reserve System",
        "Department of the Treasury",
        "Environmental Protection Agency",
        "Food and Drug Administration",
        "Commodity Futures Trading Commission",
        "Consumer Financial Protection Bureau",
        "Department of Energy",
        "Federal Trade Commission",
        "Department of Health and Human Services"
    ]
    
    # Keywords that signal material regulatory changes
    MATERIAL_KEYWORDS = [
        "disclosure", "reporting requirements", "capital requirements",
        "margin requirements", "liquidity", "stress test",
        "emissions", "climate", "carbon",
        "approval", "ban", "restriction", "prohibition",
        "merger", "acquisition", "antitrust",
        "tax", "tariff", "duty",
        "drug approval", "clinical trial",
        "interest rate", "monetary policy"
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOVINFO_API_KEY", "DEMO_KEY")
        self.session = None
        
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict:
        """Make authenticated request to GovInfo API"""
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
            logger.error(f"GovInfo API request failed: {e}")
            raise
    
    async def watch_federal_rules(
        self,
        rule_type: str = "all",  # "proposed", "final", or "all"
        agencies: Optional[List[str]] = None,
        days_ahead: int = 30,
        days_back: int = 7
    ) -> List[FederalRule]:
        """
        Watch for Federal Register rules, both proposed and final.
        Proposed rules create binary events for options trading.
        
        Args:
            rule_type: Type of rules to fetch
            agencies: List of agencies to filter (defaults to KEY_AGENCIES)
            days_ahead: Days to look ahead for comment deadlines
            days_back: Days to look back for recent rules
        
        Returns:
            List of material rules with options opportunity flags
        """
        agencies = agencies or self.KEY_AGENCIES
        rules = []
        
        # Calculate date range
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        # Use the published endpoint for date-based queries
        endpoint = f"/published/{start_date}/{end_date}"
        params = {
            "offsetMark": "*",
            "pageSize": 100,
            "collection": "FR"  # Federal Register
        }
        
        data = await self._make_request(endpoint, params)
        
        for package in data.get("packages", []):
            package_id = package.get("packageId")
            
            # Get package details
            detail_endpoint = f"/packages/{package_id}/summary"
            detail_data = await self._make_request(detail_endpoint)
            
            # Parse rule from detail
            rule = await self._parse_federal_register_document(detail_data)
            
            if rule and self._is_material_rule(rule, rule_type, agencies):
                rules.append(rule)
        
        # Also search for specific document types
        if rule_type in ["proposed", "all"]:
            rules.extend(await self._search_proposed_rules(agencies, days_ahead))
        
        if rule_type in ["final", "all"]:
            rules.extend(await self._search_final_rules(agencies, days_back))
        
        # Deduplicate by document number
        seen = set()
        unique_rules = []
        for rule in rules:
            if rule.document_number not in seen:
                seen.add(rule.document_number)
                unique_rules.append(rule)
        
        return unique_rules
    
    async def track_rin_lifecycle(
        self,
        agency: Optional[str] = None,
        priority_only: bool = True
    ) -> List[RINTracking]:
        """
        Track Regulation Identifier Numbers through their lifecycle.
        Provides 6-18 month visibility into regulatory pipeline.
        
        Args:
            agency: Specific agency to track
            priority_only: Only track economically significant rules
        
        Returns:
            List of RINs with timeline and options windows
        """
        rins = []
        
        # This would typically integrate with Reginfo.gov API
        # For now, we'll search Federal Register for RIN references
        endpoint = "/search"
        
        search_query = "RIN"
        if agency:
            search_query += f" AND {agency}"
        if priority_only:
            search_query += " AND (economically significant OR major)"
        
        params = {
            "query": search_query,
            "pageSize": 50,
            "offsetMark": "*",
            "collection": "FR"
        }
        
        # Note: Search endpoint requires POST request
        # For demonstration, using published endpoint instead
        endpoint = f"/published/{datetime.now().strftime('%Y-%m-%d')}/{(datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d')}"
        params = {
            "offsetMark": "*",
            "pageSize": 100,
            "collection": "FR"
        }
        
        data = await self._make_request(endpoint, params)
        
        # Track RINs and their stages
        rin_map = {}
        for package in data.get("packages", []):
            package_id = package.get("packageId")
            detail_endpoint = f"/packages/{package_id}/summary"
            detail_data = await self._make_request(detail_endpoint)
            
            rin = self._extract_rin(detail_data)
            if rin:
                if rin not in rin_map:
                    rin_map[rin] = RINTracking(
                        rin=rin,
                        agency=self._extract_agency_from_package(detail_data),
                        title=detail_data.get("title", ""),
                        stage=self._determine_rin_stage(detail_data),
                        priority=self._determine_priority(detail_data),
                        published_date=datetime.fromisoformat(detail_data.get("dateIssued", "").replace("Z", "+00:00")) if detail_data.get("dateIssued") else None,
                        proposed_date=None,
                        final_date=None,
                        timeline_milestones=[],
                        affected_industries=self._identify_affected_industries(detail_data),
                        economic_impact=self._estimate_economic_impact(detail_data),
                        materiality_score=self._calculate_rin_materiality(detail_data),
                        options_windows=[]
                    )
                
                # Update timeline based on document type
                rin_tracking = rin_map[rin]
                doc_type = detail_data.get("documentType", "")
                
                if "proposed" in doc_type.lower():
                    rin_tracking.proposed_date = datetime.fromisoformat(detail_data.get("dateIssued", "").replace("Z", "+00:00")) if detail_data.get("dateIssued") else None
                    # Add options window around comment close
                    if detail_data.get("commentCloseDate"):
                        close_date = datetime.fromisoformat(detail_data.get("commentCloseDate", "").replace("Z", "+00:00"))
                        rin_tracking.options_windows.append({
                            "window_type": "comment_close",
                            "date": close_date,
                            "description": "Binary event - comment period close"
                        })
                elif "final" in doc_type.lower():
                    rin_tracking.final_date = datetime.fromisoformat(detail_data.get("dateIssued", "").replace("Z", "+00:00")) if detail_data.get("dateIssued") else None
        
        return list(rin_map.values())
    
    async def _parse_federal_register_document(self, doc_data: Dict) -> Optional[FederalRule]:
        """Parse Federal Register document into FederalRule model"""
        try:
            # Determine rule type
            doc_type = doc_data.get("documentType", "").lower()
            if "proposed" in doc_type:
                rule_type = RuleType.PROPOSED
            elif "final" in doc_type:
                rule_type = RuleType.FINAL
            elif "interim" in doc_type:
                rule_type = RuleType.INTERIM_FINAL
            else:
                rule_type = RuleType.NOTICE
            
            # Extract dates
            pub_date = datetime.fromisoformat(doc_data.get("dateIssued", "").replace("Z", "+00:00")) if doc_data.get("dateIssued") else datetime.now()
            
            # Comment close date for proposed rules
            comment_close = None
            if rule_type == RuleType.PROPOSED and doc_data.get("commentCloseDate"):
                comment_close = datetime.fromisoformat(doc_data.get("commentCloseDate", "").replace("Z", "+00:00"))
            
            # Effective date for final rules
            effective_date = None
            if rule_type == RuleType.FINAL and doc_data.get("effectiveDate"):
                effective_date = datetime.fromisoformat(doc_data.get("effectiveDate", "").replace("Z", "+00:00"))
            
            # Calculate materiality
            materiality_score = self._calculate_rule_materiality(doc_data, rule_type)
            
            # Determine if this creates a binary event for options
            binary_event = (rule_type == RuleType.PROPOSED and comment_close is not None)
            options_opportunity = binary_event and materiality_score >= 7.0
            
            rule = FederalRule(
                document_number=doc_data.get("documentNumber", ""),
                rule_type=rule_type,
                title=doc_data.get("title", ""),
                agency=self._extract_agency_from_package(doc_data),
                rin=self._extract_rin(doc_data),
                publication_date=pub_date,
                effective_date=effective_date,
                comment_close_date=comment_close,
                summary=doc_data.get("summary", ""),
                affected_industries=self._identify_affected_industries(doc_data),
                cfr_references=self._extract_cfr_references(doc_data),
                materiality_score=materiality_score,
                binary_event=binary_event,
                options_opportunity=options_opportunity,
                federal_register_url=doc_data.get("detailsLink", "")
            )
            
            return rule
        except Exception as e:
            logger.error(f"Error parsing Federal Register document: {e}")
            return None
    
    async def _search_proposed_rules(self, agencies: List[str], days_ahead: int) -> List[FederalRule]:
        """Search specifically for proposed rules with upcoming comment deadlines"""
        rules = []
        
        # Search for proposed rules
        # Note: In production, would use the search API with POST request
        # For now, using date-based search
        end_date = datetime.now() + timedelta(days=days_ahead)
        
        for agency in agencies:
            # Would search by agency and document type
            # Simplified implementation
            pass
        
        return rules
    
    async def _search_final_rules(self, agencies: List[str], days_back: int) -> List[FederalRule]:
        """Search for recently published final rules"""
        rules = []
        
        # Search for final rules
        # Similar to proposed rules search
        start_date = datetime.now() - timedelta(days=days_back)
        
        for agency in agencies:
            # Would search by agency and document type
            # Simplified implementation
            pass
        
        return rules
    
    def _is_material_rule(self, rule: FederalRule, rule_type: str, agencies: List[str]) -> bool:
        """Determine if a rule is material for investment decisions"""
        # Filter by rule type
        if rule_type != "all":
            if rule_type == "proposed" and rule.rule_type != RuleType.PROPOSED:
                return False
            if rule_type == "final" and rule.rule_type != RuleType.FINAL:
                return False
        
        # Filter by agency
        if agencies and not any(agency.lower() in rule.agency.lower() for agency in agencies):
            return False
        
        # Materiality threshold
        return rule.materiality_score >= 5.0
    
    def _calculate_rule_materiality(self, doc_data: Dict, rule_type: RuleType) -> float:
        """Calculate materiality score for a rule (0-10)"""
        score = 0.0
        
        # Agency importance
        agency = self._extract_agency_from_package(doc_data)
        if any(key_agency.lower() in agency.lower() for key_agency in self.KEY_AGENCIES):
            score += 3.0
        
        # Rule type scoring
        if rule_type == RuleType.FINAL:
            score += 2.0  # Final rules have immediate impact
        elif rule_type == RuleType.PROPOSED:
            score += 1.5  # Proposed rules create options opportunities
        
        # Title and summary keyword matching
        text = (doc_data.get("title", "") + " " + doc_data.get("summary", "")).lower()
        keyword_matches = sum(1 for kw in self.MATERIAL_KEYWORDS if kw in text)
        score += min(keyword_matches * 0.5, 3.0)
        
        # Economic significance
        if "economically significant" in text or "major rule" in text:
            score += 2.0
        
        # Comment period for proposed rules (shorter = more urgent)
        if rule_type == RuleType.PROPOSED and doc_data.get("commentCloseDate"):
            try:
                close_date = datetime.fromisoformat(doc_data.get("commentCloseDate", "").replace("Z", "+00:00"))
                days_to_close = (close_date - datetime.now()).days
                if days_to_close <= 30:
                    score += 1.0  # Near-term catalyst
            except:
                pass
        
        return min(score, 10.0)
    
    def _extract_agency_from_package(self, doc_data: Dict) -> str:
        """Extract agency name from package data"""
        # Try multiple fields
        agency = doc_data.get("agency", "")
        if not agency:
            agency = doc_data.get("issuingAgency", "")
        if not agency:
            # Parse from title
            title = doc_data.get("title", "")
            for key_agency in self.KEY_AGENCIES:
                if key_agency.lower() in title.lower():
                    return key_agency
        return agency or "Unknown Agency"
    
    def _extract_rin(self, doc_data: Dict) -> Optional[str]:
        """Extract RIN from document data"""
        # Look for RIN in various fields
        rin = doc_data.get("rin", "")
        if not rin:
            # Try to extract from text
            text = doc_data.get("summary", "") + " " + doc_data.get("title", "")
            rin_match = re.search(r'\b\d{4}-[A-Z]{2}\d{2}\b', text)
            if rin_match:
                rin = rin_match.group(0)
        return rin if rin else None
    
    def _identify_affected_industries(self, doc_data: Dict) -> List[str]:
        """Identify industries affected by the rule"""
        industries = []
        text = (doc_data.get("title", "") + " " + doc_data.get("summary", "")).lower()
        
        industry_keywords = {
            "Banking": ["bank", "deposit", "lending", "credit"],
            "Securities": ["securities", "exchange", "broker", "dealer"],
            "Insurance": ["insurance", "underwriting", "actuarial"],
            "Energy": ["energy", "oil", "gas", "renewable", "electricity"],
            "Healthcare": ["health", "medical", "drug", "pharmaceutical", "hospital"],
            "Technology": ["technology", "software", "data", "cyber", "digital"],
            "Manufacturing": ["manufacturing", "production", "industrial"],
            "Transportation": ["transportation", "airline", "railroad", "trucking", "shipping"],
            "Real Estate": ["real estate", "mortgage", "housing", "property"],
            "Telecommunications": ["telecommunications", "broadband", "wireless", "spectrum"]
        }
        
        for industry, keywords in industry_keywords.items():
            if any(kw in text for kw in keywords):
                industries.append(industry)
        
        return industries
    
    def _extract_cfr_references(self, doc_data: Dict) -> List[str]:
        """Extract CFR (Code of Federal Regulations) references"""
        cfr_refs = []
        text = doc_data.get("summary", "") + " " + doc_data.get("title", "")
        
        # Look for CFR patterns (e.g., "17 CFR 240")
        cfr_matches = re.findall(r'\b\d{1,2}\s+CFR\s+[\d.]+\b', text)
        cfr_refs.extend(cfr_matches)
        
        return list(set(cfr_refs))
    
    def _determine_rin_stage(self, doc_data: Dict) -> str:
        """Determine current stage of RIN in regulatory process"""
        doc_type = doc_data.get("documentType", "").lower()
        
        if "advance notice" in doc_type or "anprm" in doc_type:
            return "Advance Notice"
        elif "proposed" in doc_type or "nprm" in doc_type:
            return "Proposed Rule"
        elif "interim final" in doc_type:
            return "Interim Final Rule"
        elif "final" in doc_type:
            return "Final Rule"
        elif "withdrawal" in doc_type:
            return "Withdrawn"
        else:
            return "Notice"
    
    def _determine_priority(self, doc_data: Dict) -> str:
        """Determine regulatory priority level"""
        text = (doc_data.get("title", "") + " " + doc_data.get("summary", "")).lower()
        
        if "economically significant" in text:
            return "Economically Significant"
        elif "significant" in text or "major" in text:
            return "Other Significant"
        else:
            return "Routine"
    
    def _estimate_economic_impact(self, doc_data: Dict) -> Optional[float]:
        """Estimate economic impact in millions"""
        text = doc_data.get("summary", "")
        
        # Look for dollar amounts
        impact_match = re.search(r'\$\s*([\d,]+)\s*(million|billion)', text, re.IGNORECASE)
        if impact_match:
            amount = float(impact_match.group(1).replace(",", ""))
            if "billion" in impact_match.group(2).lower():
                amount *= 1000
            return amount
        
        return None
    
    def _calculate_rin_materiality(self, doc_data: Dict) -> float:
        """Calculate materiality score for RIN tracking"""
        # Use same logic as rule materiality
        return self._calculate_rule_materiality(doc_data, RuleType.PROPOSED)