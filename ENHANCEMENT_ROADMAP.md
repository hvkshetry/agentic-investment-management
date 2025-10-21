# High-ROI Integration Enhancement Roadmap

**Status**: Foundation complete, ready for enhancement phase
**Last Updated**: 2025-01-20
**Source**: Codex analysis and architectural review

## Executive Summary

With all red/yellow flags resolved and documentation consolidated, the system is ready for high-value integrations. This roadmap prioritizes event feeds by development ROI, data quality, and portfolio impact.

## Priority Rankings

### ★★★★ Tier 1: Market Structure (Highest ROI)
**Impact**: Direct liquidity and trading decisions
**Data Quality**: CSV/JSON, reliable, well-structured
**Maintenance**: Schedule-based polling + QA
**Timeline**: Single session implementation possible

### ★★★★ Tier 1: Healthcare Regulatory
**Impact**: Critical for biotech/medtech holdings
**Data Quality**: Well-documented REST APIs, stable
**Maintenance**: Rate-limited but manageable
**Timeline**: 1-2 sessions for MVP

### ★★★ Tier 2: Litigation & IP
**Impact**: Sector-specific but high value
**Data Quality**: Structured JSON with auth tokens
**Maintenance**: Higher ingest volume, NLP requirements
**Timeline**: 2-3 sessions with entity resolution

### ★★ Tier 3: Environmental
**Impact**: Episodic, geography-dependent
**Data Quality**: Free and reliable APIs
**Maintenance**: Geospatial mapping complexity
**Timeline**: 3-4 sessions (deferred)

---

## Top 3 Integrations (Detailed Implementation)

### 1. Market Structure Event Hub ★★★★

#### API Assessment
**Data Sources:**
- **FINRA Short Sale Volume**: `https://cdn.finra.org/equity/regsho/daily/SHORTVOLUME_{YYYYMMDD}.txt`
  - Daily files, pipe-delimited, no auth
  - Fields: Date, Symbol, ShortVolume, ShortExemptVolume, TotalVolume
  - Rate limit: None (CDN polite polling)

- **FINRA Short Interest**: `https://cdn.finra.org/equity/shortinterest/{DATE}.txt`
  - Bi-monthly (mid-month, month-end), pipe-delimited
  - Fields: SettlementDate, Symbol, ShortInterest, AverageDailyVolume, DaysTocover
  - Rate limit: None (static files)

- **NYSE/NASDAQ Trading Halts**: JSON feeds
  - Real-time or near-real-time
  - Fields: Symbol, HaltTime, ResumeTime, ReasonCode, Status
  - Rate limit: Websocket or polling-based

- **Optional**: UnusualWhales/SqueezeMetrics (paid, premium data)

#### Data Schema
```json
{
  "event_type": "short_volume_spike|halt_issued|short_interest_report",
  "symbol": "AAPL",
  "timestamp": "2025-01-20T14:30:00Z",
  "metric": {
    "short_volume_ratio": 0.58,
    "halt_reason": "T1_regulatory_concern",
    "days_to_cover": 4.2
  },
  "window": "1d|7d|30d",
  "source_url": "https://cdn.finra.org/...",
  "confidence": 0.95
}
```

#### MCP Server Design
**Recommendation**: Extend `policy-events-service` with a `market_microstructure` router

**Rationale**:
- Reuses existing scheduler and cache infrastructure
- Policy events and market structure both trigger portfolio alerts
- Unified event envelope format

**New Tools**:
```python
# Get recent short volume data
mcp__policy-events-service__get_short_volume(
    symbols: List[str] = None,  # None = all symbols
    days_back: int = 5
)

# Get latest short interest data
mcp__policy-events-service__get_short_interest(
    symbols: List[str] = None,
    report_date: str = None  # None = most recent
)

# Get trading halts
mcp__policy-events-service__get_trading_halts(
    symbols: List[str] = None,
    hours_back: int = 24,
    include_resumed: bool = False
)
```

#### Agent Integration
- **market-scanner**: Flags halts and volume spikes in daily monitoring
- **risk-analyst**: Consumes short-interest utilization for liquidity risk
- **gate-validator**: Enforces liquidity HALTs if short interest > threshold

#### Testing Strategy
- **Golden Files**: Historical date comparison (known short squeezes)
- **Unit Tests**: Ratio calculations, edge cases (zero volume)
- **Integration**: HEAD requests to CDN only (no download in CI)
- **Validation**: Cross-check against broker data for portfolio holdings

#### Quick Win Implementation (2-4 hours)
```python
# Phase 1: FINRA short volume importer
# 1. Download daily file
# 2. Parse pipe-delimited format
# 3. Calculate short volume ratio
# 4. Surface in market-scanner agent
# 5. Add to risk_analysis.md in daily-check workflow

# Deliverable: Short squeeze risk in daily portfolio check
```

---

### 2. Healthcare Regulatory Monitor ★★★★

#### API Assessment
**Data Sources:**
- **OpenFDA Drug Events**: `https://api.fda.gov/drug/event.json`
  - No auth, 240 requests/min rate limit
  - Search by product name, company, event date
  - Fields: patient, drug, reaction, serious, outcome

- **OpenFDA Device Events**: `https://api.fda.gov/device/event.json`
  - Same rate limits as drug events
  - Fields: device, event_type, manufacturer, date_of_event

- **ClinicalTrials.gov**: `https://clinicaltrials.gov/api/v2/studies`
  - REST/JSON, no auth
  - Filter by condition, phase, overall_status
  - Fields: NCTId, BriefTitle, OverallStatus, CompletionDate, Interventions

- **CMS Coverage Database**: HTML/CSV downloads (requires scraper)
  - National Coverage Determinations (NCDs)
  - Local Coverage Determinations (LCDs)
  - Needs caching layer to avoid frequent scraping

#### Data Schema
```json
{
  "event_type": "fda_adverse_event|trial_status_change|cms_coverage_decision",
  "product_identifier": {
    "ndc": "12345-678-90",  // National Drug Code
    "unii": "ABC123DEF456",  // Unique Ingredient Identifier
    "ticker": "ABBV"  // Mapped ticker symbol
  },
  "severity": "serious|moderate|minor",
  "narrative": "FDA adverse event report for product X...",
  "impact": {
    "phase": "Phase III",
    "status_change": "completed→terminated",
    "coverage": "approved|denied|expanded"
  },
  "timestamp": "2025-01-20T09:00:00Z",
  "source_url": "https://api.fda.gov/...",
  "confidence": 0.85
}
```

#### MCP Server Design
**Recommendation**: New lightweight `regulatory-health-server`

**Rationale**:
- Isolates rate-limited API calls
- Requires product-to-ticker mapping (separate concern)
- Healthcare-specific domain logic

**Architecture**:
```python
# FastAPI with cached session
# Separate router for each data source
# Unified response format

class RegulatoryHealthServer:
    - /fda/adverse_events
    - /fda/device_events
    - /clinical_trials/status
    - /cms/coverage_decisions
```

**New Tools**:
```python
# Get FDA adverse events for ticker or product
mcp__regulatory-health-server__get_adverse_events(
    ticker: str = None,
    product_name: str = None,
    days_back: int = 30,
    severity: str = "serious"  # serious|all
)

# Get clinical trial updates
mcp__regulatory-health-server__get_trial_updates(
    ticker: str = None,
    condition: str = None,
    phase: str = None,
    status_change: bool = True  # Only status changes
)

# Get CMS coverage decisions
mcp__regulatory-health-server__get_coverage_decisions(
    ticker: str = None,
    decision_type: str = "NCD",  # NCD|LCD
    days_back: int = 90
)
```

#### Agent Integration
- **equity-analyst** (or new **healthcare-analyst**): Analyzes FDA/trial impacts
- **gate-validator**: Compliance review for coverage decisions
- **tax-advisor**: If reimbursement shifts affect muni healthcare bond holdings

#### Testing Strategy
- **Mock Adapters**: Recorded responses for each API
- **Ticker Mapping**: Backfill on known FDA alerts (e.g., Vioxx withdrawal)
- **Rate Limit Monitoring**: SLA alerts on 239/240 requests
- **Validation**: Compare FDA data against news reports

#### Implementation Timeline
- **Session 1**: FDA adverse events + ticker mapping
- **Session 2**: ClinicalTrials.gov integration
- **Session 3**: CMS scraper with caching

---

### 3. Litigation & IP Feed ★★★

#### API Assessment
**Data Sources:**
- **CourtListener**: `https://www.courtlistener.com/api/rest/v3/`
  - Token auth required (free tier available)
  - 1 request/sec soft limit
  - Endpoints: `/dockets/`, `/opinions/`, `/audio/`
  - Fields: case_name, court, date_filed, parties, docket_number

- **USPTO PTAB**: `https://developer.uspto.gov/ptab-api`
  - Public API, no auth required
  - Filter by application_number, inventor, assignee
  - Fields: ProceedingNumber, PatentNumber, Status, InstitutionDecision

- **USITC EDIS**: RSS feed (XML)
  - Investigation notices, Commission opinions
  - Fields: InvestigationNumber, Title, Type, FilingDate

#### Data Schema
```json
{
  "event_type": "litigation_docket|ptab_petition|usitc_investigation",
  "case_id": "1:23-cv-12345",
  "parties": {
    "plaintiff": "Company A Inc.",
    "defendant": "Company B Corp.",
    "linked_symbols": ["CMPA", "CMPB"]
  },
  "patent_info": {
    "patent_number": "US1234567",
    "status": "invalidated|upheld|pending"
  },
  "next_deadline": "2025-03-15",
  "impact_assessment": "high|medium|low",
  "timestamp": "2025-01-20T10:00:00Z",
  "source_url": "https://www.courtlistener.com/...",
  "confidence": 0.75
}
```

#### MCP Server Design
**Recommendation**: Separate `legal-events-server` with async processing

**Rationale**:
- High ingest volume requires local SQLite cache for deduplication
- NLP needed for entity extraction from legal text
- Separate concern from market data

**Architecture**:
```python
# Async FastAPI with background tasks
# SQLite cache for case tracking
# Ticker tagging via NER models

class LegalEventsServer:
    - /litigation/dockets
    - /litigation/opinions
    - /patent/ptab_decisions
    - /trade/usitc_investigations
```

**New Tools**:
```python
# Get litigation dockets for ticker
mcp__legal-events-server__get_litigation(
    ticker: str = None,
    party_name: str = None,
    court: str = None,  # district|circuit|supreme
    days_back: int = 90,
    case_type: str = None  # patent|securities|antitrust
)

# Get PTAB decisions
mcp__legal-events-server__get_ptab_decisions(
    ticker: str = None,
    patent_number: str = None,
    status: str = None,  # invalidated|upheld|pending
    days_back: int = 180
)

# Get USITC investigations
mcp__legal-events-server__get_usitc_investigations(
    ticker: str = None,
    investigation_type: str = "337",  # Section 337 IP cases
    status: str = "active"
)
```

#### Agent Integration
- **portfolio-manager**: Thesis impact assessment
- **risk-analyst**: Legal tail risk scenarios
- **ic-memo-generator**: Auto-summaries for major cases

#### Testing Strategy
- **Smoke Tests**: Token-protected staging datasets
- **Text Classification**: Unit tests for ticker tagging accuracy
- **Rate Limit Guards**: Exponential backoff mocks
- **Validation**: Cross-reference against legal databases (Justia, Google Scholar)

#### Implementation Timeline
- **Session 1**: CourtListener docket ingestion + ticker mapping
- **Session 2**: USPTO PTAB API integration
- **Session 3**: USITC RSS parser + deduplication

---

## Unified Architecture Components

### EventEnvelope Standard Format
All event feeds use this common structure:

```python
@dataclass
class EventEnvelope:
    id: str                    # Unique event ID
    event_type: str            # Type from enum
    subjects: List[str]        # Ticker symbols affected
    trigger_time: datetime     # When event occurred
    confidence: float          # 0.0 to 1.0
    payload: Dict[str, Any]    # Event-specific data
    source: str                # API/feed origin
    metadata: Dict[str, Any]   # Optional context
```

### Entity Resolution Service
Centralized mapping in `shared/entity_resolver.py`:

```python
class EntityResolver:
    """Map various identifiers to portfolio holdings"""

    def resolve_ticker(self, identifier: str, id_type: str) -> Optional[str]:
        """
        Args:
            identifier: CUSIP, ISIN, FDA product code, patent number, etc.
            id_type: Type of identifier

        Returns:
            Ticker symbol if found in portfolio
        """
        pass

    def resolve_holdings(self, event: EventEnvelope) -> List[Position]:
        """Find portfolio positions affected by event"""
        pass
```

**Reference Tables** (in `Investing/State/`):
- `cusip_to_ticker.json`
- `fda_product_to_ticker.json`
- `patent_assignee_to_ticker.json`
- `geo_exposure.json` (for environmental events)

### Caching Strategy

**Three-Layer Cache**:
1. **HTTP Cache**: aiohttp with `Expires` headers (15-30 min)
2. **Hot Data**: Redis/memory for frequently accessed (15-30 min TTL)
3. **Audit Trail**: Parquet snapshots for compliance

**Freshness Metadata**: Each cached item tagged with:
```python
{
    "cached_at": "2025-01-20T14:30:00Z",
    "expires_at": "2025-01-20T15:00:00Z",
    "source_modified": "2025-01-20T14:29:55Z",
    "can_replay": True
}
```

### Alert Prioritization

**Tier 1 - Immediate HALT** (Triggers agent wake + workflow stop):
- Trading halts (T1, M1 codes)
- PTAB patent invalidation for major holdings
- FDA market withdrawal
- USITC import ban

**Tier 2 - Daily Summary** (Included in `/daily-check`):
- Clinical trial status changes
- Short interest spikes (>30% SI or >5 days to cover)
- New litigation filings
- Coverage decisions

**Tier 3 - Risk Scenario Queue** (Background processing):
- Environmental alerts (earthquakes, hurricanes)
- Minor FDA adverse events
- PTAB petitions filed (not decided)

---

## Quick Wins (2-4 Hour Sessions)

### Quick Win #1: FINRA Short Interest Dashboard

**Goal**: Surface short squeeze risk in daily portfolio monitoring

**Implementation**:
```python
# File: policy-events-mcp-server/finra_short_interest.py

async def get_short_interest(symbols: List[str] = None, days_back: int = 30):
    """Download and parse FINRA short interest files"""
    # 1. Determine report dates (bi-monthly)
    # 2. Download pipe-delimited files from CDN
    # 3. Parse and calculate days-to-cover
    # 4. Filter to portfolio holdings
    # 5. Return high-risk positions (DTF > 5)
```

**Agent Hook** (in `market-scanner` agent):
```python
# Check short interest for portfolio holdings
short_risk = mcp__policy-events-service__get_short_interest(
    symbols=portfolio_tickers,
    days_back=30
)

# Flag high-risk positions in daily report
for position in short_risk:
    if position["days_to_cover"] > 5:
        alert(f"{position['symbol']}: High short interest - {position['days_to_cover']} DTF")
```

**Deliverable**: Short squeeze risk section added to `/daily-check` workflow

---

### Quick Win #2: USGS Earthquake Event Testing

**Goal**: Test event envelope + geo mapping with real-time data

**Implementation**:
```python
# File: policy-events-mcp-server/usgs_earthquakes.py

async def get_significant_earthquakes(hours_back: int = 24):
    """Fetch USGS earthquake GeoJSON feed"""
    # 1. Pull https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.geojson
    # 2. Parse GeoJSON features
    # 3. Map lat/long to affected regions
    # 4. Cross-reference with geo_exposure.json
    # 5. Return EventEnvelope objects
```

**Entity Resolution** (in `shared/entity_resolver.py`):
```python
def map_geo_to_holdings(latitude: float, longitude: float, radius_km: float = 500):
    """Find portfolio holdings with exposure to geographic area"""
    # Check geo_exposure.json for:
    # - Manufacturing facilities
    # - Major offices
    # - Supply chain hubs
    # - Real estate holdings
```

**Deliverable**: Proof of concept for environmental event ingestion

---

## Common Pitfalls & Solutions

### 1. CourtListener Pagination (429 Errors)
**Problem**: `page_size > 100` triggers rate limit errors

**Solution**:
```python
# Throttle requests and persist resume tokens
async def fetch_dockets(page_size=50, max_retries=3):
    for page in range(total_pages):
        response = await session.get(url, params={"page": page, "page_size": 50})
        if response.status == 429:
            await asyncio.sleep(exponential_backoff(attempt))
        # Persist page number to resume on restart
        save_checkpoint(page)
```

### 2. OpenFDA Data Backfills
**Problem**: Occasionally backfills data with changed primary keys

**Solution**:
```python
# Version ingestion and reconcile deltas
def ingest_fda_events(event_date: str):
    current_version = hash_dataset(events)
    if current_version != cached_version:
        # Detect changed records
        deltas = compute_delta(events, cached_events)
        log_warning(f"FDA backfill detected: {len(deltas)} changed records")
        # Re-process affected tickers
```

### 3. FINRA Missing Symbols
**Problem**: Files contain missing symbols for halted/delisted issues

**Solution**:
```python
# Guard against zero-volume divisions
def calculate_short_ratio(short_vol: int, total_vol: int) -> Optional[float]:
    if total_vol == 0:
        log_warning(f"Zero total volume for symbol")
        return None
    return short_vol / total_vol
```

### 4. NOAA/NWS Duplicate Alerts
**Problem**: Can push duplicate IDs with same event

**Solution**:
```python
# Dedupe via composite key
def dedupe_alerts(alerts: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for alert in alerts:
        key = (alert["id"], alert["sent"])  # Composite key
        if key not in seen:
            seen.add(key)
            unique.append(alert)
    return unique
```

### 5. MCP Tool Timeouts
**Problem**: Blocking third-party calls stall orchestrated workflows

**Solution**:
```python
# Isolate retries with generous timeouts
@timeout(seconds=30)
async def fetch_with_retry(url: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await asyncio.wait_for(session.get(url), timeout=10)
        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

---

## Next Steps

1. **Schema Blueprint**: Define exact EventEnvelope fields for Market Structure
2. **MCP Contract**: Specify tool signatures for `policy-events-service` extensions
3. **Quick Win Implementation**: Build FINRA short interest importer (Session 1)
4. **Entity Resolution**: Create ticker mapping tables for FDA products
5. **Caching Layer**: Implement three-tier cache with freshness tracking

Ready to proceed with detailed schema design or start Quick Win #1.
