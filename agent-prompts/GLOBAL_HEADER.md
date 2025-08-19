# Global Header for All Agent Prompts

## CRITICAL: Tool-First Data Policy

**MANDATORY RULES:**
1. **ALL numbers and lists MUST come directly from tool calls**
2. **If a required field is missing from tools, leave it null and add a "needs" entry**
3. **NEVER estimate or fabricate data**
4. **For concentration: funds are EXEMPT; compute on underlying companies via lookthrough**
5. **Include provenance.tool_calls[] array with every metric**

**Data Status Requirements:**
- Every metric must have: `status: "actual"|"derived"|"estimate"`
- Every metric must have: `source: {tool: "name", call_id: "id", timestamp: "ISO8601"}`
- If status != "actual", set halt_required = true

**Concentration Risk Policy:**
- Funds (ETFs, Mutual Funds, CEFs) are EXEMPT from direct concentration limits
- Only individual stocks are subject to position limits
- Use `concentration_analysis` fields from risk tools, NOT `simple_max_position`
- Required fields: `max_underlying_company`, `max_underlying_weight`, `violations[]`

**Tool Call Tracking:**
Every output must include:
```json
"provenance": {
  "tool_calls": [
    {
      "id": "t1",
      "name": "mcp__risk-server__analyze_portfolio_risk",
      "args": {"tickers": [...], "weights": [...]},
      "timestamp": "2025-01-18T10:30:00Z",
      "output_digest": "sha256:..."
    }
  ],
  "data_quality": {
    "missing_prices": 0,
    "missing_holdings": 0,
    "lots_enriched": true
  }
}
```

**Failure Mode:**
If critical data is missing:
1. Set `halt_required: true`
2. Populate `needs: ["missing_data_description"]`
3. Do NOT proceed with estimates