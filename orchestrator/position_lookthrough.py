#!/usr/bin/env python3
"""
Position Look-Through Analysis for Concentration Risk
Aggregates exposure to individual companies across all holdings (direct + fund holdings)
"""

import logging
from typing import Dict, List, Tuple, Any
import yfinance as yf
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class ConcentrationResult:
    """Result of concentration analysis"""
    passed: bool
    max_concentration: float
    max_concentration_symbol: str
    violations: List[Tuple[str, float]]  # List of (symbol, concentration) exceeding limit
    details: Dict[str, Any]
    
class PositionLookthrough:
    """
    Analyzes true concentration risk by looking through ETF/mutual fund holdings
    to aggregate exposure to individual companies
    """
    
    # ETF/Fund types that need look-through analysis
    FUND_TYPES = {'ETF', 'MUTUALFUND', 'CEF'}  # Closed-End Fund
    
    # Broad market ETFs EXEMPT from single-position concentration limits
    BROAD_MARKET_ETFS = {
        'VTI',   # Vanguard Total Stock Market
        'VOO',   # Vanguard S&P 500
        'SPY',   # SPDR S&P 500
        'IVV',   # iShares Core S&P 500
        'VT',    # Vanguard Total World Stock
        'VXUS',  # Vanguard Total International Stock
        'IXUS',  # iShares Core MSCI Total International
        'ACWI',  # iShares MSCI ACWI
        'URTH',  # iShares MSCI World
        'ITOT',  # iShares Core S&P Total Market
        'SCHB',  # Schwab US Broad Market
        'VEA',   # Vanguard Developed Markets
        'VWO',   # Vanguard Emerging Markets
        'IEFA',  # iShares Core MSCI EAFE
        'EFA',   # iShares MSCI EAFE
        'IEMG',  # iShares Core MSCI Emerging Markets
    }
    
    # Cache for fund holdings to avoid repeated API calls
    _holdings_cache = {}
    
    def __init__(self, concentration_limit: float = 0.10):
        """
        Initialize with concentration limit
        
        Args:
            concentration_limit: Maximum allowed concentration in any single company (default 10%)
        """
        self.concentration_limit = concentration_limit
        # Initialize mappings on first use
        self._cik_to_ticker = None
        self._ticker_to_cik = None
        
    def get_fund_holdings(self, symbol: str) -> Dict[str, float]:
        """
        Get holdings of an ETF or mutual fund using OpenBB SDK
        
        Args:
            symbol: Fund ticker symbol
            
        Returns:
            Dictionary of {holding_symbol: weight_in_fund}
        """
        # Check cache first
        if symbol in self._holdings_cache:
            return self._holdings_cache[symbol]
            
        holdings = {}
        try:
            # First check if it's a fund using yfinance
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Check if it's a fund
            quote_type = info.get('quoteType', '')
            if quote_type not in self.FUND_TYPES:
                # Not a fund, return empty holdings
                return {}
                
            # Use OpenBB SDK with SEC provider only (tested and working)
            from openbb import obb
            
            provider = 'sec'  # Standardize on SEC provider
            last_error = None
            
            try:
                logger.info(f"Using SEC provider for {symbol} holdings")
                
                result = obb.etf.holdings(symbol=symbol, provider=provider)
                
                if result and hasattr(result, 'results') and result.results:
                    # Process OpenBB response
                    for holding in result.results[:100]:  # Top 100 holdings
                        # Get holding identifier
                        holding_id = None
                        
                        # For SEC provider, use CUSIP to get ticker
                        if hasattr(holding, 'cusip') and holding.cusip:
                            # Map CUSIP to ticker using our comprehensive mapping
                            holding_id = self._map_sec_holding_to_ticker(holding)
                        
                        if holding_id:
                            # SEC provider uses 'weight' field
                            weight = getattr(holding, 'weight', 0)
                            
                            # Convert percentage to decimal if needed
                            if weight > 1:
                                weight = weight / 100.0
                                
                            if weight > 0:
                                holdings[holding_id] = weight
                    
                    if holdings:
                        logger.info(f"✅ Got {len(holdings)} holdings for {symbol} from SEC")
                else:
                    logger.warning(f"SEC provider returned no data for {symbol}")
                    
            except Exception as e:
                error_str = str(e)
                logger.warning(f"SEC provider failed for {symbol}: {error_str[:100]}")
                last_error = e
            
            # If SEC provider didn't work, log but don't fail (some funds don't have SEC data)
            if not holdings and last_error:
                logger.warning(f"Could not get ETF holdings for {symbol} from SEC: {last_error}")
                # Return empty holdings rather than failing
                return {}
                
        except Exception as e:
            logger.warning(f"Could not get holdings for {symbol}: {e}")
            
        # Cache the result
        self._holdings_cache[symbol] = holdings
        return holdings
    
    def get_fund_holdings_from_mcp(self, symbol: str, mcp_holdings_data: List[Dict]) -> Dict[str, float]:
        """
        Process ETF holdings data from MCP tool response
        
        Args:
            symbol: Fund ticker symbol
            mcp_holdings_data: Response from mcp__openbb-curated__etf_holdings
            
        Returns:
            Dictionary of {holding_symbol: weight_in_fund}
        """
        holdings = {}
        
        # Process MCP response format
        # Expected format: List of holdings with 'symbol' and 'weight' fields
        for holding in mcp_holdings_data:
            if isinstance(holding, dict):
                holding_symbol = holding.get('symbol', '')
                weight = holding.get('weight', 0.0)
                
                # Convert percentage to decimal if needed
                if weight > 1:
                    weight = weight / 100.0
                    
                if holding_symbol and weight > 0:
                    holdings[holding_symbol] = weight
        
        # Cache the result
        self._holdings_cache[symbol] = holdings
        logger.info(f"Processed {len(holdings)} holdings for {symbol} from MCP data")
        
        return holdings
        
        
    def _map_sec_holding_to_ticker(self, holding) -> str:
        """
        Map SEC holding data to ticker symbol using CUSIP-based matching
        
        Args:
            holding: SEC holding object with cusip field
            
        Returns:
            Ticker symbol or identifier
        """
        # CUSIP-based matching (only method)
        if hasattr(holding, 'cusip') and holding.cusip:
            ticker = self._cusip_to_ticker_lookup(holding.cusip)
            if ticker:
                logger.debug(f"CUSIP match: {holding.cusip[:6]} -> {ticker}")
                return ticker
            else:
                # Use CUSIP prefix as identifier if no mapping found
                logger.debug(f"No CUSIP match for {holding.cusip[:6]}")
                return f"CUSIP:{holding.cusip[:6]}"
        
        return "UNKNOWN"
    
    
    def _initialize_cik_ticker_mappings(self):
        """
        Initialize CIK-to-ticker and ticker-to-CIK mappings from SEC files
        """
        import os
        
        if self._cik_to_ticker is not None:
            return  # Already initialized
        
        self._cik_to_ticker = {}
        self._ticker_to_cik = {}
        
        # Load ticker.txt (ticker -> CIK mapping)
        ticker_file = '/home/hvksh/investing/data/ticker.txt'
        if os.path.exists(ticker_file):
            try:
                with open(ticker_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and '\t' in line:
                            ticker, cik = line.split('\t')
                            ticker = ticker.upper()
                            self._ticker_to_cik[ticker] = cik
                            self._cik_to_ticker[cik] = ticker
                
                logger.info(f"✅ Loaded {len(self._cik_to_ticker)} CIK-to-ticker mappings from ticker.txt")
            except Exception as e:
                logger.error(f"Failed to load ticker.txt: {e}")
        
        # Also load from company_tickers.json for additional mappings
        company_file = '/home/hvksh/investing/data/company_tickers.json'
        if os.path.exists(company_file):
            try:
                import json
                with open(company_file, 'r') as f:
                    company_data = json.load(f)
                
                for key, company in company_data.items():
                    if 'cik_str' in company and 'ticker' in company:
                        cik = str(company['cik_str'])
                        ticker = company['ticker'].upper()
                        # Only add if not already present (ticker.txt takes precedence)
                        if cik not in self._cik_to_ticker:
                            self._cik_to_ticker[cik] = ticker
                        if ticker not in self._ticker_to_cik:
                            self._ticker_to_cik[ticker] = cik
                
                logger.info(f"✅ Total CIK-to-ticker mappings: {len(self._cik_to_ticker)}")
            except Exception as e:
                logger.error(f"Failed to load company_tickers.json: {e}")
    
    def _cik_to_ticker_lookup(self, cik: str) -> str:
        """
        Look up ticker by CIK number
        
        Args:
            cik: CIK number (as string)
            
        Returns:
            Ticker symbol or None
        """
        if self._cik_to_ticker is None:
            self._initialize_cik_ticker_mappings()
        
        # Try with and without leading zeros
        cik_clean = str(int(cik))  # Remove leading zeros
        
        # Try exact match
        if cik in self._cik_to_ticker:
            return self._cik_to_ticker[cik]
        
        # Try without leading zeros
        if cik_clean in self._cik_to_ticker:
            return self._cik_to_ticker[cik_clean]
        
        # Try with 10-digit padding (SEC standard)
        cik_padded = cik.zfill(10)
        if cik_padded in self._cik_to_ticker:
            return self._cik_to_ticker[cik_padded]
        
        return None
    
    def _cusip_to_ticker_lookup(self, cusip: str) -> str:
        """
        Look up ticker by CUSIP (using issuer prefix)
        Uses our generated CUSIP-to-ticker mapping from SEC filings
        
        Args:
            cusip: CUSIP identifier
            
        Returns:
            Ticker symbol or None
        """
        if not hasattr(self, '_cusip_to_ticker'):
            self._load_cusip_mappings()
        
        if not cusip or len(cusip) < 6:
            return None
        
        # Use first 6 characters (issuer identifier)
        cusip_prefix = cusip[:6].upper()
        
        # Try direct CUSIP-to-ticker mapping
        if cusip_prefix in self._cusip_to_ticker:
            return self._cusip_to_ticker[cusip_prefix]
        
        # Try via CUSIP-to-CIK-to-ticker
        if cusip_prefix in self._cusip_to_cik:
            cik = self._cusip_to_cik[cusip_prefix]
            ticker = self._cik_to_ticker_lookup(cik)
            if ticker:
                return ticker
        
        return None
    
    def _load_cusip_mappings(self):
        """
        Load CUSIP-to-ticker and CUSIP-to-CIK mappings
        """
        import json
        import os
        
        self._cusip_to_ticker = {}
        self._cusip_to_cik = {}
        
        # Load direct CUSIP-to-ticker mapping
        cusip_ticker_file = '/home/hvksh/investing/data/cusip_to_ticker.json'
        if os.path.exists(cusip_ticker_file):
            try:
                with open(cusip_ticker_file, 'r') as f:
                    self._cusip_to_ticker = json.load(f)
                logger.info(f"✅ Loaded {len(self._cusip_to_ticker)} CUSIP-to-ticker mappings")
            except Exception as e:
                logger.error(f"Failed to load CUSIP-to-ticker mapping: {e}")
        
        # Load CUSIP-to-CIK mapping
        cusip_cik_file = '/home/hvksh/investing/data/cusip_to_cik.json'
        if os.path.exists(cusip_cik_file):
            try:
                with open(cusip_cik_file, 'r') as f:
                    self._cusip_to_cik = json.load(f)
                logger.info(f"✅ Loaded {len(self._cusip_to_cik)} CUSIP-to-CIK mappings")
            except Exception as e:
                logger.error(f"Failed to load CUSIP-to-CIK mapping: {e}")
    
    
    def is_fund(self, symbol: str) -> bool:
        """
        Check if a symbol is an ETF or mutual fund
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            True if the symbol is a fund
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            quote_type = info.get('quoteType', '')
            return quote_type in self.FUND_TYPES
        except:
            return False
            
    def calculate_concentration(self, portfolio: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate true concentration across all holdings
        
        Args:
            portfolio: Dictionary of {symbol: weight_in_portfolio}
            
        Returns:
            Dictionary of {underlying_symbol: total_concentration}
        """
        # Aggregate exposure to each underlying company
        company_exposure = defaultdict(float)
        
        for symbol, weight in portfolio.items():
            if self.is_fund(symbol):
                # Get fund holdings and calculate weighted exposure
                holdings = self.get_fund_holdings(symbol)
                for holding_symbol, holding_weight in holdings.items():
                    # Total exposure = portfolio weight * weight in fund
                    company_exposure[holding_symbol] += weight * holding_weight
                    logger.debug(f"{symbol} ({weight:.2%}) holds {holding_symbol} at {holding_weight:.2%} "
                               f"= {weight * holding_weight:.3%} exposure")
            else:
                # Direct holding
                company_exposure[symbol] += weight
                logger.debug(f"Direct holding: {symbol} = {weight:.2%}")
                
        return dict(company_exposure)
        
    def check_concentration_limits(self, portfolio: Dict[str, float]) -> ConcentrationResult:
        """
        Check if portfolio meets concentration limits
        Broad market ETFs are EXEMPT from single-position limits
        
        Args:
            portfolio: Dictionary of {symbol: weight_in_portfolio}
            
        Returns:
            ConcentrationResult with pass/fail and details
        """
        # Separate broad market ETFs from other positions
        broad_market_positions = {}
        other_positions = {}
        
        for ticker, weight in portfolio.items():
            if ticker.upper() in self.BROAD_MARKET_ETFS:
                broad_market_positions[ticker] = weight
            else:
                other_positions[ticker] = weight
        
        # Calculate true concentration only for non-broad-market positions
        company_exposure = self.calculate_concentration(other_positions)
        
        # Find violations
        violations = []
        max_concentration = 0
        max_symbol = ""
        
        for symbol, concentration in company_exposure.items():
            if concentration > max_concentration:
                max_concentration = concentration
                max_symbol = symbol
                
            if concentration > self.concentration_limit:
                violations.append((symbol, concentration))
                logger.warning(f"Concentration violation: {symbol} = {concentration:.2%} "
                             f"exceeds {self.concentration_limit:.2%} limit")
                
        # Sort violations by concentration (highest first)
        violations.sort(key=lambda x: x[1], reverse=True)
        
        passed = len(violations) == 0
        
        return ConcentrationResult(
            passed=passed,
            max_concentration=max_concentration,
            max_concentration_symbol=max_symbol,
            violations=violations,
            details={
                'company_exposures': company_exposure,
                'limit': self.concentration_limit,
                'total_companies': len(company_exposure),
                'companies_over_5pct': sum(1 for c in company_exposure.values() if c > 0.05),
                'broad_market_etfs': broad_market_positions,
                'broad_market_total_weight': sum(broad_market_positions.values()),
                'broad_market_exempt': True
            }
        )
        
    def get_concentration_report(self, portfolio: Dict[str, float]) -> str:
        """
        Generate a human-readable concentration report
        
        Args:
            portfolio: Dictionary of {symbol: weight_in_portfolio}
            
        Returns:
            Formatted report string
        """
        result = self.check_concentration_limits(portfolio)
        
        report = "# Concentration Risk Analysis (Look-Through)\n\n"
        
        # Show broad market ETF exemption
        if result.details.get('broad_market_etfs'):
            broad_market_weight = result.details.get('broad_market_total_weight', 0)
            report += f"📊 **Broad Market ETFs**: {broad_market_weight:.1%} (EXEMPT from concentration limits)\n"
            for etf, weight in result.details['broad_market_etfs'].items():
                report += f"  - {etf}: {weight:.2%}\n"
            report += "\n"
        
        if result.passed:
            report += f"✅ **PASSED**: No single company exceeds {self.concentration_limit:.1%} limit\n\n"
        else:
            report += f"❌ **FAILED**: {len(result.violations)} companies exceed {self.concentration_limit:.1%} limit\n\n"
            
        report += f"**Maximum Single-Name Concentration**: {result.max_concentration_symbol} at {result.max_concentration:.2%}\n\n"
        
        if result.violations:
            report += "## Violations\n"
            for symbol, concentration in result.violations:
                report += f"- {symbol}: {concentration:.2%} (exceeds by {concentration - self.concentration_limit:.2%})\n"
            report += "\n"
            
        # Top exposures
        exposures = result.details['company_exposures']
        top_exposures = sorted(exposures.items(), key=lambda x: x[1], reverse=True)[:10]
        
        report += "## Top 10 Company Exposures (After Look-Through)\n"
        for symbol, concentration in top_exposures:
            status = "⚠️" if concentration > self.concentration_limit else "✓"
            report += f"{status} {symbol}: {concentration:.2%}\n"
            
        report += f"\n**Total Companies**: {result.details['total_companies']}\n"
        report += f"**Companies > 5%**: {result.details['companies_over_5pct']}\n"
        
        return report