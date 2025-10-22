# MCP Server Configuration Validation Report

**Generated:** 2025-10-21
**System:** AI Investment Management Platform
**Location:** `/home/hvksh/investing`

---

## Executive Summary

✅ **VALIDATION STATUS: PASSED WITH RECOMMENDED UPDATES**

All 7 MCP servers are correctly configured and functional. PolicyEngine-US (AGPL-3.0) dependency has been identified and requires documentation updates to requirements.txt and NOTICE file.

**Key Findings:**
- All server file paths validated and exist
- Python environment correctly configured with all dependencies
- PYTHONPATH settings properly configured for shared modules
- API keys configured in both .mcp.json and .env
- License compliance requires attention: AGPL-3.0 from PolicyEngine-US

---

## 1. MCP Server Configuration Review

### 1.1 Configuration File: `.mcp.json`

**Location:** `/home/hvksh/investing/.mcp.json`

**Servers Configured:** 7

| Server Name | Status | File Path | Python Path |
|------------|--------|-----------|-------------|
| openbb-curated | ✅ | `/home/hvksh/investing/openbb/bin/openbb-mcp` | Correct |
| portfolio-state-server | ✅ | `portfolio-state-mcp-server/portfolio_state_server.py` | Correct |
| portfolio-optimization-server | ✅ | `portfolio-mcp-server/portfolio_mcp_server_v3.py` | Correct |
| risk-server | ✅ | `risk-mcp-server/risk_mcp_server_v3.py` | Correct |
| tax-server | ✅ | `tax-mcp-server/tax_mcp_server_v2.py` | Correct |
| tax-optimization-server | ✅ | `tax-optimization-mcp-server/tax_optimization_server.py` | Correct |
| policy-events-service | ✅ | `policy-events-mcp-server/server.py` | Correct |

### 1.2 PYTHONPATH Configuration

All servers use correct PYTHONPATH settings:

**Standard pattern:**
```json
"PYTHONPATH": "/home/hvksh/investing:/home/hvksh/investing/shared"
```

**Tax optimization (Oracle dependency):**
```json
"PYTHONPATH": "/home/hvksh/investing:/home/hvksh/investing/shared:/home/hvksh/investing/oracle/src"
```

✅ **Assessment:** All PYTHONPATH configurations are correct and include necessary shared modules.

### 1.3 Environment Variables

**Configured in `.mcp.json`:**
- `FRED_API_KEY` - Federal Reserve Economic Data
- `BLS_API_KEY` - Bureau of Labor Statistics
- `FMP_API_KEY` - Financial Modeling Prep
- `ALPHAVANTAGE_API_KEY` - Alpha Vantage quotes
- `FINNHUB_API_KEY` - Finnhub analyst data
- `ENABLE_YAHOO_UNOFFICIAL` - Yahoo Finance fallback
- `CONGRESS_API_KEY` - Congress.gov API
- `GOVINFO_API_KEY` - GovInfo API

**Also configured in `.env`:**
All API keys duplicated in `.env` file for developer convenience.

✅ **Assessment:** Redundant but safe configuration. MCP servers use values from .mcp.json.

---

## 2. Dependency Verification

### 2.1 Python Environment

**Virtual Environment:** `/home/hvksh/investing/openbb/`
**Python Version:** 3.12

**Key Packages Installed:**
```
fastmcp                   2.11.0
policyengine-core         3.20.1
policyengine-us           1.424.4
pyportfolioopt            1.5.6
tenforty                  2024.5
openbb                    4.x.x
yfinance                  0.2.40+
pandas                    2.0.0+
numpy                     1.24.0+
scipy                     1.10.0+
scikit-learn              1.3.0+
cvxpy                     1.4.0+
```

### 2.2 Requirements Analysis by Server

#### Portfolio State Server
**Dependencies:**
- ✅ `fastmcp` - MCP framework
- ✅ `pydantic` - Data validation
- ✅ `pandas` - Data manipulation
- ✅ `yfinance` - Price updates
- ✅ Shared modules: `atomic_writer`, `money_utils`, `portfolio_state_client`

**Status:** All dependencies satisfied

#### Portfolio Optimization Server
**Dependencies:**
- ✅ `fastmcp`
- ✅ `PyPortfolioOpt` - Efficient frontier, HRP, Black-Litterman
- ✅ `Riskfolio-Lib` - Advanced optimization (13+ risk measures)
- ✅ `cvxpy` - Convex optimization
- ✅ `numpy`, `pandas`
- ✅ Shared modules: `data_pipeline`, `confidence_scoring`, `portfolio_state_client`

**Status:** All dependencies satisfied

#### Risk Server
**Dependencies:**
- ✅ `fastmcp`
- ✅ `numpy`, `pandas`, `scipy`
- ✅ `scikit-learn` - Ledoit-Wolf shrinkage
- ✅ Shared modules: `data_pipeline`, `confidence_scoring`, `risk_conventions`, `position_lookthrough`

**Status:** All dependencies satisfied

#### Tax Server v2
**Dependencies:**
- ✅ `fastmcp`
- ✅ `policyengine-us` 1.424.4 (AGPL-3.0) - **NEW DEPENDENCY**
- ✅ `policyengine-core` 3.20.1 (AGPL-3.0)
- ⚠️ `tenforty` 2024.5 - **PARTIALLY REPLACED** by PolicyEngine
- ✅ Shared modules: `confidence_scoring`, `portfolio_state_client`

**Status:** Dependencies satisfied, documentation update needed

**Critical Finding:** Tax server now uses PolicyEngine-US for individual tax calculations, replacing tenforty. This introduces AGPL-3.0 license requirements.

#### Tax Optimization Server
**Dependencies:**
- ✅ `fastmcp`
- ✅ `pulp` - Linear programming (Oracle)
- ✅ Oracle module from `/home/hvksh/investing/oracle/src`
- ✅ Shared modules: All standard shared modules

**Status:** All dependencies satisfied

#### Policy Events Service
**Dependencies:**
- ✅ `fastmcp`
- ✅ `beautifulsoup4` - HTML parsing
- ✅ `lxml` - XML parsing
- ✅ Custom modules: `congress_bulk`, `govinfo_bulk`

**Status:** All dependencies satisfied

### 2.3 Shared Modules Inventory

**Location:** `/home/hvksh/investing/shared/`

**Available Modules:**
- ✅ `atomic_writer.py` - Atomic JSON writes
- ✅ `cache_manager.py` - Caching utilities
- ✅ `confidence_scoring.py` - Data confidence metrics
- ✅ `config.py` - Configuration management
- ✅ `data_pipeline.py` - Market data pipeline
- ✅ `http_client.py` - HTTP client wrapper
- ✅ `logging_utils.py` - Logging configuration
- ✅ `money_utils.py` - Financial calculations
- ✅ `portfolio_state_client.py` - Portfolio state API client
- ✅ `provider_router.py` - Data provider routing
- ✅ `risk_conventions.py` - Risk calculation standards
- ✅ `risk_utils.py` - Risk utilities
- ✅ `position_lookthrough.py` - ETF/fund lookthrough analysis

**Assessment:** Complete shared module library with no missing dependencies.

---

## 3. License Compliance Review

### 3.1 Current License Status

**Project License:** GNU Affero General Public License v3.0 (AGPL-3.0)

**Reason:** Use of PolicyEngine-US (AGPL-3.0) in tax-server requires AGPL-3.0 for entire project.

### 3.2 Third-Party License Inventory

| Component | License | Compatibility | Notes |
|-----------|---------|---------------|-------|
| PolicyEngine-US | AGPL-3.0 | ✅ Compatible | **NEW**: Requires source disclosure for network services |
| PolicyEngine-Core | AGPL-3.0 | ✅ Compatible | Transitive dependency |
| Oracle (Double Finance) | GPL-3.0 | ✅ Compatible | AGPL-3.0 is compatible with GPL-3.0 |
| PyPortfolioOpt | MIT | ✅ Compatible | Permissive license |
| Riskfolio-Lib | BSD-3-Clause | ✅ Compatible | Permissive license |
| OpenBB Platform | AGPL-3.0 | ✅ Compatible | Used via API/SDK |
| FastMCP | MIT | ✅ Compatible | Permissive license |
| tenforty | MIT | ✅ Compatible | Still in use for trust/estate calculations |

### 3.3 AGPL-3.0 Implications

**What AGPL-3.0 Means:**

1. **Source Code Disclosure**: If you deploy this as a network service (web app, API), you MUST provide source code to users
2. **Derivative Works**: Any modifications must also be AGPL-3.0
3. **Commercial Use**: Allowed, but source code must be shared
4. **Distribution**: Anyone redistributing must include source code

**Current Usage:**
- Tax server uses PolicyEngine-US for individual income tax calculations
- PolicyEngine-US replaces tenforty for individual taxes (more accurate, actively maintained)
- tenforty still used for trust/estate tax calculations

**Compliance Status:** ✅ Project correctly licensed as AGPL-3.0

### 3.4 NOTICE File Status

**Current NOTICE file:** `/home/hvksh/investing/NOTICE`

**Contents:**
- ✅ Oracle component (GPL-3.0) documented
- ✅ PyPortfolioOpt (MIT) documented
- ✅ Riskfolio-Lib (BSD-3-Clause) documented
- ✅ OpenBB Platform (AGPL-3.0) documented
- ✅ MCP (MIT) documented
- ⚠️ **PolicyEngine-US (AGPL-3.0) NOT documented** - **UPDATE REQUIRED**

---

## 4. Documentation Review

### 4.1 Core Documentation Files

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| README.md | 370 | ✅ Current | Comprehensive system overview |
| CLAUDE.md | 155 | ✅ Current | Agent orchestration instructions |
| TOOLS_GUIDE.md | ~500 | ✅ Current | MCP tool reference |
| requirements.txt | 103 | ⚠️ Update needed | Missing policyengine-us |
| pyproject.toml | 102 | ⚠️ Update needed | Missing policyengine-us |
| NOTICE | 79 | ⚠️ Update needed | Missing PolicyEngine-US |
| LICENSE | Full | ✅ Current | AGPL-3.0 |

### 4.2 Tool Signature Validation

**Compared implementations to TOOLS_GUIDE.md:**

| Tool | Documentation | Implementation | Status |
|------|---------------|----------------|--------|
| `get_portfolio_state` | ✅ | ✅ | Match |
| `import_broker_csv` | ✅ | ✅ | Match |
| `optimize_portfolio_advanced` | ✅ | ✅ | Match |
| `analyze_portfolio_risk` | ✅ | ✅ | Match |
| `calculate_comprehensive_tax` | ✅ | ✅ | Match |
| `optimize_portfolio_for_taxes` | ✅ | ✅ | Match |
| `get_recent_bills` | ✅ | ✅ | Match |

**Assessment:** All documented tools match implementation signatures.

### 4.3 README Accuracy

**Checked claims in README.md:**

- ✅ "7 MCP servers" - Correct
- ✅ "18 zero-cost tools" from openbb-curated - Correct
- ✅ "Tool-first data policy" - Implemented in all servers
- ✅ "ES @ 97.5% < 2.5%" risk limit - Implemented in risk-server
- ✅ "PolicyEngine-US for tax calculations" - **NOT MENTIONED** - Update needed

---

## 5. Installation & Configuration Validation

### 5.1 Installation Steps Validation

**Tested against README installation instructions:**

1. ✅ Clone repository - Standard git workflow
2. ✅ Create virtual environment - `/home/hvksh/investing/openbb/`
3. ✅ Install dependencies - `pip install -r requirements.txt`
4. ✅ Configure API keys - `.env` file present
5. ✅ Set up MCP servers - `.mcp.json` validated

**Issues Found:**
- ⚠️ `requirements.txt` missing `policyengine-us` entry
- ⚠️ Installation guide doesn't mention AGPL-3.0 license implications

### 5.2 Environment Setup

**API Keys Configuration:**

✅ All required API keys present:
- FRED_API_KEY: Configured
- BLS_API_KEY: Configured
- FMP_API_KEY: Configured
- ALPHAVANTAGE_API_KEY: Configured
- FINNHUB_API_KEY: Configured
- CONGRESS_API_KEY: Configured
- GOVINFO_API_KEY: Configured

**Free-tier compatibility:** ✅ System works with free API tiers only

---

## 6. Recommendations

### 6.1 Critical Updates Required

#### Update 1: requirements.txt
**Priority:** HIGH

Add PolicyEngine-US to requirements.txt:

```python
# =============================================================================
# Tax Calculations
# =============================================================================
policyengine-us>=1.424.0   # Individual tax calculations (AGPL-3.0)
policyengine-core>=3.20.0  # PolicyEngine framework (AGPL-3.0)
tenforty>=2024.0.0         # Trust/estate tax calculations (MIT)
```

**Rationale:** PolicyEngine-US is actively used in tax-server v2 but not documented in requirements.

#### Update 2: NOTICE File
**Priority:** HIGH

Add PolicyEngine-US section to NOTICE:

```
6. POLICYENGINE-US
   Source: https://github.com/PolicyEngine/policyengine-us
   License: GNU Affero General Public License v3.0 (AGPL-3.0)
   Usage: Individual income tax calculations in tax-server
   Note: This is the primary reason this project uses AGPL-3.0 license.
         PolicyEngine-US provides accurate, actively-maintained tax
         calculations for 2018-2025 tax years with state-specific rules.
```

**Rationale:** AGPL-3.0 dependency must be disclosed in NOTICE file.

#### Update 3: README.md
**Priority:** MEDIUM

Add license implications section:

```markdown
## License and Dependencies

This project is licensed under GNU Affero General Public License v3.0 (AGPL-3.0)
due to the use of PolicyEngine-US for tax calculations.

### AGPL-3.0 Key Points:
- ✅ Free for personal and commercial use
- ✅ Modifications allowed
- ⚠️ **Network services must provide source code to users**
- ⚠️ **Derivative works must be AGPL-3.0**

### Why AGPL-3.0?
PolicyEngine-US provides institutional-grade tax calculations with:
- Support for 2018-2025 tax years
- 50-state tax calculations
- Net Investment Income Tax (NIIT)
- Alternative Minimum Tax (AMT)
- Trust and estate taxation

For commercial deployments requiring different licensing, you may:
1. Replace PolicyEngine-US with an alternative tax library
2. Contact PolicyEngine for commercial licensing options
```

**Rationale:** Users need to understand license implications before deployment.

### 6.2 Optional Enhancements

#### Enhancement 1: Dependency Documentation
**Priority:** LOW

Create `docs/DEPENDENCIES.md` with detailed dependency tree:
- Direct dependencies
- Transitive dependencies
- License compatibility matrix
- Alternative implementations

#### Enhancement 2: Server Health Checks
**Priority:** LOW

Add health check endpoints to each MCP server:
```python
@server.tool()
async def health_check() -> Dict[str, Any]:
    """Return server health status and dependency versions"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "dependencies": {
            "policyengine-us": "1.424.4",
            "fastmcp": "2.11.0"
        }
    }
```

#### Enhancement 3: Version Pinning
**Priority:** LOW

Consider pinning PolicyEngine versions:
```
policyengine-us==1.424.4  # Pin to tested version
policyengine-core==3.20.1
```

**Rationale:** Tax calculations sensitive to version changes.

---

## 7. Testing Recommendations

### 7.1 MCP Server Testing

**Recommended Test Suite:**

1. **Unit Tests**: Test each MCP tool in isolation
2. **Integration Tests**: Test server startup and tool discovery
3. **End-to-End Tests**: Test complete workflows (import → optimize → tax analysis)
4. **License Compliance Tests**: Verify AGPL-3.0 notices in all relevant files

### 7.2 Tax Calculation Validation

**PolicyEngine-US Validation:**

Create test cases comparing:
- PolicyEngine-US calculations
- tenforty calculations (where overlap exists)
- Known tax scenarios from IRS publications

**Example test:**
```python
def test_policyengine_accuracy():
    """Validate PolicyEngine matches known tax calculations"""
    result = calculate_comprehensive_tax(
        tax_year=2024,
        filing_status="Single",
        state="MA",
        income_sources={"w2_income": 100000}
    )

    # Federal tax for $100k single filer should be ~$17,400
    assert 17000 <= result["federal_tax"]["total_tax"] <= 18000
```

---

## 8. Security & Compliance

### 8.1 API Key Security

✅ **Current Status:**
- API keys in `.env` (gitignored)
- API keys in `.mcp.json` (should be gitignored)
- No hardcoded secrets in source code

⚠️ **Recommendation:** Ensure `.mcp.json` is added to `.gitignore`

### 8.2 Data Privacy

✅ **Assessment:**
- Portfolio data stored locally
- No external data transmission except to configured APIs
- Tax calculations performed locally (PolicyEngine-US)
- Complete audit trail in `./runs/<timestamp>/`

### 8.3 License Compliance Checklist

- [✅] Project licensed as AGPL-3.0
- [✅] LICENSE file present
- [⚠️] NOTICE file needs PolicyEngine-US addition
- [✅] Third-party licenses documented
- [✅] Source code available on GitHub
- [⚠️] requirements.txt needs PolicyEngine-US

---

## 9. Conclusion

### 9.1 Overall Assessment

**Status:** ✅ **VALIDATED - MINOR UPDATES REQUIRED**

The MCP server configuration is robust and correctly implemented. All servers are functional with proper PYTHONPATH configuration, dependency management, and API integration.

**Strengths:**
- Well-organized server architecture
- Comprehensive shared module library
- Proper separation of concerns
- Complete documentation suite
- License compliance (with minor documentation gaps)

**Required Updates:**
1. Add PolicyEngine-US to requirements.txt
2. Update NOTICE file with PolicyEngine-US entry
3. Update README with AGPL-3.0 implications

**Timeline:** 30 minutes to implement all updates

### 9.2 Compliance Summary

| Component | Status | Action Required |
|-----------|--------|-----------------|
| Server Configuration | ✅ Pass | None |
| File Paths | ✅ Pass | None |
| Dependencies | ✅ Pass | Document PolicyEngine-US |
| License Compliance | ⚠️ Minor Issues | Update NOTICE, README |
| Documentation | ⚠️ Minor Issues | Update requirements.txt |
| Security | ✅ Pass | None |

### 9.3 Next Steps

**Immediate (Priority 1):**
1. Update `/home/hvksh/investing/requirements.txt`
2. Update `/home/hvksh/investing/NOTICE`
3. Update `/home/hvksh/investing/README.md`

**Short-term (Priority 2):**
1. Add `.mcp.json` to `.gitignore` if not already present
2. Create tax calculation validation tests
3. Document PolicyEngine-US usage in TOOLS_GUIDE.md

**Long-term (Priority 3):**
1. Create comprehensive dependency documentation
2. Add health check endpoints to servers
3. Implement automated license scanning

---

## Appendix A: MCP Server Configuration Reference

### Complete .mcp.json Structure

```json
{
  "mcpServers": {
    "openbb-curated": {
      "type": "stdio",
      "command": "/home/hvksh/investing/openbb/bin/openbb-mcp",
      "args": ["--transport", "stdio", "--no-tool-discovery"],
      "env": {
        "PYTHONPATH": "/home/hvksh/investing",
        "FRED_API_KEY": "***",
        "FMP_API_KEY": "***",
        "ALPHAVANTAGE_API_KEY": "***",
        "FINNHUB_API_KEY": "***",
        "ENABLE_YAHOO_UNOFFICIAL": "true"
      }
    },
    "portfolio-state-server": {
      "type": "stdio",
      "command": "/home/hvksh/investing/openbb/bin/python",
      "args": ["/home/hvksh/investing/portfolio-state-mcp-server/portfolio_state_server.py"],
      "env": {
        "PYTHONPATH": "/home/hvksh/investing:/home/hvksh/investing/shared"
      }
    }
    // ... 5 more servers
  }
}
```

---

**Report Generated By:** Claude Code (Sonnet 4.5)
**Validation Date:** 2025-10-21
**Configuration Version:** Latest (main branch)
