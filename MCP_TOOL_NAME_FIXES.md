# MCP Tool Name Fixes - Summary

## Issues Fixed

### 1. Incorrect Tool Names
All agent prompts had wrong MCP server prefixes in tool names. Fixed:

| Old (Wrong) | New (Correct) |
|------------|---------------|
| `mcp__portfolio-state__*` | `mcp__portfolio-state-server__*` |
| `mcp__risk-analyzer__*` | `mcp__risk-server__*` |
| `mcp__portfolio-optimization__*` | `mcp__portfolio-optimization-server__*` |
| `mcp__tax-calculator__*` | `mcp__tax-server__*` |
| `mcp__tax-optimization__*` | `mcp__tax-optimization-server__*` |

### 2. Parameter Type Issues
Added guidance to all agent prompts about OpenBB parameter types:
- ✅ Correct: `limit: 50` (integer)
- ❌ Wrong: `limit: "50"` (string)

### 3. Sequential Thinking
- Confirmed it's globally installed (not project-specific)
- Tool name: `mcp__sequential-thinking__sequentialthinking`

## Files Modified

1. **Sub-Agent Prompts:**
   - equity-analyst.md
   - risk-analyst.md
   - portfolio-manager.md
   - tax-advisor.md
   - fixed-income-analyst.md
   - macro-analyst.md
   - etf-analyst.md
   - derivatives-options-analyst.md
   - market-scanner.md

2. **Orchestrator:**
   - CLAUDE.md - Updated all tool references and added validation gates

## Key Changes by Agent

### Risk Analyst
- Changed to `mcp__risk-server__analyze_portfolio_risk`
- Removed non-existent `get_risk_free_rate` tool
- Added proper portfolio state access

### Portfolio Manager
- Changed to `mcp__portfolio-optimization-server__optimize_portfolio_advanced`
- Updated tool documentation

### Tax Advisor
- Changed to `mcp__tax-server__calculate_comprehensive_tax`
- Changed to `mcp__tax-optimization-server__find_tax_loss_harvesting_pairs`
- Removed non-existent tools

### All OpenBB Agents
- Added parameter type guidance
- Emphasized integer parameters (not strings)

## Testing
After these fixes:
1. Tool names match actual MCP server implementations
2. Parameter types are correctly specified
3. Sequential-thinking is accessible
4. Portfolio state is accessible from all agents