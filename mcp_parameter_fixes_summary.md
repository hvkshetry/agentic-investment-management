# MCP Parameter Type Fixes Summary

## Issue Identified
FastMCP's schema validation fails when parameters are typed as `Optional[List[...]]` or `Optional[Dict[...]]` because it generates union schemas that the MCP validator cannot handle properly.

## Root Cause
When a parameter is defined as `Optional[List[float]]`, FastMCP generates a JSON schema with a union type (oneOf/anyOf) that includes both the list schema and null. The MCP validation layer rejects values with the error: "'[...]' is not valid under any of the given schemas"

## Solution Applied
Remove the `Optional` wrapper from all complex type parameters (List, Dict) and use empty defaults instead:

### Changes Made

#### 1. Risk MCP Server (risk_mcp_server_v3.py)
- Changed: `weights: Optional[List[float]] = None` 
- To: `weights: List[float]` (REQUIRED parameter)
- Changed: `analysis_options: Optional[Dict[str, Any]] = None`
- To: `analysis_options: Dict[str, Any] = {}`

#### 2. Portfolio MCP Server (portfolio_mcp_server_v3.py)
- Changed: `optimization_config: Optional[Dict[str, Any]] = None`
- To: `optimization_config: Dict[str, Any] = {}`

#### 3. Tax MCP Server (tax_mcp_server_v2.py)
- Changed: `state: Optional[str] = None`
- To: `state: str = ""`
- Changed: `income_sources: Optional[Dict[str, float]] = None`
- To: `income_sources: Dict[str, float] = {}`
- Changed: `deductions: Optional[Dict[str, float]] = None`
- To: `deductions: Dict[str, float] = {}`
- Changed: `credits: Optional[Dict[str, float]] = None`
- To: `credits: Dict[str, float] = {}`
- Changed: `trust_details: Optional[Dict[str, Any]] = None`
- To: `trust_details: Dict[str, Any] = {}`

#### 4. Tax Optimization Server (tax_optimization_server.py)
- Changed: `target_allocations: Optional[Dict[str, float]] = None`
- To: `target_allocations: Dict[str, float] = {}`
- Changed: `optimization_settings: Optional[Dict[str, Any]] = None`
- To: `optimization_settings: Dict[str, Any] = {}`

## OpenBB MCP Server
The OpenBB MCP server is a third-party package that dynamically generates tools from OpenAPI specifications. Any Optional[List] or Optional[Dict] parameter issues would be in the OpenAPI schema definitions themselves, which are not modifiable in our codebase.

## Key Learnings

1. **MCP validators struggle with union types** - Avoid Optional[List] and Optional[Dict]
2. **Use empty defaults** - Instead of None, use {} for dicts and [] for lists (or make required)
3. **Required parameters work better** - For critical parameters like weights, make them required
4. **Agents pass correct types** - The agents were passing native Python types correctly; the issue was schema validation

## Testing Recommendation
Test each MCP server with the updated parameter definitions to ensure:
1. Empty dicts/lists are accepted as defaults
2. Native Python types are passed through correctly
3. No JSON string conversion is needed by agents