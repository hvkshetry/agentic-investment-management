#!/usr/bin/env python3
"""
Check GEV's actual history to understand the discrepancy
"""

import yfinance as yf
from datetime import datetime, timedelta

def check_gev_details():
    print("="*80)
    print("CHECKING GEV (GE VERNOVA) HISTORY")
    print("="*80)
    
    ticker = yf.Ticker("GEV")
    
    # Get info
    info = ticker.info
    print(f"\nCompany: {info.get('longName', 'N/A')}")
    print(f"Symbol: {info.get('symbol', 'N/A')}")
    
    # Try to get historical data
    print("\n📅 Checking available history...")
    
    # Try different date ranges
    ranges = [
        ('2 years', 730),
        ('1 year', 365),
        ('6 months', 180),
        ('3 months', 90)
    ]
    
    for label, days in ranges:
        start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end = datetime.now().strftime('%Y-%m-%d')
        
        try:
            data = yf.download('GEV', start=start, end=end, progress=False)
            if not data.empty:
                actual_days = len(data)
                first_date = data.index[0].strftime('%Y-%m-%d')
                last_date = data.index[-1].strftime('%Y-%m-%d')
                print(f"\n{label} request ({start} to {end}):")
                print(f"  - Got {actual_days} days")
                print(f"  - First date: {first_date}")
                print(f"  - Last date: {last_date}")
                
                # Calculate how old the data is
                days_since_first = (datetime.now() - data.index[0].to_pydatetime()).days
                print(f"  - Days since first trade: {days_since_first}")
                
                # If this is the 2-year request, show the spin-off date
                if days == 730 and actual_days < 500:
                    print(f"\n⚠️ GEV appears to have started trading on {first_date}")
                    print(f"   This is likely when it spun off from General Electric (GE)")
                    print(f"   Total trading days available: {actual_days}")
                    
        except Exception as e:
            print(f"\n{label}: Error - {e}")
    
    # Now check current date
    print("\n" + "="*80)
    print(f"TODAY'S DATE: {datetime.now().strftime('%Y-%m-%d')}")
    print("="*80)
    
    # Calculate expected date if GEV started in April 2024
    april_2024 = datetime(2024, 4, 1)
    days_since_april_2024 = (datetime.now() - april_2024).days
    print(f"\nDays since April 1, 2024: {days_since_april_2024}")
    print(f"Trading days (approx): {int(days_since_april_2024 * 252/365)}")
    
    # Check with max period
    print("\n🔍 Fetching maximum available history...")
    data = yf.download('GEV', period='max', progress=False)
    if not data.empty:
        print(f"Maximum data available: {len(data)} days")
        print(f"First trading date: {data.index[0].strftime('%Y-%m-%d')}")
        print(f"Last trading date: {data.index[-1].strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    check_gev_details()