# Unified Data Service Design

## Executive Summary

Based on the analysis, we need a unified data service to eliminate the 220 redundant API calls currently made across our MCP servers. The OpenBB MCP server doesn't need refactoring as it's a wrapper service, but our other servers need to be consolidated.

## Current State Analysis

### API Call Redundancy
- **Portfolio State Server**: Fetches prices via yfinance (55 calls) - Has 5-minute cache
- **Tax Server**: Now uses Portfolio State API (FIXED) ✅
- **Portfolio Optimizer**: Uses data_pipeline → yfinance (55 calls)
- **Risk Server**: Uses data_pipeline → yfinance (55 calls)
- **OpenBB MCP**: Wrapper around OpenBB API (not redundant)

### Key Findings
1. OpenBB is primarily used for treasury rates, not equity prices
2. data_pipeline.py already has caching but each server instance has its own cache
3. Portfolio State Server has the most complete price caching implementation
4. All servers need both current prices AND historical data

## Proposed Architecture

```
┌──────────────────────────────────────────────────────┐
│              Unified Data Service                      │
├──────────────────────────────────────────────────────┤
│  Current State Layer (Portfolio State Server)          │
│  - Tax lots & positions                               │
│  - Current prices (5-min cache)                       │
│  - Unrealized gains/losses                            │
│  - get_current_prices() API                           │
├──────────────────────────────────────────────────────┤
│  Historical Data Layer (Enhanced data_pipeline)        │
│  - Time series data (252+ days)                       │  
│  - Returns & correlations                             │
│  - Risk metrics & volatility                          │
│  - Shared cache with Portfolio State                  │
└──────────────────────────────────────────────────────┘
                    ▲            ▲
                    │            │
           ┌────────┴───┐  ┌────┴────────┐
           │  yfinance  │  │   OpenBB    │
           └────────────┘  └─────────────┘
```

## Implementation Plan

### Phase 1: Unify Price Fetching (IMMEDIATE)

#### 1.1 Enhance data_pipeline.py to use Portfolio State cache

```python
# In data_pipeline.py
class MarketDataPipeline:
    def __init__(self, portfolio_state_client=None):
        self.portfolio_state = portfolio_state_client
        # ... existing init code ...
    
    def fetch_equity_data(self, tickers, start_date, end_date):
        # Check Portfolio State for current prices first
        if self.portfolio_state and end_date == datetime.now().strftime('%Y-%m-%d'):
            try:
                current_prices = await self.portfolio_state.get_current_prices(tickers)
                # Use these for the most recent day
                # Only fetch historical data from yfinance
            except:
                pass  # Fall back to yfinance for everything
```

#### 1.2 Update Portfolio Optimizer to use Portfolio State

```python
# In portfolio_optimization_server.py
async def initialize_data_pipeline():
    from fastmcp import Client
    import portfolio_state_server
    
    ps_client = Client(portfolio_state_server.mcp)
    pipeline = MarketDataPipeline(portfolio_state_client=ps_client)
    return pipeline
```

#### 1.3 Update Risk Server similarly

### Phase 2: Create Shared Cache Infrastructure

#### 2.1 Implement Redis or shared memory cache

```python
# shared/cache_manager.py
class SharedCacheManager:
    def __init__(self, backend='memory'):
        if backend == 'redis':
            import redis
            self.cache = redis.Redis(host='localhost', port=6379, db=0)
        else:
            # Use multiprocessing.Manager for shared memory
            from multiprocessing import Manager
            manager = Manager()
            self.cache = manager.dict()
    
    def get_price(self, symbol: str) -> Optional[float]:
        key = f"price:{symbol}"
        return self.cache.get(key)
    
    def set_price(self, symbol: str, price: float, ttl: int = 300):
        key = f"price:{symbol}"
        self.cache[key] = (price, datetime.now())
```

#### 2.2 Update all servers to use SharedCacheManager

### Phase 3: Consolidate Data Access Patterns

#### 3.1 Create unified data access interface

```python
# shared/unified_data_service.py
class UnifiedDataService:
    def __init__(self):
        self.cache = SharedCacheManager()
        self.portfolio_state = PortfolioStateManager()
        self.market_data = MarketDataPipeline()
    
    async def get_portfolio_data(self, include_prices=True):
        """Get complete portfolio state with current prices"""
        state = self.portfolio_state.get_portfolio_state()
        if include_prices:
            symbols = list(state['positions'].keys())
            prices = await self.get_current_prices(symbols)
            # Enrich state with prices
        return state
    
    async def get_current_prices(self, symbols: List[str]):
        """Get current prices with caching"""
        prices = {}
        uncached = []
        
        # Check cache first
        for symbol in symbols:
            cached_price = self.cache.get_price(symbol)
            if cached_price:
                prices[symbol] = cached_price
            else:
                uncached.append(symbol)
        
        # Fetch uncached prices
        if uncached:
            new_prices = await self._fetch_prices(uncached)
            for symbol, price in new_prices.items():
                self.cache.set_price(symbol, price)
                prices[symbol] = price
        
        return prices
    
    async def get_historical_data(self, symbols: List[str], days: int = 252):
        """Get historical data for analysis"""
        # Check if we have today's price in cache
        # Fetch only what's needed from yfinance
        return self.market_data.fetch_equity_data(symbols, lookback_days=days)
```

## Migration Strategy

### Step 1: Non-Breaking Changes (Week 1)
1. Add SharedCacheManager to shared/ directory
2. Update data_pipeline.py to check Portfolio State cache
3. Add portfolio_state_client parameter to MarketDataPipeline

### Step 2: Update Servers (Week 2)
1. Portfolio Optimizer: Use Portfolio State for current prices
2. Risk Server: Use Portfolio State for current prices
3. Tax Server: Already done ✅

### Step 3: Monitor & Optimize (Week 3)
1. Add metrics logging for cache hits/misses
2. Monitor API call reduction
3. Fine-tune cache TTL values

## Performance Expectations

### Before (per request)
- 220 total API calls (55 symbols × 4 servers)
- ~15 seconds total latency
- High API rate limit risk

### After Implementation
- 55 API calls on first request (cached for 5 minutes)
- 0 API calls on subsequent requests within TTL
- ~3 seconds latency (75% reduction)
- Minimal API rate limit risk

## OpenBB MCP Server Assessment

The OpenBB MCP server **does NOT need refactoring** because:

1. **It's a wrapper service**: Simply exposes OpenBB API functionality
2. **Different data domain**: Primarily used for treasury rates, not equity prices
3. **No redundancy**: Doesn't duplicate price fetching done by other servers
4. **Proper separation**: Treasury rate fetching is isolated to data_pipeline.py

### OpenBB Usage Pattern
- **data_pipeline.py:383-536**: `get_risk_free_rate()` uses OpenBB for treasury yields
- **Not used for**: Equity prices (uses yfinance instead)
- **Caching**: Already implemented in data_pipeline.py

## Code Changes Required

### 1. data_pipeline.py (Minimal Changes)

```python
# Line 147: Add portfolio state client
def __init__(self, cache_ttl_minutes: int = 15, portfolio_state_client=None):
    self.portfolio_state_client = portfolio_state_client
    # ... rest of existing code ...

# Line 275: Check Portfolio State cache first
if self.portfolio_state_client:
    try:
        ps_prices = await self.portfolio_state_client.get_current_prices(tickers)
        # Use these prices for today's data
        # Only fetch historical from yfinance
```

### 2. portfolio_optimization_server.py

```python
# Add at initialization
from fastmcp import Client
import portfolio_state_server

async def create_pipeline():
    client = Client(portfolio_state_server.mcp)
    return MarketDataPipeline(portfolio_state_client=client)
```

### 3. risk_analysis_server.py

Similar changes to portfolio_optimization_server.py

## Testing Strategy

1. **Unit Tests**: Test cache manager independently
2. **Integration Tests**: Verify servers use shared cache
3. **Performance Tests**: Measure API call reduction
4. **Regression Tests**: Ensure calculations remain accurate

## Rollback Plan

If issues arise:
1. Remove portfolio_state_client parameter (servers fall back to direct fetching)
2. Each server continues to work independently
3. No breaking changes to external APIs

## Success Metrics

- [ ] API calls reduced by 75%
- [ ] Response time improved by 50%
- [ ] Cache hit rate > 80%
- [ ] Zero calculation errors
- [ ] All tests passing

## Timeline

- **Day 1-2**: Implement SharedCacheManager
- **Day 3-4**: Update data_pipeline.py
- **Day 5-6**: Update Portfolio Optimizer
- **Day 7-8**: Update Risk Server
- **Day 9-10**: Testing and monitoring
- **Day 11-12**: Performance tuning
- **Day 13-14**: Documentation and deployment

## Conclusion

The unified data service will eliminate redundant API calls while maintaining backward compatibility. The OpenBB MCP server doesn't need changes as it serves a different purpose. Focus should be on unifying equity price fetching across Portfolio State, Optimizer, and Risk servers.