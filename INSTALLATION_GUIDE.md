# Installation & Configuration Guide

## Investment Management System - MCP Server Setup

**Last Updated:** 2025-10-21
**System Requirements:** Python 3.10+, WSL2/Linux/macOS

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Steps](#installation-steps)
3. [MCP Server Configuration](#mcp-server-configuration)
4. [Environment Variables](#environment-variables)
5. [Dependency Details](#dependency-details)
6. [License Compliance](#license-compliance)
7. [Troubleshooting](#troubleshooting)
8. [Verification](#verification)

---

## Prerequisites

### System Requirements

- **Operating System:** WSL2 (Ubuntu), Linux, or macOS
- **Python:** 3.10 or higher (3.12 recommended)
- **Git:** For cloning repository
- **Disk Space:** ~2GB for virtual environment and dependencies
- **Memory:** 4GB RAM minimum (8GB recommended)

### Required Skills

- Basic command-line knowledge
- Familiarity with Python virtual environments
- Understanding of environment variables
- Basic Git usage

---

## Installation Steps

### Step 1: Clone Repository

```bash
# Navigate to your preferred location
cd ~

# Clone the repository
git clone https://github.com/hvkshetry/agentic-investment-management.git investing

# Navigate to the directory
cd investing
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment named 'openbb'
python3 -m venv openbb

# Activate the virtual environment
source openbb/bin/activate

# Verify Python version
python --version  # Should show 3.10 or higher
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt

# This will install:
# - Core: fastmcp, pydantic
# - Market Data: openbb, yfinance, pandas, numpy
# - Optimization: PyPortfolioOpt, Riskfolio-Lib, cvxpy, pulp
# - Tax: policyengine-us, policyengine-core, tenforty
# - Analytics: quantstats, empyrical, scipy, scikit-learn
# - Policy Events: beautifulsoup4, lxml
# - And more (see requirements.txt for full list)
```

**Installation Time:** 5-10 minutes depending on internet speed

**Expected Output:**
```
Successfully installed fastmcp-2.11.0 policyengine-us-1.424.4 ...
```

### Step 4: Verify Installation

```bash
# Check critical packages
python -c "import fastmcp; print('FastMCP:', fastmcp.__version__)"
python -c "import policyengine_us; print('PolicyEngine-US installed')"
python -c "import pypfopt; print('PyPortfolioOpt installed')"
python -c "import riskfolio; print('Riskfolio-Lib installed')"
```

**Expected Output:**
```
FastMCP: 2.11.0
PolicyEngine-US installed
PyPortfolioOpt installed
Riskfolio-Lib installed
```

---

## MCP Server Configuration

### Step 5: Configure MCP Servers

The repository includes a pre-configured `.mcp.json` file. You need to copy it to Claude's configuration directory:

```bash
# Create Claude config directory if it doesn't exist
mkdir -p ~/.claude

# Copy MCP configuration
cp .mcp.json ~/.claude/mcp_servers.json

# Verify file paths in config
cat ~/.claude/mcp_servers.json | grep command
```

**Important:** The `.mcp.json` file uses absolute paths. If you cloned to a different location than `~/investing`, you'll need to update the paths:

```bash
# If you installed to /custom/path/investing, update paths:
sed -i 's|/home/hvksh/investing|/custom/path/investing|g' ~/.claude/mcp_servers.json
```

### Step 6: API Keys Configuration

Create a `.env` file for API keys:

```bash
# Copy environment template
cat > .env << 'EOF'
# Policy Events API Keys
# Get free API keys from:
# Congress.gov: https://api.congress.gov/sign-up/
# GovInfo: https://api.govinfo.gov/docs/
CONGRESS_API_KEY=your_congress_key_here
GOVINFO_API_KEY=your_govinfo_key_here

# Optional: OpenBB API Keys (free tiers available)
FRED_API_KEY=your_fred_key_here
BLS_API_KEY=your_bls_key_here
FMP_API_KEY=your_fmp_key_here

# Zero-Cost Data Providers
ENABLE_YAHOO_UNOFFICIAL=true
ALPHAVANTAGE_API_KEY=your_alphavantage_key_here
FINNHUB_API_KEY=your_finnhub_key_here
EOF
```

**Get Free API Keys:**

1. **Congress.gov API** (required for policy events):
   - Visit: https://api.congress.gov/sign-up/
   - Instant approval, no credit card required

2. **GovInfo API** (required for policy events):
   - Visit: https://api.govinfo.gov/docs/
   - Instant approval, no credit card required

3. **FRED API** (optional, for economic data):
   - Visit: https://fred.stlouisfed.org/docs/api/api_key.html
   - Instant approval

4. **Alpha Vantage** (optional, quote fallback):
   - Visit: https://www.alphavantage.co/support/#api-key
   - Free tier: 5 calls/min, 500/day

5. **Finnhub** (optional, analyst coverage):
   - Visit: https://finnhub.io/register
   - Free tier: 60 calls/min

**Note:** The system works with Yahoo Finance (no API key needed) even without these optional keys.

---

## Environment Variables

### PYTHONPATH Configuration

Each MCP server requires PYTHONPATH to find shared modules. This is already configured in `.mcp.json`:

**Standard servers:**
```json
"PYTHONPATH": "/home/hvksh/investing:/home/hvksh/investing/shared"
```

**Tax optimization server (includes Oracle):**
```json
"PYTHONPATH": "/home/hvksh/investing:/home/hvksh/investing/shared:/home/hvksh/investing/oracle/src"
```

**Verify shared modules are accessible:**
```bash
# From the investing directory
python -c "import sys; sys.path.insert(0, 'shared'); import confidence_scoring; print('Shared modules OK')"
```

---

## Dependency Details

### Core Dependencies

#### MCP Framework
- **fastmcp** 2.11.0+ - Model Context Protocol server framework
- **pydantic** 2.0.0+ - Data validation and settings management

#### Market Data
- **openbb** 4.0.0+ - Comprehensive market data platform (AGPL-3.0)
- **yfinance** 0.2.40+ - Yahoo Finance data (Apache 2.0)
- **pandas** 2.0.0+ - Data manipulation (BSD-3-Clause)
- **numpy** 1.24.0+ - Numerical computing (BSD-3-Clause)

#### Portfolio Optimization
- **PyPortfolioOpt** 1.5.5+ - Efficient frontier, Black-Litterman, HRP (MIT)
- **Riskfolio-Lib** 6.0.0+ - Advanced optimization, 13+ risk measures (BSD-3-Clause)
- **cvxpy** 1.4.0+ - Convex optimization (Apache 2.0)
- **pulp** 2.7.0+ - Linear programming for Oracle (MIT)

#### Tax Calculations (AGPL-3.0 Notice)
- **policyengine-us** 1.424.0+ - Individual tax calculations (AGPL-3.0) ⚠️
- **policyengine-core** 3.20.0+ - PolicyEngine framework (AGPL-3.0) ⚠️
- **tenforty** 2024.0.0+ - Trust/estate calculations (MIT)

**⚠️ License Implication:** PolicyEngine-US is licensed under AGPL-3.0, which requires source code disclosure for network services. See [License Compliance](#license-compliance) below.

#### Statistical & ML
- **scipy** 1.10.0+ - Scientific computing (BSD-3-Clause)
- **scikit-learn** 1.3.0+ - Ledoit-Wolf shrinkage (BSD-3-Clause)
- **statsmodels** 0.14.0+ - Time series analysis (BSD-3-Clause)

#### Policy Events
- **beautifulsoup4** 4.12.0+ - HTML parsing (MIT)
- **lxml** 4.9.0+ - XML parsing (BSD-3-Clause)
- **httpx** 0.25.0+ - Async HTTP client (BSD-3-Clause)

### Dependency Tree

```
investment-management-system/
├─ fastmcp (MIT)
├─ Market Data
│  ├─ openbb (AGPL-3.0) ⚠️
│  ├─ yfinance (Apache 2.0)
│  └─ pandas/numpy (BSD-3-Clause)
├─ Optimization
│  ├─ PyPortfolioOpt (MIT)
│  ├─ Riskfolio-Lib (BSD-3-Clause)
│  └─ cvxpy (Apache 2.0)
├─ Tax Calculations
│  ├─ policyengine-us (AGPL-3.0) ⚠️ PRIMARY COPYLEFT
│  ├─ policyengine-core (AGPL-3.0) ⚠️
│  └─ tenforty (MIT)
└─ Analytics
   ├─ scipy (BSD-3-Clause)
   └─ scikit-learn (BSD-3-Clause)
```

---

## License Compliance

### Project License: AGPL-3.0

This project is licensed under **GNU Affero General Public License v3.0 (AGPL-3.0)** due to the use of:

1. **PolicyEngine-US** (AGPL-3.0) - Primary reason
2. **OpenBB Platform** (AGPL-3.0) - Used via API

### What AGPL-3.0 Means for You

#### ✅ You CAN:
- Use for personal portfolio management
- Use for commercial purposes
- Modify the code
- Distribute modified versions

#### ⚠️ You MUST:
- **Provide source code to users** if you deploy as a network service (web app, API)
- License derivative works under AGPL-3.0
- Include copyright and license notices
- Document changes you make

#### ❌ You CANNOT:
- Incorporate into proprietary software without open-sourcing it
- Remove license headers or copyright notices
- Sublicense under different terms

### Compliance Checklist

Before deploying:

- [ ] Read `/home/hvksh/investing/LICENSE` (full AGPL-3.0 text)
- [ ] Read `/home/hvksh/investing/NOTICE` (third-party attributions)
- [ ] Understand AGPL-3.0 network service requirements
- [ ] Prepared to provide source code to users
- [ ] Documented any modifications you've made

### Alternative Licensing Options

If AGPL-3.0 doesn't work for your use case:

**Option 1: Replace PolicyEngine-US**
- Use different tax calculation library (e.g., pure tenforty)
- This would allow GPL-3.0 (slightly less restrictive)
- Lose accuracy/features of PolicyEngine-US

**Option 2: Commercial License**
- Contact PolicyEngine for commercial licensing
- May require fees
- Allows proprietary use

**Option 3: Use as CLI Only**
- AGPL-3.0 only applies to network services
- Local CLI usage has fewer restrictions
- No obligation to share source if not deployed as service

### Why PolicyEngine-US?

Despite AGPL-3.0 restrictions, we chose PolicyEngine-US because:

1. **Accuracy:** Government-maintained parameter system
2. **Coverage:** 2018-2025 tax years, all states
3. **Features:** NIIT, AMT, trust/estate calculations
4. **Maintenance:** Actively updated for tax law changes
5. **Reliability:** Used by PolicyEngine.org for policy analysis

---

## Troubleshooting

### Common Installation Issues

#### Issue: "ModuleNotFoundError: No module named 'fastmcp'"

**Solution:**
```bash
# Ensure virtual environment is activated
source openbb/bin/activate

# Reinstall requirements
pip install -r requirements.txt
```

#### Issue: "ImportError: No module named 'shared.confidence_scoring'"

**Solution:**
```bash
# Check PYTHONPATH in .mcp.json
# Should include both:
# - /home/hvksh/investing
# - /home/hvksh/investing/shared

# Verify shared directory exists
ls -la shared/
```

#### Issue: "PolicyEngine calculation failed"

**Solution:**
```bash
# Verify PolicyEngine installed correctly
python -c "from policyengine_us import Simulation; print('OK')"

# Check version
pip show policyengine-us

# Reinstall if needed
pip install --upgrade policyengine-us>=1.424.0
```

#### Issue: "API key not found"

**Solution:**
```bash
# Verify .env file exists
cat .env | grep API_KEY

# Check .mcp.json has API keys
cat ~/.claude/mcp_servers.json | grep API_KEY

# Ensure API keys are valid (no placeholder text)
```

#### Issue: "Permission denied: /home/hvksh/investing"

**Solution:**
```bash
# Fix ownership
sudo chown -R $USER:$USER ~/investing

# Fix permissions
chmod -R u+rwX ~/investing
```

### Getting Help

**Check validation report:**
```bash
cat /home/hvksh/investing/MCP_VALIDATION_REPORT.md
```

**Review logs:**
```bash
# MCP servers log to stderr
# Check Claude Code logs for server errors
```

**Test individual server:**
```bash
# Test portfolio state server
source openbb/bin/activate
export PYTHONPATH="/home/hvksh/investing:/home/hvksh/investing/shared"
python portfolio-state-mcp-server/portfolio_state_server.py
# Should start without errors
```

---

## Verification

### Step 7: Verify MCP Server Configuration

```bash
# Check MCP configuration is valid JSON
python -c "import json; json.load(open('.mcp.json')); print('✓ Valid JSON')"

# Count configured servers
python -c "import json; data = json.load(open('.mcp.json')); print(f'Servers: {len(data[\"mcpServers\"])}')"
# Should output: Servers: 7
```

### Step 8: Test Server Startup

```bash
# Test each server starts without import errors
source openbb/bin/activate
export PYTHONPATH="$PWD:$PWD/shared"

# Portfolio State Server
python portfolio-state-mcp-server/portfolio_state_server.py &
PID=$!
sleep 2
kill $PID
echo "✓ Portfolio State Server OK"

# Repeat for other servers...
```

### Step 9: Test in Claude Code

1. Open Claude Code
2. Ensure you're in the `/home/hvksh/investing` directory
3. Try a simple query:

```
Use the portfolio state server to show me the schema for portfolio state
```

Expected: Claude should use `mcp__portfolio-state-server__get_portfolio_state` and return schema.

### Step 10: Import Sample Portfolio

```bash
# Create sample portfolio CSV
cat > portfolio/sample.csv << 'EOF'
Symbol,Shares,Cost Basis,Date Acquired
SPY,100,45000,2024-01-15
AGG,200,20000,2024-01-15
EOF

# In Claude Code:
# "Import the portfolio from portfolio/sample.csv using Vanguard format"
```

---

## Next Steps

After successful installation:

1. **Import Your Portfolio**
   ```
   /import-portfolio
   ```

2. **Run Daily Check**
   ```
   /daily-check
   ```

3. **Review Documentation**
   - Read `/home/hvksh/investing/CLAUDE.md` for orchestrator instructions
   - Read `/home/hvksh/investing/TOOLS_GUIDE.md` for MCP tool reference
   - Read `/home/hvksh/investing/README.md` for system overview

4. **Customize Configuration**
   - Adjust risk limits in CLAUDE.md
   - Configure additional API keys
   - Set up portfolio allocation targets

---

## Maintenance

### Updating Dependencies

```bash
# Activate virtual environment
source openbb/bin/activate

# Update specific package
pip install --upgrade policyengine-us

# Update all packages (use with caution)
pip install --upgrade -r requirements.txt

# Verify versions
pip list | grep -E "policyengine|fastmcp|pypor"
```

### Monitoring for Updates

**PolicyEngine-US:** Updates frequently for tax law changes
- Check: https://github.com/PolicyEngine/policyengine-us/releases
- Recommended: Update quarterly

**OpenBB Platform:** Major updates quarterly
- Check: https://github.com/OpenBB-finance/OpenBB/releases
- Test in development before upgrading

**Risk:** Breaking changes in optimization libraries
- Pin versions in production: `policyengine-us==1.424.4`

---

## Summary

You should now have:

✅ Virtual environment with all dependencies
✅ 7 MCP servers configured in `~/.claude/mcp_servers.json`
✅ API keys configured in `.env`
✅ Shared modules accessible via PYTHONPATH
✅ License compliance understanding
✅ Working portfolio management system

**Installation Time:** ~30 minutes total
**Disk Space Used:** ~1.5GB

**Ready to use!** Start with `/import-portfolio` in Claude Code.

---

**For Questions:**
- Review: `/home/hvksh/investing/MCP_VALIDATION_REPORT.md`
- Issues: https://github.com/hvkshetry/agentic-investment-management/issues
- Documentation: All `.md` files in repository root

**License:** AGPL-3.0 - See LICENSE file for details
