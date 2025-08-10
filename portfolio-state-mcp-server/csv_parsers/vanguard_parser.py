"""
Vanguard CSV parser implementation
"""

import csv
import io
from typing import List
from datetime import datetime
import logging

from .parser_factory import BaseBrokerParser
import sys
from pathlib import Path
from datetime import datetime, timedelta
sys.path.append(str(Path(__file__).parent.parent))
from portfolio_state_server import TaxLot

logger = logging.getLogger(__name__)

class VanguardParser(BaseBrokerParser):
    """Parser for Vanguard CSV exports"""
    
    def parse(self, csv_content: str, account_id: str) -> List[TaxLot]:
        """
        Parse Vanguard CSV format
        
        Vanguard CSV has multiple sections:
        1. Fund account summary
        2. Current positions (CRITICAL - contains actual holdings)
        3. Transaction history (for recent activity)
        
        We'll parse BOTH positions and transactions
        """
        tax_lots = []
        
        try:
            lines = csv_content.strip().split('\n')
            
            # FIRST: Find and parse CURRENT POSITIONS section
            positions_start = -1
            for i, line in enumerate(lines):
                if 'Account Number,Investment Name,Symbol,Shares,Share Price,Total Value' in line:
                    positions_start = i
                    break
            
            if positions_start != -1:
                # Parse current positions
                positions_end = positions_start + 1
                while positions_end < len(lines) and lines[positions_end].strip() and not lines[positions_end].startswith(','):
                    positions_end += 1
                
                reader = csv.DictReader(io.StringIO('\n'.join(lines[positions_start:positions_end])))
                
                for idx, row in enumerate(reader):
                    try:
                        if not row or not row.get('Symbol'):
                            continue
                        
                        symbol = row.get('Symbol', '').strip().upper()
                        
                        # Skip money market funds
                        if not symbol or symbol in ['VMFXX', 'CASH', 'N/A']:
                            continue
                        
                        # Get position details
                        shares = self.clean_number(row.get('Shares', '0'))
                        if shares <= 0:
                            continue
                        
                        share_price = self.clean_number(row.get('Share Price', '0'))
                        total_value = self.clean_number(row.get('Total Value', '0'))
                        
                        # For current positions, we don't have historical cost basis
                        # We'll use current value as both cost basis and value for now
                        # This means unrealized gains will be 0 until proper cost basis is provided
                        purchase_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
                        
                        # IMPORTANT: Use actual values from CSV, don't reduce them!
                        # Cost basis should ideally come from transaction history
                        # For now, use current value as cost basis (conservative for taxes)
                        cost_basis = total_value  # Use actual value, not reduced
                        purchase_price = share_price  # Use actual current price
                        
                        investment_name = row.get('Investment Name', '')
                        asset_type = self.determine_asset_type(symbol, investment_name)
                        
                        vanguard_account = row.get('Account Number', account_id).strip()
                        
                        # Create tax lot from position
                        lot = TaxLot(
                            lot_id=f"VG_POS_{vanguard_account}_{symbol}_{idx}",
                            symbol=symbol,
                            quantity=shares,
                            purchase_date=purchase_date,
                            purchase_price=purchase_price,
                            cost_basis=cost_basis,
                            asset_type=asset_type,
                            account_id=vanguard_account,
                            broker="vanguard"
                        )
                        
                        tax_lots.append(lot)
                        logger.info(f"Parsed Vanguard position: {symbol} - {shares:.3f} shares, value: ${total_value:,.2f}")
                        
                    except Exception as e:
                        logger.error(f"Error parsing position row {idx}: {e}")
                        continue
            
            # SECOND: Parse transaction history for accurate cost basis
            transaction_start = -1
            for i, line in enumerate(lines):
                if 'Trade Date' in line and 'Transaction Type' in line and 'Symbol' in line:
                    transaction_start = i
                    break
            
            if transaction_start != -1:
                # Parse transactions to get real cost basis
                reader = csv.DictReader(io.StringIO('\n'.join(lines[transaction_start:])))
                
                # Track transactions by symbol for cost basis calculation
                transactions_by_symbol = {}
                
                for row in reader:
                    try:
                        if not row or not row.get('Symbol'):
                            continue
                        
                        symbol = row.get('Symbol', '').strip().upper()
                        transaction_type = row.get('Transaction Type', '').strip().lower()
                        
                        # Skip non-security transactions
                        if not symbol or symbol in ['CASH', 'VMFXX', 'N/A', '']:
                            continue
                        
                        # Only process buy/reinvestment for cost basis
                        if transaction_type not in ['buy', 'reinvestment']:
                            continue
                        
                        # Parse transaction details
                        shares = self.clean_number(row.get('Shares', '0'))
                        if shares <= 0:
                            continue
                        
                        share_price = self.clean_number(row.get('Share Price', '0'))
                        principal = abs(self.clean_number(row.get('Principal Amount', '0')))
                        
                        trade_date = row.get('Trade Date', '')
                        if not trade_date:
                            trade_date = row.get('Settlement Date', '')
                        trade_date = self.parse_date(trade_date)
                        
                        # Store transaction for cost basis calculation
                        if symbol not in transactions_by_symbol:
                            transactions_by_symbol[symbol] = []
                        
                        transactions_by_symbol[symbol].append({
                            'date': trade_date,
                            'shares': shares,
                            'price': share_price,
                            'cost': principal if principal > 0 else shares * share_price,
                            'type': transaction_type
                        })
                        
                        logger.debug(f"Found {transaction_type}: {symbol} {shares} @ ${share_price} on {trade_date}")
                        
                    except Exception as e:
                        logger.warning(f"Error parsing transaction: {e}")
                        continue
                
                # Now update our tax lots with real cost basis from transactions
                updated_lots = []
                for lot in tax_lots:
                    symbol = lot.symbol
                    
                    if symbol in transactions_by_symbol:
                        # Calculate weighted average cost basis from transactions
                        total_shares = sum(t['shares'] for t in transactions_by_symbol[symbol])
                        total_cost = sum(t['cost'] for t in transactions_by_symbol[symbol])
                        
                        if total_shares > 0:
                            # Update lot with real cost basis
                            avg_price = total_cost / total_shares
                            lot.purchase_price = avg_price
                            lot.cost_basis = lot.quantity * avg_price
                            lot.unrealized_gain = lot.current_value - lot.cost_basis
                            
                            # Use earliest transaction date
                            earliest_date = min(t['date'] for t in transactions_by_symbol[symbol])
                            lot.purchase_date = earliest_date
                            
                            logger.info(f"Updated {symbol} with real cost basis: ${lot.cost_basis:,.2f} (${avg_price:.2f}/share)")
                    
                    updated_lots.append(lot)
                
                tax_lots = updated_lots
            
            logger.info(f"Successfully parsed {len(tax_lots)} positions from Vanguard CSV with cost basis")
            return tax_lots
            
        except Exception as e:
            logger.error(f"Error parsing Vanguard CSV: {e}")
            return []