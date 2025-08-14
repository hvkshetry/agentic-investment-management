# Institutional Portfolio Management System

A workflow-driven investment platform orchestrating specialized agents for portfolio management, risk analytics, and regulatory compliance.

## Architecture

### Workflow-Driven Design
- Deterministic execution via YAML-defined workflows
- Policy gates enforce risk and compliance constraints
- Standardized artifact contracts between agents
- Complete audit trail in `./runs/<timestamp>/`

### Components

**Orchestration Layer**: Main workflow coordinator (`main_workflow.py`)

**Specialist Agents**:
- Portfolio Manager: Position management and rebalancing
- Risk Analyst: VaR, stress testing, concentration analysis
- Tax Advisor: Tax-loss harvesting, wash sale prevention
- Market Scanner: Opportunity identification
- Allocation Agent: Strategic and tactical allocation

**MCP Servers**:
- `portfolio-state-server`: Single source of truth for holdings
- `risk-server-v3`: Advanced risk metrics (VaR, CVaR, stress tests)
- `portfolio-optimization-v3`: PyPortfolioOpt + Riskfolio-Lib
- `tax-server-v2`: Federal/state tax calculations
- `openbb-curated`: 44 financial data tools
- `policy-events-service`: Congressional bills, federal rules

## Workflows

### Portfolio Rebalancing (`rebalance_tlh.yaml`)
- Multi-strategy optimization (HRP, MaxSharpe, MinVol)
- Tax-loss harvesting integration
- Policy gate validation
- IC memo generation

### Daily Monitoring (`daily_check.yaml`)
- Risk alerts and action triggers
- Performance attribution
- Compliance checks

### Portfolio Import (`portfolio_import.yaml`)
- CSV import from major brokers
- Data validation and normalization

## Risk Management

### Concentration Limits
- Single security: 10% maximum
- ETF look-through analysis for true exposure
- Sector concentration: 30% maximum

### Risk Metrics
- Value at Risk (95% confidence)
- Stress testing scenarios
- Sharpe ratio constraints

## Key Features

### Position Look-Through Analysis
- Analyzes underlying ETF/fund holdings
- Aggregates true exposure across positions
- CUSIP-based security identification
- Supports 10,000+ fund mappings

### Tax Optimization
- Municipal bond identification
- Foreign tax credit tracking
- Wash sale rule compliance
- Tax-loss harvesting workflows

## Installation

### Prerequisites
- Python 3.10+
- OpenBB Platform
- SEC data files (provided in `data/`)

### Setup
```bash
# Clone repository
git clone https://github.com/yourusername/portfolio-manager.git
cd portfolio-manager

# Create virtual environment
python3 -m venv openbb
source openbb/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Data Sources

- **Market Data**: OpenBB Platform (SEC, Yahoo Finance)
- **Regulatory**: SEC EDGAR, Congress.gov API
- **Reference Data**: FinanceDatabase (300k+ symbols)
- **CUSIP Mappings**: SEC 13F filings

## Testing

```bash
# Run comprehensive integration test
python tests/test_comprehensive_integration.py

# Test CUSIP mappings
python build_cusip_cik_mapping.py
```

4. Place portfolio CSVs in designated directory:
```
/path/to/portfolio/
├── vanguard.csv
└── ubs.csv
```

### Running Your First Workflow

Simply tell the orchestrator in natural language:

```
"I need to rebalance my portfolio to 70% equity and 30% bonds. 
Focus on minimizing taxes and keeping risk under control."
```

The system will:
1. Parse your intent
2. Select appropriate workflow
3. Execute all stages
4. Validate through gates
5. Generate IC memo
6. Present recommendations

## Session Artifacts

Every workflow execution creates a timestamped session directory:

```
./runs/20250113_143022/
├── portfolio_snapshot.json       # Current holdings
├── macro_context.json           # Economic analysis
├── equity_analysis.json         # Stock valuations
├── optimization_candidate_1.json # HRP method
├── optimization_candidate_2.json # MaxSharpe method
├── risk_report_1.json           # Risk validation
├── tax_impact_1.json            # Tax consequences
├── gate_validation.json         # Policy compliance
├── trade_list.json              # Final orders
├── invariant_report.json        # Math validation
└── ic_memo.md                   # Executive summary
```

## Customization

### Adding New Agents
Create a new file in `agent-prompts/sub-agents/` following the template:

```yaml
---
name: your-agent-name
description: When this agent should be invoked
tools: tool1, tool2, mcp__your-server__method
---

You are a specialist in [domain].

## MANDATORY WORKFLOW
1. **Receive session directory**: You will be provided `./runs/<timestamp>/`
2. **Read dependencies**: Load required artifacts from session
3. **Perform analysis**: Execute your specialized task
4. **Write results**: Create your_analysis.json in session directory

## Task Execution Steps
[Detailed steps for completing tasks]
```

### Adding New Gates
Define policy limits in `config/policy/`:

```yaml
# config/policy/your_limits.yaml
your_gate:
  max_metric: 0.10
  min_threshold: 20
  required_conditions:
    - condition_1
    - condition_2
```

## Security & Compliance

- **No hardcoded credentials**: All sensitive data in environment variables
- **Audit trail**: Complete session history for compliance
- **Policy enforcement**: Automated gates prevent violations
- **Data isolation**: Each session has isolated artifacts
- **Read-only market data**: No execution without explicit approval

## MCP Servers Included

### Portfolio & Analysis
- **portfolio-state-server**: Single source of truth for holdings
- **risk-server-v3**: Advanced risk metrics (VaR, CVaR, stress tests)
- **portfolio-optimization-v3**: PyPortfolioOpt + Riskfolio-Lib
- **tax-server-v2**: Federal/state tax calculations
- **tax-optimization-oracle**: CBC solver for complex optimization

### Market Data
- **openbb-curated**: 44 carefully selected financial data tools
- **policy-events-service**: Congressional bills, federal rules, hearings

## Future Plans: Event-Driven Intelligence Layer

The next major evolution will integrate real-time event catalysts that drive options mispricing, focusing on machine-readable feeds that update on non-Wall Street timetables.

### Priority Event Feeds (Q1 2025)

#### Healthcare & Regulatory
- **FDA OpenFDA API**: Drug/device approvals, recalls, adverse events
  - NDA/ANDA approvals posting at 4-8pm ET
  - Class I/II recall monitoring
  - FAERS adverse event spikes
- **ClinicalTrials.gov API**: Trial status changes, results posting, completion dates
- **CMS Coverage API**: NCD/LCD decisions, MEDCAC meetings affecting reimbursement

#### Market Structure & Trading
- **NYSE/Nasdaq Halts**: LULD and news-pending halt feeds for volatility events
- **FINRA Short Interest**: Enhanced short squeeze detection
- **Options Flow**: Real-time unusual options activity detection

#### Litigation & IP
- **CourtListener/RECAP**: Federal court filings, dockets, alerts
  - TROs, preliminary injunctions, class certifications
  - Patent litigation milestones (Markman hearings, IPR decisions)
- **USPTO PTAB**: Inter partes review decisions affecting biotech/pharma
- **USITC Section 337**: Import ban investigations and determinations

#### Environmental & Infrastructure
- **NOAA/NWS Weather API**: Severe weather alerts affecting insurers, utilities
- **USGS Earthquake API**: Seismic events impacting supply chains
- **PHMSA Pipeline Incidents**: Energy infrastructure disruptions
- **EPA ECHO Enforcement**: Environmental compliance actions

### Implementation Roadmap

#### Phase 1: Core Event Infrastructure (Q1 2025)
- Unified event schema: `{timestamp, source, severity, entities, impact}`
- Entity resolution: Map agency identifiers to CIK/ticker/CUSIP
- Severity scoring heuristics by event type
- Event persistence and replay capabilities

#### Phase 2: Options Intelligence (Q2 2025)
- Implied volatility surface monitoring
- Term structure analysis around known catalysts
- Skew trading signals from asymmetric event risks
- Cross-asset correlation breaks

#### Phase 3: Automated Strategy Generation (Q3 2025)
- Event-driven portfolio hedging workflows
- Catalyst-aware option structures (straddles, calendars, butterflies)
- Risk recycling from harvested vol premium
- Dynamic gate adjustments based on event probability

### Technical Architecture Extensions

#### New MCP Servers Planned
- **event-catalyst-server**: Unified event ingestion and normalization
- **options-analytics-server**: Greeks, surface fitting, strategy backtesting
- **litigation-monitor-server**: PACER/CourtListener integration
- **regulatory-tracker-server**: Multi-agency regulatory pipeline

#### Workflow Enhancements
- Event-triggered workflow activation
- Conditional branching based on external signals
- Multi-stage approval gates for event-driven trades
- Real-time portfolio adjustment capabilities

### Research Initiatives

#### Machine Learning Applications
- Event impact prediction from historical patterns
- Natural language processing of regulatory documents
- Anomaly detection in market microstructure
- Cross-asset contagion modeling

#### Advanced Risk Metrics
- Jump risk decomposition
- Regulatory event VaR
- Litigation outcome probability modeling
- Weather-adjusted sector exposures

## Contributing

We welcome contributions, particularly in areas aligned with our event-driven roadmap:

### Priority Contributions
- Event feed integrations (FDA, CMS, NOAA, etc.)
- Options analytics and Greeks calculations
- Litigation and regulatory tracking workflows
- Cross-asset correlation analysis
- International market support
- Alternative asset classes (crypto, real estate, commodities)
- ESG/Impact investing metrics
- Advanced ML-based risk models

## License

GNU General Public License v3.0 - See [LICENSE](LICENSE) file for details.

This project is licensed under GPL-3.0 due to the inclusion of the Double Finance Oracle component. For detailed licensing information about included components, see the [NOTICE](NOTICE) file.

## Disclaimer

This system is for educational and research purposes. Not financial advice. Always consult qualified financial advisors for investment decisions.

The software is provided "as is", without warranty of any kind, express or implied. See the LICENSE file for full disclaimer.

## Acknowledgments

Built with:
- [Claude Code](https://claude.ai/code) by Anthropic
- [OpenBB](https://openbb.co/) for market data
- [PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) for optimization
- [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) for advanced risk measures

---

**For detailed documentation, see the `/docs` directory**