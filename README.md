# AI-Native Investment Advisory System

A sophisticated multi-agent investment analysis platform using Model Context Protocol (MCP) servers for modular, context-efficient financial advisory.

## Overview

This system implements a distributed architecture where specialized agents handle specific domains of investment analysis, coordinated by a lightweight orchestrator that minimizes context consumption.

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Lightweight Orchestrator               │
│         (Minimal tool exposure)                  │
└────────────────┬────────────────────────────────┘
                 │ Dispatches via Task tool
    ┌────────────┴────────────────────────┐
    │                                      │
┌───▼────┐  ┌──────────┐  ┌──────────┐  ┌▼─────────┐
│ Macro  │  │  Equity  │  │   Risk   │  │Portfolio │
│Analyst │  │ Analyst  │  │ Analyst  │  │ Manager  │
└───┬────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
    │            │              │              │
┌───▼────────────▼──────────────▼──────────────▼────┐
│           MCP Servers (Tool Providers)             │
├────────────┬───────────┬────────────┬─────────────┤
│  OpenBB    │    Tax    │ Portfolio  │    Risk     │
│  Curated   │   Server  │ Optimizer  │  Analytics  │
│ (65 tools) │ (tenforty)│  (scipy)   │   (numpy)   │
└────────────┴───────────┴────────────┴─────────────┘
```

## Key Components

### 1. OpenBB Curated MCP Server
- **Location**: `/home/hvksh/investing/openbb-mcp-customizations/`
- **Tools**: 65 curated from 184+ available
- **Categories**: Economy (20), Equity (19), Fixed Income (6), ETF (8), Derivatives (8), Other (4)
- **Purpose**: Comprehensive market data without context overload

### 2. Tax MCP Server
- **Location**: `/home/hvksh/investing/tax-mcp-server/`
- **Library**: tenforty
- **Capabilities**: Federal/state tax calculations, loss harvesting, bracket analysis
- **Tools**: 5 specialized tax tools

### 3. Portfolio Optimization MCP Server
- **Location**: `/home/hvksh/investing/portfolio-mcp-server/`
- **Methods**: Sharpe optimization, minimum variance, risk parity, efficient frontier
- **Tools**: 4 optimization tools

### 4. Risk Analytics MCP Server
- **Location**: `/home/hvksh/investing/risk-mcp-server/`
- **Metrics**: VaR, CVaR, stress testing, correlation analysis
- **Tools**: 5 risk analysis tools

### 5. Specialist Agents
- **Location**: `/home/hvksh/investing/.claude/agents/` (Windows) or `/mnt/c/Users/hvksh/investing/.claude/agents/` (WSL)
- **Agents**: 
  - macro-analyst: Economic conditions and policy
  - equity-analyst: Stock valuation and fundamentals
  - fixed-income-analyst: Bond markets and rates
  - portfolio-manager: Asset allocation and rebalancing
  - risk-analyst: Risk measurement and hedging
  - tax-advisor: Tax optimization strategies
  - market-scanner: Multi-asset monitoring

### 6. Orchestration System
- **Location**: `/home/hvksh/investing/orchestrator/`
- **Purpose**: Parallel agent coordination with dependency management
- **Context Savings**: Master only loads Task tool, not 78+ individual tools

## Installation

### Prerequisites
```bash
# Python 3.8+
pip install openbb tenforty numpy scipy pandas pydantic pytest asyncio
```

### OpenBB Setup
```bash
cd /home/hvksh/investing/openbb-mcp-customizations
./apply_customizations.sh
```

### Environment Variables
```bash
cp .env.example .env
# Edit .env with your API keys:
# - FRED_API_KEY
# - FMP_API_KEY (for trade analysis)
# - BLS_API_KEY
```

## Usage

### Running MCP Servers

```bash
# Tax Server
python3 /home/hvksh/investing/tax-mcp-server/tax_mcp_server.py

# Portfolio Server
python3 /home/hvksh/investing/portfolio-mcp-server/portfolio_mcp_server.py

# Risk Server
python3 /home/hvksh/investing/risk-mcp-server/risk_mcp_server.py
```

### Using the Orchestrator

```python
from orchestrator.parallel_orchestrator import orchestrate_analysis, AnalysisRequest
import asyncio

request = AnalysisRequest(
    query="Should I rebalance given inflation concerns?",
    portfolio={"SPY": 0.6, "AGG": 0.4},
    risk_tolerance="moderate"
)

result = asyncio.run(orchestrate_analysis(request))
```

### Agent Deployment (via Claude Code)

```markdown
For portfolio optimization analysis, I'll deploy the portfolio-manager agent.

Task Description: Analyze current allocation of 60% SPY, 40% AGG. 
Calculate optimal weights using Sharpe maximization. Consider tax implications 
of rebalancing. Output structured JSON with recommendations.
```

## Testing

```bash
# Run all integration tests
python3 /home/hvksh/investing/tests/test_integration.py

# Run specific test suite
pytest tests/test_integration.py::TestTaxMCPServer -v
```

## Performance Metrics

### Context Consumption
- **Before**: 184 tools × ~200 tokens = 36,800 tokens
- **After**: 1 Task tool = ~200 tokens
- **Reduction**: 99.5% context savings

### Response Times
- Single agent: 2-5 seconds
- Parallel analysis (5 agents): 5-8 seconds
- Full portfolio review: 10-15 seconds

## Security Notes

- API keys stored in `.env` file (never commit)
- No keys in agent prompts or code
- Use `.gitignore` for sensitive files
- Force push after any accidental key exposure

## Trade Analysis Tools

Special tools for monitoring deglobalization and trade impacts:
- `economy_direction_of_trade`: Bilateral trade flows (IMF)
- `economy_export_destinations`: Top export partners (EconDB)
- `economy_indicators`: Comprehensive indicators
- `economy_country_profile`: Country economic data
- `economy_port_volume`: Shipping and logistics

## Limitations

1. **Data Quality**
   - Free tier data may have delays
   - Limited historical depth
   - US market focus

2. **Model Limitations**
   - No real-time execution
   - Simplified tax calculations
   - Basic option pricing

3. **Integration Constraints**
   - MCP servers run separately
   - No persistent state between sessions
   - Manual orchestration in some cases

## Future Enhancements

- [ ] Add websocket support for real-time data
- [ ] Implement Redis for inter-agent communication
- [ ] Create web UI dashboard
- [ ] Add backtesting capabilities
- [ ] Expand international market coverage
- [ ] Implement option strategies
- [ ] Add crypto DeFi analysis

## Contributing

This is a specialized system for investment advisory. Contributions should:
1. Maintain AI-native architecture (no visualizations)
2. Use structured JSON/YAML for all outputs
3. Include comprehensive tests
4. Document context consumption impacts

## License

Private system - not for distribution

## Support

For issues or questions, review agent prompts in `.claude/agents/` directory for capabilities and limitations.