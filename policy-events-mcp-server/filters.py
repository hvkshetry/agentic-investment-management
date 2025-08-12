"""
Materiality filtering logic for policy events.
Scores events to filter out 95% of noise and focus on market-moving signals.
"""
from typing import Dict, List, Any
from models import (
    CongressionalBill, CommitteeMeeting, FederalRule,
    CongressionalTrade, KeyNomination, RINTracking,
    MaterialityLevel, RuleType
)
import re


class MaterialityScorer:
    """Score materiality of policy events for investment impact"""
    
    # High-impact keywords that signal material changes
    MATERIAL_KEYWORDS = {
        "tax": 3.0,
        "appropriation": 2.5,
        "budget": 2.5,
        "reform": 2.0,
        "emergency": 3.0,
        "stimulus": 3.0,
        "tariff": 2.5,
        "sanction": 2.5,
        "merger": 2.0,
        "acquisition": 2.0,
        "antitrust": 2.5,
        "disclosure": 2.0,
        "capital requirement": 3.0,
        "margin requirement": 2.5,
        "liquidity": 2.0,
        "stress test": 2.5,
        "emissions": 2.0,
        "climate": 2.0,
        "carbon": 2.0,
        "approval": 2.0,
        "ban": 3.0,
        "restriction": 2.5,
        "prohibition": 3.0,
        "interest rate": 3.0,
        "monetary policy": 3.0,
        "quantitative": 2.5,
        "inflation": 2.5,
        "recession": 3.0
    }
    
    # High-impact agencies
    MATERIAL_AGENCIES = {
        "federal reserve": 3.0,
        "securities and exchange commission": 2.5,
        "sec": 2.5,
        "treasury": 2.5,
        "commodity futures trading commission": 2.0,
        "cftc": 2.0,
        "environmental protection agency": 2.0,
        "epa": 2.0,
        "food and drug administration": 2.0,
        "fda": 2.0,
        "federal trade commission": 1.5,
        "ftc": 1.5,
        "department of energy": 1.5,
        "consumer financial protection bureau": 1.5,
        "cfpb": 1.5
    }
    
    # Key committees with market impact
    MATERIAL_COMMITTEES = {
        "finance": 3.0,
        "banking": 3.0,
        "ways and means": 3.0,
        "appropriations": 2.5,
        "budget": 2.5,
        "energy and commerce": 2.0,
        "financial services": 3.0,
        "health": 2.0
    }
    
    def score_bill(self, bill: CongressionalBill) -> float:
        """Score a congressional bill for materiality (0-10)"""
        score = 0.0
        
        # Committee importance
        for committee in bill.committees:
            for key, value in self.MATERIAL_COMMITTEES.items():
                if key in committee.lower():
                    score += value
                    break
        
        # Title and summary keywords
        text = f"{bill.title} {bill.summary or ''}".lower()
        for keyword, value in self.MATERIAL_KEYWORDS.items():
            if keyword in text:
                score += value
        
        # Status progression (closer to law = more material)
        status_scores = {
            "INTRODUCED": 0.5,
            "IN_COMMITTEE": 1.0,
            "REPORTED": 2.0,
            "PASSED_HOUSE": 3.0,
            "PASSED_SENATE": 3.0,
            "ENACTED": 4.0
        }
        score += status_scores.get(bill.status.value, 0)
        
        # Multiple affected sectors = broader impact
        score += len(bill.affected_sectors) * 0.5
        
        return min(score, 10.0)
    
    def score_hearing(self, hearing: CommitteeMeeting) -> float:
        """Score a committee hearing for materiality"""
        score = 0.0
        
        # Key officials testifying
        for official in hearing.key_officials:
            official_lower = official.lower()
            if "fed" in official_lower or "federal reserve" in official_lower:
                score += 4.0
            elif "secretary" in official_lower:
                score += 3.0
            elif "ceo" in official_lower:
                score += 2.0
            elif "commissioner" in official_lower:
                score += 2.0
        
        # Committee importance
        committee_lower = hearing.committee.lower()
        for key, value in self.MATERIAL_COMMITTEES.items():
            if key in committee_lower:
                score += value
                break
        
        # Title keywords
        title_lower = hearing.title.lower()
        for keyword, value in self.MATERIAL_KEYWORDS.items():
            if keyword in title_lower:
                score += value * 0.5  # Half weight for title
        
        # Hearing type
        if hearing.meeting_type == "Hearing":
            score += 1.0
        
        return min(score, 10.0)
    
    def score_rule(self, rule: FederalRule) -> float:
        """Score a federal rule for materiality"""
        score = 0.0
        
        # Agency importance
        agency_lower = rule.agency.lower()
        for key, value in self.MATERIAL_AGENCIES.items():
            if key in agency_lower:
                score += value
                break
        
        # Rule type
        if rule.rule_type == RuleType.FINAL:
            score += 2.0  # Final rules have immediate impact
        elif rule.rule_type == RuleType.PROPOSED:
            score += 1.5  # Proposed rules create uncertainty/options plays
        
        # Title and summary keywords
        text = f"{rule.title} {rule.summary or ''}".lower()
        for keyword, value in self.MATERIAL_KEYWORDS.items():
            if keyword in text:
                score += value
        
        # Binary event potential (for options)
        if rule.rule_type == RuleType.PROPOSED and rule.comment_close_date:
            score += 2.0  # Creates known event date
        
        # Industry scope
        if len(rule.affected_industries) == 1:
            score += 1.0  # Focused impact = cleaner trade
        elif len(rule.affected_industries) > 3:
            score += 2.0  # Broad impact
        
        return min(score, 10.0)
    
    def score_trade(self, trade: CongressionalTrade) -> float:
        """Score a congressional trade for materiality"""
        score = 5.0  # Base score for any reported trade
        
        # Transaction size
        avg_amount = (trade.amount_min + trade.amount_max) / 2
        if avg_amount >= 100000:
            score += 2.0
        elif avg_amount >= 50000:
            score += 1.0
        
        # Committee membership relevance
        key_committees = ["banking", "finance", "energy", "health"]
        if any(committee for committee in trade.committees 
               if any(key in committee.lower() for key in key_committees)):
            score += 2.0
        
        # Unusual activity flag
        if trade.unusual_activity:
            score += 2.0
        
        # Buy signals stronger than sells
        if trade.transaction_type.lower() == "buy":
            score += 0.5
        
        return min(score, 10.0)
    
    def score_nomination(self, nomination: KeyNomination) -> float:
        """Score a nomination for materiality"""
        score = 5.0  # Base for any key nomination
        
        position_lower = nomination.position.lower()
        
        # Position importance
        if "chair" in position_lower or "chairman" in position_lower:
            score += 3.0
        elif "governor" in position_lower and "federal reserve" in position_lower:
            score += 3.0
        elif "commissioner" in position_lower:
            score += 2.0
        elif "secretary" in position_lower:
            score += 2.5
        
        # Agency importance
        agency_lower = nomination.agency.lower()
        for key, value in self.MATERIAL_AGENCIES.items():
            if key in agency_lower:
                score += value * 0.5
                break
        
        # Status progression
        if nomination.confirmation_date:
            score += 1.0  # Confirmed = certain
        elif nomination.hearing_date:
            score += 0.5  # In process
        
        return min(score, 10.0)
    
    def score_rin(self, rin: RINTracking) -> float:
        """Score a RIN for materiality"""
        score = 4.0  # Base for tracked RIN
        
        # Agency importance
        agency_lower = rin.agency.lower()
        for key, value in self.MATERIAL_AGENCIES.items():
            if key in agency_lower:
                score += value
                break
        
        # Priority level
        priority_lower = rin.priority.lower()
        if "economically significant" in priority_lower:
            score += 3.0
        elif "significant" in priority_lower:
            score += 2.0
        
        # Title keywords
        title_lower = rin.title.lower()
        for keyword, value in self.MATERIAL_KEYWORDS.items():
            if keyword in title_lower:
                score += value * 0.5
        
        # Stage in process
        stage_lower = rin.stage.lower()
        if "final" in stage_lower:
            score += 2.0
        elif "proposed" in stage_lower:
            score += 1.5
        
        # Economic impact
        if rin.economic_impact and rin.economic_impact >= 100_000_000:
            score += 2.0
        elif rin.economic_impact and rin.economic_impact >= 10_000_000:
            score += 1.0
        
        # Options windows available
        if rin.options_windows:
            score += 1.0
        
        return min(score, 10.0)
    
    def get_level(self, score: float) -> MaterialityLevel:
        """Convert numerical score to materiality level"""
        if score >= 8.0:
            return MaterialityLevel.CRITICAL
        elif score >= 6.0:
            return MaterialityLevel.HIGH
        elif score >= 4.0:
            return MaterialityLevel.MEDIUM
        else:
            return MaterialityLevel.LOW
    
    def filter_events(self, events: List[Any], min_score: float = 5.0) -> List[Any]:
        """Filter events by minimum materiality score"""
        filtered = []
        for event in events:
            if hasattr(event, 'materiality_score'):
                if event.materiality_score >= min_score:
                    filtered.append(event)
            else:
                # Score the event based on type
                score = 0.0
                if isinstance(event, CongressionalBill):
                    score = self.score_bill(event)
                elif isinstance(event, CommitteeMeeting):
                    score = self.score_hearing(event)
                elif isinstance(event, FederalRule):
                    score = self.score_rule(event)
                elif isinstance(event, CongressionalTrade):
                    score = self.score_trade(event)
                elif isinstance(event, KeyNomination):
                    score = self.score_nomination(event)
                elif isinstance(event, RINTracking):
                    score = self.score_rin(event)
                
                if score >= min_score:
                    event.materiality_score = score
                    filtered.append(event)
        
        return filtered