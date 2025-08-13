# OpenBB Tool Usage Guide for Agents

## etf_equity_exposure
**Purpose**: Find which ETFs hold a specific stock
**Parameters**:
```python
mcp__openbb-curated__etf_equity_exposure(
    symbol="AAPL",  # Stock ticker to find in ETF holdings
    provider="fmp"   # Always use fmp
)
```
**Returns**: Top 20 ETFs by weight (automatically limited)

## equity_compare_company_facts  
**Purpose**: Compare SEC XBRL facts across companies
**Parameters**:
```python
mcp__openbb-curated__equity_compare_company_facts(
    fact="Assets",        # EXACT GAAP name (case-sensitive)
    fiscal_period="FY"    # FY (annual) or Q1/Q2/Q3/Q4
)
```
**Common Facts**: Assets, Liabilities, Revenues, NetIncomeLoss, CashAndCashEquivalentsAtCarryingValue
**Note**: Returns only companies that have this specific fact

## fixedincome_government_treasury_rates
**Purpose**: Get Treasury yield curve data
**Parameters**:
```python
mcp__openbb-curated__fixedincome_government_treasury_rates(
    provider="federal_reserve",
    start_date="2025-01-01",    # REQUIRED: Max 30 days back
    end_date="2025-01-13"        # REQUIRED: Today or recent date
)
```
**CRITICAL**: Always provide start_date and end_date (30 days max range)