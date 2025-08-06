# MCP Server Architecture Guide

## Overview

The new architecture uses **MCP server-to-server communication** to follow DRY principles and centralize API key management. The OpenBB MCP server (which has API keys configured) acts as the authenticated data provider for all financial servers.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   External APIs                          │
│  (FRED, Yahoo Finance, Alpha Vantage, Bloomberg, etc.)  │
└────────────────────┬────────────────────────────────────┘
                     │ Authenticated Requests
                     │ (API Keys Configured)
                     ▼
          ┌──────────────────────┐
          │  OpenBB MCP Server   │
          │  (Curated, with      │
          │   API keys)          │
          └──────────┬───────────┘
                     │ MCP Protocol
     ┌───────────────┼───────────────┬──────────────┐
     ▼               ▼               ▼              ▼
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Risk   │    │Portfolio│    │   Tax   │    │  Fixed  │
│  MCP    │    │   MCP   │    │   MCP   │    │ Income  │
│ Server  │    │ Server  │    │ Server  │    │   MCP   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
     │               │               │              │
     └───────────────┴───────────────┴──────────────┘
                          │
                     ┌─────────┐
                     │  Client │
                     │   App   │
                     └─────────┘
```

## Benefits

### 1. **DRY Principle** ✅
- API keys configured in ONE place (OpenBB server)
- No duplication of authentication logic
- Single source of truth for market data access

### 2. **Better Security** 🔒
- API keys never exposed to individual servers
- Centralized key rotation
- Audit trail for all data access

### 3. **Improved Reliability** 📈
- OpenBB server handles rate limiting
- Built-in caching at data source
- Automatic failover between data providers

### 4. **Easier Testing** 🧪
- Mock the MCP client for unit tests
- No need for test API keys in each server
- Consistent test data across all servers

## Implementation

### Step 1: Configure OpenBB MCP Server

Ensure your OpenBB MCP server has API keys configured:

```bash
# Set environment variables for OpenBB server
export OPENBB_FRED_API_KEY="your-fred-key"
export OPENBB_ALPHA_VANTAGE_API_KEY="your-av-key"
export OPENBB_POLYGON_API_KEY="your-polygon-key"

# Start OpenBB MCP server
mcp start openbb
```

### Step 2: Update Financial Servers

Each financial server now uses the MCP client instead of direct API calls:

#### Before (Direct OpenBB):
```python
# data_pipeline.py
from openbb import obb
self.obb = obb
yield_curve = self.obb.fixedincome.government.yield_curve()  # Needs API key
```

#### After (MCP Client):
```python
# data_pipeline_mcp.py
from shared.openbb_mcp_client import OpenBBMCPClient
self.mcp_client = OpenBBMCPClient(server_name="openbb")
rate_data = self.mcp_client.get_treasury_rate("10y")  # Uses OpenBB server's keys
```

### Step 3: Configure MCP Connections

In your MCP configuration file (`.mcp/config.json` or equivalent):

```json
{
  "servers": {
    "openbb": {
      "command": "uvx",
      "args": ["--from", "openbb-mcp", "openbb-mcp"],
      "env": {
        "OPENBB_FRED_API_KEY": "${OPENBB_FRED_API_KEY}",
        "OPENBB_ALPHA_VANTAGE_API_KEY": "${OPENBB_ALPHA_VANTAGE_API_KEY}"
      }
    },
    "risk": {
      "command": "python",
      "args": ["risk-mcp-server/risk_mcp_server_v3.py"],
      "env": {
        "OPENBB_MCP_SERVER": "openbb"
      }
    },
    "portfolio": {
      "command": "python",
      "args": ["portfolio-mcp-server/portfolio_mcp_server_v3.py"],
      "env": {
        "OPENBB_MCP_SERVER": "openbb"
      }
    }
  }
}
```

## Usage Examples

### 1. Risk Server Getting Treasury Rates

```python
# In risk_mcp_server_v3.py
from shared.data_pipeline_mcp import MarketDataPipeline

pipeline = MarketDataPipeline()  # Uses MCP client internally
rf_rate = pipeline.get_risk_free_rate("10y")  # Fetches via OpenBB MCP server
```

### 2. Portfolio Server Getting Market Data

```python
# In portfolio_mcp_server_v3.py
pipeline = MarketDataPipeline()
data = pipeline.fetch_equity_data(
    ["AAPL", "MSFT", "GOOGL"],
    start_date="2024-01-01"
)  # All fetched via authenticated OpenBB server
```

### 3. Client Application

The client only sees the financial servers, not the OpenBB server:

```python
# Client code
risk_result = await mcp_client.call_tool(
    server="risk",
    tool="analyze_portfolio_risk",
    args={"tickers": ["AAPL", "MSFT"]}
)
# Risk server internally uses OpenBB MCP server for data
```

## Testing with MCP Architecture

### Unit Tests
```python
# test_with_mcp_mock.py
from unittest.mock import Mock, patch

@patch('shared.openbb_mcp_client.OpenBBMCPClient')
def test_risk_calculation(mock_client):
    # Mock the MCP client responses
    mock_client.return_value.get_treasury_rate.return_value = {
        'rate': 0.045,
        'source': 'mock',
        'confidence': 1.0
    }
    
    # Test runs without needing real API keys
    result = risk_server.calculate_var(...)
    assert result['var_95'] < 0
```

### Integration Tests
```python
# test_integration.py
import pytest
import os

@pytest.mark.skipif(
    not os.getenv('OPENBB_MCP_SERVER_RUNNING'),
    reason="OpenBB MCP server not running"
)
def test_full_pipeline():
    # This test requires OpenBB MCP server to be running
    pipeline = MarketDataPipeline()
    rf_rate = pipeline.get_risk_free_rate("10y")
    assert 0 < rf_rate['rate'] < 0.20
```

## Migration Path

### Phase 1: Parallel Operation
1. Keep existing direct OpenBB code
2. Add MCP client as alternative
3. Use feature flag to switch between them

### Phase 2: Testing
1. Run tests with both methods
2. Verify MCP results match direct calls
3. Measure performance impact

### Phase 3: Full Migration
1. Switch all servers to MCP client
2. Remove direct OpenBB dependencies
3. Update documentation

## Troubleshooting

### Issue: "Unable to connect to OpenBB MCP server"
**Solution**: Ensure OpenBB MCP server is running:
```bash
mcp status openbb  # Check status
mcp start openbb   # Start if needed
```

### Issue: "Authentication failed"
**Solution**: Verify API keys in OpenBB server:
```bash
echo $OPENBB_FRED_API_KEY  # Should show your key
```

### Issue: "Timeout calling MCP tool"
**Solution**: Check network connectivity and increase timeout:
```python
client = OpenBBMCPClient(timeout=60)  # 60 second timeout
```

## Performance Considerations

### Caching
- OpenBB server caches responses (configurable TTL)
- Financial servers have secondary cache
- Reduces API calls and improves response time

### Latency
- MCP adds ~5-10ms overhead per call
- Negligible compared to external API latency (100-500ms)
- Can be optimized with connection pooling

### Scalability
- OpenBB server can handle multiple concurrent clients
- Consider load balancing for high-volume production
- Monitor API rate limits at OpenBB server level

## Security Best Practices

1. **Never commit API keys** - Use environment variables
2. **Rotate keys regularly** - Update only in OpenBB server
3. **Use secure MCP transport** - Enable TLS for production
4. **Audit access logs** - Monitor OpenBB server logs
5. **Implement rate limiting** - Prevent abuse at server level

## Conclusion

The MCP architecture provides a clean, maintainable, and secure way to manage market data access across multiple financial servers. By centralizing API authentication in the OpenBB MCP server, we achieve:

- ✅ **DRY principle** - No duplicated API configuration
- ✅ **Explicit failures** - Maintains our no-silent-failures principle  
- ✅ **Better testing** - Easy to mock MCP calls
- ✅ **Production ready** - Secure, scalable architecture

This architecture is recommended for production deployments where multiple services need authenticated market data access.