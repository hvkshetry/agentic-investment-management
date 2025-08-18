# Investment System Revision Process Documentation

## Overview
This document describes how the investment optimization system handles failed candidates and creates compliant revisions.

## Revision Workflow

### 1. Initial Optimization
The system generates optimization candidates based on:
- Portfolio state
- Market conditions
- Tax considerations
- Target allocations

### 2. Gate Validation
All candidates pass through institutional gates:
- **Risk Gate**: VaR ≤ 2%, drawdown ≤ 20%, Sharpe ≥ 0.3
- **Tax Gate**: Wash sale compliance, tax efficiency
- **Compliance Gate**: Position limits ≤ 10%, sector limits ≤ 35%
- **Realism Gate**: Transaction costs, execution feasibility
- **Credibility Gate**: Reasonable assumptions

### 3. Failure Handling
When candidates fail gates:

#### Automatic Revision Trigger
```python
if not all_gates_passed:
    revision_artifact = artifact_store.create_revision(
        original_artifact_ids=[failed_candidate_ids],
        kind=ArtifactKind.TRADE_LIST,
        created_by="orchestrator",
        payload=revised_allocation,
        revision_reason="Original candidates exceeded risk limits",
        revision_method="orchestrator_override"
    )
```

#### Revision Methods
- **orchestrator_override**: Orchestrator creates compliant alternative
- **gate_remediation**: Adjusts weights to meet gate requirements
- **constraint_tightening**: Re-optimizes with stricter constraints
- **manual_intervention**: Human override with justification

### 4. Revision Tracking
Every revision includes:
```json
{
  "revision_info": {
    "is_revision": true,
    "replaces": ["original_candidate_id_1", "original_candidate_id_2"],
    "revision_reason": "VaR violations on all candidates",
    "revision_method": "orchestrator_override",
    "revision_timestamp": "2025-08-17T21:00:00Z"
  }
}
```

## Artifact Lineage

### Original Candidates
```
optimization_candidates_20250817_203436.json
├── candidate_1: VaR -3.5% (FAILED)
├── candidate_2: VaR -3.2%, VTI 30% (FAILED)
└── candidate_3: VaR -3.8%, GEV 15% (FAILED)
```

### Gate Validation
```
gate_validation_20250817_203436.json
└── Result: NONE APPROVED
    ├── Risk violations: All exceed 2% VaR limit
    ├── Concentration violations: VTI 30%, GEV 15%
    └── Action: REQUIRE REVISION
```

### Revised Solution
```
revised_trade_list_20250817_210000.json
├── revision_info:
│   ├── is_revision: true
│   ├── replaces: ["optimization_candidates_20250817_203436"]
│   └── revision_reason: "Gate failures required compliant alternative"
├── risk_metrics:
│   └── var_95_daily: 1.98% (COMPLIANT)
└── gate_compliance: ALL PASS
```

## Implementation in Code

### Creating a Revision
```python
# In real_orchestrator.py
def handle_gate_failures(self, failed_candidates, gate_results):
    """Create compliant revision when gates fail"""
    
    # Log the failures
    logger.warning(f"All {len(failed_candidates)} candidates failed gates")
    
    # Create revised allocation with hard constraints
    revised_allocation = self.create_compliant_allocation(
        max_var=0.02,
        max_position=0.10,
        max_sector=0.35
    )
    
    # Create revision artifact
    revision = self.artifact_store.create_revision(
        original_artifact_ids=[c['id'] for c in failed_candidates],
        kind=ArtifactKind.TRADE_LIST,
        created_by="orchestrator",
        payload=revised_allocation,
        revision_reason=self.summarize_gate_failures(gate_results),
        revision_method="orchestrator_override",
        confidence=0.95
    )
    
    return revision
```

### Optimizer with Hard Constraints
```python
# In portfolio_mcp_server_v3.py
INSTITUTIONAL_CONSTRAINTS = {
    'max_weight': 0.10,        # 10% max position
    'max_sector_weight': 0.35,  # 35% max sector
    'target_var_95': 0.02       # 2% daily VaR
}

# Apply as hard constraints
ef = EfficientFrontier(mu, S, weight_bounds=(0, 0.10))
if sector_mapper:
    ef.add_sector_constraints(sector_mapper, sector_upper={'Tech': 0.35})
```

## Benefits of Revision Process

### 1. **Auditability**
- Complete trail from failed candidates to approved solution
- Clear documentation of why revisions were needed
- Traceable decision-making process

### 2. **Risk Management**
- Prevents execution of non-compliant portfolios
- Enforces institutional limits consistently
- Documents risk mitigation steps

### 3. **Transparency**
- IC Memo clearly states initial failures
- Shows progression from rejection to approval
- Maintains confidence through clear process

### 4. **Flexibility**
- Multiple revision methods available
- Can adapt to different failure scenarios
- Supports both automated and manual overrides

## Common Revision Scenarios

### Scenario 1: VaR Limit Breach
**Problem**: All candidates exceed 2% daily VaR
**Solution**: Reduce equity allocation, increase bonds
**Method**: orchestrator_override

### Scenario 2: Concentration Violation
**Problem**: Single position > 10% (e.g., VTI at 30%)
**Solution**: Redistribute to multiple ETFs
**Method**: gate_remediation

### Scenario 3: Sector Overweight
**Problem**: Technology sector > 35%
**Solution**: Rebalance to other sectors
**Method**: constraint_tightening

## Monitoring and Alerts

### Key Metrics to Track
- Revision frequency by type
- Common failure patterns
- Time from failure to revision
- Success rate of revised solutions

### Alert Triggers
- Multiple revision cycles needed
- Consistent failures in specific gates
- Unable to find compliant solution
- Manual intervention required

## Best Practices

1. **Always document revision reasons** - Be specific about which limits were violated
2. **Preserve original candidates** - Keep failed attempts for analysis
3. **Validate revisions immediately** - Run gates on revised solution before approval
4. **Track patterns** - Identify systematic issues in optimization
5. **Update constraints proactively** - Learn from failures to improve initial optimization

## Future Enhancements

1. **Machine Learning** - Predict likely failures before optimization
2. **Adaptive Constraints** - Automatically tighten based on failure patterns
3. **Multi-stage Optimization** - Progressive refinement approach
4. **Real-time Monitoring** - Continuous gate validation during market hours