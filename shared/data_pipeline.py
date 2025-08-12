#!/usr/bin/env python3
"""
Market Data Pipeline using OpenBB
Provides real-time market data with quality scoring
Replaces synthetic data injection pattern
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
import logging
from scipy import stats
import warnings
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from shared.logging_utils import get_library_logger

# Get logger without side effects
logger = get_library_logger(__name__)
logger = logging.getLogger("data_pipeline")

class DataQualityScorer:
    """Evaluates data quality and provides confidence metrics"""
    
    def __init__(self):
        self.min_sample_size = 252  # 1 year of trading days
        self.max_condition_number = 1000
        self.outlier_threshold = 3  # MAD multiplier
    
    def score_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Comprehensive data quality assessment
        Returns quality score and detailed diagnostics
        """
        issues = []
        scores = {}
        
        # Sample size adequacy
        sample_size = len(data)
        scores['sample_adequacy'] = min(1.0, sample_size / self.min_sample_size)
        if sample_size < self.min_sample_size:
            issues.append(f"Small sample: {sample_size} days (recommend {self.min_sample_size}+)")
        
        # Missing data check
        missing_pct = data.isnull().sum().sum() / data.size
        scores['completeness'] = 1.0 - missing_pct
        if missing_pct > 0.01:
            issues.append(f"Missing data: {missing_pct:.1%}")
        
        # Stationarity test (ADF)
        try:
            from statsmodels.tsa.stattools import adfuller
            returns = data.pct_change().dropna()
            
            # Check if we have enough data for stationarity test
            if len(returns) < 10 or (hasattr(returns, 'empty') and returns.empty):
                logger.warning("Insufficient data for stationarity test")
                scores['stationarity'] = 0.5  # Neutral score
                issues.append("Insufficient data for stationarity test")
            else:
                adf_pvalues = []
                for col in returns.columns:
                    col_data = returns[col].dropna()
                    if len(col_data) < 10:  # Skip columns with insufficient data
                        continue
                    try:
                        result = adfuller(col_data)
                        adf_pvalues.append(result[1])
                    except Exception as col_error:
                        logger.warning(f"Stationarity test failed for {col}: {col_error}")
                        continue
                
                if adf_pvalues:
                    stationary_pct = sum(p < 0.05 for p in adf_pvalues) / len(adf_pvalues)
                    scores['stationarity'] = stationary_pct
                    if stationary_pct < 0.8:
                        issues.append(f"Non-stationary series detected ({(1-stationary_pct):.0%})")
                else:
                    scores['stationarity'] = 0.5  # Neutral if no valid tests
                    issues.append("Could not perform stationarity tests")
        except ImportError:
            logger.warning("statsmodels not available for stationarity test")
            scores['stationarity'] = 0.5  # Neutral score
            issues.append("Stationarity test unavailable")
        except Exception as e:
            logger.warning(f"Stationarity test error: {e}")
            scores['stationarity'] = 0.5  # Don't fail, just warn
            issues.append(f"Stationarity test incomplete: {str(e)[:50]}")
            
        # Outlier detection using MAD
        outlier_counts = []
        for col in data.columns:
            series = data[col].dropna()
            median = series.median()
            mad = np.median(np.abs(series - median))
            if mad > 0:
                outliers = np.abs(series - median) > (self.outlier_threshold * mad)
                outlier_counts.append(outliers.sum())
        
        outlier_pct = sum(outlier_counts) / (len(data) * len(data.columns))
        scores['outlier_free'] = max(0, 1.0 - outlier_pct * 10)  # Penalize heavily
        if outlier_pct > 0.01:
            issues.append(f"Outliers detected: {outlier_pct:.1%} of data points")
        
        # Correlation matrix conditioning
        if len(data.columns) > 1:
            returns = data.pct_change().dropna()
            corr_matrix = returns.corr()
            eigenvalues = np.linalg.eigvals(corr_matrix)
            condition_number = max(eigenvalues) / min(eigenvalues) if min(eigenvalues) > 0 else float('inf')
            
            scores['matrix_stability'] = 1.0 / (1.0 + condition_number / self.max_condition_number)
            if condition_number > self.max_condition_number:
                issues.append(f"High condition number: {condition_number:.0f}")
        else:
            scores['matrix_stability'] = 1.0
        
        # Calculate overall score
        weights = {
            'sample_adequacy': 0.25,
            'completeness': 0.20,
            'stationarity': 0.15,
            'outlier_free': 0.20,
            'matrix_stability': 0.20
        }
        
        overall_score = sum(scores.get(k, 0) * v for k, v in weights.items())
        
        return {
            'overall_score': round(overall_score, 3),
            'components': {k: round(v, 3) for k, v in scores.items()},
            'issues': issues,
            'sample_size': sample_size,
            'condition_number': condition_number if 'condition_number' in locals() else None
        }

class MarketDataPipeline:
    """
    Production-grade market data pipeline using OpenBB
    Replaces synthetic data with real market data
    """
    
    # Invalid tickers to exclude
    INVALID_TICKERS = ['TEST', 'DUMMY', 'MOCK', 'SAMPLE', 'EXAMPLE']
    
    def __init__(self, cache_ttl_minutes: int = 15, portfolio_state_client=None):
        self.cache = {}
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.quality_scorer = DataQualityScorer()
        self.ticker_cache = {}  # Cache for resolved ticker symbols
        self.portfolio_state_client = portfolio_state_client  # For unified data access
        
        # Import shared cache manager for cross-server caching
        try:
            from cache_manager import get_shared_cache
            self.shared_cache = get_shared_cache(ttl_seconds=cache_ttl_minutes * 60)
            logger.info("Using shared cache manager for cross-server data sharing")
        except ImportError:
            self.shared_cache = None
            logger.info("Shared cache not available, using local cache only")
        
        # Lazy initialization - OpenBB will be loaded on first use
        self._obb = None
        self.use_openbb = None  # Will be determined on first access
        
        # Import yfinance for equity data (OpenBB will be used for treasury rates)
        try:
            import yfinance as yf
            import re
            self.yf = yf
            self.re = re
            self.yf_available = True
            # Check yfinance version for compatibility
            import pkg_resources
            yf_version = pkg_resources.get_distribution("yfinance").version
            logger.info(f"Using yfinance version {yf_version}")
        except ImportError:
            self.yf_available = False
            logger.warning("yfinance not available")
    
    @property
    def obb(self):
        """Lazy initialization of OpenBB - loads on first access with current environment"""
        if self._obb is None:
            try:
                from openbb import obb
                self._obb = obb
                self.use_openbb = True
                logger.info("OpenBB loaded successfully")
            except ImportError:
                logger.warning("OpenBB not available, falling back to yfinance")
                self.use_openbb = False
                if not self.yf_available:
                    raise ImportError("Neither OpenBB nor yfinance available. Install with: pip install openbb or pip install yfinance")
        return self._obb
    
    def _get_cache_key(self, tickers: List[str], start_date: str, end_date: str) -> str:
        """Generate cache key for data request"""
        return f"{','.join(sorted(tickers))}_{start_date}_{end_date}"
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cached data is still valid"""
        if not cache_entry:
            return False
        return datetime.now(timezone.utc) - cache_entry['timestamp'] < self.cache_ttl
    
    def resolve_ticker(self, ticker: str) -> Optional[str]:
        """
        Resolve ticker symbol using fuzzy matching to handle format variations.
        Tries multiple formats to find a working ticker symbol for Yahoo Finance.
        """
        # Check cache first
        if ticker in self.ticker_cache:
            return self.ticker_cache[ticker]
        
        # Skip invalid tickers
        if ticker.upper() in self.INVALID_TICKERS or ticker in ['CASH', 'VMFXX', 'N/A']:
            return None
        
        if not self.yf_available:
            # Can't resolve without yfinance
            return ticker
        
        # Common ticker format variations to try
        variations = [
            ticker,                          # Original
            ticker.replace('B', '-B'),       # BRKB -> BRK-B
            ticker.replace('A', '-A'),       # BRKA -> BRK-A
            ticker.replace('.', '-'),        # BRK.B -> BRK-B
            ticker.replace('_', '-'),        # BRK_B -> BRK-B
            ticker.replace('-', '.'),        # BRK-B -> BRK.B
            ticker.replace(' ', ''),         # Remove spaces
            self.re.sub(r'([A-Z]+)([A-Z])$', r'\1-\2', ticker) if self.re else ticker,  # Split last letter
        ]
        
        # Try each variation
        for variant in variations:
            try:
                test_ticker = self.yf.Ticker(variant)
                hist = test_ticker.history(period='5d')
                if not hist.empty:
                    # Found working ticker
                    logger.info(f"Resolved ticker {ticker} -> {variant}")
                    self.ticker_cache[ticker] = variant
                    return variant
            except Exception:
                continue
        
        logger.warning(f"Could not resolve ticker: {ticker}")
        return None
    
    def fetch_equity_data(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = 'daily'
    ) -> Dict[str, Any]:
        """
        Fetch real equity market data with quality assessment
        
        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD), defaults to 2 years ago
            end_date: End date (YYYY-MM-DD), defaults to today
            interval: Data frequency ('daily', 'weekly', 'monthly')
        
        Returns:
            Dictionary with data, returns, quality scores, and metadata
        """
        # Default dates
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now(timezone.utc) - timedelta(days=504)).strftime('%Y-%m-%d')  # 2 years
        
        # Resolve ticker aliases for Yahoo Finance compatibility
        original_tickers = tickers.copy()
        resolved_tickers = []
        ticker_map = {}  # Map resolved back to original
        
        for ticker in tickers:
            resolved = self.resolve_ticker(ticker)
            if resolved:
                resolved_tickers.append(resolved)
                ticker_map[resolved] = ticker
            else:
                logger.warning(f"Could not resolve ticker {ticker}, skipping")
        
        if not resolved_tickers:
            raise ValueError(f"Could not resolve any tickers from {tickers}")
        
        # Use resolved tickers for fetching
        tickers_to_fetch = resolved_tickers
        
        # Check shared cache first if available
        if self.shared_cache:
            # Try to get prices from shared cache
            cached_prices = self.shared_cache.get_prices(tickers)
            if cached_prices:
                logger.info(f"Found {len(cached_prices)} prices in shared cache")
        
        # Check local cache (use original tickers for cache key)
        cache_key = self._get_cache_key(original_tickers, start_date, end_date)
        if cache_key in self.cache and self._is_cache_valid(self.cache[cache_key]):
            logger.info(f"Using cached data for {original_tickers}")
            return self.cache[cache_key]['data']
        
        # Try Portfolio State Server for current prices (if client provided and fetching recent data)
        portfolio_prices = {}
        if self.portfolio_state_client and end_date == datetime.now(timezone.utc).strftime('%Y-%m-%d'):
            try:
                logger.info("Checking Portfolio State Server for current prices...")
                # Use asyncio to call async method if needed
                import asyncio
                async def get_ps_prices():
                    async with self.portfolio_state_client:
                        result = await self.portfolio_state_client.call_tool("get_portfolio_state", {})
                        if result.data and result.data.get('positions'):
                            prices = {}
                            for pos in result.data['positions']:
                                if isinstance(pos, dict) and pos.get('symbol') in tickers:
                                    prices[pos['symbol']] = pos.get('current_price', 0)
                            return prices
                    return {}
                
                # Run async function if we're not already in an async context
                try:
                    portfolio_prices = asyncio.run(get_ps_prices())
                    if portfolio_prices:
                        logger.info(f"Got {len(portfolio_prices)} prices from Portfolio State Server")
                        # Cache these prices in shared cache
                        if self.shared_cache:
                            self.shared_cache.set_prices(portfolio_prices)
                except RuntimeError:
                    # Already in async context, just log and continue
                    logger.debug("Could not fetch from Portfolio State in sync context")
            except Exception as e:
                logger.warning(f"Could not fetch prices from Portfolio State: {e}")
        
        try:
            # Try to use OpenBB first (lazy load via property)
            if self.obb is not None:  # This will trigger lazy loading
                try:
                    # Use OpenBB for data fetching (with resolved tickers)
                    data = self.obb.equity.price.historical(
                        symbol=tickers_to_fetch,
                        start=start_date,
                        end=end_date,
                        provider='yfinance'  # Can switch providers
                    )
                    prices_df = pd.DataFrame(data.results)
                    prices_df = prices_df.pivot(index='date', columns='symbol', values='close')
                except Exception as openbb_error:
                    logger.warning(f"OpenBB fetch failed: {openbb_error}, falling back to direct yfinance")
                    self.use_openbb = False  # Fallback for this request
            
            if not self.use_openbb and self.yf_available:
                # Fallback to yfinance (with resolved tickers)
                if len(tickers_to_fetch) == 1:
                    # Single ticker - download directly
                    data = self.yf.download(
                        tickers_to_fetch[0],
                        start=start_date,
                        end=end_date,
                        progress=False
                    )
                    # Check if we got any data
                    if data is None:
                        raise ValueError(f"No data available for {tickers[0]} in the specified date range")
                    elif hasattr(data, 'empty') and data.empty:
                        raise ValueError(f"No data available for {tickers[0]} in the specified date range")
                    elif isinstance(data, pd.DataFrame) and data.isna().all().all():
                        raise ValueError(f"No valid data available for {tickers[0]} (all NaN values)")
                    
                    # yfinance returns MultiIndex even for single ticker!
                    if isinstance(data.columns, pd.MultiIndex):
                        # Extract 'Adj Close' or 'Close' prices
                        if 'Adj Close' in data.columns.levels[0]:
                            prices_df = data['Adj Close']
                            # For single ticker, this will be a Series, convert to DataFrame
                            if isinstance(prices_df, pd.Series):
                                prices_df = prices_df.to_frame(tickers[0])
                            elif len(prices_df.columns) == 1:
                                prices_df.columns = tickers
                        elif 'Close' in data.columns.levels[0]:
                            prices_df = data['Close']
                            # For single ticker, this will be a Series, convert to DataFrame
                            if isinstance(prices_df, pd.Series):
                                prices_df = prices_df.to_frame(tickers[0])
                            elif len(prices_df.columns) == 1:
                                prices_df.columns = tickers
                        else:
                            raise ValueError("No price data found in yfinance response")
                    elif isinstance(data, pd.DataFrame):
                        # Non-MultiIndex DataFrame (shouldn't happen with yfinance, but handle it)
                        if 'Adj Close' in data.columns:
                            prices_df = data[['Adj Close']].rename(columns={'Adj Close': tickers[0]})
                        elif 'Close' in data.columns:
                            prices_df = data[['Close']].rename(columns={'Close': tickers[0]})
                        else:
                            prices_df = data
                    else:
                        # Single series result
                        prices_df = pd.DataFrame({tickers[0]: data})
                else:
                    # Multiple tickers - handle MultiIndex
                    data = self.yf.download(
                        tickers_to_fetch,
                        start=start_date,
                        end=end_date,
                        progress=False
                    )
                    # Check if we got any data
                    if data is None:
                        raise ValueError(f"No data available for {tickers} in the specified date range")
                    elif hasattr(data, 'empty') and data.empty:
                        raise ValueError(f"No data available for {tickers} in the specified date range")
                    elif isinstance(data, pd.DataFrame) and data.isna().all().all():
                        raise ValueError(f"No valid data available for {tickers} (all NaN values)")
                    
                    # yfinance returns MultiIndex columns for multiple tickers
                    if isinstance(data.columns, pd.MultiIndex):
                        # Extract 'Adj Close' or 'Close' prices
                        if 'Adj Close' in data.columns.levels[0]:
                            prices_df = data['Adj Close']
                        elif 'Close' in data.columns.levels[0]:
                            prices_df = data['Close']
                        else:
                            raise ValueError("No price data found in yfinance response")
                    else:
                        # Single ticker returned as regular columns
                        if 'Adj Close' in data.columns:
                            prices_df = data[['Adj Close']]
                        else:
                            prices_df = data[['Close']]
                        prices_df.columns = tickers
                
                # Ensure we have a DataFrame with ticker columns
                if isinstance(prices_df, pd.Series):
                    prices_df = prices_df.to_frame(tickers[0] if tickers else 'UNKNOWN')
            
            # Map columns back to original ticker names
            if len(ticker_map) > 0:
                # Rename columns from resolved (e.g., BRK-B) to original (e.g., BRKB)
                column_mapping = {resolved: original for resolved, original in ticker_map.items()}
                prices_df = prices_df.rename(columns=column_mapping)
                # Update tickers to use original names
                tickers = original_tickers
            
            # Calculate returns
            returns_df = prices_df.pct_change().dropna()
            
            # Log-returns for better statistical properties
            log_returns_df = np.log(prices_df / prices_df.shift(1)).dropna()
            
            # Quality assessment
            quality_report = self.quality_scorer.score_data(prices_df)
            
            # Prepare result
            result = {
                'prices': prices_df,
                'returns': returns_df,
                'log_returns': log_returns_df,
                'metadata': {
                    'tickers': tickers,
                    'start_date': start_date,
                    'end_date': end_date,
                    'interval': interval,
                    'source': 'OpenBB' if self.use_openbb else 'yfinance',
                    'fetch_time': datetime.now(timezone.utc).isoformat()
                },
                'quality': quality_report,
                'statistics': {
                    'mean_returns': returns_df.mean().to_dict(),
                    'volatility': returns_df.std().to_dict(),
                    'correlation_matrix': returns_df.corr().values.tolist(),
                    'sample_size': len(returns_df)
                }
            }
            
            # Cache the result locally
            self.cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now(timezone.utc)
            }
            
            # Also save current prices to shared cache
            if self.shared_cache and not (hasattr(prices_df, 'empty') and prices_df.empty):
                latest_prices = {}
                for ticker in tickers:
                    # Check if prices_df is a DataFrame with columns
                    if isinstance(prices_df, pd.DataFrame) and ticker in prices_df.columns:
                        latest_price = prices_df[ticker].iloc[-1]
                        if not pd.isna(latest_price):
                            latest_prices[ticker] = float(latest_price)
                    elif isinstance(prices_df, pd.Series) and len(tickers) == 1:
                        # Single ticker case - prices_df is a Series
                        latest_price = prices_df.iloc[-1]
                        if not pd.isna(latest_price):
                            latest_prices[ticker] = float(latest_price)
                
                if latest_prices:
                    self.shared_cache.set_prices(latest_prices)
                    logger.info(f"Saved {len(latest_prices)} prices to shared cache")
            
            logger.info(f"Fetched {len(prices_df)} days of data for {tickers}, quality score: {quality_report['overall_score']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch equity data: {str(e)}")
            raise ValueError(f"Data fetch failed: {str(e)}")
    
    def get_risk_free_rate(self, maturity: str = '10y') -> Dict[str, Any]:
        """
        Fetch current risk-free rate from Treasury data using OpenBB
        
        Args:
            maturity: Treasury maturity ('3m', '6m', '1y', '2y', '5y', '10y', '30y')
        
        Returns:
            Dictionary with rate and metadata
        """
        try:
            # Try to access OpenBB (will trigger lazy loading)
            if self.obb is not None:
                # Map common maturity formats to OpenBB/FRED format
                maturity_map = {
                    '3m': '3month',
                    '6m': '6month', 
                    '1y': '1year',
                    '2y': '2year',
                    '5y': '5year',
                    '10y': '10year',
                    '30y': '30year'
                }
                
                obb_maturity = maturity_map.get(maturity, maturity)
                
                try:
                    # Fetch treasury rates data from OpenBB
                    logger.info(f"Fetching treasury rates from OpenBB for {maturity} rate")
                    
                    # Get date range
                    end_date = datetime.now(timezone.utc)
                    start_date = end_date - timedelta(days=30)  # Get last month's data
                    
                    # Try Federal Reserve provider (the correct name, not 'fred')
                    try:
                        treasury_data = self.obb.fixedincome.government.treasury_rates(
                            start_date=start_date.strftime('%Y-%m-%d'),
                            end_date=end_date.strftime('%Y-%m-%d'),
                            provider='federal_reserve'
                        )
                    except Exception as fed_error:
                        # NO FALLBACK - fail loudly if Federal Reserve data unavailable
                        logger.error(f"Federal Reserve treasury rates failed: {fed_error}")
                        raise ValueError(f"Unable to fetch treasury rates from Federal Reserve: {fed_error}")
                    
                    if treasury_data and hasattr(treasury_data, 'results') and treasury_data.results:
                        # Get the latest treasury rates
                        latest_rates = treasury_data.results[-1] if treasury_data.results else None
                        
                        if latest_rates:
                            # Map maturity to treasury rate field
                            maturity_field_map = {
                                '3m': 'month_3',
                                '6m': 'month_6',
                                '1y': 'year_1',
                                '2y': 'year_2',
                                '5y': 'year_5',
                                '10y': 'year_10',
                                '30y': 'year_30'
                            }
                            
                            target_field = maturity_field_map.get(maturity, 'year_10')
                            
                            # Try to get the rate from the appropriate field
                            rate = getattr(latest_rates, target_field, None)
                            
                            if rate is not None:
                                # Convert percentage to decimal if needed
                                if rate > 1:
                                    rate = rate / 100
                                logger.info(f"Successfully fetched {maturity} treasury rate: {rate:.4f}")
                        
                        # If specific maturity not found, use closest match
                        if rate is None:
                            if maturity in ['3m', '6m']:
                                # Use 3-month rate
                                rate = getattr(latest_rates, 'month_3', None)
                                if rate is not None:
                                    if rate > 1:
                                        rate = rate / 100
                                    logger.info(f"Using 3-month rate for {maturity}: {rate:.4f}")
                            else:
                                # Use 10-year as default for longer maturities
                                rate = getattr(latest_rates, 'year_10', None)
                                if rate is not None:
                                    if rate > 1:
                                        rate = rate / 100
                                    logger.info(f"Using 10-year rate for {maturity}: {rate:.4f}")
                        
                        if rate is None:
                            raise ValueError(f"Could not extract rate from treasury data for {maturity}")
                    else:
                        raise ValueError(f"No treasury rates data returned from OpenBB")
                        
                except Exception as obb_error:
                    logger.error(f"OpenBB yield curve fetch failed: {obb_error}")
                    # NO SILENT FALLBACKS - fail loudly as required
                    raise ValueError(f"Failed to fetch risk-free rate from OpenBB: {obb_error}")
                        
            else:
                # No OpenBB available - must fail explicitly (no fallback allowed)
                logger.error("OpenBB not available for fetching risk-free rates")
                raise ValueError(f"OpenBB is required for fetching risk-free rates. Install with: pip install openbb")
            
            # Validate the rate is within reasonable bounds
            if rate < 0 or rate > 0.20:  # Reasonable bounds for risk-free rate (0-20%)
                logger.error(f"Invalid risk-free rate {rate:.4f} for {maturity}")
                raise ValueError(f"Risk-free rate {rate:.4f} for {maturity} is outside valid range (0-20%)")
            
            confidence = 0.95 if self.use_openbb else 0.7
            
            result = {
                'rate': rate,
                'annualized': True,
                'maturity': maturity,
                'source': 'OpenBB/FRED' if self.use_openbb else 'market_estimate',
                'confidence': confidence,
                'fetch_time': datetime.now(timezone.utc).isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch risk-free rate: {str(e)}")
            raise ValueError(f"Unable to fetch risk-free rate for {maturity}: {str(e)}")
    
    def fetch_market_index(self, index: str = 'SPY', lookback_days: int = 252) -> Dict[str, Any]:
        """
        Fetch market index data for benchmarking
        
        Args:
            index: Index ticker (SPY, QQQ, IWM, etc.)
            lookback_days: Number of days to fetch
        
        Returns:
            Dictionary with index data and statistics
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=lookback_days * 1.5)  # Extra buffer for trading days
        
        result = self.fetch_equity_data(
            tickers=[index],
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        # Add index-specific metrics
        returns = result['returns'][index]
        result['index_metrics'] = {
            'total_return': (result['prices'][index].iloc[-1] / result['prices'][index].iloc[0] - 1),
            'annualized_return': returns.mean() * 252,
            'annualized_vol': returns.std() * np.sqrt(252),
            'max_drawdown': self._calculate_max_drawdown(result['prices'][index]),
            'sharpe_ratio': (returns.mean() * 252) / (returns.std() * np.sqrt(252))
        }
        
        return result
    
    def _calculate_max_drawdown(self, prices: pd.Series) -> float:
        """Calculate maximum drawdown from price series"""
        cumulative = prices / prices.iloc[0]
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return float(drawdown.min())
    
    def prepare_for_optimization(
        self,
        tickers: List[str],
        lookback_days: int = 504
    ) -> Dict[str, Any]:
        """
        Prepare data specifically for portfolio optimization
        Includes covariance shrinkage and robust estimates
        
        Args:
            tickers: List of assets
            lookback_days: Historical data period
        
        Returns:
            Dictionary with returns, covariances, and optimization-ready data
        """
        # Fetch raw data
        data = self.fetch_equity_data(
            tickers=tickers,
            start_date=(datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        )
        
        returns = data['returns']
        
        # Calculate various covariance estimates
        cov_estimates = {}
        
        # 1. Sample covariance
        cov_estimates['sample'] = returns.cov().values
        
        # 2. Ledoit-Wolf shrinkage
        try:
            from sklearn.covariance import LedoitWolf
            lw = LedoitWolf()
            cov_estimates['ledoit_wolf'], shrinkage = lw.fit(returns.values).covariance_, lw.shrinkage_
            data['shrinkage_intensity'] = shrinkage
        except ImportError:
            logger.error("scikit-learn not available for Ledoit-Wolf shrinkage")
            raise ImportError("scikit-learn is required for Ledoit-Wolf shrinkage. Install with: pip install scikit-learn")
        
        # 3. Exponentially weighted covariance
        cov_estimates['exp_weighted'] = returns.ewm(span=60).cov().iloc[-len(tickers):].values
        
        # Add optimization-ready data
        data['optimization_data'] = {
            'expected_returns': returns.mean().values * 252,  # Annualized
            'covariance_matrices': cov_estimates,
            'return_series': returns.values,
            'tickers': tickers,
            'constraints_compatible': True
        }
        
        return data
    
    def prepare_for_risk_analysis(
        self,
        tickers: List[str],
        lookback_days: int = 252
    ) -> Dict[str, Any]:
        """
        Prepare data specifically for risk analysis
        Similar to prepare_for_optimization but focused on risk metrics
        
        Args:
            tickers: List of assets
            lookback_days: Historical data period (default 252 trading days = 1 year)
        
        Returns:
            Dictionary with prices, returns, and risk-ready data
        """
        # Fetch raw data
        data = self.fetch_equity_data(
            tickers=tickers,
            start_date=(datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        )
        
        # Add benchmark data if not present
        if 'benchmark_returns' not in data:
            try:
                benchmark_data = self.fetch_equity_data(
                    tickers=['SPY'],  # Use S&P 500 as default benchmark
                    start_date=(datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
                )
                data['benchmark_returns'] = benchmark_data['returns']['SPY']
            except Exception as e:
                logger.warning(f"Could not fetch benchmark data: {e}")
                data['benchmark_returns'] = None
        
        return data

# Singleton instance for import
pipeline = MarketDataPipeline()

if __name__ == "__main__":
    # Test the pipeline
    pipeline = MarketDataPipeline()
    
    # Test equity data fetch
    print("Testing equity data fetch...")
    data = pipeline.fetch_equity_data(['AAPL', 'MSFT', 'GOOGL'])
    print(f"Quality score: {data['quality']['overall_score']}")
    print(f"Issues: {data['quality']['issues']}")
    
    # Test risk-free rate
    print("\nTesting risk-free rate fetch...")
    rf = pipeline.get_risk_free_rate('10y')
    print(f"10-year Treasury rate: {rf['rate']:.2%}")
    
    # Test optimization prep
    print("\nTesting optimization data preparation...")
    opt_data = pipeline.prepare_for_optimization(['SPY', 'AGG', 'GLD'])
    print(f"Shrinkage intensity: {opt_data.get('shrinkage_intensity', 'N/A')}")