# AGENTS.md — Tool Usage Guide (Narrative Output)

A single source of truth for using MCP tools in this repo. Focus on:
- Correct tool names and native parameter types
- Provider‑specific quirks and robust calling patterns
- Clear, professor‑style narrative explanations in outputs (no JSON artifacts)

Use role templates in `agent-prompts/` for tone and structure; use this guide for tool usage correctness and to avoid trial‑and‑error.

---

## Output Style (Required)

- Write results as a narrative explanation, like a professor teaching a student.
- Do not emit JSON artifacts or envelopes. Summarize what each tool returned in prose and cite the tool name and provider inline when helpful.
- If something is missing or a tool errors, say so plainly and either retry with corrected params or explain what’s needed. Do not fabricate data.

---

## Tool Catalog (Exact Names)

Portfolio State Server (`portfolio-state-mcp-server`)
- `mcp__portfolio-state-server__get_portfolio_state`
- `mcp__portfolio-state-server__import_broker_csv`
- `mcp__portfolio-state-server__update_market_prices`
- `mcp__portfolio-state-server__simulate_sale`
- `mcp__portfolio-state-server__get_tax_loss_harvesting_opportunities`
- `mcp__portfolio-state-server__record_transaction`

Portfolio Optimization Server (`portfolio-mcp-server`)
- `mcp__portfolio-optimization-server__optimize_portfolio_advanced`

Risk Server (`risk-mcp-server`)
- `mcp__risk-server__analyze_portfolio_risk` (includes stress tests)
- `mcp__risk-server__get_risk_free_rate`

Tax Optimization Server (`tax-optimization-mcp-server`)
- `mcp__tax-optimization-server__find_tax_loss_harvesting_pairs`
- `mcp__tax-optimization-server__simulate_withdrawal_tax_impact`

Tax Server (`tax-mcp-server`)
- `mcp__tax-server__calculate_comprehensive_tax` (if enabled)

OpenBB Curated (market/macro/content)
- Pattern: `mcp__openbb-curated__<endpoint>`
- Common endpoints: `equity_profile`, `equity_price_performance`, `equity_price_historical`, `equity_fundamental_*`, `derivatives_options_chains`, `derivatives_futures_curve`, `fixedincome_government_treasury_rates`, `fixedincome_spreads_tcm`, `fixedincome_spreads_treasury_effr`, `fixedincome_government_yield_curve`, `economy_cpi`, `economy_unemployment`, `economy_interest_rates`, `commodity_price_spot`, `currency_price_historical`, `index_price_historical`, `news_company`.

Policy Events Service (bills, rules, hearings)
- Pattern: `mcp__policy-events-service__<endpoint>`
- Common endpoints: `get_recent_bills`, `get_bill_details`, `get_federal_rules`, `get_rule_details`, `get_upcoming_hearings`, `get_hearing_details`.

Do not use non‑existent tools (e.g., `mcp__risk-server__stress_test_portfolio`). Stress tests are included in `analyze_portfolio_risk`.

---

## Usage Principles (Native Types, Clean Calls)

- Always pass native types (lists, dicts, numbers). Example: `tickers=["SPY","AGG"], weights=[0.6,0.4]`.
- Numbers must be numbers (`limit=50`, not `"50"`).
- Dates are `YYYY-MM-DD`. Omit when the endpoint returns the latest by default.
- Ensure portfolio weights sum to 1.0 for risk/optimization calls; use the actual portfolio value from `get_portfolio_state`.
- When a call fails, read the error and fix params (provider names, required fields) rather than retrying blindly.

---

## Provider Notes and Gotchas (Save Time)

- Treasury rates: use `provider="federal_reserve"` for `fixedincome_government_treasury_rates` (not `fred`).
- Spreads and yield‑curve series often use `provider="fred"` (e.g., `fixedincome_spreads_tcm`, `fixedincome_spreads_treasury_effr`).
- CPI:
  - `provider="fred"` works without a `country` parameter; specify `transform="yoy"`, `frequency="monthly"`.
  - OECD endpoints (`economy_unemployment`, etc.) accept `country` like `USA`; set `seasonal_adjustment=True` where appropriate.
- News: If `provider="benzinga"` complains about paging/limits, switch to `provider="yfinance"` for broad ETF/company news.
- Yield curve: `fixedincome_government_yield_curve` requires `provider` (e.g., `fred`) and often a `yield_curve_type` (e.g., `"nominal"`).
- Options/futures: `derivatives_*` endpoints may need `date` or `delay/model`—check parameter docs and keep to native types.

---

## Quick Recipes (Narrative‑First)

- Portfolio snapshot → Risk:
  1) Call `get_portfolio_state`; summarize tickers/weights and total value in prose.
  2) Call `analyze_portfolio_risk` with those tickers/weights; explain VaR/ES and stress highlights in words.

- Optimization under ES focus:
  - Call `optimize_portfolio_advanced` with `risk_measure="CVaR"`, `confidence_level=0.975`. Explain the trade‑offs the optimizer chose and any constraints you set.

- Tax loss harvesting:
  - Start with `get_tax_loss_harvesting_opportunities` (min loss, exclude wash‑sale days). Optionally add pairs via `find_tax_loss_harvesting_pairs`. Describe candidate swaps and wash‑sale considerations narratively.

- Macro context for rates:
  - Use `economy_cpi` (fred, YoY), `economy_unemployment` (oecd, SA), `fixedincome_*` (treasury rates, tcm spread, effr spread), and optionally `news_company` for sentiment. Explain how these relate to easing/tightening probabilities.

- Sale simulation:
  - `simulate_sale(symbol, quantity, sale_price, cost_basis_method)` and interpret realized gains lots in plain language.

---

## Pitfalls to Avoid

- Passing JSON strings instead of native lists/dicts.
- Using the wrong provider alias (`federal_reserve` vs `fred`) or missing required params.
- Hardcoding portfolio value or using weights that don’t sum to 1.0.
- Reporting metrics that tools did not return.

---

## Where to Look for Structure and Tone

- Use `agent-prompts/` for role‑specific structure (e.g., risk analyst, portfolio manager). Keep outputs narrative and teach‑forward; weave tool results into the explanation rather than dumping raw payloads.
