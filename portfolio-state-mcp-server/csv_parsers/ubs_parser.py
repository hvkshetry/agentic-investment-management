"""
UBS CSV parser implementation
"""

import csv
import io
from typing import List
from datetime import datetime, timedelta
import logging
import re

from .parser_factory import BaseBrokerParser
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from portfolio_state_server import TaxLot

logger = logging.getLogger(__name__)

class UBSParser(BaseBrokerParser):
    """Parser for UBS CSV exports"""
    
    def parse(self, csv_content: str, account_id: str) -> List[TaxLot]:
        """
        Parse UBS CSV format
        
        UBS format shows current holdings with unrealized gains.
        We'll create synthetic tax lots based on unrealized gain data.
        
        Expected columns:
        - ACCOUNT NUMBER
        - DESCRIPTION
        - SYMBOL
        - CUSIP
        - QUANTITY
        - PRICE
        - VALUE
        - UNREALIZED GAIN/LOSS $
        - UNREALIZED GAIN/LOSS %
        """
        tax_lots = []
        
        try:
            lines = csv_content.strip().split('\n')
            
            # Find the HOLDINGS section
            header_idx = 0
            for i, line in enumerate(lines):
                if 'HOLDINGS' in line:
                    header_idx = i + 1  # Header is next line after HOLDINGS
                    break
            
            # Skip to actual header line with column names
            if header_idx == 0:
                # If no HOLDINGS marker, look for ACCOUNT NUMBER
                for i, line in enumerate(lines):
                    if 'ACCOUNT NUMBER' in line.upper():
                        header_idx = i
                        break
            
            # Parse CSV starting from header
            reader = csv.DictReader(io.StringIO('\n'.join(lines[header_idx:])))
            
            for idx, row in enumerate(reader):
                try:
                    # Skip empty rows or cash positions
                    if not row or not row.get('SYMBOL'):
                        continue
                    
                    symbol = row.get('SYMBOL', '').strip()
                    
                    # Skip non-equity positions (N/A symbols are cash)
                    if not symbol or symbol == 'N/A' or symbol == 'CASH':
                        continue
                    
                    # Extract account info
                    account_info = row.get('ACCOUNT NUMBER', '').strip()
                    if not account_info:
                        account_info = account_id
                    
                    # Parse account name (e.g., "(NE 55344) Hersh Trust")
                    account_match = re.search(r'\(([^)]+)\)', account_info)
                    if account_match:
                        account_code = account_match.group(1)
                    else:
                        account_code = account_info
                    
                    # Extract quantity
                    quantity = self.clean_number(row.get('QUANTITY', '0'))
                    if quantity <= 0:
                        continue
                    
                    # Extract current price and value
                    current_price = self.clean_number(row.get('PRICE', '0'))
                    current_value = self.clean_number(row.get('VALUE', '0'))
                    
                    # Extract unrealized gain/loss
                    unrealized_gain_str = row.get('UNREALIZED GAIN/LOSS $', '0')
                    unrealized_gain = self.clean_number(unrealized_gain_str)
                    
                    # Extract unrealized gain percentage
                    unrealized_pct_str = row.get('UNREALIZED GAIN/LOSS %', '0')
                    unrealized_pct = self.clean_number(unrealized_pct_str.replace('%', ''))
                    
                    # Calculate actual cost basis from unrealized gain
                    # This is accurate since UBS provides the unrealized gain/loss
                    if current_value > 0 and unrealized_gain != 0:
                        cost_basis = current_value - unrealized_gain
                    else:
                        # If no unrealized gain info, use current value as cost basis
                        cost_basis = current_value if current_value > 0 else quantity * current_price
                    
                    # Calculate purchase price
                    if quantity > 0 and cost_basis > 0:
                        purchase_price = cost_basis / quantity
                    else:
                        purchase_price = current_price
                    
                    # Estimate purchase date based on gain percentage
                    # This is a rough estimate - larger gains suggest older purchases
                    if abs(unrealized_pct) > 100:
                        # Very large gain/loss - likely held > 2 years
                        days_ago = 730
                    elif abs(unrealized_pct) > 50:
                        # Significant gain/loss - likely held > 1 year
                        days_ago = 400
                    elif abs(unrealized_pct) > 20:
                        # Moderate gain/loss - likely held 6-12 months
                        days_ago = 270
                    else:
                        # Small gain/loss - likely recent purchase
                        days_ago = 90
                    
                    purchase_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                    
                    # Get description for asset type
                    description = row.get('DESCRIPTION', '')
                    
                    # Determine asset type
                    asset_type = self.determine_asset_type(symbol, description)
                    
                    # Create synthetic tax lot
                    lot = TaxLot(
                        lot_id=f"UBS_{account_code}_{symbol}_{idx}",
                        symbol=symbol,
                        quantity=quantity,
                        purchase_date=purchase_date,
                        purchase_price=purchase_price,
                        cost_basis=cost_basis,
                        current_price=current_price,
                        current_value=current_value,
                        unrealized_gain=unrealized_gain,
                        asset_type=asset_type,
                        account_id=account_code,
                        broker="ubs"
                    )
                    
                    # Calculate holding period
                    lot.calculate_gain(current_price)
                    
                    tax_lots.append(lot)
                    logger.info(f"Parsed UBS lot: {symbol} - {quantity} shares, unrealized: ${unrealized_gain:.2f}")
                    
                except Exception as e:
                    logger.error(f"Error parsing row {idx}: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(tax_lots)} holdings from UBS CSV")
            return tax_lots
            
        except Exception as e:
            logger.error(f"Error parsing UBS CSV: {e}")
            return []