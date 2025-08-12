"""
Pydantic models for policy events data structures.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class BillStatus(str, Enum):
    """Congressional bill status types"""
    INTRODUCED = "introduced"
    IN_COMMITTEE = "in_committee"
    REPORTED = "reported"
    PASSED_HOUSE = "passed_house"
    PASSED_SENATE = "passed_senate"
    ENACTED = "enacted"
    VETOED = "vetoed"


class RuleType(str, Enum):
    """Federal Register rule types"""
    PROPOSED = "proposed"
    FINAL = "final"
    INTERIM_FINAL = "interim_final"
    NOTICE = "notice"


class MaterialityLevel(str, Enum):
    """Event materiality scoring"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CongressionalBill(BaseModel):
    """Model for material congressional bills"""
    bill_id: str = Field(..., description="Bill identifier (e.g., HR-3076)")
    congress: int = Field(..., description="Congress number")
    title: str = Field(..., description="Bill title")
    summary: Optional[str] = Field(None, description="Bill summary")
    sponsor: Optional[str] = Field(None, description="Bill sponsor")
    committees: List[str] = Field(default_factory=list, description="Committees involved")
    status: BillStatus = Field(..., description="Current bill status")
    status_date: datetime = Field(..., description="Date of last status change")
    affected_sectors: List[str] = Field(default_factory=list, description="Affected industry sectors")
    materiality_score: float = Field(0.0, description="Materiality score (0-10)")
    last_action: Optional[str] = Field(None, description="Last action taken")
    url: Optional[str] = Field(None, description="Congress.gov URL")


class CommitteeMeeting(BaseModel):
    """Model for key committee hearings/meetings"""
    event_id: str = Field(..., description="Meeting event ID")
    congress: int = Field(..., description="Congress number")
    chamber: str = Field(..., description="House or Senate")
    committee: str = Field(..., description="Committee name")
    title: str = Field(..., description="Meeting title")
    meeting_date: datetime = Field(..., description="Meeting date/time")
    meeting_type: str = Field(..., description="Hearing, Markup, or Meeting")
    witnesses: List[Dict[str, str]] = Field(default_factory=list, description="List of witnesses")
    key_officials: List[str] = Field(default_factory=list, description="Fed officials, CEOs present")
    topics: List[str] = Field(default_factory=list, description="Topics discussed")
    affected_sectors: List[str] = Field(default_factory=list, description="Affected sectors")
    materiality_score: float = Field(0.0, description="Materiality score")
    documents_url: Optional[str] = Field(None, description="Link to documents")


class FederalRule(BaseModel):
    """Model for Federal Register rules (proposed and final)"""
    document_number: str = Field(..., description="Federal Register document number")
    rule_type: RuleType = Field(..., description="Type of rule")
    title: str = Field(..., description="Rule title")
    agency: str = Field(..., description="Issuing agency")
    rin: Optional[str] = Field(None, description="Regulation Identifier Number")
    publication_date: datetime = Field(..., description="Publication date")
    effective_date: Optional[datetime] = Field(None, description="Effective date (final rules)")
    comment_close_date: Optional[datetime] = Field(None, description="Comment deadline (proposed)")
    summary: Optional[str] = Field(None, description="Rule summary")
    affected_industries: List[str] = Field(default_factory=list, description="Affected industries")
    cfr_references: List[str] = Field(default_factory=list, description="CFR sections affected")
    materiality_score: float = Field(0.0, description="Materiality score")
    binary_event: bool = Field(False, description="Creates binary outcome for options")
    options_opportunity: bool = Field(False, description="Identified options opportunity")
    federal_register_url: Optional[str] = Field(None, description="FR URL")


class CongressionalTrade(BaseModel):
    """Model for congressional trading disclosures"""
    disclosure_id: str = Field(..., description="Disclosure identifier")
    member_name: str = Field(..., description="Congress member name")
    chamber: str = Field(..., description="House or Senate")
    state: str = Field(..., description="State represented")
    committees: List[str] = Field(default_factory=list, description="Committee memberships")
    ticker: Optional[str] = Field(None, description="Stock ticker")
    asset_description: str = Field(..., description="Asset description")
    transaction_type: str = Field(..., description="Buy, Sell, Exchange")
    transaction_date: datetime = Field(..., description="Transaction date")
    disclosure_date: datetime = Field(..., description="Disclosure date")
    amount_min: float = Field(..., description="Minimum transaction amount")
    amount_max: float = Field(..., description="Maximum transaction amount")
    unusual_activity: bool = Field(False, description="Flagged as unusual")
    sector: Optional[str] = Field(None, description="Industry sector")


class KeyNomination(BaseModel):
    """Model for key government nominations"""
    nomination_id: str = Field(..., description="Nomination identifier")
    nominee_name: str = Field(..., description="Nominee name")
    position: str = Field(..., description="Position nominated for")
    agency: str = Field(..., description="Agency/Department")
    submission_date: datetime = Field(..., description="Nomination submission date")
    committee: Optional[str] = Field(None, description="Committee reviewing")
    hearing_date: Optional[datetime] = Field(None, description="Hearing date")
    confirmation_date: Optional[datetime] = Field(None, description="Confirmation date")
    status: str = Field(..., description="Current status")
    policy_implications: List[str] = Field(default_factory=list, description="Policy implications")
    affected_sectors: List[str] = Field(default_factory=list, description="Affected sectors")
    materiality_score: float = Field(0.0, description="Materiality score")


class RINTracking(BaseModel):
    """Model for tracking Regulation Identifier Numbers through lifecycle"""
    rin: str = Field(..., description="Regulation Identifier Number")
    agency: str = Field(..., description="Agency")
    title: str = Field(..., description="Regulation title")
    stage: str = Field(..., description="Current stage in regulatory process")
    priority: str = Field(..., description="Economically Significant, Other Significant, etc.")
    published_date: Optional[datetime] = Field(None, description="Publication date")
    proposed_date: Optional[datetime] = Field(None, description="Proposed rule date")
    final_date: Optional[datetime] = Field(None, description="Expected/actual final rule date")
    timeline_milestones: List[Dict[str, Any]] = Field(default_factory=list, description="Key dates")
    affected_industries: List[str] = Field(default_factory=list, description="Affected industries")
    economic_impact: Optional[float] = Field(None, description="Estimated economic impact")
    materiality_score: float = Field(0.0, description="Materiality score")
    options_windows: List[Dict[str, datetime]] = Field(default_factory=list, description="Vol opportunity windows")


class PolicyEvent(BaseModel):
    """Unified policy event for agent consumption"""
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="bill, hearing, rule, trade, nomination, rin")
    timestamp: datetime = Field(..., description="Event timestamp")
    materiality: MaterialityLevel = Field(..., description="Materiality level")
    materiality_score: float = Field(..., description="Numerical materiality score")
    title: str = Field(..., description="Event title/description")
    summary: Optional[str] = Field(None, description="Event summary")
    affected_sectors: List[str] = Field(default_factory=list, description="Affected sectors")
    affected_tickers: List[str] = Field(default_factory=list, description="Specific tickers affected")
    recommended_agents: List[str] = Field(default_factory=list, description="Agents to notify")
    time_sensitivity: str = Field("low", description="low, medium, high, urgent")
    binary_event_date: Optional[datetime] = Field(None, description="Binary event date for options")
    options_opportunity: bool = Field(False, description="Options trading opportunity")
    data: Dict[str, Any] = Field(default_factory=dict, description="Full event data")
    source_url: Optional[str] = Field(None, description="Source URL")


class MaterialityFilter(BaseModel):
    """Configuration for materiality filtering"""
    min_score: float = Field(5.0, description="Minimum materiality score")
    agencies: List[str] = Field(default_factory=list, description="High-priority agencies")
    committees: List[str] = Field(default_factory=list, description="Key committees")
    keywords: List[str] = Field(default_factory=list, description="Material keywords")
    sectors: List[str] = Field(default_factory=list, description="Sectors of interest")
    min_trade_amount: float = Field(15000, description="Minimum congressional trade amount")
    positions: List[str] = Field(default_factory=list, description="Key government positions")