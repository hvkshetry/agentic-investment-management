# Correct MCP Tool Names Reference

## Portfolio State Server
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__portfolio-state-server__import_broker_csv`
- `mcp__portfolio-state-server__update_market_prices`
- `mcp__portfolio-state-server__simulate_sale`
- `mcp__portfolio-state-server__get_tax_loss_harvesting_opportunities`
- `mcp__portfolio-state-server__record_transaction`

## Portfolio Optimization Server
- `mcp__portfolio-optimization-server__optimize_portfolio_advanced`

## Risk Server
- `mcp__risk-server__analyze_portfolio_risk` (includes stress testing)
- `mcp__risk-server__get_risk_free_rate`

## Tax Server
- `mcp__tax-server__calculate_comprehensive_tax`

## Tax Optimization Server
- `mcp__tax-optimization-server__optimize_portfolio_for_taxes`
- `mcp__tax-optimization-server__find_tax_loss_harvesting_pairs`
- `mcp__tax-optimization-server__simulate_withdrawal_tax_impact`

## Important Notes

### ❌ NON-EXISTENT TOOLS (Do not use):
- `mcp__risk-server__stress_test_portfolio` - Stress testing is part of `analyze_portfolio_risk`

### ✅ Correct Usage for Stress Testing:
```python
# Stress testing is included in analyze_portfolio_risk
mcp__risk-server__analyze_portfolio_risk(
    tickers=tickers,
    weights=weights,
    analysis_options={
        "include_stress_tests": True,
        "scenarios": ["2008_crisis", "covid_crash", "rate_shock"]
    }
)
```

### Parameter Requirements:
- All MCP tools require NATIVE Python types, not JSON strings
- Example:
  - ✅ CORRECT: `tickers=["SPY", "AGG"], weights=[0.5, 0.5]`
  - ❌ WRONG: `tickers="[\"SPY\", \"AGG\"]", weights="[0.5, 0.5]"`

### Common Patterns:
1. Always start with `get_portfolio_state` to get current holdings
2. Extract tickers and weights from the state response
3. Pass these to optimization/risk tools as native lists
4. Write results to session directory `./runs/<timestamp>/`