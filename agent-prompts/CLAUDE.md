# Investment Management Platform - Agent Orchestration Guide

## Available Specialist Agents

### 1. **Equity Research Analyst**
**Capabilities:** Fundamental analysis, financial statements, valuation metrics, insider trading, price analysis
**Use For:** Stock analysis, sector comparisons, earnings assessment, equity risk evaluation

### 2. **Macro Analyst** (Economic Indicators)
**Capabilities:** GDP, CPI, unemployment, FRED data, currency analysis, commodity prices
**Use For:** Economic cycle analysis, rate environment, inflation impact, market timing

### 3. **Fixed Income Analyst**
**Capabilities:** Treasury yields, yield curve, SOFR/EFFR rates, duration risk, credit spreads
**Use For:** Bond allocation, rate hedging, yield positioning, fixed income vs equity

### 4. **ETF Analyst**
**Capabilities:** Holdings analysis, performance metrics, expense ratios, sector/geographic exposure
**Use For:** Core portfolio construction, sector rotation, diversification, tactical allocation

### 5. **Derivatives Options Analyst**
**Capabilities:** Options chains, implied volatility, Greeks analysis, futures curves
**Use For:** Hedging strategies, income generation, volatility trading, risk overlays

### 6. **Market Scanner**
**Capabilities:** News analysis, market sentiment, overnight developments
**Use For:** Daily market updates, breaking news, sentiment shifts

### 7. **Risk Analyst**
**MCP Tools:** `analyze_portfolio_risk`, `get_risk_free_rate`
**Capabilities:** Multiple VaR methods, Ledoit-Wolf shrinkage, component risk, stress testing
**Use For:** Portfolio risk assessment, stress testing, risk attribution, hedging design

### 8. **Portfolio Manager**
**MCP Tool:** `optimize_portfolio_advanced` (handles all optimization methods)
**Capabilities:** PyPortfolioOpt, Riskfolio-Lib (13+ risk measures), HRP, constraints
**Use For:** Asset allocation, portfolio optimization, rebalancing analysis

### 9. **Tax Advisor**
**MCP Tool:** `calculate_comprehensive_tax`
**Capabilities:** Federal/state taxes, NIIT, trust tax, MA/CA specifics, loss harvesting
**Use For:** Tax impact analysis, harvesting strategies, quarterly estimates

## MANDATORY: Use Sequential Thinking

**ALWAYS use `mcp__sequential-thinking__sequentialthinking` for multi-agent coordination.**

## Orchestration Workflows

### Top-Down Analysis
1. Macro Analyst → Economic environment
2. Fixed Income Analyst → Rate implications
3. Equity Research Analyst → Sector/stock selection
4. ETF Analyst → Implementation
5. Risk Analyst → Risk assessment
6. Portfolio Manager → Optimization
7. Tax Advisor → Tax efficiency

### Portfolio Construction
1. Portfolio Manager → Strategic allocation
2. Risk Analyst → Risk budgeting
3. Tax Advisor → Tax-efficient implementation
4. Derivatives Analyst → Hedging overlay

### Risk Management
1. Risk Analyst → VaR and stress testing
2. Portfolio Manager → Position sizing
3. Derivatives Analyst → Protective strategies

## Agent Coordination

### Daily Workflow
**Market Open:**
- Market Scanner → Overnight developments
- Risk Analyst → VaR update
- Macro Analyst → Economic calendar

**Market Close:**
- Portfolio Manager → Performance attribution
- Risk Analyst → End-of-day metrics
- Tax Advisor → Realized gains/losses

### Event Triggers
- VaR breach > 2% → Risk Analyst → Portfolio Manager
- Drawdown > 10% → Full team review
- Position drift > 5% → Portfolio Manager → Tax Advisor

## Conflict Resolution

### Domain Authority
- **Macro Analyst:** Veto on economic regime
- **Risk Analyst:** Veto on position sizing
- **Tax Advisor:** Veto on trade timing (wash sales)
- **Portfolio Manager:** Veto on allocation

### Resolution Process
1. Confidence-weighted voting
2. Domain expert veto rights
3. Sharpe ratio as tiebreaker
4. Document decision rationale

## Report Generation

All agents generate reports to `/reports/` directory:
- Format: `[Type]_Analysis_[Topic]_[Date].md`
- Include: Executive summary, analysis, recommendations

## Multi-Agent Validation

For decisions > 1% of portfolio:
1. Primary agent recommendation
2. Risk Analyst validates
3. Tax Advisor confirms efficiency
4. Portfolio Manager checks allocation
5. Document rationale

## Final Mandate

1. Use Sequential Thinking for complex analyses
2. Coordinate multiple agents for comprehensive views
3. Document all investment rationale
4. Generate reports for all research
5. Consider risk in every decision
6. Maintain fiduciary standards