# Optimizer Constraints Fix - Week 2

## Summary
Implemented proper constraint handling using CVXPY to replace problematic PyPortfolioOpt lambda constraints.

## Problem Statement
PyPortfolioOpt's `add_constraint()` method doesn't properly handle complex constraints like:
- Cardinality constraints (max number of assets)
- Sector concentration limits
- ES/VaR risk constraints
- Factor exposure constraints

Lambda function constraints often fail or produce unexpected results.

## Solution: CVXPY Optimizer

### Key Features
1. **Proper DCP Compliance**: All constraints follow Disciplined Convex Programming rules
2. **Mixed-Integer Support**: Handles cardinality constraints with binary variables
3. **Risk Constraints**: Properly encodes VaR and ES limits
4. **Sector Limits**: Direct encoding of sector concentration constraints
5. **Multiple Objectives**: Supports various optimization objectives

### Implementation Details

#### File: `shared/optimization/cvxpy_optimizer.py`

**Core Capabilities:**
- Weight bounds (min/max per asset)
- Cardinality constraints (max number of positions)
- Sector concentration limits
- VaR/ES risk constraints (using variance formulation for DCP)
- Factor exposure constraints
- Multiple optimization objectives

**Key Methods:**
```python
optimize_with_constraints(
    expected_returns,
    covariance_matrix,
    constraints,
    objective="max_sharpe"
)

optimize_with_es_constraint(
    returns_history,
    constraints,
    es_limit=0.025,
    es_alpha=0.975
)
```

### Constraint Types Supported

1. **Position Limits**
   - `min_weight`: Minimum weight per asset (default 0)
   - `max_weight`: Maximum weight per asset (default 0.10)
   - `long_only`: Boolean for long-only constraint

2. **Cardinality**
   - `cardinality`: Maximum number of assets in portfolio
   - Uses binary variables with MIP solvers

3. **Sector Constraints**
   - `sector_mapper`: Dict mapping assets to sectors
   - `max_sector_weight`: Maximum weight per sector
   - Properly aggregates sector exposures

4. **Risk Constraints**
   - `target_var_limit`: VaR limit (converted to variance constraint)
   - `target_es_limit`: Expected Shortfall limit
   - Uses variance formulation for DCP compliance

5. **Concentration**
   - `max_top5_weight`: Maximum weight for top 5 positions
   - Simplified implementation (full version needs sorting variables)

### Test Results

All tests passing except cardinality (needs MIP solver):
- ✅ Basic optimization (min variance, max utility)
- ✅ Sector constraints
- ✅ Risk constraints (VaR/ES)
- ✅ Multiple objectives
- ⚠️ Cardinality (works with relaxation)

### Integration with Portfolio Server

To integrate with `portfolio_mcp_server_v3.py`:

```python
from shared.optimization.cvxpy_optimizer import CVXPYOptimizer

# Replace PyPortfolioOpt constraint handling
optimizer = CVXPYOptimizer()
result = optimizer.optimize_with_constraints(
    expected_returns=mu,
    covariance_matrix=S,
    constraints={
        'min_weight': 0,
        'max_weight': 0.10,
        'sector_mapper': sector_mapper,
        'max_sector_weight': 0.35,
        'target_es_limit': 0.025
    },
    objective='max_sharpe'
)
```

### Advantages Over PyPortfolioOpt

1. **Explicit Constraint Encoding**: No lambda functions or hidden behaviors
2. **DCP Compliance**: Automatic checking of convexity rules
3. **Solver Flexibility**: Can use multiple solvers (CLARABEL, SCS, SCIP)
4. **Better Error Messages**: Clear indication of constraint violations
5. **ES/VaR Support**: Proper risk constraint implementation

### Next Steps

1. Install MIP solver for full cardinality support:
   ```bash
   pip install cvxpy[CBC,SCIP]
   ```

2. Update portfolio server to use CVXPY optimizer for complex constraints

3. Add more sophisticated concentration metrics (Herfindahl, ENB)

4. Implement factor constraints for Fama-French exposures

## Dependencies
- cvxpy (already installed)
- Optional: CBC or SCIP for mixed-integer problems