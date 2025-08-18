# Agent Prompts ES/HALT Update - Week 5

## Summary
Updated all agent prompts to enforce Expected Shortfall (ES) as the primary risk metric with mandatory HALT rules, replacing VaR-based decision making.

## Problem Addressed
Critical issue from feedback: System was using VaR as primary risk metric when ES provides superior tail risk measurement:
- VaR only shows point estimate at confidence level
- ES shows average loss beyond VaR threshold
- HALT enforcement was not embedded in agent logic
- Agents could bypass risk limits without stopping

## Solution: ES-Primary Agent Updates

### Core Changes Applied

#### 1. Risk Analyst Agent
**ES as Primary Metric:**
- ES/CVaR at 97.5% confidence is BINDING constraint
- VaR relegated to reference only
- ES limit: 2.5% (calibrated from historical VaR)
- Component ES replaces Component VaR

**HALT Triggers:**
- ES > 2.5% → IMMEDIATE HALT
- Liquidity score < 0.3 → IMMEDIATE HALT  
- Concentration > 20% → IMMEDIATE HALT
- Average correlation > 0.8 → IMMEDIATE HALT

**HALT Protocol:**
- Write HALT_ORDER.json immediately
- Include trigger reason and corrective actions
- No trades until ES returns below limit

#### 2. Portfolio Manager Agent
**ES-Constrained Optimization:**
- ALL optimizations must satisfy ES < 2.5%
- CVaR as primary risk measure in Riskfolio-Lib
- Alpha = 0.025 for 97.5% confidence
- Max position weight reduced to 15%

**HALT Check Before Trading:**
- Check for HALT_ORDER.json before optimization
- Read risk_analysis.json for current ES
- If ES > 2.5%: Create HALT and stop
- After optimization: Verify ES still < 2.5%

**Round-2 Gate Compliance:**
- All allocations pass ES limit check
- Include lineage record
- Pass tax reconciliation
- Meet liquidity requirements

#### 3. Tax Advisor Agent
**Tax-ES Integration:**
- Tax optimization cannot breach ES limit
- Tax loss harvesting must keep ES < 2.5%
- Single source of truth via Tax Reconciliation

**Tax HALT Conditions:**
- Position mismatch → HALT
- Stale tax data (>5 min) → HALT
- Wash sale detected → HALT
- TLH pushes ES > 2.5% → HALT

#### 4. Orchestrator (CLAUDE.md)
**ES-Primary Guardrails:**
- ES at 97.5% is BINDING constraint
- HALT enforcement for ES > 2.5%
- Round-2 gate mandatory for revisions
- Tax reconciliation as single source

**Enhanced Validation Gates:**
- ES limit check FIRST
- Round-2 gate for ALL revisions
- No override allowed for ES breach
- Document HALT orders in IC memo

### Key Improvements

#### Risk Measurement
```python
# Before (VaR-primary)
if var_95 > 0.02:
    reduce_risk()

# After (ES-primary)  
if es_975 > 0.025:
    HALT_TRADING()
    write_halt_order()
```

#### Optimization Constraints
```python
# Before
optimization_config = {
    "risk_measure": "MV",  # Mean-Variance
    "max_weight": 1.0
}

# After
optimization_config = {
    "risk_measure": "CVaR",  # ES/CVaR
    "alpha": 0.025,  # 97.5% confidence
    "max_weight": 0.15,  # Concentration limit
    "es_limit": 0.025  # BINDING constraint
}
```

#### Output Format Updates
All agents now report:
- `es_975`: Expected Shortfall value
- `es_limit`: Policy limit (0.025)
- `es_utilization`: Percentage of limit used
- `es_compliant`: Boolean compliance flag
- `halt_status`: Current HALT state
- `var_95`: Reference only

### Files Updated

1. **agent-prompts/sub-agents/risk-analyst.md**
   - Added ES-PRIMARY section
   - Defined HALT triggers and protocol
   - Updated output format with ES metrics

2. **agent-prompts/sub-agents/portfolio-manager.md**
   - Added ES constraint enforcement
   - HALT check before optimization
   - CVaR as primary risk measure

3. **agent-prompts/sub-agents/tax-advisor.md**
   - Tax-ES integration rules
   - Tax-triggered HALT conditions
   - Round-2 gate compliance

4. **agent-prompts/CLAUDE.md**
   - ES-PRIMARY in guardrails
   - Enhanced validation gates
   - HALT protocol documentation

### Integration with Previous Work

#### With RiskStack (Week 1)
```python
risk_stack.loss_based["es"]["value"]  # Primary
risk_stack.loss_based["es"]["alpha"]  # 0.975
risk_stack.loss_based["var"]["value"]  # Reference
```

#### With Round-2 Gate (Week 3)
```python
es_check = {
    "passed": es_value <= es_limit,
    "value": risk_stack.loss_based["es"]["value"],
    "limit": 0.025,
    "breach_magnitude": max(0, es_value - es_limit)
}
```

#### With Tax Reconciliation (Week 4)
```python
# Tax trades must maintain ES compliance
if tax_trade_es > 0.025:
    reject_tax_optimization()
    create_halt_order()
```

### Testing Validation

Agents will now:
1. Always check ES before making decisions
2. Create HALT orders when limits breached
3. Refuse to trade during HALT
4. Validate ES for all optimizations
5. Report ES as primary metric

### Success Metrics

- 100% of agent decisions respect ES < 2.5%
- Zero trades executed during HALT status
- All optimizations CVaR-constrained
- ES reported as primary in all artifacts
- VaR only appears as reference metric

## Next Steps

Week 6: Create golden test for 2025-08-17 session validation to ensure all fixes work correctly together.