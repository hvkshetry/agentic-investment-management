#!/usr/bin/env python3
"""
Symbol Resolver - API-based symbol validation and metadata retrieval
Uses yfinance and OpenBB APIs to validate symbols and get accurate classifications
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
import yfinance as yf
from dataclasses import dataclass
from datetime import datetime
import re

logger = logging.getLogger(__name__)

@dataclass
class SymbolInfo:
    """Information about a financial instrument"""
    symbol: str
    valid: bool
    name: str
    asset_type: str  # ETF, EQUITY, MUTUALFUND, BOND, etc.
    category: str    # For funds: category like "Muni National Interm"
    exchange: str
    currency: str
    current_price: float
    is_fund: bool
    is_tradable: bool
    metadata: Dict[str, Any]

class SymbolResolver:
    """
    Resolves and validates symbols using market data APIs
    """
    
    # Known symbol changes/mappings
    SYMBOL_CHANGES = {
        'ANTM': 'ELV',  # Anthem changed to Elevance Health
        'FB': 'META',    # Facebook to Meta
        'TWTR': None,    # Twitter delisted (acquired)
    }
    
    # Cache for API results to avoid repeated calls
    _symbol_cache = {}
    
    # Fund category mapping loaded once
    _fund_categories = None
    
    def validate_symbol(self, symbol: str) -> SymbolInfo:
        """
        Validate a symbol and get its metadata
        
        Args:
            symbol: Ticker symbol to validate
            
        Returns:
            SymbolInfo object with validation results
        """
        # Check cache first
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]
            
        # Check for known symbol changes
        if symbol in self.SYMBOL_CHANGES:
            new_symbol = self.SYMBOL_CHANGES[symbol]
            if new_symbol:
                logger.warning(f"Symbol {symbol} has changed to {new_symbol}")
                symbol = new_symbol
            else:
                logger.error(f"Symbol {symbol} is no longer tradable (delisted/acquired)")
                return SymbolInfo(
                    symbol=symbol,
                    valid=False,
                    name="Delisted",
                    asset_type="UNKNOWN",
                    category="",
                    exchange="",
                    currency="",
                    current_price=0,
                    is_fund=False,
                    is_tradable=False,
                    metadata={"reason": "Delisted or acquired"}
                )
        
        try:
            # Use yfinance to get symbol info
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info or 'symbol' not in info:
                # Symbol doesn't exist
                logger.warning(f"Symbol {symbol} not found")
                result = SymbolInfo(
                    symbol=symbol,
                    valid=False,
                    name="Unknown",
                    asset_type="UNKNOWN",
                    category="",
                    exchange="",
                    currency="",
                    current_price=0,
                    is_fund=False,
                    is_tradable=False,
                    metadata={}
                )
            else:
                # Extract metadata
                quote_type = info.get('quoteType', 'EQUITY')
                asset_type = self._map_quote_type(quote_type)
                is_fund = asset_type in ['ETF', 'MUTUALFUND', 'CEF']
                
                # Get category for funds from FinanceDatabase mapping
                category = ""
                if is_fund:
                    category = self.get_fund_category_from_mapping(symbol)
                    # If not found in mapping, try yfinance
                    if not category:
                        category = info.get('category', '')
                    
                result = SymbolInfo(
                    symbol=symbol,
                    valid=True,
                    name=info.get('longName', info.get('shortName', symbol)),
                    asset_type=asset_type,
                    category=category,
                    exchange=info.get('exchange', ''),
                    currency=info.get('currency', 'USD'),
                    current_price=info.get('currentPrice', info.get('regularMarketPrice', 0)),
                    is_fund=is_fund,
                    is_tradable=True,
                    metadata={
                        'sector': info.get('sector', ''),
                        'industry': info.get('industry', ''),
                        'market_cap': info.get('marketCap', 0),
                        'pe_ratio': info.get('trailingPE', 0),
                        'dividend_yield': info.get('dividendYield', 0),
                        'expense_ratio': info.get('annualReportExpenseRatio', 0) if is_fund else 0
                    }
                )
                
            # Cache the result
            self._symbol_cache[symbol] = result
            return result
            
        except Exception as e:
            logger.error(f"Error validating symbol {symbol}: {e}")
            return SymbolInfo(
                symbol=symbol,
                valid=False,
                name="Error",
                asset_type="UNKNOWN",
                category="",
                exchange="",
                currency="",
                current_price=0,
                is_fund=False,
                is_tradable=False,
                metadata={"error": str(e)}
            )
    
    def _map_quote_type(self, quote_type: str) -> str:
        """
        Map yfinance quote types to our asset types
        
        Args:
            quote_type: Quote type from yfinance
            
        Returns:
            Standardized asset type
        """
        mapping = {
            'ETF': 'ETF',
            'MUTUALFUND': 'MUTUALFUND',
            'EQUITY': 'EQUITY',
            'INDEX': 'INDEX',
            'CURRENCY': 'CURRENCY',
            'CRYPTOCURRENCY': 'CRYPTO',
            'FUTURE': 'FUTURE',
            'OPTION': 'OPTION'
        }
        return mapping.get(quote_type, 'EQUITY')
    
    def validate_symbols_batch(self, symbols: List[str]) -> Dict[str, SymbolInfo]:
        """
        Validate multiple symbols at once
        
        Args:
            symbols: List of ticker symbols
            
        Returns:
            Dictionary mapping symbols to SymbolInfo objects
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.validate_symbol(symbol)
        return results
    
    def get_correct_classification(self, symbol: str) -> str:
        """
        Get the correct classification for a symbol
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Correct classification string
        """
        info = self.validate_symbol(symbol)
        
        if not info.valid:
            return "Invalid symbol"
            
        if info.is_fund:
            if info.category:
                return f"{info.asset_type}: {info.category}"
            else:
                return info.asset_type
        else:
            if info.metadata.get('sector'):
                return f"{info.asset_type}: {info.metadata['sector']}"
            else:
                return info.asset_type
    
    def suggest_replacement(self, symbol: str) -> Optional[str]:
        """
        Suggest a replacement for an invalid or outdated symbol
        
        Args:
            symbol: Ticker symbol that may be invalid
            
        Returns:
            Suggested replacement symbol or None
        """
        # Check known mappings
        if symbol in self.SYMBOL_CHANGES:
            return self.SYMBOL_CHANGES[symbol]
            
        # Try common variations
        variations = [
            symbol.upper(),
            symbol.lower(),
            symbol.replace('-', '.'),
            symbol.replace('.', '-'),
            symbol + 'X',  # Some funds add X
            symbol[:-1] if len(symbol) > 1 else symbol  # Remove last char
        ]
        
        for variant in variations:
            if variant != symbol:
                info = self.validate_symbol(variant)
                if info.valid:
                    return variant
                    
        return None
    
    def get_fund_category_from_mapping(self, symbol: str) -> str:
        """
        Get fund category from comprehensive mapping file
        
        Args:
            symbol: Fund ticker symbol
            
        Returns:
            Fund category or empty string
        """
        # Load fund categories if not already loaded
        if self._fund_categories is None:
            self._load_fund_categories()
        
        # Look up category
        category = self._fund_categories.get(symbol.upper(), '')
        
        if category:
            logger.debug(f"Found category for {symbol}: {category}")
        else:
            logger.debug(f"No category found for {symbol}")
        
        return category
    
    def _load_fund_categories(self):
        """
        Load fund category mapping from FinanceDatabase JSON
        """
        import json
        import os
        
        self._fund_categories = {}
        
        # Try loading common funds first (faster)
        common_file = '/home/hvksh/investing/data/fund_categories_common.json'
        full_file = '/home/hvksh/investing/data/fund_categories_financedatabase.json'
        
        if os.path.exists(common_file):
            try:
                with open(common_file, 'r') as f:
                    self._fund_categories = json.load(f)
                logger.info(f"✅ Loaded {len(self._fund_categories)} common fund categories")
                
                # If we need more, load the full database
                if len(self._fund_categories) < 100 and os.path.exists(full_file):
                    with open(full_file, 'r') as f:
                        full_categories = json.load(f)
                        self._fund_categories.update(full_categories)
                        logger.info(f"✅ Loaded {len(full_categories)} total fund categories from FinanceDatabase")
                        
            except Exception as e:
                logger.error(f"Failed to load fund categories: {e}")
                self._fund_categories = {}
        else:
            logger.warning(f"Fund category files not found")
    
    def get_fund_category(self, symbol: str) -> str:
        """
        Get the fund category for a symbol
        
        Args:
            symbol: Fund ticker symbol
            
        Returns:
            Fund category or empty string
        """
        return self.get_fund_category_from_mapping(symbol)