# Agent Validation Report
**Date**: 2025-10-21
**Reporter**: Claude Code
**Purpose**: Validate specialized agent definitions match actual tool access and capabilities

---

## Executive Summary

✅ **Overall Status**: Agent definitions are MOSTLY accurate with minor corrections needed

**Key Findings**:
1. ✅ Tax-advisor correctly references `calculate_comprehensive_tax`
2. ✅ PolicyEngine-US is properly implemented (replaced tenforty)
3. ⚠️ Tax-server NOT configured in `.mcp.json` (exists but not enabled)
4. ⚠️ One stray reference to "tenforty" in tax-advisor.md (line 138)
5. ✅ All agent tool lists match their actual capabilities
6. ✅ Smart Connections mentioned in CLAUDE.md
7. ⚠️ CLAUDE.md has outdated workflow example (should reference slash commands)

---

## Detailed Findings

### 1. Tax-Advisor Agent ✅ (with minor cleanup)

**File**: `/home/hvksh/investing/agent-prompts/sub-agents/tax-advisor.md`

**Tool Access** (CORRECT):
- ✅ `mcp__tax-server__calculate_comprehensive_tax` - Listed
- ✅ `mcp__tax-optimization-server__find_tax_loss_harvesting_pairs` - Listed
- ✅ `mcp__portfolio-state-server__get_tax_loss_harvesting_opportunities` - Listed
- ✅ `mcp__portfolio-state-server__simulate_sale` - Listed
- ✅ Policy event tools - All listed
- ✅ Sequential thinking - Listed

**Implementation Status**:
- ✅ Tax server exists at `/home/hvksh/investing/tax-mcp-server/tax_mcp_server_v2.py`
- ✅ Uses PolicyEngine-US (AGPL-3.0) for individual tax calculations
- ✅ Function `calculate_comprehensive_tax` implemented (line 42)
- ⚠️ NOT configured in `.mcp.json` (server exists but not enabled)

**Content Issues**:
- ⚠️ Line 138: References "tenforty library" - should say "PolicyEngine-US library"
- ✅ Lines 8, 73: Correctly mentions PolicyEngine-US in other places
- ✅ ES < 2.5% constraint properly documented
- ✅ Tool-First Data Policy documented
- ✅ HALT enforcement rules documented

**Git History**:
```
ebf7569 feat: Replace tenforty with PolicyEngine-US for individual tax calculations
```

**Action Required**: Fix line 138 reference

---

### 2. Equity-Analyst Agent ✅

**File**: `/home/hvksh/investing/agent-prompts/sub-agents/equity-analyst.md`

**Tool Access** (CORRECT):
- ✅ All fundamental analysis tools listed
- ✅ SEC filing tools (including new section parser)
- ✅ Ownership and insider trading tools
- ✅ Short interest tools (FINRA, Stockgrid, SEC FTD)
- ✅ Policy event tools
- ✅ Company facts comparison tool

**Content Quality**:
- ✅ Provider guidance accurate (yfinance > sec > fmp)
- ✅ Parameter type warnings present
- ✅ Limit recommendations to prevent token overflow
- ✅ No outdated references

---

### 3. Macro-Analyst Agent ✅

**File**: `/home/hvksh/investing/agent-prompts/sub-agents/macro-analyst.md`

**Tool Access** (CORRECT):
- ✅ All economy indicators (GDP, CPI, unemployment)
- ✅ Fixed income tools (yield curve, treasury rates)
- ✅ Currency and commodity tools
- ✅ Policy event tools with two-stage process
- ✅ Sequential thinking

**Content Quality**:
- ✅ Provider notes accurate (federal_reserve vs fred)
- ✅ Two-stage policy monitoring documented
- ✅ Known data issues (hearing data) documented
- ✅ Enhanced outputs (analogous periods, market views)
- ✅ No outdated references

---

### 4. Risk-Analyst Agent ✅

**File**: `/home/hvksh/investing/agent-prompts/sub-agents/risk-analyst.md`

**Tool Access** (CORRECT):
- ✅ `mcp__risk-server__analyze_portfolio_risk` (includes stress tests)
- ✅ Portfolio state tools
- ✅ Derivatives tools for hedging
- ✅ Short interest tools
- ✅ Policy event tools

**Content Quality**:
- ✅ ES/CVaR as PRIMARY risk measure clearly stated
- ✅ VaR marked as "REFERENCE ONLY"
- ✅ HALT enforcement rules documented
- ✅ Concentration risk policy (funds exempt)
- ✅ Tool-First Data Policy
- ✅ No outdated references

**Critical Note**: Correctly documents that stress testing is PART OF `analyze_portfolio_risk`, not a separate tool.

---

### 5. Portfolio-Manager Agent ✅

**File**: `/home/hvksh/investing/agent-prompts/sub-agents/portfolio-manager.md`

**Tool Access** (CORRECT):
- ✅ `mcp__portfolio-optimization-server__optimize_portfolio_advanced`
- ✅ Portfolio state tools
- ✅ ETF analysis tools
- ✅ 13F institutional holdings
- ✅ Sequential thinking

**Content Quality**:
- ✅ ES-primary optimization documented
- ✅ HALT protocol documented
- ✅ Multiple optimization methods listed
- ✅ Round-2 gate compliance
- ✅ Ledoit-Wolf shrinkage mentioned
- ✅ No outdated references

---

### 6. CLAUDE.md (Orchestrator Instructions) ⚠️

**File**: `/home/hvksh/investing/CLAUDE.md`

**Issues Found**:

1. **Outdated Workflow Example** (Lines 61-223):
   - Contains detailed 5-step workflow that should be in slash commands
   - User noted: "Those steps are examples for slash command implementation, not instructions for every interaction"
   - Should reference `.claude/commands/` instead

2. **Agent Table** (Lines 76-84):
   - ✅ Lists 5 agents: macro-analyst, equity-analyst, risk-analyst, portfolio-manager, tax-advisor
   - ✅ Descriptions are generic but accurate
   - ⚠️ Doesn't mention ALL available agents (missing: etf-analyst, fixed-income-analyst, derivatives-options-analyst, market-scanner, gate-validator, invariant-checker, ic-memo-generator)

3. **Smart Connections** (Lines 55-58):
   - ✅ Properly documented
   - ✅ Correctly states "no manual wikilinks needed"

**Recommended Updates**:
- Remove detailed workflow steps (lines 61-223)
- Add reference: "See `.claude/commands/` for workflow implementations"
- Expand agent table or reference `agent-prompts/sub-agents/` for full list

---

### 7. Additional Agents Reviewed

**Other agent files checked**:
- ✅ `etf-analyst.md` - Tools accurate
- ✅ `fixed-income-analyst.md` - Tools accurate
- ✅ `derivatives-options-analyst.md` - Tools accurate
- ✅ `market-scanner.md` - Tools accurate
- ✅ `gate-validator.md` - Tools accurate (validation-focused)
- ✅ `invariant-checker.md` - Tools accurate (consistency-focused)
- ✅ `ic-memo-generator.md` - Tools accurate (synthesis-focused)

All specialized analysts have correct tool access lists.

---

## MCP Server Configuration Issues

### Tax Server Not Enabled ⚠️

**Finding**: The tax-mcp-server EXISTS but is NOT in `.mcp.json`

```bash
$ python3 -c "import json; data = json.load(open('.mcp.json')); print('tax-mcp-server' in data.get('mcpServers', {}))"
False
```

**Impact**:
- Agent definitions reference `mcp__tax-server__calculate_comprehensive_tax`
- Tool exists in `/home/hvksh/investing/tax-mcp-server/tax_mcp_server_v2.py`
- But server is NOT configured for use

**Recommendation**: Either:
1. Add tax-mcp-server to `.mcp.json` if needed, OR
2. Update agent definitions to remove tax-server references

**Current Workaround**: Tax functionality exists in:
- `mcp__tax-optimization-server__*` tools (currently enabled)
- `mcp__portfolio-state-server__get_tax_loss_harvesting_opportunities`

---

## Tool Cross-Reference Validation

### Correctly Documented Non-Existent Tools ✅

From `TOOLS_GUIDE.md`:
```markdown
### ❌ NON-EXISTENT TOOLS (Do not use)
- `mcp__risk-server__stress_test_portfolio` - Stress testing is part of `analyze_portfolio_risk`
```

✅ Risk-analyst correctly documents this
✅ No agent files reference the non-existent tool

### Critical Tool Usage Patterns ✅

All agents correctly document:
- ✅ Native Python types required (not JSON strings)
- ✅ Parameter type warnings (limit as int, not string)
- ✅ Provider selection guidance
- ✅ Two-stage policy event pattern

---

## Policy Event Integration ✅

All relevant agents document:
- ✅ Two-stage process (bulk retrieval → detail fetching)
- ✅ Known data issues (hearing data often incomplete)
- ✅ Requirement to fetch details before analysis
- ✅ WebFetch usage for detail URLs

**Consistent across**:
- macro-analyst.md
- equity-analyst.md
- risk-analyst.md
- tax-advisor.md
- fixed-income-analyst.md
- derivatives-options-analyst.md
- market-scanner.md

---

## Recommended Actions

### Priority 1 (Critical)

1. **Fix tax-advisor.md line 138**:
   - Change: "Tax rates MUST come from tenforty library via MCP tools"
   - To: "Tax rates MUST come from PolicyEngine-US library via MCP tools"

2. **Resolve tax-server configuration**:
   - Either add to `.mcp.json` or document why it's disabled
   - If disabled, consider removing tool references or marking as "future"

### Priority 2 (Important)

3. **Update CLAUDE.md**:
   - Remove detailed workflow steps (lines 61-223)
   - Add: "See `.claude/commands/` for workflow implementations"
   - Reference: "See `WORKFLOW_ARCHITECTURE.md` for complete workflow documentation"

4. **Expand agent documentation**:
   - Add table in CLAUDE.md referencing all 12+ agents
   - Or add: "See `agent-prompts/sub-agents/` for complete agent catalog"

### Priority 3 (Nice to Have)

5. **Agent capability matrix**:
   - Create cross-reference table of agents → tools
   - Document which agents can collaborate on specific tasks
   - Examples: "Risk + Tax = tax-aware risk analysis"

---

## Agent-Tool Mapping Summary

| Agent | Primary MCP Servers | Status |
|-------|---------------------|--------|
| tax-advisor | portfolio-state, tax-server, tax-optimization, policy-events | ⚠️ tax-server not enabled |
| equity-analyst | portfolio-state, openbb-curated, policy-events | ✅ |
| macro-analyst | portfolio-state, openbb-curated, policy-events | ✅ |
| risk-analyst | portfolio-state, risk-server, openbb-curated, policy-events | ✅ |
| portfolio-manager | portfolio-state, portfolio-optimization | ✅ |
| etf-analyst | portfolio-state, openbb-curated | ✅ |
| fixed-income-analyst | portfolio-state, openbb-curated, policy-events | ✅ |
| derivatives-options-analyst | portfolio-state, openbb-curated, policy-events | ✅ |
| market-scanner | portfolio-state, openbb-curated, policy-events | ✅ |
| gate-validator | portfolio-state | ✅ |
| invariant-checker | portfolio-state | ✅ |
| ic-memo-generator | portfolio-state | ✅ |

---

## Conclusion

**Overall Assessment**: Agent definitions are **well-maintained and accurate** with only minor issues.

**Strengths**:
1. All tool lists match actual capabilities
2. PolicyEngine-US properly documented (mostly)
3. ES-primary risk framework consistently documented
4. Tool-First Data Policy across all agents
5. Two-stage policy event pattern well-documented
6. Parameter type warnings present

**Weaknesses**:
1. One stray "tenforty" reference (easy fix)
2. Tax-server configuration ambiguity (needs decision)
3. CLAUDE.md has outdated workflow example (organizational issue)

**Recommendation**: Make Priority 1 fixes immediately, Priority 2 within sprint.

---

## Appendix: File Locations

**Agent Definitions**:
- `/home/hvksh/investing/agent-prompts/sub-agents/*.md` (12 agents)
- `/home/hvksh/investing/.claude/agents/*.md` (Claude Code agent variants)

**Main Documentation**:
- `/home/hvksh/investing/CLAUDE.md` (orchestrator instructions)
- `/home/hvksh/investing/TOOLS_GUIDE.md` (MCP tool reference)
- `/home/hvksh/investing/documentation/AGENTS_TOOL_USAGE.md` (narrative guide)

**Tax Server**:
- `/home/hvksh/investing/tax-mcp-server/tax_mcp_server_v2.py` (implementation)
- Uses PolicyEngine-US (AGPL-3.0)
- NOT in `.mcp.json` currently

**Recent Commits**:
```
ebf7569 feat: Replace tenforty with PolicyEngine-US for individual tax calculations
efbb6ef Update all agents with policy event guidance
9d986f6 Redesign policy-events-mcp-server with two-stage sieve pattern
```
