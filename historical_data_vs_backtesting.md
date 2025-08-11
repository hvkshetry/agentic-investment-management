# Historical Data vs Backtesting Clarification

## What Actually Happens

### Historical Data IS Being Fetched
I need to correct my earlier statement. The system DOES fetch historical data, not just current prices:

#### 1. **Risk Analysis** (`risk_mcp_server_v3.py`)
```python
# Fetches 504 days (2 years) of historical daily prices by default
data = data_pipeline.prepare_for_optimization(tickers, lookback_days=504)
```
- Gets 2 years of daily OHLCV data from yfinance
- Uses this to calculate historical volatility, correlations, VaR, etc.

#### 2. **Portfolio Optimization** (`portfolio_mcp_server_v3.py`)
```python
# Fetches 756 days (3 years) of historical data by default
data = data_pipeline.prepare_for_optimization(tickers, lookback_days=756)
```
- Gets 3 years of daily prices from yfinance
- Uses for mean-variance optimization, Sharpe ratios, etc.

#### 3. **Data Pipeline** (`data_pipeline.py`)
```python
# The actual yfinance call that fetches historical data:
data = self.yf.download(
    tickers,
    start=start_date,  # e.g., "2023-01-01"
    end=end_date,      # e.g., "2025-01-10"
    progress=False
)
```
This fetches the FULL historical price series, not just current prices.

### What's NOT Implemented: True Backtesting

The system fetches historical data for **risk analysis** but doesn't have **backtesting simulation**:

#### Current Capabilities (What EXISTS):
1. **Historical Risk Metrics**
   - Calculate historical volatility from past 2-3 years
   - Compute VaR/CVaR based on historical returns
   - Generate correlation matrices from historical data
   - Measure maximum drawdown from historical prices

2. **Stress Testing** (Simplified)
   - Pre-defined scenarios (2008 crisis, COVID, etc.)
   - Apply hypothetical shocks (-40% equity, +5% bonds)
   - NOT replay of actual historical events

3. **Portfolio Optimization**
   - Uses historical returns to estimate expected returns
   - Calculates covariance from historical data
   - Optimizes based on historical Sharpe ratios

#### What's MISSING for True Backtesting:
1. **Rebalancing Simulation**
   ```python
   # This doesn't exist in the codebase:
   def backtest_strategy(strategy, start_date, end_date, rebalance_freq):
       for date in rebalance_dates:
           weights = strategy.calculate_weights(date)
           portfolio_value = simulate_trades(weights, prices)
           track_performance(portfolio_value)
   ```

2. **Transaction Cost Modeling**
   - No simulation of trading costs
   - No slippage modeling
   - No tax impact during rebalancing

3. **Point-in-Time Simulation**
   - No walk-forward analysis
   - No out-of-sample testing
   - No regime change detection

4. **Performance Attribution**
   - No tracking of strategy returns vs benchmark
   - No factor attribution
   - No risk-adjusted performance over time

## Summary

### What the System DOES:
- **Fetches 2-3 years of historical daily prices** from yfinance
- **Analyzes historical risk** (volatility, VaR, correlations)
- **Optimizes portfolios** using historical data
- **Applies stress scenarios** (hypothetical shocks, not historical replay)

### What it DOESN'T Do:
- **No backtesting engine** to simulate strategies over time
- **No rebalancing simulation** with transaction costs
- **No performance tracking** over historical periods
- **No walk-forward optimization**

### The Confusion:
When I said "only current market price," I was thinking of the Portfolio State Server's price updates. But the Risk and Portfolio servers DO fetch extensive historical data through the data pipeline - they just use it for **analysis** rather than **simulation**.

## If You Want Backtesting:

You would need to add:
1. A backtesting engine (like `backtrader` or `zipline`)
2. Rebalancing logic with frequencies
3. Transaction cost models
4. Performance tracking over time
5. Strategy comparison framework

The current system is designed for:
- **Current portfolio analysis** (what's my risk today?)
- **Forward-looking optimization** (how should I allocate now?)
- **NOT historical strategy validation** (how would this have performed?)

This is why there's no "backtesting" in the codebase - it's an analysis and optimization system, not a strategy testing platform.