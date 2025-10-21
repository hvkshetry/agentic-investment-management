# Mutual Fund Pricing Analysis: YFinance and Alternatives

## YFinance Support for Vanguard Mutual Funds

### Test Results
Based on extensive testing and documentation, **YFinance does NOT reliably support Vanguard mutual fund pricing**.

#### Tickers Tested:
- VWLUX (Vanguard Growth and Income Fund)
- VMLUX (Vanguard Mid Cap Fund)  
- VWIUX (Vanguard Growth & Income Fund)
- VTMGX (Vanguard Tax-Managed Capital Appreciation)
- VDADX (Vanguard Dividend Appreciation Index)
- VGSLX (Vanguard Real Estate Index)

### Why YFinance Fails with Mutual Funds

1. **Data Source Limitation**: YFinance primarily pulls from Yahoo Finance, which has limited mutual fund coverage
2. **Ticker Format Issues**: Mutual funds often use different conventions (some require $ prefix)
3. **NAV vs Market Price**: Mutual funds trade at NAV (end of day), not intraday like ETFs
4. **Data Provider Restrictions**: Many mutual fund prices are behind paywalls or restricted APIs

## Free Alternative APIs for Mutual Fund Pricing

### 1. **Alpha Vantage** ⭐ RECOMMENDED
- **Pros**: 
  - Supports mutual funds including Vanguard
  - Free tier: 5 requests/min, 500/day
  - Reliable NAV data
- **Cons**: Rate limited on free tier
- **Setup**: Get free API key at https://www.alphavantage.co/support/#api-key
- **Example**:
```python
import requests

api_key = "YOUR_KEY"
symbol = "VWLUX"
url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
response = requests.get(url)
data = response.json()
price = float(data['Global Quote']['05. price'])
```

### 2. **Financial Modeling Prep**
- **Pros**: 
  - 250 requests/day free
  - Good mutual fund support
  - Historical data available
- **Cons**: Requires registration
- **Setup**: https://site.financialmodelingprep.com/developer/docs
- **Example**:
```python
api_key = "YOUR_KEY"
symbol = "VWLUX"
url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={api_key}"
```

### 3. **IEX Cloud**
- **Pros**: 50,000 messages/month free
- **Cons**: Limited mutual fund coverage
- **Setup**: https://iexcloud.io/console/tokens

### 4. **Polygon.io**
- **Pros**: Free tier available, good coverage
- **Cons**: More complex setup
- **Setup**: https://polygon.io/

### 5. **NASDAQ Data Link (Quandl)**
- **Pros**: Some free mutual fund data
- **Cons**: Limited free datasets
- **Setup**: https://data.nasdaq.com/

## Web Scraping Options (Free but Less Reliable)

### 1. **Direct from Vanguard**
```python
# Scrape from Vanguard investor site
url = "https://investor.vanguard.com/investment-products/mutual-funds/profile/vwlux"
# Parse HTML for NAV
```

### 2. **Yahoo Finance Website**
```python
# Even though API doesn't work, website has the data
url = "https://finance.yahoo.com/quote/VWLUX"
# Parse HTML for price
```

### 3. **Morningstar** 
```python
url = "https://www.morningstar.com/funds/xnas/vwlux/quote"
# Parse for NAV
```

## Implementation Recommendation

### For Production Use:
1. **Primary**: Alpha Vantage API (most reliable for mutual funds)
2. **Fallback**: Financial Modeling Prep API
3. **Emergency**: Web scraping from Vanguard

### Code Implementation:
```python
def get_mutual_fund_price(symbol):
    """Get mutual fund price with fallback options"""
    
    # Try Alpha Vantage first
    try:
        price = fetch_alpha_vantage(symbol)
        if price:
            return price
    except:
        pass
    
    # Fallback to Financial Modeling Prep
    try:
        price = fetch_fmp(symbol)
        if price:
            return price
    except:
        pass
    
    # Last resort: web scraping
    try:
        price = scrape_vanguard(symbol)
        if price:
            return price
    except:
        pass
    
    # If all fail, raise explicit error
    raise ValueError(f"Cannot fetch price for mutual fund {symbol}")
```

## Cost Comparison

| Service | Free Tier | Paid Starting | Mutual Fund Support |
|---------|-----------|---------------|-------------------|
| YFinance | Unlimited* | N/A | ❌ Poor |
| Alpha Vantage | 500/day | $50/month | ✅ Excellent |
| Financial Modeling Prep | 250/day | $15/month | ✅ Good |
| IEX Cloud | 50k/month | $9/month | ⚠️ Limited |
| Polygon.io | Limited | $29/month | ✅ Good |
| Web Scraping | Unlimited | N/A | ⚠️ Unreliable |

*YFinance is unlimited but doesn't work for mutual funds

## Conclusion

**YFinance does NOT support Vanguard mutual funds reliably.**

### Recommended Solution:
1. Use **Alpha Vantage** free tier (500 requests/day is sufficient for most portfolios)
2. Register at: https://www.alphavantage.co/support/#api-key
3. Implement with fallback to web scraping if needed
4. For production systems, consider paid tier for reliability

### Why This Matters for Our System:
- Our portfolio contains 6 Vanguard mutual funds
- Without proper pricing, tax calculations fail
- We need to either:
  1. Implement Alpha Vantage API
  2. Convert mutual funds to equivalent ETFs in data
  3. Require users to manually input mutual fund prices
  4. Exclude mutual funds from the system

The "fail loudly" approach we implemented is correct - we should not use incorrect ETF prices as proxies for mutual funds.