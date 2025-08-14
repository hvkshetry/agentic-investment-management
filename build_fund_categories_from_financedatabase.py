#!/usr/bin/env python3
"""
Build fund category mapping using FinanceDatabase
https://github.com/JerBouma/FinanceDatabase

This provides a comprehensive, community-maintained database of:
- 36,786 ETFs with categories
- 57,881 Funds with categories
- No hardcoding needed - entirely data-driven
"""

import json
import logging
from pathlib import Path
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def install_finance_database():
    """Install FinanceDatabase package if not already installed"""
    try:
        import financedatabase
        logger.info("FinanceDatabase already installed")
        return True
    except ImportError:
        logger.info("Installing FinanceDatabase...")
        import subprocess
        import sys
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "financedatabase", "-U"])
            logger.info("✅ FinanceDatabase installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install FinanceDatabase: {e}")
            return False

def build_fund_category_mapping() -> Dict[str, str]:
    """
    Build comprehensive fund category mapping from FinanceDatabase
    
    Returns:
        Dictionary mapping symbol to category
    """
    if not install_finance_database():
        raise RuntimeError("Could not install FinanceDatabase")
    
    import financedatabase as fd
    
    fund_categories = {}
    
    # Load ETFs database
    logger.info("Loading ETF database from FinanceDatabase...")
    try:
        etfs = fd.ETFs()
        
        # Get all ETFs with their categories
        etf_data = etfs.select()
        
        if not etf_data.empty:
            import pandas as pd
            for symbol, row in etf_data.iterrows():
                category = row.get('category', '')
                # Ensure category is a string and not NaN
                if category and not pd.isna(category):
                    fund_categories[symbol] = str(category)
            
            logger.info(f"✅ Loaded {len(etf_data)} ETFs")
            
            # Show category distribution
            category_counts = etf_data['category'].value_counts().head(20)
            logger.info("\nTop 20 ETF categories:")
            for cat, count in category_counts.items():
                logger.info(f"  {cat}: {count}")
        
    except Exception as e:
        logger.error(f"Error loading ETFs: {e}")
    
    # Load Mutual Funds database
    logger.info("\nLoading Mutual Funds database from FinanceDatabase...")
    try:
        funds = fd.Funds()
        
        # Get all funds with their categories
        funds_data = funds.select()
        
        if not funds_data.empty:
            for symbol, row in funds_data.iterrows():
                category = row.get('category', '')
                # Ensure category is a string and not NaN
                if category and not pd.isna(category) and symbol not in fund_categories:
                    fund_categories[symbol] = str(category)
            
            logger.info(f"✅ Loaded {len(funds_data)} Mutual Funds")
            
            # Show category distribution
            category_counts = funds_data['category'].value_counts().head(20)
            logger.info("\nTop 20 Fund categories:")
            for cat, count in category_counts.items():
                logger.info(f"  {cat}: {count}")
        
    except Exception as e:
        logger.error(f"Error loading Funds: {e}")
    
    # Map categories to standardized names for our gate logic
    category_mapping = {
        # Municipal bonds - critical for gate logic
        'Muni National Intermediate': 'Muni National Interm',
        'Muni National Long': 'Muni National Long',
        'Muni National Short': 'Muni National Short',
        'Muni California Intermediate': 'Muni California Intermediate',
        'Muni California Long': 'Muni California Long',
        'Municipal Bonds': 'Muni National Interm',
        'High Yield Muni': 'High Yield Muni',
        
        # Fixed Income categories
        'Intermediate Core Bond': 'Intermediate-Term Bond',
        'Intermediate Core-Plus Bond': 'Intermediate-Term Bond',
        'Intermediate Government': 'Intermediate Government',
        'Long Government': 'Long Government',
        'Short Government': 'Short Government',
        'Corporate Bond': 'Corporate Bond',
        'High Yield Bond': 'High Yield Bond',
        'Emerging Markets Bond': 'Emerging Markets Bond',
        'Inflation-Protected Bond': 'Inflation-Protected Bond',
        
        # Equity categories  
        'Large Blend': 'Large Blend',
        'Large Growth': 'Large Growth',
        'Large Value': 'Large Value',
        'Mid-Cap Blend': 'Mid-Cap Blend',
        'Mid-Cap Growth': 'Mid-Cap Growth',
        'Mid-Cap Value': 'Mid-Cap Value',
        'Small Blend': 'Small Blend',
        'Small Growth': 'Small Growth',
        'Small Value': 'Small Value',
        
        # International
        'Foreign Large Blend': 'Foreign Large Blend',
        'Foreign Large Growth': 'Foreign Large Growth',
        'Foreign Large Value': 'Foreign Large Value',
        'Diversified Emerging Mkts': 'Diversified Emerging Mkts',
        'Europe Stock': 'Europe Stock',
        'Pacific/Asia ex-Japan Stk': 'Pacific/Asia ex-Japan Stk',
        
        # Sectors
        'Technology': 'Technology',
        'Health': 'Healthcare',
        'Financial': 'Financial',
        'Energy': 'Energy',
        'Real Estate': 'Real Estate',
        'Communications': 'Communications',
        'Consumer Cyclical': 'Consumer Cyclical',
        'Consumer Defensive': 'Consumer Defensive',
        'Industrials': 'Industrials',
        'Basic Materials': 'Basic Materials',
        'Utilities': 'Utilities',
        
        # Alternative
        'Commodities Broad Basket': 'Commodities Broad Basket',
        'Commodities Precious Metals': 'Commodities Precious Metals',
        'Commodities Energy': 'Commodities Energy',
        'Commodities Agriculture': 'Commodities Agriculture',
    }
    
    # Standardize categories
    standardized_categories = {}
    for symbol, category in fund_categories.items():
        # Map to standardized name if exists, otherwise keep original
        standardized = category_mapping.get(category, category)
        standardized_categories[symbol] = standardized
    
    logger.info(f"\n✅ Total fund category mappings: {len(standardized_categories)}")
    
    return standardized_categories

def save_mapping(mapping: Dict[str, str]):
    """Save fund category mapping to JSON file"""
    output_file = '/home/hvksh/investing/data/fund_categories_financedatabase.json'
    
    # Sort by symbol for readability
    sorted_mapping = dict(sorted(mapping.items()))
    
    with open(output_file, 'w') as f:
        json.dump(sorted_mapping, f, indent=2)
    
    logger.info(f"Saved {len(sorted_mapping)} fund category mappings to {output_file}")
    
    # Also save a smaller file with just common US-listed funds for faster loading
    common_symbols = [
        'SPY', 'VOO', 'IVV', 'VTI', 'QQQ', 'VEA', 'VWO', 'EEM', 'IWM', 'DIA',
        'BND', 'AGG', 'TLT', 'IEF', 'SHY', 'LQD', 'HYG', 'JNK', 'MUB', 'VTEB',
        'XLK', 'XLV', 'XLF', 'XLE', 'XLI', 'XLY', 'XLP', 'XLB', 'XLRE', 'XLU', 'XLC',
        'VUG', 'VTV', 'VBK', 'VBR', 'VOT', 'VOE', 'MDY', 'EFA', 'IEFA', 'IEMG',
        'GLD', 'IAU', 'SLV', 'USO', 'DBA', 'DBC', 'VNQ', 'VNQI',
        'VWIUX', 'VWLUX', 'VMLUX', 'VWITX', 'VWALX', 'VCAIX',
        'ARKK', 'ARKQ', 'ARKW', 'ARKG', 'ARKF'
    ]
    
    common_mapping = {s: mapping.get(s, '') for s in common_symbols if s in mapping}
    
    common_file = '/home/hvksh/investing/data/fund_categories_common.json'
    with open(common_file, 'w') as f:
        json.dump(common_mapping, f, indent=2)
    
    logger.info(f"Saved {len(common_mapping)} common fund mappings to {common_file}")

def test_critical_funds(mapping: Dict[str, str]):
    """Test that critical funds are properly categorized"""
    critical_funds = {
        'VWIUX': 'Muni',  # Should contain 'Muni'
        'MUB': 'Muni',
        'SPY': 'Large',   # Should contain 'Large'
        'QQQ': 'Growth',  # Should contain 'Growth'
        'BND': 'Bond',    # Should contain 'Bond'
        'XLK': 'Tech',    # Should contain 'Tech' or similar
        'GLD': 'Commodit', # Should contain 'Commodit'
    }
    
    logger.info("\n=== Testing Critical Fund Categories ===")
    for symbol, expected_part in critical_funds.items():
        category = mapping.get(symbol, 'NOT FOUND')
        # Handle None or float values
        if category and not isinstance(category, str):
            category = str(category)
        if category and expected_part.lower() in category.lower():
            logger.info(f"✅ {symbol}: {category}")
        else:
            logger.warning(f"⚠️ {symbol}: {category} (expected to contain '{expected_part}')")

def main():
    """Build fund category mapping from FinanceDatabase"""
    logger.info("Building fund category mapping from FinanceDatabase...")
    logger.info("This is a community-maintained, open-source database")
    logger.info("No hardcoding - entirely data-driven from 90,000+ funds/ETFs\n")
    
    # Build the mapping
    fund_categories = build_fund_category_mapping()
    
    if fund_categories:
        # Save the mapping
        save_mapping(fund_categories)
        
        # Test critical funds
        test_critical_funds(fund_categories)
    else:
        logger.error("Failed to build fund category mapping")

if __name__ == "__main__":
    main()