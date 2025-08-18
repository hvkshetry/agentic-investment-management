# MCP Tool Audit - Agent Prompts vs Server Implementations

## Available MCP Tools by Server

### 1. Portfolio State Server (portfolio-state-mcp-server)
**Actual Tools:**
- `get_portfolio_state`
- `import_broker_csv`
- `update_market_prices`
- `simulate_sale`
- `get_tax_loss_harvesting_opportunities`
- `record_transaction`

### 2. Portfolio Optimization Server (portfolio-mcp-server)
**Actual Tools:**
- `optimize_portfolio_advanced`

### 3. Risk Server (risk-mcp-server)
**Actual Tools:**
- `analyze_portfolio_risk`
- `get_risk_free_rate`

## Tool References in Agent Prompts

### portfolio-manager.md
**References:**
- ✅ `mcp__portfolio-state-server__get_portfolio_state` - CORRECT
- ✅ `mcp__portfolio-optimization-server__optimize_portfolio_advanced` - CORRECT
- ❓ `mcp__openbb-curated__etf_holdings` - Need to verify OpenBB tools
- ❓ `mcp__openbb-curated__etf_sectors` - Need to verify OpenBB tools
- ❓ `mcp__openbb-curated__etf_equity_exposure` - Need to verify OpenBB tools
- ❓ `mcp__openbb-curated__regulators_sec_institutions_search` - Need to verify OpenBB tools
- ❓ `mcp__openbb-curated__equity_ownership_form_13f` - Need to verify OpenBB tools

### risk-analyst.md
**References:**
- ✅ `mcp__portfolio-state-server__get_portfolio_state` - CORRECT
- ❌ `mcp__risk-server__analyze_portfolio_risk` - INCORRECT (should be `mcp__risk-server__analyze_portfolio_risk`)
- ❌ `mcp__risk-server__stress_test_portfolio` - DOES NOT EXIST (stress testing is part of analyze_portfolio_risk)
- ❓ `mcp__openbb-curated__derivatives_options_chains` - Need to verify OpenBB tools
- ❓ `mcp__openbb-curated__derivatives_futures_curve` - Need to verify OpenBB tools
- ❓ `mcp__openbb-curated__equity_shorts_fails_to_deliver` - Need to verify OpenBB tools
- ❓ `mcp__openbb-curated__equity_shorts_short_interest` - Need to verify OpenBB tools
- ❓ `mcp__openbb-curated__equity_shorts_short_volume` - Need to verify OpenBB tools
- ❓ `mcp__policy-events-service__get_recent_bills` - Need to verify policy events tools
- ❓ `mcp__policy-events-service__get_federal_rules` - Need to verify policy events tools
- ❓ `mcp__policy-events-service__get_upcoming_hearings` - Need to verify policy events tools
- ❓ `mcp__policy-events-service__get_bill_details` - Need to verify policy events tools
- ❓ `mcp__policy-events-service__get_rule_details` - Need to verify policy events tools
- ❓ `mcp__policy-events-service__get_hearing_details` - Need to verify policy events tools

## Issues Found

### Critical Issues:
1. **risk-analyst.md** references `mcp__risk-server__stress_test_portfolio` which DOES NOT EXIST
   - Stress testing is actually part of the `analyze_portfolio_risk` tool
   - Need to remove references to this non-existent tool

### To Verify:
1. OpenBB MCP server tools - need to check what's actually available
2. Policy Events Service tools - need to verify these exist

## Next Steps:
1. Check OpenBB and Policy Events servers for actual tool names
2. Update agent prompts to remove non-existent tools
3. Correct any misnamed tools
4. Test agents with corrected tool names