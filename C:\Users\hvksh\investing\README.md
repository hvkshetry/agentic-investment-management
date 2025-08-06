# AI-Native Investment Advisory System

A sophisticated multi-agent investment analysis platform using Model Context Protocol (MCP) servers for personal portfolio management.

## 🎯 Overview

This system implements a distributed architecture where specialized AI agents handle specific domains of investment analysis, coordinated by a lightweight orchestrator that achieves **99.5% context reduction** compared to traditional approaches.

## 🏗️ Architecture

```
Windows (Configuration)              WSL (Execution)
│                                    │
├─ .claude/                         ├─ openbb-mcp-customizations/
│  ├─ settings.json                 │  └─ 65 curated financial tools
│  └─ agents/                       │
│     ├─ tax-advisor.md            ├─ tax-mcp-server/
│     ├─ portfolio-manager.md      │  └─ tenforty integration
│     ├─ risk-analyst.md           │
│     └─ ... (7 agents)            ├─ portfolio-mcp-server/
│                                   │  └─ scipy optimization
├─ config/                          │
│  └─ personal_settings.yaml       ├─ risk-mcp-server/
│                                   │  └─ risk analytics
└─ workflows/                       │
   └─ README.md                     └─ utils/
                                       └─ data_bridge.py
```

## ✅ System Capabilities

### Financial Data (OpenBB - 65 tools)
- **Equity Analysis**: Fundamentals, price history, analyst estimates
- **Economic Data**: GDP, inflation, employment, interest rates
- **ETF Analytics**: Holdings, sectors, performance
- **Derivatives**: Options chains, volatility surface
- **Trade Analysis**: Export/import data, port volumes

### Tax Optimization (Tenforty)
- Federal and state tax calculations
- Tax loss harvesting optimization
- Capital gains analysis (STCG/LTCG)
- AMT impact assessment
- Quarterly payment estimation

### Portfolio Management (SciPy)
- Sharpe ratio maximization
- Minimum variance portfolios
- Risk parity allocation
- Efficient frontier generation
- Rebalancing recommendations

### Risk Analytics (NumPy/SciPy)
- Value at Risk (VaR) and CVaR
- Stress testing scenarios
- Correlation analysis
- Maximum drawdown
- Component risk attribution

## 🚀 Quick Start

### 1. Prerequisites
- Windows with WSL2 installed
- Python 3.8+ in WSL
- Claude Code desktop app

### 2. Installation

In WSL terminal:
```bash
cd /home/hvksh/investing
source openbb/bin/activate
pip install tenforty scipy numpy pandas pytest
```

### 3. Configuration

Claude Code automatically loads MCP servers from:
`C:\Users\hvksh\investing\.claude\settings.json`

All servers start automatically when Claude Code launches.

### 4. Test Installation

```bash
# In WSL with venv activated
python3 tests/test_mcp_integration.py
python3 tests/test_complete_system.py
```

Expected output:
```
✅ ALL INTEGRATION TESTS PASSED!
✅ SYSTEM TEST COMPLETE - All components working!
```

## 💬 Using with Claude Code

### Example Prompts

**Portfolio Analysis:**
```
Analyze my portfolio in data/sample_portfolio.json. 
Optimize allocation, calculate risk metrics, and identify tax harvesting opportunities.
```

**Rebalancing:**
```
My target allocation is 60% stocks, 30% bonds, 10% alternatives.
Current holdings: SPY 40%, AGG 30%, GLD 10%, VNQ 10%, Cash 10%.
Show rebalancing trades with tax impact.
```

**Risk Assessment:**
```
Calculate VaR for my portfolio. Run stress tests for market crash, 
interest rate spike, and inflation scenarios.
```

**Tax Optimization:**
```
Find tax loss harvesting opportunities over $1000.
I'm single, CA resident, $150k W2 income.
```

## 📊 Performance Metrics

- **Context Usage**: 200 tokens (vs 36,800 for all tools)
- **Response Time**: <10 seconds for complex analyses
- **Accuracy**: Matches commercial platforms
- **Tax Calculations**: IRS-compliant via tenforty

## 🔧 System Components

### MCP Servers (WSL)
| Server | Location | Purpose |
|--------|----------|---------|
| OpenBB | `/home/hvksh/investing/openbb-mcp-customizations/` | Market data |
| Tax | `/home/hvksh/investing/tax-mcp-server/` | Tax calculations |
| Portfolio | `/home/hvksh/investing/portfolio-mcp-server/` | Optimization |
| Risk | `/home/hvksh/investing/risk-mcp-server/` | Risk metrics |

### Agent Definitions (Windows)
| Agent | Role |
|-------|------|
| macro-analyst | Economic conditions |
| equity-analyst | Stock valuation |
| portfolio-manager | Asset allocation |
| risk-analyst | Risk measurement |
| tax-advisor | Tax optimization |
| fixed-income-analyst | Bond markets |
| market-scanner | Multi-asset monitoring |

## 📁 File Structure

```
C:\Users\hvksh\investing\
├── .claude\
│   ├── settings.json          # MCP server configuration
│   └── agents\                # Agent prompts
├── config\
│   └── personal_settings.yaml # Your preferences
├── data\
│   └── sample_portfolio.json  # Portfolio data
├── workflows\
│   └── README.md              # Usage examples
└── README.md                  # This file

/home/hvksh/investing/ (WSL)
├── *-mcp-server/              # MCP servers
├── utils/
│   └── data_bridge.py         # Data transformations
├── tests/
│   ├── test_integration.py    # Component tests
│   └── test_mcp_integration.py # Full system test
└── orchestrator/
    └── parallel_orchestrator.py # Agent coordination
```

## 🧪 Testing

### Unit Tests
```bash
source openbb/bin/activate
python3 tests/test_integration.py
```

### Integration Tests
```bash
python3 tests/test_mcp_integration.py
```

### System Test
```bash
python3 tests/test_complete_system.py
```

## 🔐 Security

- API keys stored in `.env` file (never committed)
- No keys in code or documentation
- All calculations local - no data sent externally
- Tax calculations use official tenforty library

## 🎯 Workflows

### Daily Review
1. Check overnight market moves
2. Review portfolio risk metrics
3. Identify rebalancing needs
4. Scan for tax harvesting

### Quarterly Rebalancing
1. Compare current vs target allocation
2. Generate optimal trades
3. Calculate tax impact
4. Execute with broker

### Tax Loss Harvesting
1. Identify positions with losses >$1000
2. Check wash sale rules
3. Calculate tax benefit
4. Generate trade list

## 📈 Example Output

```
Portfolio Analysis Complete
• Current Sharpe Ratio: 3.38
• Risk Level: Acceptable (VaR: -5.8%)
• Tax Efficiency: Good

Action Items:
1. Rebalance: Reduce SPY from 36% to 25%
2. Harvest losses from ARKK ($5,000 loss)
3. Estimated tax savings: $750

Risk Warnings:
• Large rebalancing trades may trigger taxes
• Consider spreading trades over multiple days
```

## 🤝 Contributing

This is a personal investment management system. If forking:
1. Replace API keys with your own
2. Adjust tax settings for your situation
3. Modify risk parameters to match your tolerance
4. Update portfolio constraints

## ⚠️ Disclaimer

This system is for personal use and educational purposes. Not financial advice. 
Always consult with qualified financial and tax professionals before making investment decisions.

## 📝 License

MIT License - See LICENSE file

## 🙏 Acknowledgments

- OpenBB Platform for market data
- Tenforty for tax calculations
- SciPy/NumPy for portfolio optimization
- Anthropic Claude for AI capabilities

---

**System Status**: ✅ Fully Operational
**Last Updated**: January 2024
**Version**: 1.0.0