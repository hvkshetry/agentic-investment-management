# AI Investment Management System

An institutional-grade investment platform orchestrating specialized AI agents through deterministic workflows for comprehensive portfolio management, risk analysis, and tax optimization.

## Key Innovation: Workflow-Driven Architecture

This system represents a paradigm shift from ad-hoc tool usage to **deterministic, workflow-driven portfolio management**. Instead of agents making isolated decisions, they collaborate through structured workflows with defined stages, gates, and validation layers.

**Core Principles:**
- **Declarative Workflows**: Define investment processes via slash commands, not code
- **Policy Gates**: Automated compliance checks prevent pathological optimizations
- **Artifact Contracts**: Standardized data flow between agents
- **Audit Trail**: Complete session history in `./runs/<timestamp>/`
- **Tool-First Data**: All metrics from MCP servers—no estimation allowed

## System Architecture

```
┌─────────────────────────────────────────┐
│         Orchestration Layer             │
│         (CLAUDE.md - Main AI)           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Workflow Engine                  │
│   Accessible via Slash Commands:        │
│   • /daily-check                        │
│   • /rebalance                          │
│   • /import-portfolio                   │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│        Specialist Agents (12)           │
│                                          │
│  Domain Experts:        Validators:     │
│  • portfolio-manager    • gate-validator│
│  • risk-analyst        • ic-memo-gen    │
│  • tax-advisor         • invariant-check│
│  • equity-analyst                       │
│  • macro-analyst       [Extensible]     │
│  • fixed-income-analyst                 │
│  • market-scanner                       │
│  • etf-analyst                          │
│  • derivatives-analyst                  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         MCP Server Layer                │
│                                          │
│  • portfolio-state-server (Truth)       │
│  • risk-server-v3                       │
│  • portfolio-optimization-v3            │
│  • tax-server-v2                        │
│  • tax-optimization-oracle              │
│  • openbb-curated (18 zero-cost tools) │
│  • policy-events-service                │
└─────────────────────────────────────────┘
```

## Critical Risk Management

### Expected Shortfall (ES) Primary Constraint
**ES @ 97.5% confidence must remain below 2.5%**—this is the binding risk limit, not VaR. Expected Shortfall measures the average loss beyond the VaR threshold, providing superior tail risk measurement.

- **ES Limit**: 2.5% (NON-NEGOTIABLE)
- **HALT Protocol**: Automatic trading stop if ES exceeds limit
- **Round-2 Gate**: Mandatory validation for all portfolio revisions

### Tool-First Data Policy
Strict enforcement of data integrity with mandatory provenance tracking:
- ALL metrics must come from MCP tool calls
- No estimation or fabrication allowed
- Every data point includes source and timestamp
- Missing data explicitly noted with "needs" entries

### Concentration Risk Management
- ALL funds (ETFs, mutual funds, CEFs) are EXEMPT from individual limits
- Only individual stocks subject to 20% position limit
- Lookthrough analysis for true underlying exposure
- Automatic HALT if concentration breach detected

### Tax Reconciliation
Single-source-of-truth for tax calculations:
- Recomputation on every portfolio revision
- Immutable tax artifacts with checksums
- FIFO lot selection and wash sale detection
- Complete audit trail for IRS compliance

## Slash Command Workflows

Access pre-built workflows via simple commands:

**`/daily-check`** - Morning portfolio monitoring with risk alerts and action triggers

**`/rebalance`** - Full institutional-grade rebalancing with:
- Multiple optimization methods (HRP, MaxSharpe, Risk Parity)
- Risk validation and stress testing
- Tax loss harvesting integration
- Policy gate validation
- IC memo generation

**`/import-portfolio`** - Import and validate broker CSV files

Each workflow executes a deterministic sequence of agents, validates through policy gates, and generates a complete audit trail in `./runs/<timestamp>/`.

## Policy Gates System

Automated safeguards prevent pathological optimizations:

- **Risk Gate**: ES @ 97.5% ≤ 2.5% (binding), VaR reference only
- **Tax Gate**: Single-source-of-truth reconciliation, wash sale prevention
- **Compliance Gate**: Regulatory requirements, account minimums
- **Realism Gate**: Prevents impossible Sharpe ratios (>3.0)
- **Credibility Gate**: Multi-source validation requirements
- **Round-2 Gate**: MANDATORY validation for all portfolio revisions
- **HALT Protocol**: Automatic trading stop on critical failures

## MCP Servers (7 Total)

### Portfolio & Analysis (5 servers)
- **portfolio-state-server**: Single source of truth for holdings and tax lots
- **risk-server-v3**: Advanced risk metrics (ES, VaR, CVaR, stress tests)
- **portfolio-optimization-v3**: PyPortfolioOpt + Riskfolio-Lib integration
- **tax-server-v2**: Federal/state tax calculations (2018-2025)
- **tax-optimization-oracle**: CBC solver for tax-aware optimization

### Market Data & Intelligence (2 servers)
- **openbb-curated**: 18 zero-cost financial data tools
  - Real-time quotes (Yahoo/Alpha Vantage)
  - FX data (ECB/Frankfurter)
  - Macro indicators (World Bank, IMF)
  - News & sentiment (GDELT)
  - Analyst coverage (Finnhub, FMP)
  - SEC filing section parser (edgar-crawler)
  - Charting (QuickChart)
  - Commodities (LBMA gold/silver)
- **policy-events-service**: Congressional bills, federal rules, hearings

## Getting Started

### Prerequisites
1. Claude Code CLI installed and configured
2. Python 3.10+ with virtual environment
3. WSL/Linux (recommended) or macOS
4. Portfolio CSV files from your broker

### Quick Setup

1. **Clone and install:**
```bash
git clone <repository-url>
cd ai-investment-management
python -m venv openbb
source openbb/bin/activate
pip install -r requirements.txt
```

2. **Configure API keys** (optional—works with free-tier only):
```bash
cp .env.example .env
# Add API keys if you have them (Alpha Vantage, Finnhub, FMP)
# System works without any paid APIs using Yahoo Finance
```

3. **Set up MCP servers:**
```bash
cp .mcp.json ~/.claude/mcp_servers.json
# Edit paths if needed (should work as-is)
```

4. **Place your portfolio CSVs** in the `portfolio/` directory

### Run Your First Workflow

Simply use the slash command in Claude Code:

```
/import-portfolio
```

Follow up with:

```
/daily-check
```

Or for full rebalancing:

```
/rebalance with target allocation: 80% equity, 20% fixed income
```

The system will execute the workflow, validate through gates, and present recommendations with a complete audit trail in `./runs/<timestamp>/`.

## Session Artifacts

Every workflow execution creates a timestamped directory with:

```
./runs/20250113_143022/
├── portfolio_snapshot.json       # Current holdings
├── macro_context.json           # Economic analysis
├── equity_analysis.json         # Stock valuations
├── optimization_candidate_*.json # Multiple strategies tested
├── risk_report_*.json           # Risk validation
├── tax_impact_*.json            # Tax consequences
├── gate_validation.json         # Policy compliance
├── trade_list.json              # Final orders
└── ic_memo.md                   # Executive summary
```

## Customization

### Adding New Agents
Create a file in `agent-prompts/sub-agents/` following the YAML template structure. Your agent receives a session directory, reads dependencies, performs analysis, and writes results.

### Adding New Gates
Define policy limits in `config/policy/` as YAML files with your constraints and thresholds.

### Creating Custom Workflows
Define workflows in `config/workflows/` as YAML, then expose via slash command in `.claude/commands/`.

## Advanced Features

### Position Look-Through Analysis
- Analyzes underlying holdings of ETFs and mutual funds
- True concentration risk across direct and indirect positions
- CUSIP-based identification from SEC filings
- Supports 10,000+ fund mappings via FinanceDatabase

### Enhanced Data Pipeline
- SEC EDGAR integration for CUSIP-CIK mapping
- FinanceDatabase integration (300,000+ symbols)
- Automated CUSIP mappings for 320+ major securities
- Real-time updates from SEC daily files

### Tax Optimization
- Municipal bond detection for tax-exempt income
- Foreign tax credit tracking
- Automated wash sale compliance (30-day rule)
- Tax loss harvesting integrated into rebalancing

## Security & Compliance

### Data Protection
- No hardcoded credentials (`.env` for all secrets)
- Sensitive files excluded from git
- Complete audit trail for compliance
- Isolated artifacts per session

### Risk Controls
- Automated policy gates prevent violations
- HALT protocol on ES breach (>2.5%)
- Round-2 mandatory validation
- Tool-first data policy (no estimation)

### Public Deployment
Before sharing publicly, run:
```bash
./cleanup_for_public.sh
```

## Important GDELT Usage Note

When using news search tools powered by GDELT:

**❌ DON'T use abbreviations shorter than 3 characters:**
- "AI" → Use "artificial intelligence"
- "ML" → Use "machine learning"
- "IoT" → Use "internet of things"

**✅ DO use full terms or exceptions:**
- Geographic codes are OK: US, UK, EU, UN
- Full phrases work best: "digital twin water systems"

GDELT rejects queries with keywords shorter than 3 characters. If you see GDELT errors, reformulate with longer terms.

## Future Plans: Event-Driven Intelligence

The roadmap includes integrating real-time event catalysts for options mispricing:

### Priority Event Feeds (2025)
- **Healthcare**: FDA OpenFDA API, ClinicalTrials.gov, CMS coverage decisions
- **Market Structure**: NYSE/Nasdaq halts, FINRA short interest, unusual options activity
- **Litigation**: CourtListener/RECAP federal filings, USPTO PTAB decisions, USITC investigations
- **Environmental**: NOAA weather alerts, USGS earthquakes, PHMSA pipeline incidents, EPA enforcement

### Implementation Phases
1. **Q1 2025**: Core event infrastructure with unified schema and entity resolution
2. **Q2 2025**: Options intelligence with IV surface monitoring and skew analysis
3. **Q3 2025**: Automated strategy generation for event-driven hedging and catalyst trading

## Directory Consolidation

**All development consolidated to Linux location**: `/home/[user]/investing`

If you previously had `C:\Users\[username]\investing`:
- ✅ All files migrated to Linux location
- ✅ Safe to delete Windows directory after verification
- See `DEPRECATED_LOCATION.md` in old location for details

## Contributing

We welcome contributions, particularly:
- Event feed integrations (FDA, CMS, NOAA, CourtListener)
- Options analytics and Greeks calculations
- International market support
- Alternative asset classes (crypto, real estate)
- ESG/Impact investing metrics
- Advanced ML-based risk models

## License

GNU General Public License v3.0 - See [LICENSE](LICENSE) file for details.

This project uses GPL-3.0 due to the Double Finance Oracle component. See [NOTICE](NOTICE) for full licensing information.

## Data Sources

- **Market Data**: OpenBB Platform (SEC, Yahoo Finance, Federal Reserve)
- **Regulatory**: SEC EDGAR, Congress.gov API
- **Reference Data**: FinanceDatabase (94,405 fund categories)
- **CUSIP Mappings**: SEC 13F filings, company_tickers.json

## Acknowledgments

Built with:
- [Claude Code](https://claude.ai/code) by Anthropic
- [OpenBB](https://openbb.co/) for market data
- [PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) for optimization
- [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) for risk measures
- [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase) for security categorization

## Disclaimer

This system is for educational and research purposes. Not financial advice. Always consult qualified financial advisors for investment decisions.

The software is provided "as is", without warranty of any kind. See LICENSE for full details.

---

**For detailed documentation, see the `/docs` directory**
