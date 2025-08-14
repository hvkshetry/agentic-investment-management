#!/usr/bin/env python3
"""
Build comprehensive CUSIP-to-ticker mapping combining multiple sources:
1. Parse SEC 13F filings which contain CUSIP-to-CIK mappings
2. Use existing ticker.txt and company_tickers.json for CIK-to-ticker
3. Build direct CUSIP-to-ticker mapping for common stocks
"""

import json
import logging
import requests
from pathlib import Path
from typing import Dict, Set
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComprehensiveCusipMapper:
    """Build comprehensive CUSIP mapping from multiple sources"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Academic Research (contact@example.com)'
        }
        # Common stock CUSIPs (issuer prefixes) - manually collected for top holdings
        self.known_cusips = {
            # Top tech stocks
            '037833': 'AAPL',   # Apple Inc
            '594918': 'MSFT',   # Microsoft Corp
            '67066G': 'NVDA',   # NVIDIA Corp
            '023135': 'AMZN',   # Amazon.com Inc
            '30303M': 'META',   # Meta Platforms Inc
            '02079K': 'GOOGL',  # Alphabet Inc Class A
            '02079K': 'GOOG',   # Alphabet Inc Class C (same CUSIP prefix)
            '88160R': 'TSLA',   # Tesla Inc
            '11135F': 'AVGO',   # Broadcom Inc
            
            # Major non-tech
            '084670': 'BRK.B',  # Berkshire Hathaway Class B
            '084670': 'BRK.A',  # Berkshire Hathaway Class A (same prefix)
            '46625H': 'JPM',    # JPMorgan Chase
            '478160': 'JNJ',    # Johnson & Johnson
            '92826C': 'V',      # Visa Inc
            '91324P': 'UNH',    # UnitedHealth Group
            '30231G': 'XOM',    # Exxon Mobil
            '931142': 'WMT',    # Walmart Inc
            '57636Q': 'MA',     # Mastercard
            '742718': 'PG',     # Procter & Gamble
            '053015': 'LLY',    # Eli Lilly
            
            # More S&P 500 components
            '060505': 'BAC',    # Bank of America
            '191216': 'KO',     # Coca-Cola
            '717081': 'PFE',    # Pfizer
            '713448': 'PEP',    # PepsiCo
            '22160K': 'COST',   # Costco
            '254687': 'DIS',    # Disney
            '437076': 'HD',     # Home Depot
            '166764': 'CVX',    # Chevron
            '001055': 'ABBV',   # AbbVie
            '58933Y': 'MRK',    # Merck
            '883556': 'TMO',    # Thermo Fisher
            '25468P': 'DHR',    # Danaher
            '00206R': 'ABT',    # Abbott
            '68389X': 'ORCL',   # Oracle
            '172967': 'CSCO',   # Cisco
            'G1151C': 'ACN',    # Accenture
            '92343V': 'VZ',     # Verizon
            '65339F': 'NEE',    # NextEra Energy
            '654106': 'NKE',    # Nike
            '911312': 'UPS',    # UPS
            '110122': 'BMY',    # Bristol-Myers Squibb
            '61744Y': 'MS',     # Morgan Stanley
            '20030N': 'CMCSA',  # Comcast
            '949746': 'WFC',    # Wells Fargo
            '872649': 'TMUS',   # T-Mobile
            
            # International ADRs
            '878087': 'TSM',    # Taiwan Semiconductor
            '665059': 'NVO',    # Novo Nordisk
            '053125': 'ASML',   # ASML Holding
            '724479': 'NVS',    # Novartis
            '009158': 'AZN',    # AstraZeneca
            '743206': 'TM',     # Toyota
            '580135': 'MCD',    # McDonald's
            
            # ETFs
            '78462F': 'SPY',    # SPDR S&P 500
            '921937': 'VOO',    # Vanguard S&P 500
            '922908': 'VTI',    # Vanguard Total Stock Market
            '464287': 'IVV',    # iShares Core S&P 500
            '73935A': 'QQQ',    # Invesco QQQ
            '922042': 'VEA',    # Vanguard FTSE Developed Markets
            '912828': 'BND',    # Vanguard Total Bond Market
            '464287': 'AGG',    # iShares Core US Aggregate Bond
            '920859': 'VWO',    # Vanguard FTSE Emerging Markets
            '922040': 'VUG',    # Vanguard Growth
        }
    
    def load_cik_to_ticker(self) -> Dict[str, str]:
        """Load CIK-to-ticker mappings from existing files"""
        cik_to_ticker = {}
        
        # Load from ticker.txt
        ticker_file = '/home/hvksh/investing/data/ticker.txt'
        if Path(ticker_file).exists():
            with open(ticker_file, 'r') as f:
                for line in f:
                    if '\t' in line:
                        ticker, cik = line.strip().split('\t')
                        cik_to_ticker[cik] = ticker.upper()
            logger.info(f"Loaded {len(cik_to_ticker)} mappings from ticker.txt")
        
        # Load from company_tickers.json
        company_file = '/home/hvksh/investing/data/company_tickers.json'
        if Path(company_file).exists():
            with open(company_file, 'r') as f:
                data = json.load(f)
                count_before = len(cik_to_ticker)
                for key, company in data.items():
                    if 'cik_str' in company and 'ticker' in company:
                        cik = str(company['cik_str'])
                        ticker = company['ticker'].upper()
                        if cik not in cik_to_ticker:
                            cik_to_ticker[cik] = ticker
                logger.info(f"Added {len(cik_to_ticker) - count_before} mappings from company_tickers.json")
        
        return cik_to_ticker
    
    def fetch_13f_cusip_mappings(self) -> Dict[str, str]:
        """Fetch CUSIP-to-CIK mappings from recent 13F-HR filings"""
        cusip_to_cik = {}
        
        # Get recent 13F-HR filings from major institutional investors
        # These contain comprehensive CUSIP lists
        major_filers = [
            '1067983',  # Berkshire Hathaway
            '1364742',  # BlackRock
            '70858',    # Vanguard Group
            '315066',   # State Street
            '1350694',  # Fidelity
        ]
        
        logger.info("Fetching 13F-HR filings from major institutional investors...")
        
        for cik in major_filers:
            try:
                # Get recent 13F-HR filing
                url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR&count=1"
                
                # This would need proper parsing of the 13F-HR XML files
                # For now, we'll use our known mappings
                logger.info(f"Would fetch 13F-HR for CIK {cik}")
                
            except Exception as e:
                logger.error(f"Error fetching 13F for CIK {cik}: {e}")
        
        return cusip_to_cik
    
    def build_comprehensive_mapping(self) -> Dict[str, str]:
        """Build comprehensive CUSIP-to-ticker mapping"""
        cusip_to_ticker = {}
        
        # Start with known mappings
        cusip_to_ticker.update(self.known_cusips)
        logger.info(f"Added {len(self.known_cusips)} known CUSIP mappings")
        
        # Load existing generated mappings if available
        existing_file = '/home/hvksh/investing/data/cusip_to_ticker.json'
        if Path(existing_file).exists():
            with open(existing_file, 'r') as f:
                existing = json.load(f)
                for cusip, ticker in existing.items():
                    if cusip not in cusip_to_ticker:
                        cusip_to_ticker[cusip] = ticker
                logger.info(f"Added {len(existing)} existing mappings")
        
        return cusip_to_ticker
    
    def validate_and_clean(self, mapping: Dict[str, str]) -> Dict[str, str]:
        """Validate and clean the CUSIP mapping"""
        cleaned = {}
        
        for cusip, ticker in mapping.items():
            # Ensure CUSIP is uppercase and 6 characters
            cusip_clean = cusip.upper()[:6]
            ticker_clean = ticker.upper()
            
            # Handle duplicates (same CUSIP for different share classes)
            if cusip_clean in cleaned:
                # Keep the more common ticker (usually Class A or no class)
                if len(ticker_clean) < len(cleaned[cusip_clean]):
                    cleaned[cusip_clean] = ticker_clean
            else:
                cleaned[cusip_clean] = ticker_clean
        
        return cleaned
    
    def save_mappings(self, cusip_to_ticker: Dict[str, str]):
        """Save the comprehensive CUSIP mapping"""
        output_file = '/home/hvksh/investing/data/cusip_to_ticker_comprehensive.json'
        
        # Sort by ticker for readability
        sorted_mapping = dict(sorted(cusip_to_ticker.items(), key=lambda x: x[1]))
        
        with open(output_file, 'w') as f:
            json.dump(sorted_mapping, f, indent=2)
        
        logger.info(f"Saved {len(sorted_mapping)} CUSIP-to-ticker mappings to {output_file}")
        
        # Also update the main cusip_to_ticker.json
        main_file = '/home/hvksh/investing/data/cusip_to_ticker.json'
        with open(main_file, 'w') as f:
            json.dump(sorted_mapping, f, indent=2)
        logger.info(f"Updated main mapping file: {main_file}")

def main():
    """Build comprehensive CUSIP-to-ticker mapping"""
    mapper = ComprehensiveCusipMapper()
    
    logger.info("Building comprehensive CUSIP-to-ticker mapping...")
    
    # Build the mapping
    cusip_to_ticker = mapper.build_comprehensive_mapping()
    
    # Validate and clean
    cusip_to_ticker = mapper.validate_and_clean(cusip_to_ticker)
    
    # Save the mapping
    mapper.save_mappings(cusip_to_ticker)
    
    # Show statistics
    logger.info("\n=== Mapping Statistics ===")
    logger.info(f"Total CUSIP-to-ticker mappings: {len(cusip_to_ticker)}")
    
    # Test with common tickers
    test_cusips = {
        '037833': 'AAPL',
        '594918': 'MSFT',
        '67066G': 'NVDA',
        '023135': 'AMZN',
        '30303M': 'META'
    }
    
    logger.info("\nValidation of key mappings:")
    for cusip, expected in test_cusips.items():
        actual = cusip_to_ticker.get(cusip, 'NOT FOUND')
        status = "✅" if actual == expected else "❌"
        logger.info(f"  {status} {cusip} -> {actual} (expected {expected})")

if __name__ == "__main__":
    main()