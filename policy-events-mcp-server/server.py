"""
Policy Events MCP Server - High ROI government data for investment decisions.
Provides material events only (95% noise reduction) from Congress, Federal Register, and disclosures.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path

from fastmcp import FastMCP
from pydantic import Field

# Import our models
from models import (
    CongressionalBill, CommitteeMeeting, FederalRule, 
    CongressionalTrade, KeyNomination, RINTracking,
    PolicyEvent, MaterialityLevel, MaterialityFilter
)

# Import scrapers
from scrapers.congress_api import CongressAPIClient
from scrapers.govinfo_api import GovInfoAPIClient
from scrapers.senate_disclosures import SenateDisclosureScraper

# Import filters and cache
from filters import MaterialityScorer
from cache import EventCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="policy-events-service",
    version="1.0.0"
)

# Initialize clients and cache
congress_client = CongressAPIClient()
govinfo_client = GovInfoAPIClient()
senate_scraper = SenateDisclosureScraper()
materiality_scorer = MaterialityScorer()
event_cache = EventCache()


@mcp.tool()
async def track_material_bills(
    congress: Optional[int] = Field(None, description="Congress number (defaults to current 118)"),
    days_back: int = Field(7, description="Number of days to look back"),
    min_materiality: float = Field(5.0, description="Minimum materiality score (0-10)")
) -> List[Dict[str, Any]]:
    """
    Track material congressional bills from key committees.
    Filters for Finance, Banking, Energy, Health, Ways & Means committees.
    Returns bills that impact specific sectors with status changes.
    """
    try:
        async with congress_client:
            bills = await congress_client.track_material_bills(
                congress=congress,
                days_back=days_back
            )
        
        # Filter by materiality
        material_bills = [
            bill for bill in bills 
            if bill.materiality_score >= min_materiality
        ]
        
        # Check cache for duplicates
        unique_bills = []
        for bill in material_bills:
            if not event_cache.is_duplicate("bill", bill.bill_id):
                unique_bills.append(bill)
                event_cache.add_event("bill", bill.bill_id)
        
        # Convert to PolicyEvent format
        events = []
        for bill in unique_bills:
            event = PolicyEvent(
                event_id=f"bill_{bill.bill_id}",
                event_type="bill",
                timestamp=bill.status_date,
                materiality=materiality_scorer.get_level(bill.materiality_score),
                materiality_score=bill.materiality_score,
                title=f"Bill {bill.bill_id}: {bill.title}",
                summary=bill.summary,
                affected_sectors=bill.affected_sectors,
                affected_tickers=[],  # Would need sector-to-ticker mapping
                recommended_agents=_recommend_agents_for_bill(bill),
                time_sensitivity="medium" if bill.status in ["PASSED_HOUSE", "PASSED_SENATE"] else "low",
                binary_event_date=None,
                options_opportunity=False,
                data=bill.model_dump(),
                source_url=bill.url
            )
            events.append(event.model_dump())
        
        logger.info(f"Found {len(events)} material bills out of {len(bills)} total")
        return events
        
    except Exception as e:
        logger.error(f"Error tracking material bills: {e}")
        raise


@mcp.tool()
async def monitor_key_hearings(
    congress: Optional[int] = Field(None, description="Congress number (defaults to current 118)"),
    days_ahead: int = Field(30, description="Days to look ahead for scheduled hearings"),
    chamber: Optional[str] = Field(None, description="'house', 'senate', or None for both")
) -> List[Dict[str, Any]]:
    """
    Monitor upcoming committee hearings with key witnesses.
    Focuses on Fed officials, Fortune 500 CEOs, Cabinet members.
    Returns hearings that could move markets.
    """
    try:
        async with congress_client:
            hearings = await congress_client.monitor_key_hearings(
                congress=congress,
                days_ahead=days_ahead,
                chamber=chamber
            )
        
        # Filter for truly material hearings
        material_hearings = [
            hearing for hearing in hearings
            if hearing.materiality_score >= 6.0 or len(hearing.key_officials) > 0
        ]
        
        # Check cache
        unique_hearings = []
        for hearing in material_hearings:
            if not event_cache.is_duplicate("hearing", hearing.event_id):
                unique_hearings.append(hearing)
                event_cache.add_event("hearing", hearing.event_id)
        
        # Convert to PolicyEvent format
        events = []
        for hearing in unique_hearings:
            # Check if creates binary event (Fed testimony often does)
            is_fed_hearing = any("federal reserve" in official.lower() 
                                for official in hearing.key_officials)
            
            event = PolicyEvent(
                event_id=f"hearing_{hearing.event_id}",
                event_type="hearing",
                timestamp=hearing.meeting_date,
                materiality=materiality_scorer.get_level(hearing.materiality_score),
                materiality_score=hearing.materiality_score,
                title=hearing.title,
                summary=f"{hearing.committee} hearing with {', '.join(hearing.key_officials[:3])}",
                affected_sectors=hearing.affected_sectors,
                affected_tickers=[],
                recommended_agents=_recommend_agents_for_hearing(hearing),
                time_sensitivity="high" if hearing.meeting_date < datetime.now() + timedelta(days=7) else "medium",
                binary_event_date=hearing.meeting_date if is_fed_hearing else None,
                options_opportunity=is_fed_hearing,
                data=hearing.model_dump(),
                source_url=hearing.documents_url
            )
            events.append(event.model_dump())
        
        logger.info(f"Found {len(events)} key hearings with material witnesses")
        return events
        
    except Exception as e:
        logger.error(f"Error monitoring key hearings: {e}")
        raise


@mcp.tool()
async def watch_federal_rules(
    rule_type: str = Field("all", description="'proposed', 'final', or 'all'"),
    agencies: Optional[List[str]] = Field(None, description="List of agencies to filter"),
    days_ahead: int = Field(30, description="Days ahead for comment deadlines"),
    days_back: int = Field(7, description="Days back for recent rules")
) -> List[Dict[str, Any]]:
    """
    Watch Federal Register for proposed and final rules.
    Proposed rules create binary events (comment deadlines) for options plays.
    Final rules signal compliance costs and sector impacts.
    """
    try:
        async with govinfo_client:
            rules = await govinfo_client.watch_federal_rules(
                rule_type=rule_type,
                agencies=agencies,
                days_ahead=days_ahead,
                days_back=days_back
            )
        
        # Score and filter for materiality
        material_rules = []
        for rule in rules:
            rule.materiality_score = materiality_scorer.score_rule(rule)
            if rule.materiality_score >= 5.0:
                # Flag binary events for proposed rules
                if rule.rule_type == RuleType.PROPOSED and rule.comment_close_date:
                    rule.binary_event = True
                    rule.options_opportunity = rule.materiality_score >= 7.0
                material_rules.append(rule)
        
        # Check cache
        unique_rules = []
        for rule in material_rules:
            if not event_cache.is_duplicate("rule", rule.document_number):
                unique_rules.append(rule)
                event_cache.add_event("rule", rule.document_number)
        
        # Convert to PolicyEvent format
        events = []
        for rule in unique_rules:
            event = PolicyEvent(
                event_id=f"rule_{rule.document_number}",
                event_type="rule",
                timestamp=rule.publication_date,
                materiality=materiality_scorer.get_level(rule.materiality_score),
                materiality_score=rule.materiality_score,
                title=f"{rule.rule_type.value.title()} Rule: {rule.title}",
                summary=rule.summary,
                affected_sectors=list(set(rule.affected_industries)),
                affected_tickers=[],  # Would map industries to tickers
                recommended_agents=_recommend_agents_for_rule(rule),
                time_sensitivity="urgent" if rule.comment_close_date and rule.comment_close_date < datetime.now() + timedelta(days=7) else "medium",
                binary_event_date=rule.comment_close_date if rule.binary_event else None,
                options_opportunity=rule.options_opportunity,
                data=rule.model_dump(),
                source_url=rule.federal_register_url
            )
            events.append(event.model_dump())
        
        logger.info(f"Found {len(events)} material rules ({sum(1 for r in unique_rules if r.options_opportunity)} with options opportunities)")
        return events
        
    except Exception as e:
        logger.error(f"Error watching federal rules: {e}")
        raise


@mcp.tool()
async def track_congressional_trades(
    min_amount: int = Field(15000, description="Minimum transaction amount"),
    days_back: int = Field(7, description="Days to look back"),
    committee_filter: Optional[List[str]] = Field(None, description="Filter by committee membership")
) -> List[Dict[str, Any]]:
    """
    Track congressional trading disclosures from Senate eFD.
    Filters for transactions >$15k and unusual patterns.
    Provides insider sentiment signals for sectors.
    """
    try:
        trades = await senate_scraper.get_recent_trades(
            days_back=days_back,
            min_amount=min_amount
        )
        
        # Filter for committee correlation if specified
        if committee_filter:
            trades = [
                trade for trade in trades
                if any(committee in trade.committees for committee in committee_filter)
            ]
        
        # Identify unusual activity patterns
        trades_by_sector = {}
        for trade in trades:
            if trade.sector:
                if trade.sector not in trades_by_sector:
                    trades_by_sector[trade.sector] = []
                trades_by_sector[trade.sector].append(trade)
        
        # Flag unusual clustering
        for sector, sector_trades in trades_by_sector.items():
            if len(sector_trades) >= 3:  # 3+ trades in same sector
                for trade in sector_trades:
                    trade.unusual_activity = True
        
        # Check cache
        unique_trades = []
        for trade in trades:
            if not event_cache.is_duplicate("trade", trade.disclosure_id):
                unique_trades.append(trade)
                event_cache.add_event("trade", trade.disclosure_id)
        
        # Convert to PolicyEvent format
        events = []
        for trade in unique_trades:
            materiality = 7.0 if trade.unusual_activity else 5.0
            
            event = PolicyEvent(
                event_id=f"trade_{trade.disclosure_id}",
                event_type="trade",
                timestamp=trade.disclosure_date,
                materiality=materiality_scorer.get_level(materiality),
                materiality_score=materiality,
                title=f"{trade.member_name} {trade.transaction_type} {trade.ticker or trade.asset_description}",
                summary=f"${trade.amount_min:,.0f}-${trade.amount_max:,.0f} transaction",
                affected_sectors=[trade.sector] if trade.sector else [],
                affected_tickers=[trade.ticker] if trade.ticker else [],
                recommended_agents=["equity-analyst"],
                time_sensitivity="high" if trade.unusual_activity else "low",
                binary_event_date=None,
                options_opportunity=False,
                data=trade.model_dump(),
                source_url=f"https://efdsearch.senate.gov/search/view/ptr/{trade.disclosure_id}/"
            )
            events.append(event.model_dump())
        
        logger.info(f"Found {len(events)} congressional trades ({sum(1 for t in unique_trades if t.unusual_activity)} flagged as unusual)")
        return events
        
    except Exception as e:
        logger.error(f"Error tracking congressional trades: {e}")
        raise


@mcp.tool()
async def monitor_key_nominations(
    congress: Optional[int] = Field(None, description="Congress number"),
    days_back: int = Field(30, description="Days to look back"),
    positions: Optional[List[str]] = Field(None, description="Specific positions to monitor")
) -> List[Dict[str, Any]]:
    """
    Monitor nominations for key financial/regulatory positions.
    Focuses on Fed governors, SEC commissioners, Treasury officials.
    Signals potential policy regime changes.
    """
    try:
        async with congress_client:
            nominations = await congress_client.monitor_key_nominations(
                congress=congress,
                days_back=days_back
            )
        
        # Filter by position if specified
        if positions:
            nominations = [
                nom for nom in nominations
                if any(pos.lower() in nom.position.lower() for pos in positions)
            ]
        
        # Only include high-materiality nominations
        material_nominations = [
            nom for nom in nominations
            if nom.materiality_score >= 7.0
        ]
        
        # Check cache
        unique_nominations = []
        for nom in material_nominations:
            if not event_cache.is_duplicate("nomination", nom.nomination_id):
                unique_nominations.append(nom)
                event_cache.add_event("nomination", nom.nomination_id)
        
        # Convert to PolicyEvent format
        events = []
        for nom in unique_nominations:
            event = PolicyEvent(
                event_id=f"nomination_{nom.nomination_id}",
                event_type="nomination",
                timestamp=nom.submission_date,
                materiality=materiality_scorer.get_level(nom.materiality_score),
                materiality_score=nom.materiality_score,
                title=f"{nom.nominee_name} nominated for {nom.position}",
                summary=f"Status: {nom.status}",
                affected_sectors=nom.affected_sectors,
                affected_tickers=[],
                recommended_agents=_recommend_agents_for_nomination(nom),
                time_sensitivity="medium",
                binary_event_date=nom.hearing_date,
                options_opportunity=nom.position.lower().startswith("federal reserve"),
                data=nom.model_dump(),
                source_url=f"https://www.congress.gov/nomination/{congress}/{nom.nomination_id}"
            )
            events.append(event.model_dump())
        
        logger.info(f"Found {len(events)} key nominations")
        return events
        
    except Exception as e:
        logger.error(f"Error monitoring nominations: {e}")
        raise


@mcp.tool()
async def track_rin_lifecycle(
    agencies: Optional[List[str]] = Field(None, description="Agencies to monitor"),
    priority_only: bool = Field(True, description="Only track economically significant rules"),
    days_ahead: int = Field(180, description="Days to look ahead in regulatory pipeline")
) -> List[Dict[str, Any]]:
    """
    Track Regulation Identifier Numbers through their lifecycle.
    Provides 6-18 month visibility into regulatory pipeline.
    Identifies options windows around regulatory milestones.
    """
    try:
        # This would integrate with Reginfo.gov API
        # For now, using GovInfo to track RINs mentioned in rules
        async with govinfo_client:
            rins = await govinfo_client.track_rins(
                agencies=agencies,
                priority_only=priority_only
            )
        
        # Calculate options windows
        for rin in rins:
            rin.options_windows = []
            
            # Proposed rule publication creates first window
            if rin.proposed_date:
                rin.options_windows.append({
                    "date": rin.proposed_date,
                    "event": "Proposed rule publication",
                    "vol_expansion_expected": True
                })
            
            # Comment period close creates second window
            if rin.proposed_date:
                comment_close = rin.proposed_date + timedelta(days=60)
                rin.options_windows.append({
                    "date": comment_close,
                    "event": "Comment period close",
                    "vol_expansion_expected": True
                })
            
            # Final rule creates third window
            if rin.final_date:
                rin.options_windows.append({
                    "date": rin.final_date,
                    "event": "Final rule publication",
                    "vol_expansion_expected": False  # Vol collapse after certainty
                })
        
        # Score materiality
        for rin in rins:
            rin.materiality_score = materiality_scorer.score_rin(rin)
        
        # Filter for material RINs
        material_rins = [
            rin for rin in rins
            if rin.materiality_score >= 6.0
        ]
        
        # Check cache
        unique_rins = []
        for rin in material_rins:
            if not event_cache.is_duplicate("rin", rin.rin):
                unique_rins.append(rin)
                event_cache.add_event("rin", rin.rin)
        
        # Convert to PolicyEvent format
        events = []
        for rin in unique_rins:
            # Find next options window
            next_window = None
            for window in rin.options_windows:
                if window["date"] > datetime.now():
                    next_window = window
                    break
            
            event = PolicyEvent(
                event_id=f"rin_{rin.rin}",
                event_type="rin",
                timestamp=rin.published_date or datetime.now(),
                materiality=materiality_scorer.get_level(rin.materiality_score),
                materiality_score=rin.materiality_score,
                title=f"RIN {rin.rin}: {rin.title}",
                summary=f"Stage: {rin.stage}, Priority: {rin.priority}",
                affected_sectors=rin.affected_industries,
                affected_tickers=[],
                recommended_agents=["derivatives-options-analyst"] if next_window else ["risk-analyst"],
                time_sensitivity="low",  # Long timeline
                binary_event_date=next_window["date"] if next_window else None,
                options_opportunity=bool(next_window and next_window.get("vol_expansion_expected")),
                data=rin.model_dump(),
                source_url=f"https://www.reginfo.gov/public/do/eAgendaViewRule?pubId=&RIN={rin.rin}"
            )
            events.append(event.model_dump())
        
        logger.info(f"Tracking {len(events)} RINs with {sum(1 for e in events if e['options_opportunity'])} options opportunities")
        return events
        
    except Exception as e:
        logger.error(f"Error tracking RIN lifecycle: {e}")
        raise


# Helper functions
def _recommend_agents_for_bill(bill: CongressionalBill) -> List[str]:
    """Recommend agents based on bill content"""
    agents = []
    
    # Tax bills go to tax advisor
    if any(committee in ["hswm00", "ssfi00"] for committee in bill.committees):
        agents.append("tax-advisor")
    
    # Sector-specific bills go to equity analyst
    if bill.affected_sectors:
        agents.append("equity-analyst")
    
    # Financial bills go to macro analyst
    if "Finance" in bill.affected_sectors:
        agents.append("macro-analyst")
    
    return agents or ["equity-analyst"]


def _recommend_agents_for_hearing(hearing: CommitteeMeeting) -> List[str]:
    """Recommend agents based on hearing content"""
    agents = []
    
    # Fed hearings go to macro analyst
    if any("federal reserve" in official.lower() for official in hearing.key_officials):
        agents.append("macro-analyst")
        agents.append("derivatives-options-analyst")  # Vol event
    
    # CEO hearings go to equity analyst
    if any("ceo" in witness.get("position", "").lower() for witness in hearing.witnesses):
        agents.append("equity-analyst")
    
    return agents or ["market-scanner"]


def _recommend_agents_for_rule(rule: FederalRule) -> List[str]:
    """Recommend agents based on rule content"""
    agents = []
    
    # SEC/CFTC rules affect trading
    if rule.agency in ["Securities and Exchange Commission", "Commodity Futures Trading Commission"]:
        agents.append("risk-analyst")
    
    # EPA rules affect energy sector
    if rule.agency == "Environmental Protection Agency":
        agents.append("equity-analyst")
    
    # Proposed rules with options opportunities
    if rule.options_opportunity:
        agents.append("derivatives-options-analyst")
    
    return agents or ["risk-analyst"]


def _recommend_agents_for_nomination(nom: KeyNomination) -> List[str]:
    """Recommend agents based on nomination"""
    if "federal reserve" in nom.position.lower():
        return ["macro-analyst"]
    elif "sec" in nom.position.lower():
        return ["risk-analyst", "equity-analyst"]
    else:
        return ["market-scanner"]


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()