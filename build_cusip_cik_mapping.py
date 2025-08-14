#!/usr/bin/env python3
"""
Build CUSIP-CIK mapping from SEC EDGAR filings
Based on https://github.com/leoliu0/cik-cusip-mapping methodology
"""

import re
import csv
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import requests
from typing import Dict, Set, Tuple
import time
from collections import Counter, defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CusipCikMapper:
    """Build CUSIP-CIK mapping from SEC filings"""
    
    def __init__(self):
        self.base_url = "https://www.sec.gov/Archives/edgar"
        self.headers = {
            'User-Agent': 'Academic Research (contact@example.com)'
        }
        # Pattern to match CUSIP (9 characters: 6 issuer + 2 issue + 1 check digit)
        self.cusip_pattern = re.compile(
            r'[0-9A-Z]{1}[0-9]{3}[0-9A-Za-z]{2}[0-9]{2}[0-9]'
        )
        # More lenient pattern for partial CUSIPs
        self.cusip_partial_pattern = re.compile(
            r'[0-9A-Z]{1}[0-9]{3}[0-9A-Za-z]{2}'
        )
        
    def download_index(self, year: int, quarter: int) -> list:
        """Download EDGAR index for a specific quarter"""
        url = f"{self.base_url}/full-index/{year}/QTR{quarter}/master.idx"
        
        logger.info(f"Downloading index for {year} Q{quarter}")
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            lines = response.text.split('\n')
            # Skip header lines
            data_start = 0
            for i, line in enumerate(lines):
                if line.startswith('CIK|'):
                    data_start = i + 1
                    break
            
            filings = []
            for line in lines[data_start:]:
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        cik, company, form_type = parts[0], parts[1], parts[2]
                        date_filed, filename = parts[3], parts[4]
                        
                        # Focus on forms that contain CUSIP information
                        if any(form in form_type for form in ['13F', '13G', '13D', 'N-Q', 'N-CSR', 'N-PORT']):
                            filings.append({
                                'cik': cik.strip(),
                                'company': company.strip(),
                                'form_type': form_type.strip(),
                                'date': date_filed.strip(),
                                'filename': filename.strip()
                            })
            
            logger.info(f"Found {len(filings)} relevant filings")
            return filings
            
        except Exception as e:
            logger.error(f"Error downloading index: {e}")
            return []
    
    def extract_cusip_from_filing(self, filing_path: str) -> Set[str]:
        """Extract CUSIP numbers from a filing"""
        url = f"https://www.sec.gov/Archives/{filing_path}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            text = response.text[:500000]  # Limit to first 500KB to avoid huge files
            
            # Find all CUSIP patterns
            cusips = set()
            
            # Look for CUSIP mentions with context
            cusip_contexts = [
                r'CUSIP[\s:#]*([0-9A-Z]{6}[0-9A-Z]{3})',
                r'CUSIP NUMBER[\s:#]*([0-9A-Z]{6}[0-9A-Z]{3})',
                r'<CUSIP>([0-9A-Z]{6}[0-9A-Z]{3})</CUSIP>',
            ]
            
            for pattern in cusip_contexts:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    clean_cusip = ''.join(c for c in match if c.isalnum())
                    if len(clean_cusip) >= 6:
                        # Take first 6 chars (issuer identifier)
                        cusips.add(clean_cusip[:6].upper())
            
            # Also find standalone CUSIPs
            matches = self.cusip_partial_pattern.findall(text)
            for match in matches:
                clean_cusip = ''.join(c for c in match if c.isalnum())
                if len(clean_cusip) >= 6:
                    cusips.add(clean_cusip[:6].upper())
            
            return cusips
            
        except Exception as e:
            logger.debug(f"Error processing filing {filing_path}: {e}")
            return set()
    
    def build_mapping_from_recent_filings(self, months_back: int = 6) -> Dict[str, str]:
        """Build CUSIP-CIK mapping from recent filings"""
        cusip_to_cik = {}
        cik_to_cusips = defaultdict(set)
        
        # Calculate quarters to download
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months_back * 30)
        
        quarters = []
        current = start_date
        while current <= end_date:
            year = current.year
            quarter = (current.month - 1) // 3 + 1
            quarters.append((year, quarter))
            current += timedelta(days=92)  # Move to next quarter
        
        quarters = list(set(quarters))[-2:]  # Last 2 quarters
        
        logger.info(f"Processing quarters: {quarters}")
        
        for year, quarter in quarters:
            filings = self.download_index(year, quarter)
            
            # Sample filings to avoid rate limiting
            sample_size = min(100, len(filings))
            import random
            sampled_filings = random.sample(filings, sample_size) if filings else []
            
            logger.info(f"Processing {len(sampled_filings)} sampled filings from {year} Q{quarter}")
            
            for i, filing in enumerate(sampled_filings):
                if i % 10 == 0:
                    logger.info(f"Progress: {i}/{len(sampled_filings)}")
                
                cusips = self.extract_cusip_from_filing(filing['filename'])
                cik = filing['cik'].lstrip('0')  # Remove leading zeros
                
                for cusip in cusips:
                    cik_to_cusips[cik].add(cusip)
                    # Only map if we don't have a conflict
                    if cusip not in cusip_to_cik or cusip_to_cik[cusip] == cik:
                        cusip_to_cik[cusip] = cik
                
                # Rate limiting
                time.sleep(0.1)
        
        # Resolve conflicts - keep most common mapping
        logger.info("Resolving CUSIP conflicts...")
        final_mapping = {}
        for cusip, cik in cusip_to_cik.items():
            final_mapping[cusip] = cik
        
        logger.info(f"Built mapping with {len(final_mapping)} CUSIP-CIK pairs")
        
        return final_mapping
    
    def save_mapping(self, mapping: Dict[str, str], output_file: str):
        """Save CUSIP-CIK mapping to file"""
        with open(output_file, 'w') as f:
            json.dump(mapping, f, indent=2)
        logger.info(f"Saved mapping to {output_file}")
    
    def load_ticker_mapping(self) -> Dict[str, str]:
        """Load CIK-to-ticker mapping from SEC files"""
        cik_to_ticker = {}
        
        # Load from ticker.txt
        ticker_file = '/home/hvksh/investing/data/ticker.txt'
        if Path(ticker_file).exists():
            with open(ticker_file, 'r') as f:
                for line in f:
                    if '\t' in line:
                        ticker, cik = line.strip().split('\t')
                        cik_to_ticker[cik] = ticker.upper()
        
        # Load from company_tickers.json
        company_file = '/home/hvksh/investing/data/company_tickers.json'
        if Path(company_file).exists():
            with open(company_file, 'r') as f:
                data = json.load(f)
                for key, company in data.items():
                    if 'cik_str' in company and 'ticker' in company:
                        cik = str(company['cik_str'])
                        ticker = company['ticker'].upper()
                        if cik not in cik_to_ticker:
                            cik_to_ticker[cik] = ticker
        
        return cik_to_ticker
    
    def build_cusip_to_ticker_mapping(self, cusip_to_cik: Dict[str, str]) -> Dict[str, str]:
        """Build CUSIP-to-ticker mapping using CIK as intermediary"""
        cik_to_ticker = self.load_ticker_mapping()
        cusip_to_ticker = {}
        
        for cusip, cik in cusip_to_cik.items():
            if cik in cik_to_ticker:
                cusip_to_ticker[cusip] = cik_to_ticker[cik]
        
        logger.info(f"Built CUSIP-to-ticker mapping with {len(cusip_to_ticker)} entries")
        return cusip_to_ticker

def main():
    """Build current CUSIP-CIK mapping from recent SEC filings"""
    mapper = CusipCikMapper()
    
    # Build mapping from recent filings - look back 6 months for more coverage
    logger.info("Building CUSIP-CIK mapping from recent SEC filings (6 months)...")
    cusip_to_cik = mapper.build_mapping_from_recent_filings(months_back=6)
    
    # Save CIK mapping
    mapper.save_mapping(cusip_to_cik, '/home/hvksh/investing/data/cusip_to_cik.json')
    
    # Build and save ticker mapping
    cusip_to_ticker = mapper.build_cusip_to_ticker_mapping(cusip_to_cik)
    mapper.save_mapping(cusip_to_ticker, '/home/hvksh/investing/data/cusip_to_ticker.json')
    
    # Show statistics
    logger.info("\n=== Mapping Statistics ===")
    logger.info(f"CUSIP-to-CIK mappings: {len(cusip_to_cik)}")
    logger.info(f"CUSIP-to-ticker mappings: {len(cusip_to_ticker)}")
    
    # Show sample mappings
    if cusip_to_ticker:
        logger.info("\nSample CUSIP-to-ticker mappings:")
        for cusip, ticker in list(cusip_to_ticker.items())[:10]:
            cik = cusip_to_cik.get(cusip, 'Unknown')
            logger.info(f"  {cusip} -> CIK {cik} -> {ticker}")

if __name__ == "__main__":
    main()