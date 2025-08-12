#!/usr/bin/env python3
"""
Clean portfolio state JSON to remove test data and dynamic price fields
Makes the portfolio state production-ready with only immutable historical data
"""

import json
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from shared.atomic_writer import atomic_dump_json

def clean_portfolio_state():
    """Remove test data and dynamic fields from portfolio state"""
    
    state_file = Path("/home/hvksh/investing/portfolio-state-mcp-server/state/portfolio_state.json")
    
    # Read current state
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    # Fields to remove from each tax lot
    dynamic_fields = ['current_price', 'current_value', 'unrealized_gain']
    
    # Clean tax lots
    cleaned_tax_lots = {}
    removed_tickers = []
    
    for ticker, lots in state.get('tax_lots', {}).items():
        # Skip TEST and other mock tickers
        if ticker.upper() in ['TEST', 'DUMMY', 'MOCK', 'SAMPLE']:
            removed_tickers.append(ticker)
            print(f"Removing mock ticker: {ticker}")
            continue
        
        # Clean each lot
        cleaned_lots = []
        for lot in lots:
            # Remove dynamic fields
            for field in dynamic_fields:
                if field in lot:
                    del lot[field]
            
            # Also check for test accounts/brokers
            if lot.get('account_id', '').lower() in ['test_account', 'dummy_account', 'mock_account']:
                print(f"Skipping lot with test account: {lot['lot_id']}")
                continue
                
            if lot.get('broker', '').lower() in ['test', 'dummy', 'mock']:
                print(f"Skipping lot with test broker: {lot['lot_id']}")
                continue
            
            cleaned_lots.append(lot)
        
        if cleaned_lots:
            cleaned_tax_lots[ticker] = cleaned_lots
    
    # Update state
    state['tax_lots'] = cleaned_tax_lots
    
    # Remove current_prices if it exists
    if 'current_prices' in state:
        del state['current_prices']
        print("Removed current_prices object")
    
    # Save cleaned state
    atomic_dump_json(state, state_file)
    
    print(f"\nCleaning complete:")
    print(f"- Removed {len(removed_tickers)} mock tickers: {removed_tickers}")
    print(f"- Removed dynamic fields: {dynamic_fields}")
    print(f"- Remaining tickers: {list(cleaned_tax_lots.keys())}")
    print(f"- Total positions: {len(cleaned_tax_lots)}")
    
    return cleaned_tax_lots

if __name__ == "__main__":
    clean_portfolio_state()