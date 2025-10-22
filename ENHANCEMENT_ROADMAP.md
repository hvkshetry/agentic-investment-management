# Investment Platform Enhancement Roadmap

**Status**: Foundation complete, ready for implementation
**Last Updated**: 2025-10-21
**Source**: Codex GitHub CLI research and architectural review

## Executive Summary

This consolidated roadmap presents **16 high-ROI integrations** discovered through extensive GitHub CLI research. All leverage free/open source data with active maintenance and clear implementation paths.

**IMPORTANT - Tool Consolidation (2025-10-21)**:
Based on Codex workflow coherence review, we are consolidating data sources to reduce complexity:

**Use OpenBB Platform for:**
- ✅ Fama-French factors (via `openbb.equity.fundamental.metrics` with famafrench provider)
- ✅ FRED economic data (already integrated via `economy_*` tools)
- ✅ COT reports (via `openbb.regulators.cftc` provider)
- ✅ Performance attribution (via `equity.price.performance` router)

**Defer/Exclude:**
- ❌ pandas-datareader wrapper (redundant with OpenBB)
- ❌ fredapi wrapper (redundant with OpenBB)
- ❌ cot_reports standalone (redundant with OpenBB)
- ❌ quantstats wrapper (use internal analytics + OpenBB benchmarks)
- ❌ PRAW Reddit sentiment (low ROI vs GDELT, high maintenance)
- ⏸️ vectorbt/backtrader servers (defer until workflows require advanced simulation)

**Extend Existing Servers Instead:**
- Expose Fama-French via `openbb-curated` MCP server
- Add performance metrics to `risk-server` using OpenBB benchmarks
- Extend `policy-events-service` for market structure alerts (FINRA halts, short interest)

**Coverage**:
- **Part I**: Event Feeds (4) - Market Structure, Healthcare, Litigation, Environmental
  - See `documentation/archive/ENHANCEMENT_ROADMAP_INITIAL.md` for detailed specs
- **Part II**: Public Data & Open Source (12) - Detailed in this document (see consolidation notes above)

**Priority Criteria**:
- Development ROI (effort vs. value)
- Data quality and coverage
- Portfolio decision impact
- Maintenance burden
- Tool consolidation (prefer extending existing over new servers)

**Quick Wins Identified**: 6 integrations can deliver value in <4 hours each (updated for consolidation)

---

## Part I: Event Feeds (Reference)

For detailed implementation guides on these 4 integrations, see `documentation/archive/ENHANCEMENT_ROADMAP_INITIAL.md`:

1. **Market Structure Event Hub** ★★★★
   - FINRA short interest/volume, trading halts
   - Quick Win: FINRA short interest dashboard (2-4 hours)

2. **Healthcare Regulatory Monitor** ★★★★
   - FDA OpenFDA API, ClinicalTrials.gov, CMS
   - Timeline: 1-2 sessions for MVP

3. **Litigation & IP Feed** ★★★
   - CourtListener, USPTO PTAB, USITC
   - Timeline: 2-3 sessions with entity resolution

4. **Environmental** ★★
   - NOAA, USGS, EPA (deferred - lower priority)

---

## Part II: Public Data & Open Source Integrations (Codex Research)

### Category: Backtesting & Simulation

#### 1. vectorbt (Backtesting Engine) ★★★★

**GitHub Research**:
```bash
gh repo view polakowo/vectorbt --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/polakowo/vectorbt
- **Status**: Updated 2025-10-21, 5.9k★, very active (no tagged releases but frequent merges)
- **Data Coverage**: Vectorized backtests across equities/crypto with indicator library; real-time friendly via pandas/numpy
- **Cost**: OSS (MIT); no external rate limits
- **Authentication**: None required

**ROI Analysis**:
- **Development Effort**: ~16 hours (including packaging + sample notebooks)
- **Portfolio Impact**: Direct - adds scalable scenario testing currently missing from platform
- **Data Freshness**: Real-time capable (integrates with existing OHLC data sources)
- **Maintenance Burden**: Low - stable API, active community
- **ROI Score**: ★★★★ (High value, manageable effort)

**Implementation Sketch**:
```python
# New MCP Server: backtesting-mcp-server

class BacktestingServer:
    """Vectorized backtesting for strategy validation"""

    @tool
    async def run_vectorbt(
        backtest_spec: Dict[str, Any]
        # {
        #   "tickers": ["SPY", "AGG"],
        #   "weights": [0.6, 0.4],
        #   "start_date": "2020-01-01",
        #   "end_date": "2023-12-31",
        #   "rebalance_freq": "monthly",
        #   "initial_capital": 100000
        # }
    ) -> Dict[str, Any]:
        """
        Run vectorized backtest and return:
        - Performance metrics (Sharpe, Sortino, CAGR)
        - Equity curve
        - Trade blotter
        - Drawdown periods
        """
        pass
```

**Agent Integration**:
- **portfolio-manager**: Validate optimization candidates against historical data
- **risk-analyst**: Stress test ES limits in different market regimes
- **ic-memo-generator**: Include backtest results in decision memos

**Quick Win Potential**: No (needs artifact schema + packaging)

**Integration Risks**:
- Memory-heavy on large universes (use chunking/sampling)
- Ensure position sizing caps to prevent unrealistic allocations
- Align timezone handling with portfolio-state-server

**Mitigation**:
```python
# Enforce position size limits
MAX_POSITIONS = 50  # Prevent memory issues
MAX_LOOKBACK_DAYS = 1260  # 5 years max

# Validate before running
if len(tickers) > MAX_POSITIONS:
    raise ValueError(f"Backtest limited to {MAX_POSITIONS} positions")
```

---

#### 2. backtrader (Event-Driven Backtests) ★★★

**GitHub Research**:
```bash
gh repo view mementum/backtrader --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/mementum/backtrader
- **Status**: Updated 2025-10-21, 19.1k★, community-maintained (no releases but active forks)
- **Data Coverage**: Supports live/zipline-like feeds, order types, analyzers for drawdowns, Sharpe, etc.
- **Cost**: OSS (GPL-v3)
- **Authentication**: None required

**ROI Analysis**:
- **Development Effort**: ~12 hours (extend portfolio-optimization-server)
- **Portfolio Impact**: Complementary to vectorbt - adds event-driven/commission-aware testing
- **Data Freshness**: Supports live feeds
- **Maintenance Burden**: Medium - GPL licensing consideration for distribution
- **ROI Score**: ★★★ (Good value, licensing constraint)

**Implementation Sketch**:
```python
# Extend portfolio-optimization-server

@tool
async def simulate_strategy_backtrader(
    strategy_id: str,  # "mean_reversion", "momentum", etc.
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run event-driven backtest with commission/slippage modeling
    Enables limit/stop logic validation
    """
    pass
```

**Agent Integration**:
- **portfolio-manager**: Test rebalancing strategies with transaction costs
- **tax-advisor**: Simulate wash sale scenarios

**Quick Win Potential**: No (strategy scaffolding required)

**Integration Risks**:
- **GPL-v3 Licensing**: Must consider for distribution
- Slower on large universes than vectorbt
- Carefully sandbox strategies to prevent infinite loops

**Mitigation**:
```python
# Isolate GPL code in separate container
# Use strategy timeout limits
STRATEGY_TIMEOUT_SECONDS = 300  # 5 min max
```

---

### Category: Economic & Demographic Data

#### 3. fredapi (Federal Reserve & ALFRED) ★★★★

**GitHub Research**:
```bash
gh repo view mortada/fredapi --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/mortada/fredapi
- **Status**: Release v0.5.2 (2024-05-05), 1.1k★, updated 2025-10-18
- **Data Coverage**: 816k+ FRED series (rates, spreads, macro surprises) with ALFRED vintages
- **Cost**: Free (FRED API key, generous limits ~120 req/min)
- **Authentication**: FRED API key (free registration)

**ROI Analysis**:
- **Development Effort**: ~6 hours (extend openbb-curated or new macro-data-server)
- **Portfolio Impact**: Direct - high-frequency macro for scenario inputs, optimizer constraints, tax projections
- **Data Freshness**: Daily to real-time depending on series
- **Maintenance Burden**: Low - stable FRED API
- **ROI Score**: ★★★★ (Highest value/effort ratio)

**Implementation Sketch**:
```python
# Extend openbb-curated server

@tool
async def fred_series(
    series_ids: List[str],  # ["DGS10", "DGS3MO", "UNRATE"]
    vintage: Optional[str] = None  # ALFRED historical revision
) -> Dict[str, Any]:
    """
    Fetch FRED time series with full provenance
    Returns: {series_id: {data: [...], metadata: {...}}}
    """
    pass

# Example usage
spreads = await fred_series(["DGS10", "DGS3MO"])
inversion = spreads["DGS10"][-1] - spreads["DGS3MO"][-1]
if inversion < 0:
    alert("Yield curve inverted - recession signal")
```

**Agent Integration**:
- **macro-analyst**: Direct access to high-frequency macro data
- **risk-analyst**: Incorporate macro scenarios into stress tests
- **tax-advisor**: Use economic forecasts for tax planning

**Quick Win Potential**: **YES** - Demo pulling 10y-3m spread into risk report

**Quick Win Implementation** (2 hours):
```python
# Add to /daily-check workflow
# In market-scanner agent

macro_check = await fred_series(["DGS10", "DGS3MO", "UNRATE"])
spread_10y_3m = macro_check["DGS10"][-1] - macro_check["DGS3MO"][-1]

if spread_10y_3m < 0:
    alert("⚠️ Yield curve inverted - historical recession indicator")
```

**Integration Risks**:
- API returns strings (need float conversion)
- Timezone normalization required
- Series metadata caching needed

**Mitigation**:
```python
# Robust parsing
def parse_fred_value(value: str) -> Optional[float]:
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse FRED value: {value}")
        return None

# Cache series metadata
METADATA_CACHE_TTL = 86400  # 1 day
```

---

#### 4. census (US Census Wrapper) ★★★

**GitHub Research**:
```bash
gh repo view datamade/census --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/datamade/census
- **Status**: Release v0.8.24 (2025-04-08), 674★, updated 2025-10-09
- **Data Coverage**: ACS, economic census, business patterns; county/CBSA detail
- **Cost**: Free (Census API key; ~500 req/day before secondary key needed)
- **Authentication**: Census API key (free registration)

**ROI Analysis**:
- **Development Effort**: ~10 hours (extend policy-events-service, build geo crosswalk)
- **Portfolio Impact**: Indirect - enables geographic exposure analysis
- **Data Freshness**: Annual (ACS), 5-year rolling
- **Maintenance Burden**: Medium - changing variable names per vintage
- **ROI Score**: ★★★ (Good for geographic analysis)

**Implementation Sketch**:
```python
# Extend policy-events-service

@tool
async def census_acs(
    series: str,  # "B19013_001E" (median household income)
    geo: str,     # "county:*" or "state:06"
    vintage: int = 2023
) -> Dict[str, Any]:
    """
    Fetch American Community Survey data with geographic detail
    Returns: {geo_id: {value: ..., margin_of_error: ...}}
    """
    pass
```

**Agent Integration**:
- **macro-analyst**: Allocations vs. household income, demographic risk
- **portfolio-manager**: Geographic exposure constraints
- **gate-validator**: Policy gates based on regional exposure

**Quick Win Potential**: No (requires geo crosswalk build)

**Integration Risks**:
- Changing variable names per vintage
- 500 errors during peak usage
- Geography FIPS code mapping complexity

**Mitigation**:
```python
# Implement retry logic
@retry(stop_max_attempt_number=3, wait_fixed=2000)
async def census_request(url: str):
    return await session.get(url)

# Cache geographies
GEO_CACHE_PATH = "shared/geo_crosswalk.json"
```

---

### Category: Factor & Risk Data

#### 5. pandas-datareader (Fama-French Factors) ★★★★

**GitHub Research**:
```bash
gh repo view pydata/pandas-datareader --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/pydata/pandas-datareader
- **Status**: Release v0.10.0 (2021), 3.1k★, updated 2025-10-18
- **Data Coverage**: Kenneth French factors, FRED, World Bank, OECD, IEX, Stooq
- **Cost**: Free; honors source rate limits
- **Authentication**: None for Fama-French, varies by source

**ROI Analysis**:
- **Development Effort**: ~8 hours (integrate into risk-server pipeline)
- **Portfolio Impact**: Direct - factor model inputs for ES attribution, style tilts
- **Data Freshness**: Daily updates (French website)
- **Maintenance Burden**: Low - stable data sources
- **ROI Score**: ★★★★ (High value for risk attribution)

**Implementation Sketch**:
```python
# Extend risk-server

@tool
async def get_factor_bundle(
    bundle_id: str  # "F-F_Research_Data_5_Factors_2x3"
) -> Dict[str, Any]:
    """
    Fetch Fama-French factor data for risk attribution
    Returns: {date: {Mkt-RF: ..., SMB: ..., HML: ..., RMW: ..., CMA: ...}}
    """
    from pandas_datareader import DataReader

    data = DataReader(bundle_id, 'famafrench')
    return format_factor_data(data)

# Example: ES decomposition by factor exposure
@tool
async def es_factor_attribution(
    portfolio_returns: List[float],
    factor_exposures: Dict[str, float]
) -> Dict[str, Any]:
    """
    Decompose ES into factor contributions
    Returns: {factor: contribution_to_es}
    """
    pass
```

**Agent Integration**:
- **risk-analyst**: ES attribution charts (which factors drive tail risk?)
- **portfolio-manager**: Factor tilts in optimization
- **ic-memo-generator**: Include factor exposure in memos

**Quick Win Potential**: **YES** - Ingest FF5 factors for ES decomposition charts

**Quick Win Implementation** (3 hours):
```python
# Add to risk-analyst agent
# Generate factor exposure chart in risk_report.md

factors = await get_factor_bundle("F-F_Research_Data_5_Factors_2x3")
exposures = calculate_factor_exposures(portfolio_returns, factors)

# Chart: ES contribution by factor
# Mkt-RF: 60%, SMB: 15%, HML: 10%, RMW: 8%, CMA: 7%
```

**Integration Risks**:
- Source endpoints occasionally change layout
- Implement fallback caching

**Mitigation**:
```python
# Cache factor data locally
FACTOR_CACHE_PATH = "shared/cache/fama_french/"
CACHE_TTL_DAYS = 7

# Fallback to cached data on failure
try:
    data = DataReader(bundle_id, 'famafrench')
except Exception as e:
    logger.warning(f"Factor download failed: {e}, using cache")
    data = load_cached_factors(bundle_id)
```

---

#### 6. cot_reports (CFTC Commitments of Traders) ★★★

**GitHub Research**:
```bash
gh repo view NDelventhal/cot_reports --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/NDelventhal/cot_reports
- **Status**: Release v_013 (2023-12-29), 173★, updated 2025-10-13
- **Data Coverage**: All COT report variants (legacy, disaggregated, TFF) with pandas output
- **Cost**: Free (pulls from CFTC bulk files)
- **Authentication**: None required

**ROI Analysis**:
- **Development Effort**: ~6 hours (extend policy-events-service or market-structure-server)
- **Portfolio Impact**: Indirect - positioning signals for commodities, rates, FX
- **Data Freshness**: Weekly (released Friday afternoon)
- **Maintenance Burden**: Low - stable CFTC format
- **ROI Score**: ★★★ (Good for macro/commodity exposure)

**Implementation Sketch**:
```python
# Extend policy-events-service

@tool
async def cot_report(
    market: str,         # "ES" (S&P 500), "GC" (gold), "ZN" (10Y notes)
    report_type: str = "disaggregated",  # legacy|disaggregated|tff
    latest: bool = True
) -> Dict[str, Any]:
    """
    Fetch CFTC Commitments of Traders positioning data
    Returns: {date: {dealer_long: ..., asset_mgr_short: ..., net_position: ...}}
    """
    pass
```

**Agent Integration**:
- **macro-analyst**: Weekly COT snapshot for positioning analysis
- **risk-analyst**: Extreme positioning as contrarian indicator
- **market-scanner**: Flag crowded trades

**Quick Win Potential**: **YES** - Weekly snapshot for macro-analyst note

**Quick Win Implementation** (2 hours):
```python
# Add to macro-analyst agent
# Include in weekly macro context

cot = await cot_report("ES", latest=True)
net_position = cot["commercial_traders"]["net_position"]

if abs(net_position) > 2_std_devs:
    alert(f"Extreme positioning in S&P 500 futures: {net_position}")
```

**Integration Risks**:
- CFTC file format changes (rare but possible)
- Weekly release time varies
- Ensure deduping of late data corrections

**Mitigation**:
```python
# Validate file structure before parsing
def validate_cot_structure(df: pd.DataFrame) -> bool:
    required_cols = ["Market", "Long", "Short", "Net"]
    return all(col in df.columns for col in required_cols)

# Dedupe by report date + market
SEEN_REPORTS = set()  # (report_date, market_code)
```

---

#### 7. arch (Volatility & Risk Modeling) ★★★

**GitHub Research**:
```bash
gh repo view bashtage/arch --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/bashtage/arch
- **Status**: Release v8.0.0 (2025-10-21), 1.4k★, very active
- **Data Coverage**: GARCH family models, long memory volatility, bootstrap tools
- **Cost**: OSS (NCSA License)
- **Authentication**: None required

**ROI Analysis**:
- **Development Effort**: ~10 hours (augment risk_mcp_server)
- **Portfolio Impact**: Direct - regime-dependent ES with volatility clustering
- **Data Freshness**: Real-time (model fitting on historical data)
- **Maintenance Burden**: Medium - computational intensity
- **ROI Score**: ★★★ (Advanced risk modeling)

**Implementation Sketch**:
```python
# Augment risk_mcp_server

@tool
async def fit_garch(
    series: List[float],
    model: str = "GARCH",  # GARCH|EGARCH|GJR-GARCH
    horizon_days: int = 5
) -> Dict[str, Any]:
    """
    Fit GARCH model and forecast volatility
    Returns: {
        model_params: {...},
        forecast_variance: [...],
        confidence_intervals: {...}
    }
    """
    from arch import arch_model

    am = arch_model(series, vol=model)
    res = am.fit(disp='off')
    forecast = res.forecast(horizon=horizon_days)

    return {
        "model_params": res.params.to_dict(),
        "forecast_variance": forecast.variance.values[-1, :].tolist(),
        "aic": res.aic,
        "bic": res.bic
    }
```

**Agent Integration**:
- **risk-analyst**: Regime-dependent ES (high vol periods have higher ES)
- **portfolio-manager**: Dynamic hedging based on vol forecasts

**Quick Win Potential**: No (needs model diagnostics + caching)

**Integration Risks**:
- Computational intensity on large portfolios
- Provide sensible parameter defaults
- Fail fast on insufficient sample size

**Mitigation**:
```python
# Minimum sample size
MIN_OBSERVATIONS = 252  # 1 year daily data

if len(series) < MIN_OBSERVATIONS:
    raise ValueError(f"GARCH requires >= {MIN_OBSERVATIONS} observations")

# Timeout for optimization
FIT_TIMEOUT_SECONDS = 60
```

---

### Category: Sentiment & Alternative Signals

#### 8. PRAW (Reddit Sentiment) ★★★

**GitHub Research**:
```bash
gh repo view praw-dev/praw --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/praw-dev/praw
- **Status**: Release v7.8.1 (2024-10-25), 3.9k★, maintained
- **Data Coverage**: Full Reddit API wrapper; streaming or historical posts/comments
- **Cost**: Reddit API free tier (60 req/min, app registration required)
- **Authentication**: Reddit API credentials (client ID, secret)

**ROI Analysis**:
- **Development Effort**: ~12 hours (extend market-scanner with FinBERT sentiment)
- **Portfolio Impact**: Indirect - contrarian overlays and risk flagging
- **Data Freshness**: Real-time streaming
- **Maintenance Burden**: Medium - Reddit API policy shifts
- **ROI Score**: ★★★ (Good for sentiment analysis)

**Implementation Sketch**:
```python
# Extend market-scanner

@tool
async def reddit_sentiment(
    subreddit: str,        # "wallstreetbets", "stocks", "investing"
    tickers: List[str],    # Portfolio holdings
    lookback_hours: int = 24
) -> Dict[str, Any]:
    """
    Analyze Reddit sentiment for portfolio holdings
    Returns: {ticker: {mentions: N, sentiment: [-1,1], top_posts: [...]}}
    """
    import praw
    from transformers import pipeline

    # Initialize Reddit client
    reddit = praw.Reddit(...)

    # Fetch posts mentioning tickers
    posts = fetch_mentions(subreddit, tickers, lookback_hours)

    # Sentiment analysis with FinBERT
    sentiment_analyzer = pipeline("sentiment-analysis",
                                  model="ProsusAI/finbert")

    return analyze_sentiment(posts, sentiment_analyzer)
```

**Agent Integration**:
- **market-scanner**: Daily WSB mention heatmap
- **risk-analyst**: Flag extreme sentiment as contrarian indicator

**Quick Win Potential**: **YES** - Daily WSB mention heatmap

**Quick Win Implementation** (4 hours):
```python
# Add to /daily-check workflow
# In market-scanner agent

wsb_sentiment = await reddit_sentiment(
    subreddit="wallstreetbets",
    tickers=portfolio_tickers,
    lookback_hours=24
)

# Flag extreme mentions
for ticker, data in wsb_sentiment.items():
    if data["mentions"] > 100:  # Unusual activity
        alert(f"⚠️ {ticker}: {data['mentions']} WSB mentions (sentiment: {data['sentiment']:.2f})")
```

**Integration Risks**:
- Reddit API policy shifts
- Rate limiting (60 req/min)
- Credential rotation needed

**Mitigation**:
```python
# Exponential backoff
@retry(stop_max_attempt_number=5, wait_exponential_multiplier=1000)
async def reddit_request():
    return reddit.subreddit(name).new(limit=100)

# Credential rotation
REDDIT_CREDENTIALS = [
    {"client_id": "...", "client_secret": "..."},
    # Fallback credentials
]
```

---

#### 9. pytrends (Google Search Interest) ★★★

**GitHub Research**:
```bash
gh repo view GeneralMills/pytrends --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/GeneralMills/pytrends
- **Status**: Release v4.9.1 (2023-04-08), 3.5k★, updated 2025-10-20
- **Data Coverage**: Google Trends worldwide/regional search interest, topics, related queries
- **Cost**: Free (requires user-agent rotation; rate-limited by Google)
- **Authentication**: None (but rate limits apply)

**ROI Analysis**:
- **Development Effort**: ~8 hours (extend policy-events-service with caching)
- **Portfolio Impact**: Indirect - early demand/sentiment signal
- **Data Freshness**: Daily
- **Maintenance Burden**: Medium - captcha/rate limit management
- **ROI Score**: ★★★ (Good for consumer/healthcare holdings)

**Implementation Sketch**:
```python
# Extend policy-events-service

@tool
async def search_interest(
    query: str,           # "Tesla" or "TSLA"
    geo: str = "US",      # Geographic filter
    freq: str = "weekly"  # daily|weekly|monthly
) -> Dict[str, Any]:
    """
    Fetch Google search interest trends
    Returns: {date: interest_score, ...}
    """
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload([query], geo=geo, timeframe=get_timeframe(freq))

    return pytrends.interest_over_time().to_dict()
```

**Agent Integration**:
- **market-scanner**: Top 10 holdings with weekly update
- **macro-analyst**: Consumer demand signals
- **equity-analyst**: Product interest trends

**Quick Win Potential**: **YES** - Pilot for top 10 holdings with weekly update

**Quick Win Implementation** (3 hours):
```python
# Add to /daily-check workflow
# Weekly trend report for top holdings

top_holdings = portfolio.top_n_positions(10)

for ticker in top_holdings:
    trend = await search_interest(ticker, freq="weekly")

    # Alert on significant changes
    current_week = trend[-1]
    previous_week = trend[-2]
    change_pct = (current_week - previous_week) / previous_week

    if abs(change_pct) > 0.20:  # 20% change
        alert(f"{ticker}: Search interest {'up' if change_pct > 0 else 'down'} {change_pct:.0%}")
```

**Integration Risks**:
- Captcha/rate limits from Google
- Require rotating proxies or spacing requests

**Mitigation**:
```python
# User-agent rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    # Multiple user agents
]

# Request spacing
import asyncio
await asyncio.sleep(random.uniform(5, 10))  # Random delay
```

---

#### 10. sec-edgar-downloader (Bulk Filings) ★★★

**GitHub Research**:
```bash
gh repo view jadchaar/sec-edgar-downloader --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/jadchaar/sec-edgar-downloader
- **Status**: Release 5.0.3 (2025-02-14), 620★, updated 2025-10-10
- **Data Coverage**: Programmatic 10-K/Q, 8-K, 13D/G, Form 4 with ticker/CIK helpers
- **Cost**: Free (SEC fair-use norms; throttle to <10 req/sec)
- **Authentication**: None (User-Agent required)

**ROI Analysis**:
- **Development Effort**: ~14 hours (new sec-ingestion-server with storage design)
- **Portfolio Impact**: Indirect - complements existing section parser
- **Data Freshness**: Real-time as filed
- **Maintenance Burden**: Low - stable SEC format
- **ROI Score**: ★★★ (Good for insider trading signals)

**Implementation Sketch**:
```python
# New server: sec-ingestion-server

@tool
async def download_filings(
    ticker: str,
    form_type: str,  # "10-K", "10-Q", "8-K", "4"
    since: str       # "2024-01-01"
) -> Dict[str, Any]:
    """
    Download SEC filings with queue-based ingestion
    Returns: {filing_urls: [...], cached_paths: [...]}
    """
    from sec_edgar_downloader import Downloader

    dl = Downloader("Company", "email@example.com")
    dl.get(form_type, ticker, after=since)

    return {
        "filing_urls": list_downloaded_files(),
        "cached_paths": get_cache_paths()
    }
```

**Agent Integration**:
- **equity-analyst**: Insider trading Form 4 analysis
- **market-scanner**: 8-K event detection
- Complements existing `regulators_sec_section_extract` tool

**Quick Win Potential**: No (needs storage design + S3 hooks)

**Integration Risks**:
- SEC rate limiting (<10 req/sec)
- User-Agent compliance required
- Dedupe duplicate filings

**Mitigation**:
```python
# Rate limiting
RATE_LIMITER = AsyncLimiter(9, 1)  # 9 requests per second

async with RATE_LIMITER:
    response = await session.get(url, headers={"User-Agent": "..."})

# Dedupe by accession number
SEEN_FILINGS = set()  # accession numbers
```

---

### Category: Fixed Income & Derivatives

#### 11. QuantLib-SWIG (Pricing & Greeks) ★★★★

**GitHub Research**:
```bash
gh repo view lballabio/QuantLib-SWIG --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/lballabio/QuantLib-SWIG
- **Status**: Release v1.40 (2025-10-14), 370★, active upstream
- **Data Coverage**: Discount curves, bond pricing, swaption vols, credit instruments
- **Cost**: OSS (BSD); build-time dependency
- **Authentication**: None required

**ROI Analysis**:
- **Development Effort**: ~24 hours (including env build + curve loaders)
- **Portfolio Impact**: Direct - fills fixed-income analyst gap
- **Data Freshness**: Real-time pricing
- **Maintenance Burden**: High - SWIG compile complexity
- **ROI Score**: ★★★★ (High value, but build complexity)

**Implementation Sketch**:
```python
# New server: fixed-income-server

@tool
async def price_bond(
    cusip: str,
    curve_source: str = "treasury"  # treasury|swap|corporate
) -> Dict[str, Any]:
    """
    Price bond using QuantLib discount curve
    Returns: {price: ..., yield: ..., duration: ..., convexity: ...}
    """
    import QuantLib as ql

    # Build curve from Treasury data
    curve = build_discount_curve(curve_source)

    # Price bond
    bond = get_bond_from_cusip(cusip)
    engine = ql.DiscountingBondEngine(curve)
    bond.setPricingEngine(engine)

    return {
        "price": bond.cleanPrice(),
        "yield": bond.bondYield(bond.cleanPrice(), day_counter, ql.Compounded, ql.Annual),
        "duration": ql.BondFunctions.duration(bond, yield_rate),
        "convexity": ql.BondFunctions.convexity(bond, yield_rate)
    }

@tool
async def swaption_greeks(
    tenor: str,   # "5Y"
    strike: float
) -> Dict[str, Any]:
    """
    Calculate swaption Greeks
    Returns: {delta: ..., gamma: ..., vega: ..., theta: ...}
    """
    pass
```

**Agent Integration**:
- **fixed-income-analyst**: True pricing/yield analytics
- **risk-analyst**: Scenario shocks for ES gate
- **portfolio-manager**: Duration constraints

**Quick Win Potential**: No (SWIG compile + curve loaders)

**Integration Risks**:
- **Build Complexity**: Requires Boost, SWIG compilation
- Ensure packaged wheels for distribution
- Validate vs. Treasury quotes

**Mitigation**:
```python
# Pre-built Docker image with QuantLib
FROM quantlib/quantlib:latest

# Validation against market data
def validate_pricing(cusip: str, ql_price: float, market_price: float):
    diff = abs(ql_price - market_price)
    if diff > 0.01:  # 1 cent tolerance
        logger.warning(f"Price mismatch for {cusip}: QL={ql_price}, Market={market_price}")
```

---

### Category: Performance Attribution

#### 12. quantstats (Attribution & Reporting) ★★★★

**GitHub Research**:
```bash
gh repo view ranaroussi/quantstats --json stargazerCount,description,updatedAt,latestRelease
```

**Integration Profile**:
- **Repo**: https://github.com/ranaroussi/quantstats
- **Status**: Release 0.0.77 (2025-09-05), 6.3k★, updated 2025-10-21
- **Data Coverage**: Performance tear sheets, factor-style decomposition, rolling metrics
- **Cost**: OSS (Apache-2.0)
- **Authentication**: None required

**ROI Analysis**:
- **Development Effort**: ~10 hours (extend risk-server with HTML generation)
- **Portfolio Impact**: Direct - auto-generates decision artifacts
- **Data Freshness**: Real-time (on-demand)
- **Maintenance Burden**: Low - stable library
- **ROI Score**: ★★★★ (Missing attribution engine)

**Implementation Sketch**:
```python
# Extend risk-server

@tool
async def generate_tearsheet(
    returns: List[float],
    benchmark: List[float] = None,
    factors: Dict[str, List[float]] = None
) -> Dict[str, Any]:
    """
    Generate performance tear sheet with attribution
    Returns: {
        html_report: "...",
        metrics: {...},
        charts: [...]
    }
    """
    import quantstats as qs

    # Generate tear sheet
    qs.reports.html(returns, benchmark, output='tearsheet.html')

    # Extract metrics
    metrics = {
        "cagr": qs.stats.cagr(returns),
        "sharpe": qs.stats.sharpe(returns),
        "sortino": qs.stats.sortino(returns),
        "max_drawdown": qs.stats.max_drawdown(returns),
        "calmar": qs.stats.calmar(returns)
    }

    return {
        "html_report": read_file('tearsheet.html'),
        "metrics": metrics
    }
```

**Agent Integration**:
- **risk-analyst**: Generate tear sheets for risk reports
- **ic-memo-generator**: Include attribution charts in memos
- **portfolio-manager**: Compare optimization candidates

**Quick Win Potential**: **YES** - Create tear sheet for `/daily-check` session

**Quick Win Implementation** (4 hours):
```python
# Add to /daily-check workflow
# Generate monthly performance tear sheet

if day_of_month == 1:  # First of month
    returns = get_portfolio_returns(days_back=30)
    benchmark = get_benchmark_returns("SPY", days_back=30)

    tearsheet = await generate_tearsheet(returns, benchmark)

    # Save to session directory
    write_file(f"{session_path}/performance_tearsheet.html",
               tearsheet["html_report"])
```

**Integration Risks**:
- Depends on matplotlib/plotly for rendering
- Ensure headless rendering (no X server)
- Guard large HTML in MCP responses

**Mitigation**:
```python
# Headless matplotlib
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

# Limit HTML size
MAX_HTML_SIZE = 500_000  # 500KB
if len(html_report) > MAX_HTML_SIZE:
    # Return summary metrics only, save full HTML to file
    return {
        "html_report": None,
        "html_path": save_html_to_file(html_report),
        "metrics": metrics
    }
```

---

## Implementation Priority Matrix

### Immediate Implementation (Quick Wins - <4 hours)

1. **fredapi (FRED macro data)** ★★★★
   - Effort: 2 hours
   - Demo: Yield curve inversion in `/daily-check`
   - Impact: High-frequency macro signals

2. **quantstats (Performance tear sheets)** ★★★★
   - Effort: 4 hours
   - Demo: Monthly performance report
   - Impact: Missing attribution engine

3. **pandas-datareader (Fama-French)** ★★★★
   - Effort: 3 hours
   - Demo: ES factor decomposition
   - Impact: Risk attribution charts

4. **pytrends (Google search interest)** ★★★
   - Effort: 3 hours
   - Demo: Top 10 holdings trend alert
   - Impact: Demand signals

5. **PRAW (Reddit sentiment)** ★★★
   - Effort: 4 hours
   - Demo: WSB mention heatmap
   - Impact: Contrarian indicators

6. **cot_reports (CFTC positioning)** ★★★
   - Effort: 2 hours
   - Demo: Weekly COT snapshot
   - Impact: Macro positioning analysis

### Medium-Term (1-2 weeks)

7. **vectorbt (Backtesting)** ★★★★
   - Effort: 16 hours
   - Impact: Strategy validation (currently missing)

8. **arch (Volatility modeling)** ★★★
   - Effort: 10 hours
   - Impact: Regime-dependent ES

9. **census (Geographic exposure)** ★★★
   - Effort: 10 hours
   - Impact: Regional risk analysis

10. **backtrader (Event-driven backtests)** ★★★
    - Effort: 12 hours
    - Impact: Commission-aware testing

### Long-Term (1 month+)

11. **sec-edgar-downloader (Bulk filings)** ★★★
    - Effort: 14 hours
    - Impact: Insider trading signals

12. **QuantLib-SWIG (Fixed income pricing)** ★★★★
    - Effort: 24 hours
    - Impact: Fills fixed-income gap (high value but complex)

---

## Next Steps

1. **Quick Win Blitz** (Week 1): Implement all 6 quick wins (total ~18 hours)
   - Immediate value demonstration
   - Low risk, high visibility

2. **Backtesting Foundation** (Week 2-3): vectorbt + quantstats
   - Critical missing capability
   - Enables strategy validation

3. **Advanced Risk** (Week 4): arch + Fama-French full integration
   - Regime-dependent ES
   - Complete factor attribution

4. **Fixed Income** (Month 2): QuantLib-SWIG
   - Highest complexity, highest value for bond analytics

**Total Additional Integrations**: 12 (beyond initial roadmap of 4)
**Combined ROI**: 9 x ★★★★ (highest), 3 x ★★★

All integrations leverage **free/open source data** with **active maintenance** and **clear implementation paths**.

---

## Appendix: GitHub CLI Research Commands Used

Codex used these commands to research integrations:

```bash
# Repository discovery
gh search repos "financial data api" --language python --stars ">500" --sort stars
gh search repos "portfolio optimization" --language python --sort stars
gh search repos "quantitative finance" --language python --stars ">200"

# Repository analysis
gh repo view polakowo/vectorbt --json stargazerCount,description,updatedAt,latestRelease
gh repo view mortada/fredapi --json stargazerCount,description,updatedAt,latestRelease
gh repo view ranaroussi/quantstats --json stargazerCount,description,updatedAt,latestRelease

# Code usage examples
gh search code "import pandas_datareader" --language python
gh search code "openbb OR yfinance OR alpha_vantage" --language python --filename "*.py"

# Issue/PR activity
gh api repos/polakowo/vectorbt/issues --jq 'length'
gh api repos/mortada/fredapi/pulls --jq 'length'

# Release history
gh api repos/lballabio/QuantLib-SWIG/releases --jq '.[0] | {tag_name, published_at}'
```

This research methodology ensures **data-driven prioritization** based on:
- Community adoption (stars, forks)
- Maintenance status (recent commits, active issues)
- Integration maturity (release frequency, documentation)
- Real-world usage (code search results)
