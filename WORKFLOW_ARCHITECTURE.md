# Workflow Architecture

**Status**: Production-ready workflows + planned enhancements
**Last Updated**: 2025-10-21
**Source**: Codex workflow coherence review

## Overview

This document defines the coherent workflow architecture for the investment management system. Each workflow is designed as a deterministic sequence of agent calls with clear inputs, outputs, and success criteria.

## Design Principles

1. **Tool-First Data**: All metrics must come from MCP tool calls with provenance
2. **Fail-Fast Validation**: Check prerequisites before expensive operations
3. **Minimal Tool Sets**: Each workflow uses only tools it actually needs
4. **Clear Agent Roles**: Agents have defined responsibilities and don't overlap
5. **Artifact Contracts**: Standardized JSON schemas for data interchange
6. **Audit Trail**: Complete session history in `./runs/<timestamp>/`

## Core Workflows (Production-Ready)

### 1. /import-portfolio

**Purpose**: Import broker CSV files and validate portfolio state

**Agents**: `@portfolio-manager`

**Tools**:
- `Read` - Read CSV files from portfolio/ directory
- `mcp__portfolio-state-server__import_broker_csv` - Import positions and tax lots
- `mcp__portfolio-state-server__get_portfolio_state` - Validate import
- `Write` - Create import summary

**Inputs**: None (reads from `portfolio/*.csv`)

**Outputs**:
- `import_summary.json` - Import status, positions count, validation
- Portfolio state persisted in MCP server

**Success Criteria**:
- All CSV files parsed successfully
- No duplicate positions
- Tax lots validated with acquisition dates
- Total portfolio value matches broker statements

**Example**:
```
/import-portfolio
```

---

### 2. /daily-check (Revised)

**Purpose**: Daily portfolio monitoring with risk assessment and news scanning

**Agents**: `@market-scanner`, `@risk-analyst`

**Tools**:
- `mcp__portfolio-state-server__get_portfolio_state` - Get current state
- `mcp__openbb-curated__news_company` - Position-level news
- `mcp__policy-events-service__get_recent_bills` - Congressional activity
- `mcp__policy-events-service__get_federal_rules` - Regulatory changes
- `mcp__risk-server__analyze_portfolio_risk` - ES and gate validation
- `Write` - Create artifacts

**Inputs**: None

**Prerequisites**: Portfolio state must be T+1 or newer (fail fast if stale)

**Outputs**:
- `market_scan.json` - News sentiment, policy events
- `portfolio_check.json` - Current allocation, daily change
- `risk_check.json` - ES @ 97.5%, gate validation results
- `daily_note.md` - Executive summary with action items

**Success Criteria**:
- State freshness validated (T+1 check)
- ES @ 97.5% ≤ 2.5% (Risk Alert Level 3 - CRITICAL if breached)
- Concentration check: no single stock >20% (funds exempt)
- News scan completed for all portfolio tickers

**Key Changes from Original**:
- ❌ Removed `import_broker_csv` from allowed-tools (use `/import-portfolio` instead)
- ✅ Added fail-fast state freshness check
- ✅ Added `get_federal_rules` for regulatory news

**Example**:
```
/daily-check
```

---

### 3. /rebalance (Tightened)

**Purpose**: Full institutional-grade portfolio rebalancing with multiple optimization methods

**Agents**:
- `@portfolio-manager` (lead)
- `@risk-analyst`
- `@tax-advisor`
- `@macro-analyst`
- `@gate-validator`
- `@ic-memo-generator`

**Tools** (Consolidated):
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__portfolio-optimization-server__optimize_portfolio_advanced`
- `mcp__risk-server__analyze_portfolio_risk`
- `mcp__tax-server__calculate_comprehensive_tax`
- `mcp__tax-optimization-server__optimize_portfolio_for_taxes`
- `mcp__openbb-curated__economy_cpi` - Inflation context
- `mcp__openbb-curated__fixedincome_government_yield_curve` - Yield curve
- `mcp__policy-events-service__get_recent_bills`
- `mcp__policy-events-service__get_federal_rules`
- `Write`

**Inputs**: Target allocation (e.g., "80% equity, 20% fixed income")

**Prerequisites**: `portfolio_snapshot.json` from `/import-portfolio` or `/daily-check`

**Outputs**:
- `portfolio_snapshot.json` - Current state
- `macro_context.json` - Economic backdrop
- `optimization_candidate_hrp.json` - Hierarchical Risk Parity
- `optimization_candidate_maxsharpe.json` - Maximum Sharpe ratio
- `optimization_candidate_riskparity.json` - Equal risk contribution
- `risk_report_*.json` - Risk validation for each candidate
- `tax_impact_*.json` - Tax consequences for each candidate
- `gate_validation.json` - Policy gate results
- `trade_list.json` - Final recommended trades
- `ic_memo.md` - Investment Committee memo

**Success Criteria**:
- Multiple optimization methods tested (HRP, MaxSharpe, RiskParity)
- ES @ 97.5% ≤ 2.5% for selected candidate (Risk Alert Level 3 - CRITICAL if breached)
- Tax impact calculated with provenance
- Policy gates passed (Risk, Tax, Compliance, Realism, Credibility)
- Round-2 gate validation completed
- Trade list with specific lot selection (FIFO/HIFO)

**Example**:
```
/rebalance with target allocation: 60% equity, 35% fixed income, 5% cash
```

---

## New High-Priority Workflows

### 4. /research-equity (NEW)

**Purpose**: Comprehensive equity research with fundamental analysis and valuation

**Agents**: `@equity-analyst`, `@market-scanner`

**Tools**:
- `mcp__openbb-curated__equity_profile` - Company info, sector, industry
- `mcp__openbb-curated__equity_fundamental_metrics` - ROE, margins, ratios
- `mcp__openbb-curated__equity_fundamental_income` - P&L statements
- `mcp__openbb-curated__equity_fundamental_balance` - Balance sheet
- `mcp__openbb-curated__equity_estimates_consensus` - Analyst targets
- `mcp__openbb-curated__news_company` - Recent news
- `mcp__openbb-curated__equity_price_historical` - Price performance
- `Write`

**Inputs**: Comma-separated tickers (e.g., "AAPL,MSFT,GOOGL")

**Outputs**:
- `company_profiles.json` - Basic company info
- `fundamental_analysis.json` - Key financial ratios
- `valuation_snapshot.json` - P/E, P/B, analyst targets
- `news_summary.json` - Recent developments
- `equity_research.md` - Comprehensive analysis with recommendation

**Success Criteria**:
- Financial metrics retrieved for all tickers
- Analyst consensus included (price targets, recommendations)
- Comparative analysis if multiple tickers
- Investment thesis with bull/bear cases
- Clear recommendation with price target

**Example**:
```
/research-equity AAPL,MSFT,GOOGL
```

---

### 5. /tax-planning (NEW)

**Purpose**: Quarterly tax planning with liability estimation and TLH opportunities

**Agents**: `@tax-advisor`

**Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__portfolio-state-server__simulate_sale`
- `mcp__tax-server__calculate_comprehensive_tax`
- `mcp__tax-optimization-server__find_tax_loss_harvesting_pairs`
- `Write`

**Inputs**: Quarter (e.g., "Q1", "Q2", "Q3", "Q4")

**Prerequisites**: Current portfolio state

**Outputs**:
- `tax_estimate_<quarter>.json` - Federal/state/NIIT liability
- `tlh_opportunities.json` - Ranked harvesting candidates
- `sale_simulations.json` - Tax impact of different scenarios
- `tax_plan_<quarter>.md` - Comprehensive action plan
- `tax_actions.json` - Specific trades to execute

**Success Criteria**:
- Tax liability calculated for federal, state, NIIT
- TLH opportunities ranked by tax savings
- Wash sale compliance verified (30-day rule)
- Cost basis method documented (FIFO/HIFO)
- Year-end projection included (Q4 only)

**Example**:
```
/tax-planning Q4
```

---

### 6. /performance-review (NEW)

**Purpose**: Quarterly performance attribution and benchmark comparison

**Agents**: `@risk-analyst`, `@ic-memo-generator`

**Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__risk-server__analyze_portfolio_risk` - Performance metrics
- `mcp__openbb-curated__equity_price_historical` - Position returns
- `mcp__openbb-curated__index_price_historical` - Benchmark returns
- `mcp__openbb-curated__etf_holdings` - Fund lookthrough (if needed)
- `Write`

**Inputs**: Benchmark symbol (e.g., "SPY", "AGG", "60/40")

**Prerequisites**: Historical transaction data in portfolio state

**Outputs**:
- `attribution.json` - Performance breakdown by asset class/sector/position
- `risk_adjusted_metrics.json` - Sharpe, Sortino, drawdown vs benchmark
- `holdings_performance.json` - Position-level returns
- `performance_report.md` - Comprehensive analysis
- `performance_summary.json` - Executive metrics

**Success Criteria**:
- Time-weighted returns calculated (1M, 3M, 12M, YTD)
- Benchmark comparison for same periods
- Attribution by asset class, sector, security selection
- Risk-adjusted metrics (Sharpe, Sortino, max drawdown)
- Top contributors and detractors identified

**Example**:
```
/performance-review SPY
```

For blended benchmarks:
```
/performance-review 60/40 (60% SPY, 40% AGG)
```

---

## Future Workflows (Planned)

Located in `.claude/commands/future/` with detailed prerequisites and implementation notes.

### 7. /factor-analysis (PLANNED)

**Purpose**: Analyze portfolio factor exposures using Fama-French multi-factor model

**Status**: Requires OpenBB Fama-French provider exposure via `openbb-curated`

**Prerequisites**:
- Expose `openbb.equity.fundamental.metrics` with famafrench provider
- Add factor exposure output to risk-server
- Implement factor regression in portfolio-optimization-server

**Tools** (When Ready):
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__openbb-curated__famafrench_factor_loadings` (not yet exposed)
- `mcp__risk-server__analyze_portfolio_risk` (needs factor extension)
- `Write`

**Expected Outputs**:
- `factor_exposures.json` - FF3/FF5 loadings (Market, SMB, HML, RMW, CMA)
- `factor_risk_decomposition.json` - ES-by-factor breakdown
- `factor_attribution.json` - Return decomposition by factor
- `factor_analysis.md` - Portfolio tilts, hedging ideas

**Implementation Priority**: Medium (requires extending OpenBB integration)

---

### 8. /options-overlay (PLANNED)

**Purpose**: Design options overlay strategy for income or protection

**Status**: Requires QuantLib integration and Greeks calculation

**Prerequisites**:
- Integrate QuantLib pricing engine
- Add Greeks calculation (Delta, Gamma, Vega, Theta)
- Extend portfolio-state-server for options positions
- Add options risk metrics to risk-server

**Tools** (When Ready):
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__openbb-curated__derivatives_options_chains` (already available)
- `mcp__quantlib__price_options` (not yet implemented)
- `mcp__quantlib__calculate_greeks` (not yet implemented)
- `mcp__risk-server__analyze_portfolio_risk` (needs options extension)
- `Write`

**Expected Outputs**:
- `options_chains.json` - Filtered options data
- `options_pricing.json` - Theoretical values and Greeks
- `strategy_design.json` - Overlay structure (covered call, protective put, collar)
- `options_risk_analysis.json` - Portfolio Greeks and stress tests
- `options_overlay.md` - Implementation plan

**Implementation Priority**: Medium (significant dev work, but high value)

---

### 9. /tax-harvest-scan (PLANNED)

**Purpose**: Automated daily TLH scan with actionable trade recommendations

**Status**: Requires automated lot scoring and calendar scheduling

**Prerequisites**:
- Implement automated lot scoring algorithm
- Add calendar scheduling for daily scans
- Wash sale tracking across all accounts
- Optional: Direct broker integration for execution

**Tools** (When Ready):
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__tax-optimization-server__find_tax_loss_harvesting_pairs` (already available)
- `mcp__tax-server__calculate_comprehensive_tax`
- `mcp__openbb-curated__equity_price_historical`
- `Write`

**Expected Outputs**:
- `tlh_scan_<date>.json` - Ranked opportunities
- `wash_sale_calendar.json` - Blocked periods
- `tax_impact_forecast.json` - Estimated savings
- `tlh_trade_list_<date>.json` - Exact trade instructions
- `tlh_scan_report_<date>.md` - Actionable recommendations

**Implementation Priority**: High (but requires automation infrastructure)

---

## Tool Consolidation Strategy

Per Codex review, we consolidate data sources to reduce complexity:

### Keep (7 MCP Servers)

1. **portfolio-state-server** - Single source of truth for holdings/tax lots
2. **risk-server-v3** - ES gating, performance metrics, stress tests
3. **portfolio-optimization-v3** - PyPortfolioOpt/Riskfolio integration
4. **tax-server-v2** - Federal/state/NIIT calculations
5. **tax-optimization-oracle** - Tax-aware optimization (CBC solver)
6. **openbb-curated** - Unified data source (extends to cover more)
7. **policy-events-service** - Congress/regulatory (extends to market structure)

### Extend Existing Servers

**OpenBB-Curated Extensions**:
- ✅ Expose Fama-French factors (use `openbb.equity.fundamental.metrics` with famafrench provider)
- ✅ Performance attribution (use `openbb.equity.price.performance` router)
- ✅ COT reports (use `openbb.regulators.cftc` provider)

**Risk-Server Extensions**:
- Add `generate_performance_report` tool (wraps internal analytics + OpenBB benchmarks)
- Add factor exposure output (for `/factor-analysis` workflow)
- Add options risk metrics (portfolio Greeks, gamma exposure)

**Policy-Events-Service Extensions**:
- Add market structure alerts (FINRA short interest, trading halts)
- Integrate with `openbb.regulators.finra` when available

### Exclude/Defer

**Redundant with OpenBB**:
- ❌ pandas-datareader wrapper
- ❌ fredapi wrapper
- ❌ cot_reports standalone
- ❌ quantstats wrapper (use risk-server + OpenBB benchmarks)

**Low ROI**:
- ❌ PRAW Reddit sentiment (high maintenance, low signal vs GDELT)

**Defer Until Workflows Require**:
- ⏸️ vectorbt server (defer until advanced backtesting workflow)
- ⏸️ backtrader server (defer until strategy simulation workflow)
- ⏸️ QuantLib server (needed for `/options-overlay` - medium priority)

### Consolidation Benefits

1. **Reduced Complexity**: 7 servers vs 12+ if all proposed integrations were standalone
2. **Single Data Source**: OpenBB Platform covers FRED, Fama-French, COT, benchmarks
3. **Consistent API**: All financial data through OpenBB provider interface
4. **Lower Maintenance**: One update path instead of multiple library dependencies
5. **Better Reliability**: OpenBB Platform tested and widely used

---

## Workflow Execution Model

### Session Management

Every workflow creates a timestamped session directory:

```
./runs/20251021_143000/
├── portfolio_snapshot.json       # Current holdings
├── macro_context.json            # Economic analysis
├── optimization_candidate_*.json # Multiple strategies tested
├── risk_report_*.json            # Risk validation
├── tax_impact_*.json             # Tax consequences
├── gate_validation.json          # Policy compliance
├── trade_list.json               # Final orders
└── ic_memo.md                    # Executive summary
```

### Agent Coordination

Agents write to the same session directory and read each other's artifacts:

1. **Sequential Dependencies**: `@macro-analyst` → `@portfolio-manager` → `@risk-analyst`
2. **Parallel Analysis**: Risk and tax validation can run concurrently
3. **Gate Validation**: Always last step before trade generation
4. **IC Memo**: Synthesizes all artifacts into executive summary

### Success Criteria

Every workflow has explicit success criteria:

- **Data Provenance**: All metrics from MCP tools with timestamps
- **Schema Compliance**: Artifacts match `schemas/artifact_schemas.json`
- **Gate Validation**: ES ≤ 2.5%, concentration ≤ 20%, wash sale compliance
- **Audit Trail**: Complete session history for regulatory compliance

---

## Implementation Roadmap

### Phase 1: Core Workflows (✅ Complete)

- [x] `/import-portfolio` - Production ready
- [x] `/daily-check` - Refactored (removed CSV import, added fail-fast)
- [x] `/rebalance` - Production ready (tighten tool list)

### Phase 2: New High-Priority Workflows (⏳ In Progress)

- [x] `/research-equity` - Slash command created (2025-10-21)
- [x] `/tax-planning` - Slash command created (2025-10-21)
- [x] `/performance-review` - Slash command created (2025-10-21)
- [ ] Test all three new workflows with real data
- [ ] Update agent prompts if needed
- [ ] Document in README.md

### Phase 3: OpenBB Extensions (Next)

- [ ] Expose Fama-French factors via `openbb-curated`
- [ ] Add performance report tool to `risk-server`
- [ ] Extend `policy-events-service` for market structure alerts
- [ ] Update TOOLS_GUIDE.md with new tools

### Phase 4: Future Workflows (Planned)

- [ ] `/factor-analysis` - After OpenBB Fama-French exposure
- [ ] `/options-overlay` - After QuantLib integration
- [ ] `/tax-harvest-scan` - After automation infrastructure

---

## Slash Command Conventions

All slash commands follow consistent structure:

```markdown
---
description: Brief description of workflow purpose
allowed-tools: tool1, tool2, tool3 (only tools actually used)
argument-hint: <param> (e.g., "SPY") - Optional parameter hint
---

Detailed workflow description...

## Prerequisites
List any preconditions (e.g., portfolio state must be current)

## Workflow Steps
1-5 steps with specific tool calls

## Agents Used
List agents with their roles

## Output Location
Where artifacts are saved

## Success Criteria
Explicit success conditions

## Example Usage
Concrete examples with actual commands
```

---

## Conclusion

This architecture provides:

1. **Coherence**: Every tool serves a clear workflow purpose
2. **Elegance**: Minimal tool set, consolidated data sources
3. **Extensibility**: Clear path for adding new workflows
4. **Maintainability**: Single source for each data type
5. **Auditability**: Complete session history with provenance

The system now has **6 production workflows** (3 existing + 3 new) and **3 planned workflows** with clear prerequisites and implementation paths.
