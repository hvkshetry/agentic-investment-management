# AI Investment Management System

An institutional-grade, workflow-driven investment platform that orchestrates specialized AI agents through deterministic workflows to deliver comprehensive portfolio management, risk analysis, and tax optimization.

## Key Innovation: Workflow-Driven Architecture

This system represents a paradigm shift from ad-hoc tool usage to **deterministic, workflow-driven portfolio management**. Instead of agents making isolated decisions, they collaborate through structured workflows with defined stages, gates, and validation layers.

### Core Principles
- **Declarative Workflows**: Define investment processes in YAML, not code
- **Policy Gates**: Automated compliance checks prevent pathological optimizations
- **Artifact Contracts**: Standardized data flow between agents
- **Audit Trail**: Complete session history in `./runs/<timestamp>/`
- **Natural Language Control**: Seed workflows with plain English instructions

## System Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────┐
│         Orchestration Layer             │
│         (CLAUDE.md - Main AI)           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Workflow Engine                  │
│   (Declarative YAML Configurations)      │
│                                          │
│  • rebalance_tlh.yaml                   │
│  • daily_check.yaml                     │
│  • portfolio_import.yaml                │
│  • [Your custom workflows...]           │
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
│  • openbb-curated (44 tools)           │
│  • policy-events-service                │
└─────────────────────────────────────────┘
```

## Critical System Improvements (2025-08-18)

### Expected Shortfall (ES) Primary Risk Management
The system now uses **Expected Shortfall at 97.5% confidence** as the primary risk metric, replacing VaR-based decisions. ES provides superior tail risk measurement by showing the average loss beyond VaR threshold.

- **ES Limit**: 2.5% (binding constraint)
- **HALT Protocol**: Automatic trading stop if ES exceeds limit
- **Round-2 Gate**: Mandatory validation for all portfolio revisions

### Tax Reconciliation System
Single-source-of-truth for all tax calculations with:
- Recomputation on every portfolio revision
- Immutable tax artifacts with checksums
- FIFO lot selection and wash sale detection
- Complete audit trail for IRS compliance

### Key Components
- `shared/risk_conventions.py`: Standardized risk calculations
- `orchestrator/round2_gate.py`: Mandatory revision validation
- `tax-mcp-server/tax_reconciliation.py`: Tax single-source-of-truth
- `shared/optimization/cvxpy_optimizer.py`: Proper constraint handling

See `documentation/COMPLETE_FIX_SUMMARY.md` for full details.

## Pre-Built Workflows

### 1. **Portfolio Rebalancing with Tax Loss Harvesting** (`rebalance_tlh.yaml`)
Full institutional-grade rebalancing with multiple optimization methods, risk validation, and tax efficiency.

**Natural Language Trigger:**
```
"Rebalance my portfolio to 80% equity / 20% fixed income with tax efficiency"
```

**Workflow Stages:**
1. Portfolio import from CSV
2. Parallel market analysis (macro, equity, fixed income)
3. Multiple optimization candidates (HRP, MaxSharpe, etc.)
4. Risk validation and stress testing
5. Tax impact analysis and harvesting
6. Policy gate validation
7. Final selection and trade list
8. IC memo generation

### 2. **Daily Portfolio Check** (`daily_check.yaml`)
Lightweight morning monitoring with risk alerts and action triggers.

**Natural Language Trigger:**
```
"Run my daily portfolio check"
```

### 3. **Portfolio Import** (`portfolio_import.yaml`)
Import and validate portfolio data from broker CSV files.

**Natural Language Trigger:**
```
"Import my portfolio statements from Vanguard and UBS"
```

## Policy Gates System

### Automated Safeguards (ES-Primary)
- **Risk Gate**: ES limits (2.5% at 97.5% confidence), VaR reference only
- **Tax Gate**: Single-source-of-truth reconciliation, wash sale prevention
- **Compliance Gate**: Regulatory requirements, account minimums
- **Realism Gate**: Prevents impossible Sharpe ratios (>3.0)
- **Credibility Gate**: Multi-source validation requirements
- **Round-2 Gate**: MANDATORY validation for all portfolio revisions
- **HALT Protocol**: Automatic trading stop if ES > 2.5% or critical failures

### Example: ES-Primary Risk Control
```yaml
# config/policy/risk_limits.yaml
risk_limits:
  es_limit: 0.025           # 2.5% Expected Shortfall (BINDING)
  es_alpha: 0.975           # 97.5% confidence level
  var_limit: 0.020          # 2.0% VaR (reference only)
position_limits:
  max_single_position: 0.15  # 15% max concentration
  min_positions: 15          # Ensures diversification
halt_triggers:
  es_breach: true           # HALT if ES > 2.5%
  liquidity_crisis: 0.3     # HALT if liquidity score < 0.3
```

## Creating Custom Workflows

Workflows are defined in YAML and live in `config/workflows/`. Here's a template:

```yaml
workflow: your_workflow_name
description: What this workflow accomplishes
schedule: on_demand  # or: daily, weekly, monthly

# Token budget (guideline, not hard limit)
guidelines:
  target_tokens: 50000

# Agent sequence with dependencies
sub_agents_sequence:
  - id: step_1
    name: portfolio-manager
    task: |
      Your detailed task instructions here
    outputs: [artifact_name]
    
  - id: step_2
    name: risk-analyst
    task: |
      Analyze the portfolio for risk
    depends_on: [step_1]
    outputs: [risk_report]
    gates: [risk_gate]

# Gate definitions
gates:
  risk_gate:
    checks:
      - var_95 <= 0.02
      - sharpe_ratio >= 0.5

# Action triggers
triggers:
  alert_user:
    conditions:
      - risk_level == "HIGH"
    action: send_notification
```

## Getting Started

### Prerequisites
1. **Claude Code CLI** installed and configured
2. **Python 3.10+** with virtual environment
3. **WSL/Linux** (recommended) or macOS
4. **Portfolio CSV files** in supported format

### Installation

1. Clone the repository:
```bash
git clone https://github.com/[your-username]/ai-investment-management.git
cd ai-investment-management
```

2. Set up Python environment:
```bash
python -m venv openbb
source openbb/bin/activate
pip install -r requirements.txt
```

3. Configure MCP servers in `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "portfolio-state-server": {
      "command": "python",
      "args": ["[path]/portfolio-state-mcp-server/state_server.py"]
    },
    "risk-server-v3": {
      "command": "python",
      "args": ["[path]/risk-mcp-server-v3/risk_server.py"]
    }
    // ... other servers
  }
}
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

## New Features (Latest Release)

### Position Look-Through Analysis
- **ETF/Fund Transparency**: Analyzes underlying holdings of ETFs and mutual funds
- **True Concentration Risk**: Aggregates exposure across direct holdings and fund positions
- **CUSIP-Based Identification**: Maps securities using CUSIP identifiers from SEC filings
- **Comprehensive Coverage**: Supports 10,000+ fund mappings via FinanceDatabase

### Enhanced Data Pipeline
- **SEC EDGAR Integration**: Automated CUSIP-CIK mapping from 13F filings
- **FinanceDatabase Integration**: 300,000+ symbols with categorization
- **Real-Time Updates**: SEC data files refreshed nightly
- **CUSIP Mappings**: 320+ major securities pre-mapped

### Tax Optimization Improvements
- **Municipal Bond Detection**: Identifies tax-exempt securities
- **Foreign Tax Credit Tracking**: Optimizes international holdings
- **Wash Sale Compliance**: Automated 30-day rule enforcement
- **Tax Loss Harvesting**: Integrated into rebalancing workflows

### Testing & Validation
- **Comprehensive Integration Tests**: `test_comprehensive_integration.py`
- **CUSIP Mapping Builder**: `build_cusip_cik_mapping.py` for expanding coverage
- **Fund Category Builder**: Automated categorization from FinanceDatabase

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
- [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) for advanced risk measures
- [FinanceDatabase](https://github.com/JerBouma/FinanceDatabase) for security categorization

---

**For detailed documentation, see the `/docs` directory**