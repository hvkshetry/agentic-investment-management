# Investment Analysis Workflows

## System Architecture

### MCP Servers (WSL)
- **Location**: `/home/hvksh/investing/`
- **OpenBB Curated**: 65 financial data tools
- **Tax Server**: Tax calculations via tenforty
- **Portfolio Server**: Optimization via scipy
- **Risk Server**: VaR, stress testing, correlations

### Configuration (Windows)
- **Agent Definitions**: `C:\Users\hvksh\investing\.claude\agents\`
- **Claude Settings**: `C:\Users\hvksh\investing\.claude\settings.json`
- **Personal Config**: `C:\Users\hvksh\investing\config\`

## Common Workflows

### 1. Portfolio Rebalancing Analysis

**Prompt for Claude Code:**
```
Analyze my portfolio for rebalancing. Current holdings:
- SPY: 40%
- AGG: 30%
- GLD: 10%
- VNQ: 10%
- Cash: 10%

Target allocation is 60/30/10 stocks/bonds/alternatives.
Show tax impact and provide specific trade recommendations.
```

**What happens behind the scenes:**
1. OpenBB tools fetch current prices
2. Portfolio server optimizes allocation
3. Risk server calculates new portfolio risk
4. Tax server estimates tax impact
5. Orchestrator synthesizes recommendations

### 2. Tax Loss Harvesting

**Prompt for Claude Code:**
```
Find tax loss harvesting opportunities in my portfolio.
Minimum loss threshold: $1000
Check for wash sale violations.
```

**Process flow:**
1. Get current positions and cost basis
2. Fetch current prices via OpenBB
3. Calculate unrealized gains/losses
4. Tax server identifies harvest candidates
5. Generate trade list avoiding wash sales

### 3. Risk Assessment

**Prompt for Claude Code:**
```
Run comprehensive risk analysis on my portfolio.
Include VaR, stress testing for market crash scenarios,
and correlation analysis.
```

**Analysis steps:**
1. Fetch 252 days of price history
2. Calculate portfolio returns
3. Risk server computes VaR (95% and 99%)
4. Run stress tests (2008 crisis, COVID crash, etc.)
5. Analyze correlations for diversification

### 4. New Position Analysis

**Prompt for Claude Code:**
```
Should I add NVDA to my portfolio?
Analyze fundamentals, impact on portfolio risk,
optimal position size, and tax implications.
```

**Multi-agent coordination:**
1. Equity analyst evaluates NVDA fundamentals
2. Portfolio manager determines optimal weight
3. Risk analyst assesses portfolio impact
4. Tax advisor calculates future tax implications

### 5. Quarterly Review

**Prompt for Claude Code:**
```
Perform my quarterly portfolio review.
Check performance, risk metrics, rebalancing needs,
and tax optimization opportunities.
```

**Comprehensive analysis:**
1. Calculate YTD and quarterly returns
2. Compare to benchmarks
3. Assess risk metrics changes
4. Identify rebalancing triggers
5. Find tax harvesting opportunities

## Data Flow Examples

### OpenBB → Portfolio Optimization
```python
# OpenBB returns price data
price_data = {
    "SPY": [400, 405, 403, 407, 410],
    "AGG": [100, 101, 100.5, 101.5, 102]
}

# Data bridge converts to returns
returns_matrix = [
    [0.0125, 0.01],    # Day 1 returns
    [-0.0049, -0.0049], # Day 2 returns
    [0.0099, 0.0099],   # Day 3 returns
    [0.0074, 0.0049]    # Day 4 returns
]

# Portfolio server optimizes
optimal_weights = {"SPY": 0.65, "AGG": 0.35}
```

### Portfolio → Tax Analysis
```python
# Current portfolio
current = {"SPY": 0.50, "AGG": 0.50}

# Optimized portfolio  
target = {"SPY": 0.65, "AGG": 0.35}

# Rebalancing trades
trades = [
    {"symbol": "SPY", "action": "buy", "amount": 15000},
    {"symbol": "AGG", "action": "sell", "amount": 15000}
]

# Tax impact
capital_gains = 3000  # From AGG sale
tax_liability = 450   # At 15% LTCG rate
```

## Quick Reference Commands

### Daily Tasks
- **Morning check**: "Review overnight market moves and portfolio impact"
- **Risk monitor**: "Check if portfolio VaR exceeds 15%"
- **News scan**: "Any news affecting my holdings?"

### Weekly Tasks
- **Performance**: "Calculate weekly returns vs SPY benchmark"
- **Correlation check**: "Are my holdings becoming more correlated?"

### Monthly Tasks
- **Rebalancing**: "Check for 5% deviation from target allocation"
- **Tax harvesting**: "Find losses to offset YTD gains"
- **Sector rotation**: "Analyze sector performance and adjust exposure"

### Quarterly Tasks
- **Full review**: "Complete portfolio review with recommendations"
- **Tax planning**: "Calculate estimated quarterly tax payments"
- **Strategy assessment**: "Evaluate strategy performance vs goals"

## Integration Points

### MCP Server Tools

**OpenBB (65 tools)**
- equity_price_historical
- economy_gdp_real
- etf_holdings
- derivatives_chains
- (and 61 more...)

**Tax Server (5 tools)**
- tax_calculate
- tax_harvest
- tax_compare
- tax_quarterly
- tax_bracket

**Portfolio Server (4 tools)**
- portfolio_optimize_sharpe
- portfolio_optimize_variance
- portfolio_efficient_frontier
- portfolio_risk_parity

**Risk Server (5 tools)**
- risk_calculate_var
- risk_analyze_metrics
- risk_stress_test
- risk_correlation
- risk_component

## Tips for Effective Use

1. **Be specific**: Include ticker symbols, percentages, and thresholds
2. **Chain analyses**: "After optimizing, show tax impact"
3. **Set constraints**: "Max 10% in any single stock"
4. **Request formats**: "Show results as a table" or "Give me JSON output"
5. **Time horizons**: Specify short-term (days), medium (months), or long (years)

## Troubleshooting

### If analysis seems slow
- OpenBB may be fetching large amounts of historical data
- Try specifying shorter time periods

### If tax calculations seem off
- Verify your filing status and state in personal config
- Check if all income sources are included

### If optimization fails
- Ensure you have enough historical data (minimum 60 days)
- Check for assets with incomplete price history

## Example Multi-Step Analysis

```
User: "I have $100k to invest. Create an optimal portfolio for moderate risk 
tolerance, then show me the tax implications if I sell in 1 year vs 2 years."

System executes:
1. Macro analyst assesses market conditions
2. Portfolio manager creates 60/40 allocation
3. Equity analyst selects specific ETFs
4. Risk analyst confirms moderate risk profile
5. Tax advisor compares STCG vs LTCG scenarios
6. Orchestrator synthesizes final recommendation
```

Result: Complete investment plan with specific ETFs, risk metrics, and tax-optimized holding strategy.