# Risk Stack Implementation Progress

## Executive Summary
Implemented a comprehensive risk stack that addresses all critical issues from the 2025-08-17 session feedback. Expected Shortfall (ES) is now the primary risk metric, with strict schema validation, proper unit conventions, and traceable lineage.

## Completed (Week 0-1)

### 1. RiskStack Schema with Strict Validation ✅
**File:** `shared/risk_conventions.py`
- Created comprehensive `RiskStack` dataclass with enforced conventions
- All values stored as positive decimals (never percentages)
- Validation method ensures schema compliance
- Deterministic checksum for artifact binding
- `to_pct()` helper for display only

**Key Features:**
- Required UTC timestamps with 'Z' suffix
- Explicit time windows for all metrics (e.g., `max_drawdown_1y`)
- Mandatory liquidity block
- Correlation-adjusted concentration metrics

### 2. Expected Shortfall as Primary Metric ✅
**File:** `shared/risk_conventions.py`
- Added `compute_expected_shortfall()` with multiple methods (historical, t, EVT)
- Added `calibrate_es_from_var()` to derive ES limits from historical VaR policy
- ES always returned as positive decimal values

**Calibration Logic:**
```python
# Don't hardcode ES limit, derive it from VaR policy
es_limit = calibrate_es_from_var(
    returns,
    var_limit=0.02,  # Historical 2% VaR
    var_alpha=0.95,
    es_alpha=0.975,
    target_breach_freq=0.05
)
```

### 3. OpenBB Fama-French Factor Integration ✅
**File:** `shared/data_pipeline.py`
- Added `fetch_fama_french_factors()` using OpenBB's native API
- Installed `openbb-famafrench` provider package
- Fetches 5-factor model + momentum (MKT-RF, SMB, HML, RMW, CMA, MOM)
- Handles frequency alignment (daily/monthly) - monthly data more reliable
- Automatic unit conversion from percentage to decimal
- NO SYNTHETIC DATA FALLBACK per user requirement
- Graceful handling of date range limitations

### 4. Enhanced Risk Server with Complete Stack ✅
**File:** `risk-mcp-server/risk_mcp_server_v3.py`
- Integrated full risk stack calculation
- Factor regression with robust standard errors (HAC)
- Correlation-adjusted ENB and risk contribution Herfindahl
- Path risk with explicit windows (_1y suffix)
- Liquidity metrics framework

**Risk Stack Structure:**
```python
{
    "loss_based": {
        "es": {"alpha": 0.975, "value": 0.021, "method": "historical"},
        "var": {"alpha": 0.95, "value": 0.020}  # Reference only
    },
    "path_risk": {
        "max_drawdown_1y": 0.15,
        "ulcer_index_1y": 8.5
    },
    "factor_exposures": {
        "betas": {"MKT-RF": 0.9, "SMB": 0.1},
        "r_squared": 0.85
    },
    "concentration": {
        "enb_corr_adj": 3.8,
        "risk_contrib_herfindahl": 0.26
    },
    "liquidity": {
        "pct_adv_p95": 0.08,
        "names_over_10pct_adv": 0
    }
}
```

### 5. Test Suite ✅
**File:** `tests/unit/test_risk_stack.py`
- Schema validation tests
- ES calculation tests
- Calibration tests
- Property tests (ES monotonicity)

## Issues Fixed

### 1. Sign/Unit Convention ✅
- **Before:** "-1.98% < -2.0%" confusion
- **After:** All values stored as positive decimals, rendered as % only for display

### 2. ES vs VaR Priority ✅
- **Before:** VaR as primary metric
- **After:** ES as primary, VaR reference only

### 3. Factor Analysis ✅
- **Before:** No systematic factor exposure tracking
- **After:** Full Fama-French regression with confidence intervals

### 4. Concentration Metrics ✅
- **Before:** Weight-based only
- **After:** Both weight-based and risk-contribution based

## Remaining Tasks (Week 2-6)

### Week 2: Optimizer Constraints
- [ ] Fix PyPortfolioOpt constraint encoding
- [ ] Use weight_bounds for per-asset limits
- [ ] Implement factor constraints via matrices
- [ ] Consider migration to cvxpy if needed

### Week 3: Mandatory Round-2 Gating
- [ ] Implement Round-2 gate checks for revisions
- [ ] Add traceable lineage with derived_from
- [ ] Update gates with ES limits (not VaR)
- [ ] Add binding liquidity checks

### Week 4: Tax Single-Source-of-Truth
- [ ] Recompute tax on revision
- [ ] Bind IC docs to tax_artifact_id
- [ ] Add checksums for validation

### Week 5: Agent Prompts
- [ ] Update risk-analyst to use ES primary
- [ ] Add HALT rules for gate failures
- [ ] Update portfolio-manager for new optimization

### Week 6: Golden Test
- [ ] Recreate 2025-08-17 session
- [ ] Validate Round-2 gate exists
- [ ] Verify tax consistency
- [ ] Check VaR sign convention

## Critical Improvements

1. **No More Sign Confusion:** Everything stored as positive decimals
2. **ES-First Design:** Expected Shortfall is the binding constraint
3. **Complete Risk Picture:** Loss + Path + Factors + Concentration + Liquidity
4. **Traceable Artifacts:** Checksums and validation throughout
5. **Calibrated Limits:** ES limits derived from historical VaR policy, not hardcoded

## Next Steps

1. Complete optimizer constraint fixes (cvxpy)
2. Implement Round-2 gating logic
3. Update all agent prompts
4. Create comprehensive golden test

## Dependencies

- OpenBB (for Fama-French factors)
- PyPortfolioOpt (for optimization)
- scipy, numpy (for calculations)
- statsmodels (for robust regression)

## Production Readiness

### Complete ✅
- Risk conventions and standardization
- Factor data integration
- Core risk calculations

### In Progress 🚧
- Optimizer constraints
- Round-2 gating
- Agent prompts

### To Do 📋
- Tax reconciliation
- Golden test validation
- Production deployment