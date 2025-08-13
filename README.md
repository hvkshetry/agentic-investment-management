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

### Automated Safeguards
- **Risk Gate**: VaR limits, Sharpe minimums, stress test thresholds
- **Tax Gate**: Wash sale prevention, loss harvesting rules
- **Compliance Gate**: Regulatory requirements, account minimums
- **Realism Gate**: Prevents impossible Sharpe ratios (>3.0)
- **Credibility Gate**: Multi-source validation requirements

### Example: Preventing GEV Pathology
```yaml
# config/policy/risk_limits.yaml
position_limits:
  max_single_position: 0.10  # 10% max prevents 25% GEV issue
  min_positions: 20          # Ensures diversification
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

MIT License - See LICENSE file for details

## Disclaimer

This system is for educational and research purposes. Not financial advice. Always consult qualified financial advisors for investment decisions.

## Acknowledgments

Built with:
- [Claude Code](https://claude.ai/code) by Anthropic
- [OpenBB](https://openbb.co/) for market data
- [PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) for optimization
- [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) for advanced risk measures

---

**For detailed documentation, see the `/docs` directory**