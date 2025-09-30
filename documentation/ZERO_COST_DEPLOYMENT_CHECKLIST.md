# Zero-Cost Data Provider Deployment Checklist

## Status: ✅ PRODUCTION READY

Based on comprehensive Codex review, implementation is ready for production deployment.

---

## Pre-Deployment Verification

### 1. Environment Variables

Required environment variables (all optional, but recommended for full functionality):

```bash
# Primary Quotes Provider (Unofficial Yahoo Finance)
export ENABLE_YAHOO_UNOFFICIAL=true

# Fallback Quotes Provider
export ALPHAVANTAGE_API_KEY=your_key_here  # Free tier: 5 calls/min, 500/day

# Analyst Coverage
export FINNHUB_API_KEY=your_key_here       # Free tier: 60 calls/min
export FMP_API_KEY=your_key_here           # Limited free tier: ~10 calls/min
```

**Verification**:
```bash
# Check which providers are available
python -c "
import os
print(f'Yahoo (unofficial): {os.getenv(\"ENABLE_YAHOO_UNOFFICIAL\", \"true\")}')
print(f'Alpha Vantage: {\"SET\" if os.getenv(\"ALPHAVANTAGE_API_KEY\") else \"NOT SET\"}')
print(f'Finnhub: {\"SET\" if os.getenv(\"FINNHUB_API_KEY\") else \"NOT SET\"}')
print(f'FMP: {\"SET\" if os.getenv(\"FMP_API_KEY\") else \"NOT SET\"}')
"
```

### 2. Dependencies

Verify `httpx` is installed (required for HTTP client):

```bash
source .venv/bin/activate
python -c "import httpx; print(f'httpx version: {httpx.__version__}')"
```

### 3. Test Suite

Run comprehensive test suite:

```bash
source .venv/bin/activate
pytest openbb-mcp-customizations/tests/test_zero_cost_tools.py -v

# Expected: 17/17 tests PASSED
```

### 4. Tool Registration

Verify all 17 tools are registered:

```bash
python -c "
from openbb_mcp_customizations.openbb_mcp_server.curated_tools import CURATED_TOOLS
zero_cost_tools = [
    'marketdata_quote', 'marketdata_quote_batch',
    'fx_quote', 'fx_convert', 'fx_historical',
    'economy_wb_indicator', 'economy_imf_series',
    'news_search', 'news_search_company',
    'equity_screener',
    'analyst_price_target', 'analyst_recommendations', 'analyst_estimates',
    'chart_line', 'chart_bar',
    'commodity_gold', 'commodity_silver'
]
registered = [t for t in zero_cost_tools if t in CURATED_TOOLS]
print(f'Registered: {len(registered)}/17')
print(f'Missing: {set(zero_cost_tools) - set(registered)}')
"
```

---

## Deployment Day Checklist

### Before Deployment

- [ ] Environment variables configured in production environment
- [ ] Test suite passes: 17/17 tests
- [ ] All 17 tools registered in `curated_tools.py`
- [ ] Logging level set to INFO or higher
- [ ] Backup of current production state created

### During Deployment

- [ ] Deploy code to production environment
- [ ] Verify MCP server starts without errors
- [ ] Check startup logs for provider registration messages:
  ```
  ✓ Registered 17 zero-cost custom MCP tools
  ✓ Frankfurter registered as primary FX provider (ECB official)
  ✓ Yahoo Finance registered as primary quote provider (unofficial)
  ```

### After Deployment

- [ ] Run smoke test with sample MCP calls:
  - `marketdata_quote` with symbols=["AAPL"]
  - `fx_convert` from_currency="USD", to_currency="EUR", amount=100
  - `economy_wb_indicator` indicator="NY.GDP.MKTP.CD", countries=["US"]
- [ ] Monitor logs for first 15 minutes:
  - No `ProviderUnavailableError` spikes
  - No unexpected `RateLimitError` patterns
  - Failover working correctly (Yahoo → Alpha Vantage if needed)
- [ ] Verify provenance disclaimers appear in responses

---

## Known Limitations & Warnings

### API Stability
- **Yahoo Finance**: Unofficial API may break without notice
  - **Mitigation**: Alpha Vantage failover configured
  - **Action if down**: Set `ENABLE_YAHOO_UNOFFICIAL=false`

### Rate Limits (Free Tiers)
- **Alpha Vantage**: 5 calls/min (strictly enforced)
- **Finnhub**: 60 calls/min
- **FMP**: ~10 calls/min (conservative estimate)
- **Yahoo**: No official limit (30/min throttle applied)
- **GDELT**: No strict limit (20/min throttle applied)

### Data Freshness
- **Frankfurter (FX)**: ECB official rates (end-of-day, updated daily)
- **LBMA (Gold/Silver)**: Daily fixes (end-of-day)
- **Yahoo (Quotes)**: Near real-time (15-second cache)
- **World Bank/IMF**: Historical data (not real-time)

---

## Monitoring Setup (Week 1)

### Critical Metrics

1. **Provider Availability**:
   - Track `ProviderUnavailableError` count per provider
   - Alert if Yahoo unavailable > 5 minutes
   - Alert if all providers for a capability fail

2. **Rate Limiting**:
   - Track `RateLimitError` count per provider
   - Alert if >10 rate limit errors/hour per provider
   - Monitor throttle quota usage

3. **Data Quality**:
   - Track `partial_errors` frequency
   - Monitor staleness warnings
   - Track fallback usage rate

### Log Patterns to Monitor

```bash
# Rate limit errors
grep "rate limited" /var/log/mcp-server.log

# Provider unavailable
grep "ProviderUnavailableError" /var/log/mcp-server.log

# Partial errors (some symbols failed)
grep "partial_errors" /var/log/mcp-server.log

# Circuit breaker state changes
grep "marked unavailable\|marked degraded\|marked healthy" /var/log/mcp-server.log
```

---

## Rollback Plan

If issues arise, follow this rollback procedure:

### Quick Disable (No Code Changes)
```bash
# Disable Yahoo Finance (use Alpha Vantage only)
export ENABLE_YAHOO_UNOFFICIAL=false
# Restart MCP server
```

### Full Rollback
1. Revert to previous git commit: `git revert <commit-hash>`
2. Restart MCP server
3. Verify original functionality restored
4. Investigate issues in development environment

---

## Post-Launch Improvements

See `documentation/AGENTS_TOOL_USAGE.md` for detailed improvement plan.

**Priority items (Week 1)**:
1. Fix Alpha Vantage double-throttling (1 hour)
2. Set up monitoring dashboard (2 hours)
3. Tune rate limits based on real usage (ongoing)

**Low priority (Month 1)**:
1. Fix `datetime.utcnow()` deprecation warnings
2. Expose public throttler API
3. Add integration tests with real APIs

---

## Support Contacts

- **Code Owner**: Claude (AI Assistant)
- **Repository**: https://github.com/hvkshetry/agentic-investment-management.git
- **Issues**: Create GitHub issue with logs and reproduction steps

---

## Version History

- **v1.0** (2025-09-30): Initial production deployment
  - 17 zero-cost MCP tools
  - Comprehensive test suite (17/17 passing)
  - Codex review approved for production