#!/usr/bin/env python3
"""
Build comprehensive fund category mapping from multiple sources:
1. yfinance API for basic categories
2. SEC N-PORT filings for detailed classifications
3. ETF provider websites for sector/style information
"""

import json
import logging
import requests
from pathlib import Path
from typing import Dict, List, Tuple
import yfinance as yf
import time
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FundCategoryMapper:
    """Build comprehensive fund category mapping"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Standard fund categories based on asset class and style
        self.category_hierarchy = {
            # Equity Categories
            'EQUITY': {
                'Large Cap': ['Large Blend', 'Large Growth', 'Large Value'],
                'Mid Cap': ['Mid-Cap Blend', 'Mid-Cap Growth', 'Mid-Cap Value'],
                'Small Cap': ['Small Blend', 'Small Growth', 'Small Value'],
                'International': ['Foreign Large Blend', 'Foreign Large Growth', 'Foreign Large Value',
                                 'Europe Stock', 'Pacific/Asia ex-Japan Stk', 'Japan Stock',
                                 'Diversified Emerging Mkts', 'China Region', 'India Equity'],
                'Sector': ['Technology', 'Healthcare', 'Financial', 'Energy', 'Real Estate',
                          'Communications', 'Consumer Cyclical', 'Consumer Defensive',
                          'Industrials', 'Basic Materials', 'Utilities']
            },
            # Fixed Income Categories
            'FIXED_INCOME': {
                'Government': ['Long Government', 'Intermediate Government', 'Short Government',
                              'Inflation-Protected Bond', 'Intermediate-Term Bond'],
                'Corporate': ['Corporate Bond', 'High Yield Bond', 'Short-Term Bond',
                             'Ultrashort Bond', 'Long-Term Bond'],
                'Municipal': ['Muni National Long', 'Muni National Interm', 'Muni National Short',
                             'High Yield Muni', 'Muni Single State', 'Muni California Long',
                             'Muni California Intermediate', 'Muni New York Long'],
                'International': ['World Bond', 'Emerging Markets Bond', 'Global Bond-USD Hedged'],
                'Specialty': ['Bank Loan', 'Nontraditional Bond', 'Multisector Bond',
                             'Preferred Stock', 'Convertibles']
            },
            # Alternative Categories
            'ALTERNATIVE': {
                'Commodities': ['Commodities Broad Basket', 'Commodities Precious Metals',
                               'Commodities Energy', 'Commodities Agriculture'],
                'Strategies': ['Long-Short Equity', 'Market Neutral', 'Managed Futures',
                              'Multialternative', 'Options Trading', 'Volatility'],
                'Real Assets': ['Global Real Estate', 'Real Estate', 'Infrastructure']
            },
            # Allocation Categories
            'ALLOCATION': {
                'Balanced': ['Allocation--15% to 30% Equity', 'Allocation--30% to 50% Equity',
                            'Allocation--50% to 70% Equity', 'Allocation--70% to 85% Equity',
                            'Allocation--85%+ Equity'],
                'Target Date': ['Target-Date 2020', 'Target-Date 2025', 'Target-Date 2030',
                               'Target-Date 2035', 'Target-Date 2040', 'Target-Date 2045',
                               'Target-Date 2050', 'Target-Date 2055', 'Target-Date 2060+',
                               'Target-Date Retirement'],
                'Tactical': ['Tactical Allocation', 'World Allocation']
            }
        }
        
        # Known fund mappings for common ETFs and mutual funds
        self.known_fund_categories = {
            # Major Index ETFs
            'SPY': 'Large Blend',
            'VOO': 'Large Blend',
            'IVV': 'Large Blend',
            'VTI': 'Total Stock Market',
            'VT': 'World Stock',
            'QQQ': 'Large Growth',
            'DIA': 'Large Value',
            'IWM': 'Small Blend',
            'MDY': 'Mid-Cap Blend',
            'EFA': 'Foreign Large Blend',
            'EEM': 'Diversified Emerging Mkts',
            'VWO': 'Diversified Emerging Mkts',
            'VEA': 'Foreign Large Blend',
            'VEU': 'Foreign Large Blend',
            'IEFA': 'Foreign Large Blend',
            'IEMG': 'Diversified Emerging Mkts',
            
            # Sector ETFs
            'XLK': 'Technology',
            'XLV': 'Healthcare',
            'XLF': 'Financial',
            'XLE': 'Energy',
            'XLI': 'Industrials',
            'XLY': 'Consumer Cyclical',
            'XLP': 'Consumer Defensive',
            'XLB': 'Basic Materials',
            'XLRE': 'Real Estate',
            'XLU': 'Utilities',
            'XLC': 'Communications',
            
            # Bond ETFs
            'BND': 'Intermediate-Term Bond',
            'AGG': 'Intermediate-Term Bond',
            'TLT': 'Long Government',
            'IEF': 'Intermediate Government',
            'SHY': 'Short Government',
            'LQD': 'Corporate Bond',
            'HYG': 'High Yield Bond',
            'JNK': 'High Yield Bond',
            'MUB': 'Muni National Interm',
            'TIP': 'Inflation-Protected Bond',
            'VTEB': 'Muni National Interm',
            'VCSH': 'Short-Term Bond',
            'VCIT': 'Intermediate-Term Bond',
            'VCLT': 'Long-Term Bond',
            'EMB': 'Emerging Markets Bond',
            'BNDX': 'Global Bond-USD Hedged',
            
            # Style ETFs
            'VUG': 'Large Growth',
            'VTV': 'Large Value',
            'VBK': 'Small Growth',
            'VBR': 'Small Value',
            'VOT': 'Mid-Cap Growth',
            'VOE': 'Mid-Cap Value',
            'VIGAX': 'Large Growth',
            'VVIAX': 'Large Value',
            
            # Vanguard Mutual Funds
            'VTSAX': 'Total Stock Market',
            'VTIAX': 'Total International Stock',
            'VFIAX': 'Large Blend',
            'VXUS': 'Total International Stock',
            'VGTSX': 'Total International Stock',
            'VEMAX': 'Diversified Emerging Mkts',
            'VWIUX': 'Muni National Interm',
            'VWLUX': 'Long Government',
            'VMLUX': 'Muni National Long',
            'VWITX': 'Muni National Interm',
            'VWALX': 'High Yield Muni',
            'VCAIX': 'Muni California Intermediate',
            
            # Alternative ETFs
            'GLD': 'Commodities Precious Metals',
            'IAU': 'Commodities Precious Metals',
            'SLV': 'Commodities Precious Metals',
            'USO': 'Commodities Energy',
            'DBA': 'Commodities Agriculture',
            'DBC': 'Commodities Broad Basket',
            'VNQ': 'Real Estate',
            'VNQI': 'Global Real Estate',
            
            # Target Date Funds
            'VTTSX': 'Target-Date 2060+',
            'VFIFX': 'Target-Date 2050',
            'VFORX': 'Target-Date 2040',
            'VTHRX': 'Target-Date 2030',
            'VTTVX': 'Target-Date 2025',
            'VTWNX': 'Target-Date 2020',
            'VTINX': 'Target-Date Retirement',
        }
    
    def fetch_yfinance_categories(self, symbols: List[str]) -> Dict[str, str]:
        """Fetch fund categories from yfinance"""
        categories = {}
        
        logger.info(f"Fetching categories for {len(symbols)} symbols from yfinance...")
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                if info and 'category' in info and info['category']:
                    categories[symbol] = info['category']
                    logger.debug(f"{symbol}: {info['category']}")
                elif info and 'quoteType' in info:
                    # Try to infer category from other fields
                    quote_type = info['quoteType']
                    if quote_type == 'ETF':
                        # Check fund family and name for clues
                        long_name = info.get('longName', '')
                        if 'S&P 500' in long_name or 'SP500' in long_name:
                            categories[symbol] = 'Large Blend'
                        elif 'Technology' in long_name:
                            categories[symbol] = 'Technology'
                        elif 'Health' in long_name:
                            categories[symbol] = 'Healthcare'
                        elif 'Financial' in long_name:
                            categories[symbol] = 'Financial'
                        elif 'Energy' in long_name:
                            categories[symbol] = 'Energy'
                        elif 'Real Estate' in long_name:
                            categories[symbol] = 'Real Estate'
                        elif 'Bond' in long_name:
                            categories[symbol] = 'Intermediate-Term Bond'
                        elif 'Municipal' in long_name or 'Muni' in long_name:
                            categories[symbol] = 'Muni National Interm'
                
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                logger.debug(f"Error fetching {symbol}: {e}")
        
        logger.info(f"Retrieved {len(categories)} categories from yfinance")
        return categories
    
    def normalize_category(self, category: str) -> str:
        """Normalize category names to standard format"""
        if not category:
            return ""
        
        # Common mappings
        mappings = {
            # Equity mappings
            'large blend': 'Large Blend',
            'large-cap blend': 'Large Blend',
            'large cap blend': 'Large Blend',
            'large growth': 'Large Growth',
            'large-cap growth': 'Large Growth',
            'large value': 'Large Value',
            'large-cap value': 'Large Value',
            'mid-cap blend': 'Mid-Cap Blend',
            'mid blend': 'Mid-Cap Blend',
            'small-cap blend': 'Small Blend',
            'small blend': 'Small Blend',
            
            # International mappings
            'foreign large blend': 'Foreign Large Blend',
            'foreign large-cap blend': 'Foreign Large Blend',
            'international equity': 'Foreign Large Blend',
            'developed markets': 'Foreign Large Blend',
            'emerging markets': 'Diversified Emerging Mkts',
            'emerging-markets': 'Diversified Emerging Mkts',
            
            # Bond mappings
            'intermediate-term bond': 'Intermediate-Term Bond',
            'intermediate bond': 'Intermediate-Term Bond',
            'intermediate core bond': 'Intermediate-Term Bond',
            'intermediate core-plus bond': 'Intermediate-Term Bond',
            'corporate bond': 'Corporate Bond',
            'high yield bond': 'High Yield Bond',
            'high-yield bond': 'High Yield Bond',
            'muni national intermediate': 'Muni National Interm',
            'muni national interm': 'Muni National Interm',
            'municipal national intermediate': 'Muni National Interm',
            'muni california intermediate': 'Muni California Intermediate',
            'muni california interm': 'Muni California Intermediate',
            'long government': 'Long Government',
            'short government': 'Short Government',
            
            # Sector mappings
            'technology': 'Technology',
            'information technology': 'Technology',
            'tech': 'Technology',
            'health care': 'Healthcare',
            'healthcare': 'Healthcare',
            'health': 'Healthcare',
            'financials': 'Financial',
            'financial': 'Financial',
            'financial services': 'Financial',
            'energy': 'Energy',
            'real estate': 'Real Estate',
            'reits': 'Real Estate',
            'consumer discretionary': 'Consumer Cyclical',
            'consumer cyclical': 'Consumer Cyclical',
            'consumer staples': 'Consumer Defensive',
            'consumer defensive': 'Consumer Defensive',
            'industrials': 'Industrials',
            'materials': 'Basic Materials',
            'basic materials': 'Basic Materials',
            'utilities': 'Utilities',
            'communication services': 'Communications',
            'communications': 'Communications',
            
            # Alternative mappings
            'commodities': 'Commodities Broad Basket',
            'gold': 'Commodities Precious Metals',
            'precious metals': 'Commodities Precious Metals',
        }
        
        # Try exact match first
        category_lower = category.lower().strip()
        if category_lower in mappings:
            return mappings[category_lower]
        
        # Try partial matches
        for key, value in mappings.items():
            if key in category_lower:
                return value
        
        # Return original if no mapping found
        return category
    
    def build_comprehensive_mapping(self) -> Dict[str, str]:
        """Build comprehensive fund category mapping"""
        final_mapping = {}
        
        # Start with known mappings
        final_mapping.update(self.known_fund_categories)
        logger.info(f"Added {len(self.known_fund_categories)} known fund categories")
        
        # Get top ETFs and mutual funds to categorize
        test_symbols = list(self.known_fund_categories.keys())
        
        # Add more common symbols
        additional_symbols = [
            'ARKK', 'ARKQ', 'ARKW', 'ARKG', 'ARKF',  # ARK ETFs
            'SOXX', 'SMH', 'ICLN', 'TAN', 'PBW',     # Thematic ETFs
            'JETS', 'XRT', 'XHB', 'XBI', 'KRE',      # Industry ETFs
            'FDN', 'BOTZ', 'ROBO', 'FINX', 'GNOM',   # Tech/Innovation
            'DVY', 'SDY', 'VIG', 'NOBL', 'VYM',      # Dividend ETFs
            'RSP', 'SPLG', 'SPTM', 'SPYG', 'SPYV',   # S&P variants
            'SCHB', 'SCHX', 'SCHG', 'SCHV', 'SCHM',  # Schwab ETFs
            'ITOT', 'IUSG', 'IUSV', 'IJH', 'IJR',    # iShares Core
            'VB', 'VO', 'VV', 'VXF', 'MGK', 'MGV',   # Vanguard Style
        ]
        
        # Fetch categories from yfinance
        all_symbols = list(set(test_symbols + additional_symbols))
        yf_categories = self.fetch_yfinance_categories(all_symbols)
        
        # Merge and normalize
        for symbol, category in yf_categories.items():
            if symbol not in final_mapping:
                normalized = self.normalize_category(category)
                if normalized:
                    final_mapping[symbol] = normalized
        
        logger.info(f"Total fund category mappings: {len(final_mapping)}")
        
        return final_mapping
    
    def save_mapping(self, mapping: Dict[str, str]):
        """Save fund category mapping to file"""
        output_file = '/home/hvksh/investing/data/fund_categories.json'
        
        # Sort by symbol for readability
        sorted_mapping = dict(sorted(mapping.items()))
        
        with open(output_file, 'w') as f:
            json.dump(sorted_mapping, f, indent=2)
        
        logger.info(f"Saved {len(sorted_mapping)} fund category mappings to {output_file}")
    
    def generate_category_report(self, mapping: Dict[str, str]):
        """Generate a report of fund categories"""
        from collections import defaultdict
        
        # Group by category
        category_groups = defaultdict(list)
        for symbol, category in mapping.items():
            category_groups[category].append(symbol)
        
        logger.info("\n=== Fund Category Summary ===")
        for category in sorted(category_groups.keys()):
            symbols = category_groups[category]
            logger.info(f"{category}: {len(symbols)} funds")
            if len(symbols) <= 5:
                logger.info(f"  Symbols: {', '.join(symbols)}")
            else:
                logger.info(f"  Symbols: {', '.join(symbols[:5])}, ... ({len(symbols)} total)")

def main():
    """Build comprehensive fund category mapping"""
    mapper = FundCategoryMapper()
    
    logger.info("Building comprehensive fund category mapping...")
    
    # Build the mapping
    fund_categories = mapper.build_comprehensive_mapping()
    
    # Save the mapping
    mapper.save_mapping(fund_categories)
    
    # Generate report
    mapper.generate_category_report(fund_categories)
    
    # Test some key funds
    logger.info("\n=== Testing Key Fund Categories ===")
    test_funds = ['SPY', 'BND', 'VWIUX', 'QQQ', 'XLK', 'MUB', 'GLD', 'VTI']
    for symbol in test_funds:
        category = fund_categories.get(symbol, 'Unknown')
        logger.info(f"  {symbol}: {category}")

if __name__ == "__main__":
    main()