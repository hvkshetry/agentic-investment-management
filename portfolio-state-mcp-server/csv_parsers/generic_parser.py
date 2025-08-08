"""
Generic CSV parser for unknown broker formats
"""

import csv
import io
from typing import List
from datetime import datetime
import logging

from .parser_factory import BaseBrokerParser
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from portfolio_state_server import TaxLot

logger = logging.getLogger(__name__)

class GenericParser(BaseBrokerParser):
    """Generic parser for unknown CSV formats"""
    
    def parse(self, csv_content: str, account_id: str) -> List[TaxLot]:
        """
        Parse generic CSV format
        
        Attempts to identify common column patterns:
        - Symbol/Ticker
        - Quantity/Shares
        - Date/Trade Date
        - Price/Cost
        """
        tax_lots = []
        
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            
            for idx, row in enumerate(reader):
                try:
                    # Find symbol column
                    symbol = None
                    for col in ['Symbol', 'Ticker', 'SYMBOL', 'TICKER', 'symbol', 'ticker']:
                        if col in row and row[col]:
                            symbol = row[col].strip().upper()
                            break
                    
                    if not symbol or symbol in ['CASH', 'N/A']:
                        continue
                    
                    # Find quantity column
                    quantity = 0
                    for col in ['Quantity', 'Shares', 'QUANTITY', 'SHARES', 'quantity', 'shares', 'Units']:
                        if col in row and row[col]:
                            quantity = self.clean_number(row[col])
                            if quantity > 0:
                                break
                    
                    if quantity <= 0:
                        continue
                    
                    # Find date column
                    date_str = None
                    for col in ['Date', 'Trade Date', 'Purchase Date', 'DATE', 'date', 'trade_date']:
                        if col in row and row[col]:
                            date_str = row[col]
                            break
                    
                    purchase_date = self.parse_date(date_str) if date_str else datetime.now().strftime("%Y-%m-%d")
                    
                    # Find price column
                    price = 0
                    for col in ['Price', 'Cost', 'Share Price', 'PRICE', 'price', 'cost']:
                        if col in row and row[col]:
                            price = self.clean_number(row[col])
                            if price > 0:
                                break
                    
                    # Find cost basis or calculate it
                    cost_basis = 0
                    for col in ['Cost Basis', 'Total Cost', 'Value', 'COST BASIS', 'cost_basis', 'total_cost']:
                        if col in row and row[col]:
                            cost_basis = self.clean_number(row[col])
                            if cost_basis > 0:
                                break
                    
                    if cost_basis == 0 and price > 0:
                        cost_basis = quantity * price
                    
                    if cost_basis <= 0:
                        continue
                    
                    if price == 0 and cost_basis > 0:
                        price = cost_basis / quantity
                    
                    # Create tax lot
                    lot = TaxLot(
                        lot_id=f"GEN_{account_id}_{symbol}_{idx}",
                        symbol=symbol,
                        quantity=quantity,
                        purchase_date=purchase_date,
                        purchase_price=price,
                        cost_basis=cost_basis,
                        asset_type="equity",  # Default to equity
                        account_id=account_id,
                        broker="generic"
                    )
                    
                    tax_lots.append(lot)
                    logger.info(f"Parsed generic lot: {symbol} - {quantity} shares")
                    
                except Exception as e:
                    logger.warning(f"Could not parse row {idx}: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(tax_lots)} lots from generic CSV")
            return tax_lots
            
        except Exception as e:
            logger.error(f"Error parsing generic CSV: {e}")
            return []