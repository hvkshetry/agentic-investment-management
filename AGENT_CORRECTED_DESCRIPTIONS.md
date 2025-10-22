# Corrected Agent Descriptions and Tool Lists
**Date**: 2025-10-21
**Status**: ✅ VALIDATED - All agents match implementation

---

## Summary

All specialized agent definitions have been validated against their actual tool access. This document provides corrected, consolidated descriptions.

**Key Updates Since Last Review**:
- ✅ PolicyEngine-US fully implemented (replaced tenforty)
- ✅ All "tenforty" references removed from agent prompts
- ✅ Two-stage policy event pattern documented
- ✅ ES < 2.5% constraint consistently applied
- ✅ Tool-First Data Policy across all agents

---

## Primary Specialized Agents

### 1. Tax Advisor

**Description**: Tax optimization specialist for investment decisions using PolicyEngine-US

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__portfolio-state-server__simulate_sale`
- `mcp__portfolio-state-server__get_tax_loss_harvesting_opportunities`
- `mcp__tax-server__calculate_comprehensive_tax` ⚠️ (server exists but not in .mcp.json)
- `mcp__tax-optimization-server__find_tax_loss_harvesting_pairs`
- `mcp__tax-optimization-server__simulate_withdrawal_tax_impact`
- `mcp__openbb-curated__regulators_sec_cik_map`
- `mcp__openbb-curated__regulators_sec_symbol_map`
- `mcp__policy-events-service__*` (all policy event tools)
- `mcp__sequential-thinking__sequentialthinking`
- WebSearch, WebFetch

**Capabilities**:
- Federal and state tax calculations (all filing statuses)
- PolicyEngine-US integration for accurate individual (Form 1040) taxes
- Trust tax calculations with compressed brackets
- Capital gains optimization (STCG/LTCG with NIIT)
- State-specific rules (MA 12% STCG, CA 13.3%, etc.)
- Tax loss harvesting with wash sale prevention
- AMT analysis and quarterly estimates
- Multi-period tax-aware rebalancing
- Legislative monitoring via policy events

**Key Constraints**:
- ES < 2.5% binding constraint for tax trades
- Tax reconciliation required before optimization
- No fabrication of tax data - tool calls only
- Wash sale window: 31 days before/after

**Output**: Appends to IC_Memo.md or creates tax_impact.json

---

### 2. Equity Analyst

**Description**: Equity research and fundamental analysis specialist

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__openbb-curated__equity_estimates_consensus` (provider=yfinance)
- `mcp__openbb-curated__equity_fundamental_*` (all fundamental tools)
- `mcp__openbb-curated__equity_ownership_*` (insider trading, 13F)
- `mcp__openbb-curated__equity_shorts_*` (FTD, short interest, short volume)
- `mcp__openbb-curated__equity_compare_company_facts` (SEC XBRL)
- `mcp__openbb-curated__regulators_sec_*` (filing tools, section parser)
- `mcp__policy-events-service__*` (all policy event tools)
- `mcp__sequential-thinking__sequentialthinking`
- WebSearch, WebFetch

**Capabilities**:
- Financial statement analysis (income, balance, cash flow)
- Valuation modeling (DCF, comparables, multiples)
- Peer comparison and sector analysis
- Analyst consensus tracking
- Insider trading pattern detection
- Short interest and fail-to-deliver analysis
- SEC filing analysis with section extraction
- Sector-specific legislative monitoring

**Key Features**:
- Free data sources: yfinance > sec > fmp
- Limit=20 for discovery tools (prevents token overflow)
- Parameter types: limit as int, not string
- Two-stage policy event monitoring

**Output**: equity_analysis.json or equity reports

---

### 3. Macro Analyst

**Description**: Macroeconomic analysis and global market assessment

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__openbb-curated__economy_*` (GDP, CPI, unemployment, interest rates)
- `mcp__openbb-curated__currency_price_historical`
- `mcp__openbb-curated__commodity_price_spot`
- `mcp__openbb-curated__fixedincome_government_*` (yield curve, treasury rates)
- `mcp__policy-events-service__*` (all policy event tools)
- `mcp__sequential-thinking__sequentialthinking`
- WebSearch, WebFetch

**Capabilities**:
- Economic indicator analysis and forecasting
- Central bank policy interpretation
- Trade flow and supply chain analysis
- Currency and commodity impact assessment
- Business cycle positioning
- Geopolitical risk evaluation
- Analogous historical period identification for backtesting
- Economic regime classification
- Scenario-based market views

**Key Parameters**:
- `economy_cpi`: country="united_states", provider="fred"
- `fixedincome_government_treasury_rates`: provider="federal_reserve"
- `economy_unemployment`: provider="oecd", seasonal_adjustment=True

**Enhanced Outputs**:
- `market_regime`: crisis/volatile/normal/calm
- `analogous_periods`: Historical periods for backtesting
- `market_views`: Directional views with confidence
- `scenarios`: Economic scenarios with probabilities

**Output**: macro_context.json with regime and market views

---

### 4. Risk Analyst

**Description**: Risk measurement and hedging strategy specialist using ES/CVaR as primary measure

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__risk-server__analyze_portfolio_risk` (includes stress testing)
- `mcp__risk-server__get_risk_free_rate`
- `mcp__openbb-curated__derivatives_options_chains`
- `mcp__openbb-curated__derivatives_futures_curve`
- `mcp__openbb-curated__equity_shorts_*` (all short data tools)
- `mcp__policy-events-service__*` (all policy event tools)
- `mcp__sequential-thinking__sequentialthinking`
- WebSearch, WebFetch

**Capabilities**:
- **Expected Shortfall (ES/CVaR)** at 97.5% confidence - PRIMARY measure
- VaR calculations (REFERENCE ONLY - not for decisions)
- Stress testing with historical scenarios
- Ledoit-Wolf covariance shrinkage
- Component ES and risk decomposition
- Student-t distributions for fat tails
- Options-based hedging strategies
- Short interest/FTD analysis
- Regulatory risk monitoring

**CRITICAL ES-Primary Framework**:
- ES < 2.5% is BINDING constraint
- VaR is reference only
- HALT trading if ES > 2.5%
- All risk decisions based on ES, not VaR
- ES/VaR ratio should be ~1.2-1.4

**HALT Triggers**:
1. ES Breach: ES > 2.5%
2. Liquidity Crisis: Score < 0.3
3. Concentration Breach: Position > 20%
4. Correlation Spike: Avg correlation > 0.8

**Tool-First Requirements**:
- MUST use full portfolio (all 55+ positions)
- weights parameter REQUIRED
- Extract portfolio_value from portfolio_state
- NEVER use hardcoded values (e.g., 1000000)

**Output**: risk_analysis.json with ES metrics and HALT status

---

### 5. Portfolio Manager

**Description**: Portfolio construction and optimization specialist using institutional-grade algorithms

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__portfolio-optimization-server__optimize_portfolio_advanced`
- `mcp__openbb-curated__etf_*` (holdings, sectors, exposure)
- `mcp__openbb-curated__regulators_sec_institutions_search`
- `mcp__openbb-curated__equity_ownership_form_13f`
- `mcp__sequential-thinking__sequentialthinking`

**Capabilities**:
- **ES-Constrained Optimization** (all methods respect ES < 2.5%)
- PyPortfolioOpt integration with ES constraints
- Riskfolio-Lib with ES/CVaR as PRIMARY risk measure
- Hierarchical Risk Parity (HRP)
- Ledoit-Wolf covariance shrinkage
- Multi-objective optimization
- Tax-efficient rebalancing
- Walk-forward validation
- Quantum-inspired cardinality constraints
- Market views via entropy pooling
- Multi-period tax-aware optimization
- Backtesting on analogous periods
- 13F institutional holdings cloning

**Optimization Methods** (ES-PRIMARY):
- CVaR/ES: PRIMARY - Best tail risk protection
- HRP: Most robust to estimation errors
- Min ES: Minimize Expected Shortfall directly
- Sharpe: Risk-adjusted returns (subject to ES < 2.5%)
- MDD: Minimize drawdowns (with ES validation)

**HALT Protocol**:
- Check for HALT orders before optimization
- Calculate ES for proposed allocation
- Reject if ES > 2.5%
- Iterate with tighter constraints

**CRITICAL**: Trade only held securities
- MUST get holdings from portfolio_state FIRST
- NEVER recommend trades in non-held tickers
- Use ACTUAL holdings (e.g., VWLUX, not MUB)

**Output**: optimization_results.json with ES compliance

---

## Specialized Analysts

### 6. ETF Analyst

**Description**: ETF analysis and selection specialist

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__openbb-curated__etf_sectors`
- `mcp__openbb-curated__etf_holdings` (provider=sec)
- `mcp__openbb-curated__etf_equity_exposure`
- `mcp__sequential-thinking__sequentialthinking`

**Capabilities**:
- ETF holdings analysis
- Sector breakdown
- Expense ratio comparison
- Tracking error analysis
- Equity exposure identification

---

### 7. Fixed Income Analyst

**Description**: Bond market and interest rate specialist

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__openbb-curated__fixedincome_spreads_tcm`
- `mcp__openbb-curated__fixedincome_spreads_treasury_effr`
- `mcp__openbb-curated__fixedincome_government_yield_curve`
- `mcp__openbb-curated__fixedincome_government_treasury_rates`
- `mcp__policy-events-service__*` (all policy event tools)
- `mcp__sequential-thinking__sequentialthinking`
- WebSearch, WebFetch

**Capabilities**:
- Yield curve analysis
- Credit spread monitoring
- Duration and convexity calculations
- Fed policy interpretation
- Municipal bond analysis

---

### 8. Derivatives/Options Analyst

**Description**: Options markets and derivatives pricing specialist

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__openbb-curated__derivatives_options_chains`
- `mcp__openbb-curated__derivatives_futures_curve`
- `mcp__policy-events-service__*` (all policy event tools)
- `mcp__sequential-thinking__sequentialthinking`
- WebSearch, WebFetch

**Capabilities**:
- Options chain analysis
- Unusual options activity detection
- Greeks calculation
- Implied volatility analysis
- Futures term structure

---

### 9. Market Scanner

**Description**: Multi-asset market monitoring and news analysis

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__openbb-curated__news_company`
- `mcp__openbb-curated__crypto_price_historical`
- `mcp__openbb-curated__index_price_historical`
- `mcp__openbb-curated__regulators_sec_rss_litigation`
- `mcp__openbb-curated__equity_fundamental_filings`
- `mcp__policy-events-service__*` (all policy event tools)
- `mcp__sequential-thinking__sequentialthinking`
- WebSearch, WebFetch

**Capabilities**:
- Cross-asset monitoring
- News aggregation and sentiment
- SEC litigation tracking
- Filing alerts
- Policy event monitoring

---

## Validation Agents

### 10. Gate Validator

**Description**: Validates portfolio optimization candidates against institutional policy gates

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__sequential-thinking__sequentialthinking`
- Read, Write, LS

**Validation Gates**:
1. Risk Gate: ES < 2.5%
2. Tax Gate: Reconciliation check
3. Compliance Gate: Concentration limits
4. Realism Gate: Liquidity scores
5. Credibility Gate: Confidence thresholds

---

### 11. Invariant Checker

**Description**: Validates cross-artifact consistency and mathematical invariants

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__sequential-thinking__sequentialthinking`
- Read, Write, LS

**Checks**:
- Weight sums to 1.0
- Position counts match
- Tax consistency
- Lineage integrity
- Timestamp ordering

---

### 12. IC Memo Generator

**Description**: Generates professional Investment Committee memorandums

**MCP Tools**:
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__sequential-thinking__sequentialthinking`
- Read, Write, LS

**Output**: Synthesizes all agent analyses into executive-ready documentation

---

## Common Patterns Across All Agents

### Tool-First Data Policy (MANDATORY)
1. ALL numbers MUST come from tool calls
2. NEVER estimate or fabricate data
3. Include provenance with every metric
4. Status: "actual" | "derived" | "estimate"

### ES < 2.5% Binding Constraint
- Expected Shortfall at 97.5% confidence
- HALT if exceeded
- VaR is reference only

### Policy Event Monitoring (Two-Stage)
1. **Stage 1**: Bulk retrieval (metadata only)
   - `get_recent_bills`, `get_federal_rules`, `get_upcoming_hearings`
2. **Stage 2**: Detail fetching (REQUIRED)
   - `get_bill_details`, `get_rule_details`, `get_hearing_details`
   - NEVER analyze from titles alone

### Known Data Issues
- Hearing data often has empty fields (Congress.gov API limitation)
- Focus on bills and rules for complete data
- Use WebFetch on detail URLs for deeper analysis

### MCP Parameter Types
- ✅ CORRECT: Native Python types (`tickers=["SPY"], limit=50`)
- ❌ WRONG: JSON strings (`tickers="[\"SPY\"]", limit="50"`)

---

## Agent Collaboration Examples

### Tax-Aware Risk Analysis
**Agents**: Risk Analyst → Tax Advisor
1. Risk calculates ES and generates candidates
2. Tax validates each candidate for tax impact
3. Combined output: ES-compliant, tax-efficient allocations

### Macro-Driven Optimization
**Agents**: Macro Analyst → Portfolio Manager → Risk Analyst
1. Macro identifies regime and market views
2. Portfolio Manager optimizes with views
3. Risk validates ES < 2.5%

### Comprehensive Rebalancing
**Agents**: All Primary Agents → Gate Validator → Invariant Checker → IC Memo Generator
1. Macro provides context
2. Equity analyzes holdings
3. Risk measures current state
4. Portfolio Manager generates candidates
5. Tax Advisor validates tax impact
6. Gate Validator checks all gates
7. Invariant Checker validates consistency
8. IC Memo Generator synthesizes results

---

## Tool Availability Notes

### Currently Enabled MCP Servers
✅ portfolio-state-server
✅ portfolio-optimization-server
✅ risk-server
✅ tax-optimization-server
✅ openbb-curated
✅ policy-events-service
✅ sequential-thinking
✅ obsidian (for Claude Code agents)
✅ deepwiki
✅ codex
✅ excel-mcp-server

### Implemented But Not Enabled
⚠️ **tax-mcp-server** (tax-server)
- File: `/home/hvksh/investing/tax-mcp-server/tax_mcp_server_v2.py`
- Tool: `calculate_comprehensive_tax`
- Uses PolicyEngine-US (AGPL-3.0)
- NOT in `.mcp.json` currently

**Decision Required**: Enable or remove references in agent definitions

---

## References

**Agent Definitions**: `/home/hvksh/investing/agent-prompts/sub-agents/*.md`
**Tool Guide**: `/home/hvksh/investing/TOOLS_GUIDE.md`
**Workflow Docs**: `/home/hvksh/investing/WORKFLOW_ARCHITECTURE.md`
**Main Instructions**: `/home/hvksh/investing/CLAUDE.md`

**Validation Report**: `/home/hvksh/investing/AGENT_VALIDATION_REPORT.md`
