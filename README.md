# AI Investment Management Team

A sophisticated investment analysis platform combining MCP servers with Claude Code's agent orchestration system to deliver institutional-grade portfolio management, risk analysis, and tax optimization.

## 🏦 System Overview

This platform functions as an AI-powered investment management team, with specialized agents working together through MCP (Model Context Protocol) servers to provide comprehensive financial analysis and portfolio management.

### Investment Team Structure

**Main Orchestrator** coordinates 9 specialized analysts:
- **Risk Analyst** - VaR calculations, stress testing, portfolio risk metrics
- **Portfolio Manager** - Advanced optimization using PyPortfolioOpt/Riskfolio-Lib
- **Tax Advisor** - Federal/state tax optimization, NIIT, trust calculations
- **Macro Analyst** - Economic indicators, central bank policy, regime detection
- **Equity Analyst** - Fundamental analysis, valuation, earnings assessment
- **Fixed Income Analyst** - Yield curves, duration management, credit analysis
- **Market Scanner** - Cross-asset monitoring, sentiment analysis, opportunity detection
- **ETF Analyst** - Fund selection, expense analysis, holdings evaluation
- **Derivatives Analyst** - Options chains, volatility analysis, Greeks

## 🛠️ Core Capabilities

### Risk Management
- **VaR Methods**: Historical, Parametric, Cornish-Fisher
- **Stress Testing**: 2008 crisis, COVID-19, custom scenarios
- **Risk Metrics**: Sharpe, Sortino, CVaR, Maximum Drawdown
- **Correlation Analysis**: Ledoit-Wolf shrinkage for robust estimates

### Portfolio Optimization
- **Modern Portfolio Theory**: Efficient frontier, Black-Litterman
- **Risk Parity**: Equal risk contribution, hierarchical risk parity
- **Advanced Objectives**: 13+ Riskfolio-Lib measures (CVaR, MAD, Ulcer Index)
- **Constraints**: Long-only, position limits, sector allocation

### Tax Optimization
- **Federal Calculations**: Complete brackets, AMT, deductions
- **Investment Taxes**: NIIT (3.8%), capital gains optimization
- **Entity Support**: Individual, trust, estate calculations
- **State Taxes**: Massachusetts-specific with 12% STCG

### Market Data (60+ OpenBB Tools)
- **Equities**: Fundamentals, ownership, analyst estimates
- **Fixed Income**: Treasury rates, yield curves, spreads
- **Economics**: GDP, inflation, employment, trade data
- **ETFs**: Holdings, performance, expense analysis
- **Derivatives**: Options chains, futures curves

## 🚀 Claude Code Configuration

### Prerequisites
1. Install Claude Code CLI
2. Clone this repository to WSL (Ubuntu recommended)
3. Set up Python environment with dependencies

### MCP Server Configuration

Create or update `~/.claude/settings.json` (Windows: `C:\Users\[username]\.claude\settings.json`):

```json
{
  "mcpServers": {
    "openbb-curated": {
      "type": "stdio",
      "command": "wsl",
      "args": [
        "-d", "Ubuntu",
        "/home/[username]/investing/openbb/bin/openbb-mcp",
        "--transport", "stdio",
        "--no-tool-discovery"
      ]
    },
    "tax-server": {
      "type": "stdio",
      "command": "wsl",
      "args": [
        "-d", "Ubuntu",
        "/home/[username]/investing/openbb/bin/python",
        "/home/[username]/investing/tax-mcp-server/tax_mcp_server_v2.py"
      ]
    },
    "portfolio-server": {
      "type": "stdio",
      "command": "wsl",
      "args": [
        "-d", "Ubuntu",
        "/home/[username]/investing/openbb/bin/python",
        "/home/[username]/investing/portfolio-mcp-server/portfolio_mcp_server_v3.py"
      ]
    },
    "risk-server": {
      "type": "stdio",
      "command": "wsl",
      "args": [
        "-d", "Ubuntu",
        "/home/[username]/investing/openbb/bin/python",
        "/home/[username]/investing/risk-mcp-server/risk_mcp_server_v3.py"
      ]
    }
  }
}
```

### Agent Configuration

1. Copy agent prompts to your project:
```bash
cp agent-prompts/CLAUDE.md /path/to/your/project/CLAUDE.md
cp -r agent-prompts/sub-agents /path/to/your/project/.claude/agents/
```

2. The agents will automatically coordinate through the main orchestrator when you work on investment tasks.

### API Keys Setup

Create `~/.openbb_platform/user_settings.json`:
```json
{
  "credentials": {
    "fred_api_key": "your_fred_key",
    "bls_api_key": "your_bls_key",
    "fmp_api_key": "your_fmp_key"
  }
}
```

**Get Free API Keys:**
- [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) - Economic data
- [BLS](https://www.bls.gov/developers/api_registration.htm) - Labor statistics
- [FMP](https://site.financialmodelingprep.com/developer/docs/) - Market data

## 💼 Usage Examples

### Comprehensive Portfolio Rebalancing
"I have saved my current portfolio holdings (statements including cost basis) as CSV files. Given the macro environment, Fed pivot expectations, and current valuations, what do you recommend as prudent reallocation moves? Also, what low risk/high upside asymmetric 'bets' are available that - given your analysis - present a compelling expected value?"

### Tax-Optimized Exit Strategy
"I need to liquidate $500k from my portfolio for a real estate purchase. Analyze my holdings for tax-loss harvesting opportunities, calculate the optimal assets to sell considering STCG vs LTCG implications, NIIT thresholds, and state tax impacts. Also evaluate if establishing a trust structure would provide benefits given my $350k W2 income."

### Multi-Strategy Risk Analysis
"Perform a comprehensive risk assessment across my equity portfolio, fixed income allocation, and options positions. Include stress tests for: 1) 2008-style financial crisis, 2) 1970s stagflation scenario, 3) Japan-style deflation. Calculate my portfolio's factor exposures, identify hidden correlations, and suggest hedging strategies using options that maintain upside participation."

### Institutional-Grade Research Request
"Conduct a full investment committee-style analysis on the semiconductor sector. Include: macro drivers, supply chain dynamics, geopolitical risks (China/Taiwan), competitive positioning of major players, valuation metrics vs historical ranges, options flow analysis for institutional positioning, and specific ETF/equity recommendations with position sizing based on risk parity principles."

## 📊 Key Features

- **Real Market Data**: Live integration with FRED, OpenBB, and financial APIs
- **Professional Algorithms**: Institutional-grade optimization methods
- **Comprehensive Coverage**: Equities, bonds, ETFs, options, commodities, crypto
- **Tax Intelligence**: Federal, state, NIIT, trust calculations
- **Risk Analytics**: Multiple VaR methods, stress testing, Monte Carlo
- **Token Optimized**: ~45% reduction in prompt tokens for efficiency

## 🧪 Testing

```bash
# Activate environment
source openbb/bin/activate

# Run test suite
python -m pytest test_all_fixes.py -v
```

**Test Coverage**: 100% (13/13 tests passing)
- Portfolio optimization algorithms
- Risk calculations with real data
- Tax computation accuracy
- Market data integration
- Agent coordination

## 📁 Project Structure

```
investing/
├── agent-prompts/           # Claude Code agent system prompts
│   ├── CLAUDE.md           # Main orchestrator
│   └── sub-agents/         # 9 specialized analysts
├── risk-mcp-server/        # Risk analysis MCP server
├── portfolio-mcp-server/   # Portfolio optimization server
├── tax-mcp-server/         # Tax calculation server
├── openbb-mcp-customizations/ # OpenBB integration
└── shared/                 # Common utilities
```

## 🔒 Security

- API keys stored securely in user settings
- No hardcoded credentials
- Explicit error handling (no silent failures)
- Data validation at every step

## 📚 Documentation

- `MCP_ARCHITECTURE_GUIDE.md` - Technical architecture details
- `agent-prompts/` - Agent system prompts and capabilities
- `test_all_fixes.py` - Comprehensive usage examples

## 📄 License

MIT License - See LICENSE file for details

---

**Built with**: Claude Code, MCP Protocol, PyPortfolioOpt, Riskfolio-Lib, OpenBB