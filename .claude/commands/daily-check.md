---
description: Run daily portfolio monitoring and risk assessment
allowed-tools: Read, mcp__portfolio-state-server__import_broker_csv, mcp__portfolio-state-server__get_portfolio_state, mcp__openbb-curated__news_company, mcp__policy-events-service__get_recent_bills, mcp__risk-server__analyze_portfolio_risk, Write
---

Run my daily portfolio monitoring workflow. This is a lightweight check, not a full rebalancing.

## Workflow Steps

1. **Import Current Portfolio State**
   - Read Vanguard CSV from `portfolio/vanguard.csv`
   - Read UBS CSV from `portfolio/ubs.csv`
   - Import both using `mcp__portfolio-state-server__import_broker_csv`
   - Confirm both imports successful

2. **Scan Market & News**
   - Use `@market-scanner` agent to check overnight developments
   - Focus on news affecting my portfolio holdings
   - Check for policy events that could impact positions
   - Create `market_scan.json` with sentiment and key events

3. **Check Portfolio Status**
   - Get current portfolio state with `mcp__portfolio-state-server__get_portfolio_state`
   - Calculate overnight changes and allocation drift
   - Create `portfolio_check.json` with current metrics

4. **Quick Risk Assessment with Gate Validation**
   - Run risk analysis with `mcp__risk-server__analyze_portfolio_risk`
   - Extract `executive_summary.es_975_1day` from response
   - Extract `executive_summary.halt_required` flag
   - **CRITICAL ES GATE**:
     - If `halt_required == true`, IMMEDIATELY HALT and alert user
     - If ES > 2.5%, HALT even if flag is false (defensive check)
     - ES @ 97.5% confidence MUST be ≤ 2.5% (BINDING CONSTRAINT)
   - **Concentration Gate**: Check 20% max per individual stock (funds exempt)
   - Create `risk_check.json` with current risk metrics and gate results

5. **Generate Daily Summary**
   - Create `daily_note.md` with:
     - Portfolio summary (total value, daily change)
     - Market summary (key developments, sentiment)
     - Action items (rebalance needed? alerts?)
   - Alert if: ES > 2.5%, allocation drift > 5%, or daily loss > 5%

## Critical Constraints

- **ES ≤ 2.5%** at 97.5% confidence (HALT if exceeded)
- **Concentration**: Max 20% per individual stock (funds/ETFs exempt)
- **Tool-first data**: All metrics must come from MCP tool calls with provenance

## Output Location

Save all artifacts to current session directory for audit trail.
