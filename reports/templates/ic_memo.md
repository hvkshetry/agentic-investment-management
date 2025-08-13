# Investment Committee Memorandum

**Date:** {{ date }}  
**Portfolio Value:** ${{ portfolio_value | format_currency }}  
**Session ID:** {{ session_id }}

---

## Executive Summary

### Proposed Actions
{{ for action in proposed_actions }}
- {{ action.description }} (Impact: {{ action.impact }})
{{ endfor }}

### Expected Portfolio Impact
| Metric | Current | Proposed | Change |
|--------|---------|----------|--------|
| Expected Return | {{ current.return }}% | {{ proposed.return }}% | {{ proposed.return - current.return | format_change }}% |
| Volatility | {{ current.volatility }}% | {{ proposed.volatility }}% | {{ proposed.volatility - current.volatility | format_change }}% |
| Sharpe Ratio | {{ current.sharpe }} | {{ proposed.sharpe }} | {{ proposed.sharpe - current.sharpe | format_change }} |
| 95% Daily VaR | {{ current.var }}% | {{ proposed.var }}% | {{ proposed.var - current.var | format_change }}% |

### Gate Validation Summary
| Gate | Status | Details |
|------|--------|---------|
| Risk | {{ gates.risk.status }} | {{ gates.risk.summary }} |
| Tax | {{ gates.tax.status }} | {{ gates.tax.summary }} |
| Compliance | {{ gates.compliance.status }} | {{ gates.compliance.summary }} |
| Realism | {{ gates.realism.status }} | {{ gates.realism.summary }} |
| Credibility | {{ gates.credibility.status }} | {{ gates.credibility.summary }} |

**Recommendation:** {{ recommendation }}

---

## Market Environment

### Economic Indicators
- **GDP Growth:** {{ macro.gdp_growth }}% ({{ macro.gdp_trend }})
- **CPI Inflation:** {{ macro.cpi }}% ({{ macro.inflation_trend }})
- **Unemployment:** {{ macro.unemployment }}% ({{ macro.employment_trend }})

### Rate Environment
- **10Y Treasury:** {{ macro.ten_year }}%
- **2Y Treasury:** {{ macro.two_year }}%
- **2s10s Spread:** {{ macro.spread }} bps ({{ macro.curve_shape }})
- **Fed Outlook:** {{ macro.fed_outlook }}

### Market Sentiment
- **VIX:** {{ market.vix }}
- **Put/Call Ratio:** {{ market.put_call }}
- **Market Regime:** {{ market.regime }}

### Key Developments
{{ for event in market.key_events }}
- {{ event.description }} (Impact: {{ event.impact }})
{{ endfor }}

---

## Portfolio Analysis

### Current Allocation
| Asset Class | Weight | Target | Drift |
|-------------|--------|--------|-------|
{{ for asset in allocation }}
| {{ asset.name }} | {{ asset.current }}% | {{ asset.target }}% | {{ asset.drift | format_drift }}% |
{{ endfor }}

### Equity Analysis

#### Overvalued Positions
| Ticker | Weight | P/E | vs Sector | Recommendation |
|--------|--------|-----|-----------|----------------|
{{ for position in equity.overvalued }}
| {{ position.ticker }} | {{ position.weight }}% | {{ position.pe }}x | {{ position.vs_sector }}% | {{ position.action }} |
{{ endfor }}

#### Undervalued Opportunities  
| Ticker | Weight | P/E | vs Sector | Recommendation |
|--------|--------|-----|-----------|----------------|
{{ for position in equity.undervalued }}
| {{ position.ticker }} | {{ position.weight }}% | {{ position.pe }}x | {{ position.vs_sector }}% | {{ position.action }} |
{{ endfor }}

### Fixed Income Analysis
- **Portfolio Duration:** {{ fixed_income.duration }} years (Target: {{ fixed_income.target_duration }})
- **Average Credit Quality:** {{ fixed_income.credit_quality }}
- **Yield to Maturity:** {{ fixed_income.ytm }}%
- **Duration Recommendation:** {{ fixed_income.duration_stance }}

---

## Optimization Proposal

### Method: {{ optimization.method }}

### Expected Performance
- **Annual Return:** {{ optimization.expected_return }}%
- **Annual Volatility:** {{ optimization.expected_volatility }}%
- **Sharpe Ratio:** {{ optimization.expected_sharpe }}
- **Max Drawdown:** {{ optimization.expected_drawdown }}%

### Major Position Changes
| Position | Current | Target | Change | Rationale |
|----------|---------|--------|--------|-----------|
{{ for change in optimization.changes }}
| {{ change.ticker }} | {{ change.current }}% | {{ change.target }}% | {{ change.delta | format_change }}% | {{ change.rationale }} |
{{ endfor }}

---

## Risk Assessment

### Risk Metrics Comparison
| Metric | Current | Post-Trade | Change | Status |
|--------|---------|------------|--------|--------|
| 95% Daily VaR | {{ risk.current.var }}% | {{ risk.proposed.var }}% | {{ risk.change.var }}% | {{ risk.status.var }} |
| CVaR (95%) | {{ risk.current.cvar }}% | {{ risk.proposed.cvar }}% | {{ risk.change.cvar }}% | {{ risk.status.cvar }} |
| Max Drawdown | {{ risk.current.drawdown }}% | {{ risk.proposed.drawdown }}% | {{ risk.change.drawdown }}% | {{ risk.status.drawdown }} |
| Sharpe Ratio | {{ risk.current.sharpe }} | {{ risk.proposed.sharpe }} | {{ risk.change.sharpe }} | {{ risk.status.sharpe }} |

### Stress Test Results
| Scenario | Current Impact | Post-Trade Impact | Improvement |
|----------|---------------|-------------------|-------------|
{{ for test in risk.stress_tests }}
| {{ test.name }} | {{ test.current }}% | {{ test.proposed }}% | {{ test.improvement }}% |
{{ endfor }}

### Top Risk Contributors
| Position | Current Contribution | Post-Trade Contribution | Change |
|----------|---------------------|------------------------|--------|
{{ for contributor in risk.top_contributors }}
| {{ contributor.ticker }} | {{ contributor.current }}% | {{ contributor.proposed }}% | {{ contributor.change }}% |
{{ endfor }}

---

## Tax Impact Analysis

### Realized Gains/Losses
- **Short-Term Gains:** ${{ tax.stcg | format_currency }}
- **Long-Term Gains:** ${{ tax.ltcg | format_currency }}
- **Harvested Losses:** ${{ tax.losses | format_currency }}
- **Net Tax Liability:** ${{ tax.net_liability | format_currency }}

### Tax Efficiency Metrics
- **Tax Drag:** {{ tax.drag }}% (Limit: {{ tax.drag_limit }}%)
- **Effective Tax Rate:** {{ tax.effective_rate }}%
- **After-Tax Return:** {{ tax.after_tax_return }}%

### Wash Sale Check
{{ if tax.wash_sale_violations }}
⚠️ **Wash Sale Violations Detected:**
{{ for violation in tax.wash_sale_violations }}
- {{ violation.description }}
{{ endfor }}
{{ else }}
✅ **No wash sale violations detected**
{{ endif }}

---

## Trade Execution Plan

### Summary Statistics
- **Total Trades:** {{ trades.count }}
- **Total Turnover:** ${{ trades.turnover | format_currency }} ({{ trades.turnover_percent }}% of portfolio)
- **Estimated Transaction Costs:** ${{ trades.costs | format_currency }}

### Trade Blotter
| # | Ticker | Action | Shares | Est. Price | Amount | Account | Rationale |
|---|--------|--------|--------|------------|--------|---------|-----------|
{{ for trade in trades.orders }}
| {{ trade.number }} | {{ trade.ticker }} | {{ trade.action }} | {{ trade.shares }} | ${{ trade.price }} | ${{ trade.amount | format_currency }} | {{ trade.account }} | {{ trade.rationale }} |
{{ endfor }}

---

## Compliance & Gate Validation

### Risk Gate: {{ gates.risk.icon }} {{ gates.risk.result }}
{{ for check in gates.risk.checks }}
- {{ check.name }}: {{ check.value }} {{ check.operator }} {{ check.limit }} → {{ check.result }}
{{ endfor }}

### Tax Gate: {{ gates.tax.icon }} {{ gates.tax.result }}
{{ for check in gates.tax.checks }}
- {{ check.name }}: {{ check.result }}
{{ endfor }}

### Compliance Gate: {{ gates.compliance.icon }} {{ gates.compliance.result }}
{{ for check in gates.compliance.checks }}
- {{ check.name }}: {{ check.result }}
{{ endfor }}

### Realism Gate: {{ gates.realism.icon }} {{ gates.realism.result }}
{{ if gates.realism.issues }}
**Issues Identified:**
{{ for issue in gates.realism.issues }}
- {{ issue.description }}
{{ endfor }}
**Resolution:** {{ gates.realism.resolution }}
{{ endif }}

### Credibility Gate: {{ gates.credibility.icon }} {{ gates.credibility.result }}
{{ if gates.credibility.warnings }}
**Warnings:**
{{ for warning in gates.credibility.warnings }}
- {{ warning.description }}
{{ endfor }}
{{ endif }}

---

## Decision Requirements

{{ if overrides_required }}
### ⚠️ Override Justification Required

The following require explicit approval:
{{ for override in overrides }}
- **{{ override.gate }}:** {{ override.issue }}
  - **Justification:** {{ override.justification }}
  - **Risk:** {{ override.risk }}
  - **Mitigation:** {{ override.mitigation }}
{{ endfor }}
{{ endif }}

### Next Steps
1. {{ next_steps.1 }}
2. {{ next_steps.2 }}
3. {{ next_steps.3 }}

### Review Schedule
- **Next Review:** {{ review.next_date }}
- **Triggers:** {{ review.triggers }}

---

## Appendices

### A. Detailed Holdings List
[View full holdings breakdown in session artifacts]

### B. Full Optimization Output
[View complete optimization metrics in optimization_candidate.json]

### C. Tax Lot Details
[View detailed tax lots in portfolio_snapshot.json]

### D. Risk Decomposition
[View full risk attribution in risk_report.json]

### E. Data Sources & Quality
- **Portfolio Data:** {{ data.portfolio_source }} (Quality: {{ data.portfolio_quality }})
- **Market Data:** {{ data.market_source }} (Quality: {{ data.market_quality }})
- **Economic Data:** {{ data.economic_source }} (Quality: {{ data.economic_quality }})

---

**Generated:** {{ timestamp }}  
**Session:** {{ session_id }}  
**Artifacts:** {{ artifact_count }} documents analyzed  
**Confidence:** {{ overall_confidence }}%

---

*This memorandum is for internal use only and should not be construed as investment advice. All projections are estimates based on historical data and model assumptions.*