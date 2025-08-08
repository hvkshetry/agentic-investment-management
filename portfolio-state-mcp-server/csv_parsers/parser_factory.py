"""
Factory for creating broker-specific CSV parsers
"""

from typing import List, Dict, Any, Protocol
from abc import ABC, abstractmethod
import csv
import io
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import from parent directory
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from portfolio_state_server import TaxLot, AssetType

class BaseBrokerParser(ABC):
    """Abstract base class for broker CSV parsers"""
    
    @abstractmethod
    def parse(self, csv_content: str, account_id: str) -> List[TaxLot]:
        """Parse CSV content and return list of tax lots"""
        pass
    
    def clean_number(self, value: str) -> float:
        """Clean and convert string to float"""
        if not value:
            return 0.0
        # Remove currency symbols, commas, and whitespace
        cleaned = re.sub(r'[$,\s%]', '', str(value))
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0
    
    def parse_date(self, date_str: str) -> str:
        """Parse date string to YYYY-MM-DD format"""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")
        
        # Try different date formats
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%b %d, %Y",
            "%B %d, %Y",
            "%d-%b-%Y",
            "%d-%b-%y"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        # If no format matches, return current date
        logger.warning(f"Could not parse date: {date_str}")
        return datetime.now().strftime("%Y-%m-%d")
    
    def determine_asset_type(self, symbol: str, description: str = "") -> str:
        """Determine asset type from symbol and description"""
        symbol_upper = symbol.upper()
        desc_lower = description.lower() if description else ""
        
        # Check for specific patterns
        if any(word in desc_lower for word in ["bond", "treasury", "note", "bill"]):
            return AssetType.BOND
        elif any(word in desc_lower for word in ["etf", "exchange traded", "index fund"]):
            return AssetType.ETF
        elif any(word in desc_lower for word in ["mutual fund", "fund"]):
            return AssetType.MUTUAL_FUND
        elif any(word in desc_lower for word in ["option", "call", "put"]):
            return AssetType.OPTION
        elif any(word in desc_lower for word in ["reit", "real estate"]):
            return AssetType.REIT
        elif symbol_upper in ["BTC", "ETH", "DOGE", "ADA", "DOT"]:
            return AssetType.CRYPTO
        elif symbol_upper in ["GLD", "SLV", "USO", "UNG"]:
            return AssetType.COMMODITY
        elif symbol_upper in ["VMFXX", "SPAXX", "FDRXX"] or "money market" in desc_lower:
            return AssetType.CASH
        else:
            # Default to equity for stocks
            return AssetType.EQUITY

class BrokerCSVParser:
    """Factory for creating broker-specific parsers"""
    
    @staticmethod
    def create_parser(broker: str) -> BaseBrokerParser:
        """Create parser for specific broker"""
        broker_lower = broker.lower()
        
        if broker_lower == "vanguard":
            from .vanguard_parser import VanguardParser
            return VanguardParser()
        elif broker_lower == "ubs":
            from .ubs_parser import UBSParser
            return UBSParser()
        elif broker_lower == "fidelity":
            from .fidelity_parser import FidelityParser
            return FidelityParser()
        elif broker_lower == "schwab":
            from .schwab_parser import SchwabParser
            return SchwabParser()
        elif broker_lower == "etrade":
            from .etrade_parser import ETradeParser
            return ETradeParser()
        elif broker_lower == "td_ameritrade" or broker_lower == "td":
            from .td_parser import TDAmeritradeParser
            return TDAmeritradeParser()
        elif broker_lower == "robinhood":
            from .robinhood_parser import RobinhoodParser
            return RobinhoodParser()
        elif broker_lower == "interactive_brokers" or broker_lower == "ibkr":
            from .ibkr_parser import InteractiveBrokersParser
            return InteractiveBrokersParser()
        else:
            # Default to generic parser
            from .generic_parser import GenericParser
            return GenericParser()