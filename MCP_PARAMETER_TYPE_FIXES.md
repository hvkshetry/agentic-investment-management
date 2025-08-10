# MCP Parameter Type and Artifact Fixes

## Critical Issues Fixed

### 1. Parameter Type Conversion Error
**Problem:** Subagents were passing ALL parameters as JSON strings instead of native types
- ❌ WRONG: `weights: "[0.25, 0.23, 0.12]"` (string)
- ❌ WRONG: `analysis_options: "{\"confidence_levels\": [0.95]}"` (string)
- ✅ FIXED: `weights: [0.25, 0.23, 0.12]` (list)
- ✅ FIXED: `analysis_options: {"confidence_levels": [0.95]}` (dict)

### 2. Missing Artifact Creation
**Problem:** No artifacts were being written to `./runs/<timestamp>/`
**Solution:** Added mandatory workflow steps to all agents:
1. Check for existing artifacts
2. Read upstream analyses
3. Perform analysis
4. Write artifacts using Write tool
5. Share with downstream agents

### 3. Siloed Agent Operation
**Problem:** Agents working in isolation without sharing context
**Solution:** Established artifact reading order:
- Portfolio State → All agents
- Macro Context → Risk, Portfolio Manager
- Risk Analysis → Portfolio Manager, Tax Advisor
- Optimization Results → Tax Advisor
- Tax Impact → Final decision

## Files Modified

### Agent Prompts Updated:
1. **risk-analyst.md**
   - Added native parameter type examples
   - Added artifact creation workflow
   - Fixed tool parameter documentation

2. **portfolio-manager.md**
   - Added native parameter type examples
   - Added requirement to read risk analysis
   - Fixed optimization_config parameter

3. **tax-advisor.md**
   - Added artifact reading from upstream agents
   - Added native parameter type guidance
   - Fixed tool parameter examples

4. **macro-analyst.md**
   - Added artifact creation workflow
   - Integrated with downstream agents

5. **fixed-income-analyst.md**
   - Added artifact workflow
   - Added macro context reading

6. **CLAUDE.md (Orchestrator)**
   - Added critical parameter type warning
   - Detailed artifact creation requirements
   - Cross-agent communication matrix
   - Artifact reading order

## Correct MCP Tool Usage Examples

### Risk Analysis
```python
mcp__risk-server__analyze_portfolio_risk(
    tickers=["AAPL", "GOOGL"],        # List, NOT string
    weights=[0.5, 0.5],                # List, NOT string
    analysis_options={                 # Dict, NOT string
        "confidence_levels": [0.95],
        "time_horizons": [1, 5, 21]
    }
)
```

### Portfolio Optimization
```python
mcp__portfolio-optimization-server__optimize_portfolio_advanced(
    tickers=["SPY", "AGG"],           # List, NOT string
    optimization_config={             # Dict, NOT string
        "lookback_days": 756,
        "risk_measure": "MV",
        "optimization_methods": ["HRP"]
    }
)
```

## Artifact Structure

Each agent must create artifacts in:
```
./runs/<timestamp>/
├── portfolio_state.json       # From Portfolio State Server
├── macro_context.json         # From Macro Analyst
├── risk_analysis.json         # From Risk Analyst
├── optimization_results.json  # From Portfolio Manager
├── tax_impact.json           # From Tax Advisor
└── decision_memo.json        # From Orchestrator
```

## Testing Checklist

After these fixes:
- [ ] Parameters passed as native types (not strings)
- [ ] Artifacts created in runs directory
- [ ] Agents read upstream artifacts
- [ ] Cross-agent context sharing working
- [ ] No "invalid under any schema" errors
- [ ] Full workflow completes successfully