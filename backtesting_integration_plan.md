# Backtesting Integration Plan with bt Library

## Executive Summary
**Recommended Library**: bt (https://github.com/pmorissette/bt)
- Uses same data source (yfinance) as existing pipeline
- Portfolio-first design perfect for 55+ positions
- Easy integration with minimal code changes
- Transaction cost modeling built-in

## Key Finding: Economic Cycle Matching
**No library has built-in cycle matching**, but we can implement custom solution using:
- FRED economic indicators (already accessible via OpenBB)
- Historical correlation analysis
- Custom bt.Algo for regime detection

## Integration Architecture

### Phase 1: Basic Integration (Week 1)
```python
# backtest_mcp_server.py
from fastmcp import FastMCP
import bt
from shared.data_pipeline import MarketDataPipeline

@server.tool()
async def backtest_portfolio_strategy(
    strategy_type: str = "buy_and_hold",
    lookback_years: int = 10,
    rebalance_frequency: str = "monthly",
    transaction_cost: float = 0.001
) -> Dict[str, Any]:
    """
    Backtest portfolio strategies using historical data
    """
    # Use existing pipeline for data
    pipeline = MarketDataPipeline()
    data = pipeline.fetch_equity_data(tickers, lookback_days=lookback_years*252)
    
    # Create bt strategy
    strategy = create_strategy(strategy_type, rebalance_frequency)
    backtest = bt.Backtest(strategy, data, commissions=lambda q, p: q*p*transaction_cost)
    
    # Run backtest
    results = bt.run(backtest)
    return parse_results(results)
```

### Phase 2: Economic Cycle Matching (Week 2)

```python
class EconomicCycleAnalyzer:
    """Find analogous historical periods based on economic indicators"""
    
    def __init__(self, pipeline: MarketDataPipeline):
        self.pipeline = pipeline
        self.indicators = [
            'DGS10',     # 10-year Treasury
            'T10Y2Y',    # Yield curve
            'UNRATE',    # Unemployment
            'CPIAUCSL',  # CPI
            'VIXCLS',    # VIX
            'GDP'        # GDP growth
        ]
    
    def find_similar_periods(self, current_date, lookback_days=90):
        """
        Find historical periods with similar economic conditions
        Uses DTW or correlation analysis
        """
        # Get current economic snapshot
        current_snapshot = self.get_economic_snapshot(current_date)
        
        # Scan historical periods
        similar_periods = []
        for historical_date in historical_dates:
            hist_snapshot = self.get_economic_snapshot(historical_date)
            similarity = calculate_similarity(current_snapshot, hist_snapshot)
            if similarity > threshold:
                similar_periods.append({
                    'date': historical_date,
                    'similarity': similarity,
                    'forward_returns': get_forward_returns(historical_date)
                })
        
        return similar_periods
```

### Phase 3: Custom bt Algorithms (Week 3)

```python
class CycleAwareRebalance(bt.Algo):
    """Rebalance based on economic cycle stage"""
    
    def __call__(self, target):
        cycle_stage = self.detect_cycle_stage(target.now)
        
        # Adjust weights based on cycle
        if cycle_stage == 'expansion':
            # Overweight equities
            weights = self.expansion_weights
        elif cycle_stage == 'contraction':
            # Defensive positioning
            weights = self.defensive_weights
        
        target.weights = weights
        return True

# Integration with bt
strategy = bt.Strategy('CycleAware', [
    bt.algos.RunMonthly(),
    CycleAwareRebalance(),
    bt.algos.Rebalance()
])
```

## Data Requirements

### Already Available:
- ✅ Historical equity prices (yfinance via data_pipeline)
- ✅ Risk-free rates (OpenBB/FRED)
- ✅ Portfolio positions (Portfolio State Server)

### Need to Add:
- 📊 Economic indicators time series (FRED via OpenBB)
- 📈 Benchmark indices for comparison
- 💰 Historical dividend data (yfinance has this)

## Implementation Steps

### 1. Install bt Library
```bash
pip install bt
```

### 2. Create Backtesting MCP Server
- New file: `backtest-mcp-server/backtest_server.py`
- Tools: `backtest_strategy`, `find_analogous_periods`, `compare_strategies`

### 3. Extend Data Pipeline
```python
# Add to data_pipeline.py
def fetch_economic_indicators(indicators: List[str], start_date: str) -> pd.DataFrame:
    """Fetch economic time series from FRED"""
    # Use OpenBB to get FRED data
    pass

def calculate_cycle_similarity(period1: pd.DataFrame, period2: pd.DataFrame) -> float:
    """Calculate similarity between two economic periods"""
    # Use DTW or correlation
    pass
```

### 4. Create Strategy Library
```python
# strategies/portfolio_strategies.py
strategies = {
    'buy_and_hold': bt.algos.RunOnce() + bt.algos.SelectAll() + bt.algos.WeighEqually(),
    'momentum': MomentumStrategy(),
    'mean_reversion': MeanReversionStrategy(),
    'risk_parity': RiskParityStrategy(),
    'cycle_aware': CycleAwareStrategy()
}
```

## Expected Outcomes

### What You'll Get:
1. **Historical Performance**: How portfolio would have performed
2. **Drawdown Analysis**: Worst losses in various scenarios
3. **Cycle Comparisons**: "In 1994, similar conditions led to..."
4. **Strategy Comparison**: Which approach works in current regime
5. **Risk-Adjusted Returns**: Sharpe, Sortino, Calmar ratios

### Integration with Existing Tools:
- Risk Server: Use backtest results for better VaR estimates
- Portfolio Server: Optimize based on backtest performance
- Tax Server: Model tax impact of rebalancing strategies

## Alternative Libraries (If bt Falls Short)

1. **finmarketpy**: Better for multi-source data and complex analytics
2. **backtrader**: More mature but harder integration
3. **Custom Solution**: Build on pandas + your existing pipeline

## Next Steps

1. **Approve library choice** (bt recommended)
2. **Create proof-of-concept** with simple buy-and_hold backtest
3. **Implement cycle matching** algorithm
4. **Build MCP server** for backtesting tools
5. **Test with actual portfolio** data

## Cost-Benefit Analysis

### Benefits:
- Validate strategies before implementation
- Understand risk in historical context
- Find analogous periods for better forecasting
- Optimize rebalancing frequency

### Costs:
- ~40 hours development time
- Additional complexity in system
- More data storage requirements
- Computational overhead for simulations

### ROI:
Even 1% improvement in risk-adjusted returns on $5M portfolio = $50k/year
Development cost easily justified by risk reduction alone.