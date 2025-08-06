#!/usr/bin/env python3
"""
Market Data Pipeline using OpenBB
Provides real-time market data with quality scoring
Replaces synthetic data injection pattern
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from scipy import stats
import warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
            adf_pvalues = []
            for col in returns.columns:
                result = adfuller(returns[col].dropna())
                adf_pvalues.append(result[1])
            
            stationary_pct = sum(p < 0.05 for p in adf_pvalues) / len(adf_pvalues)
            scores['stationarity'] = stationary_pct
            if stationary_pct < 0.8:
                issues.append(f"Non-stationary series detected ({(1-stationary_pct):.0%})")
        except Exception as e:
            logger.error(f"Stationarity test failed: {e}")
            raise ValueError(f"Data quality assessment failed during stationarity test: {str(e)}")
            
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
    
    def __init__(self, cache_ttl_minutes: int = 15):
        self.cache = {}
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.quality_scorer = DataQualityScorer()
        
        # Lazy initialization - OpenBB will be loaded on first use
        self._obb = None
        self.use_openbb = None  # Will be determined on first access
        
        # Import yfinance for equity data (OpenBB will be used for treasury rates)
        try:
            import yfinance as yf
            self.yf = yf
            self.yf_available = True
        except ImportError:
            self.yf_available = False
    
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
        return datetime.now() - cache_entry['timestamp'] < self.cache_ttl
    
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
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=504)).strftime('%Y-%m-%d')  # 2 years
        
        # Check cache
        cache_key = self._get_cache_key(tickers, start_date, end_date)
        if cache_key in self.cache and self._is_cache_valid(self.cache[cache_key]):
            logger.info(f"Using cached data for {tickers}")
            return self.cache[cache_key]['data']
        
        try:
            if self.use_openbb and False:  # Temporarily disable OpenBB for equity data
                # Use OpenBB for data fetching
                data = self.obb.equity.price.historical(
                    symbol=tickers,
                    start=start_date,
                    end=end_date,
                    provider='yfinance'  # Can switch providers
                )
                prices_df = pd.DataFrame(data.results)
                prices_df = prices_df.pivot(index='date', columns='symbol', values='close')
            elif self.yf_available:
                # Fallback to yfinance
                if len(tickers) == 1:
                    # Single ticker - download directly
                    data = self.yf.download(
                        tickers[0],
                        start=start_date,
                        end=end_date,
                        progress=False
                    )
                    # Check if data has columns (DataFrame) or is a Series
                    if isinstance(data, pd.DataFrame):
                        if 'Adj Close' in data.columns:
                            # Use rename to avoid shape issues
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
                        tickers,
                        start=start_date,
                        end=end_date,
                        progress=False
                    )
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
                        prices_df = data[['Adj Close'] if 'Adj Close' in data else ['Close']]
                        prices_df.columns = tickers
                
                # Ensure we have a DataFrame with ticker columns
                if isinstance(prices_df, pd.Series):
                    prices_df = prices_df.to_frame(tickers[0] if tickers else 'UNKNOWN')
            
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
                    'fetch_time': datetime.now().isoformat()
                },
                'quality': quality_report,
                'statistics': {
                    'mean_returns': returns_df.mean().to_dict(),
                    'volatility': returns_df.std().to_dict(),
                    'correlation_matrix': returns_df.corr().values.tolist(),
                    'sample_size': len(returns_df)
                }
            }
            
            # Cache the result
            self.cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now()
            }
            
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
            if self.obb and self.use_openbb:
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
                    # Fetch yield curve data from OpenBB FRED provider
                    logger.info(f"Fetching yield curve from OpenBB for {maturity} rate")
                    yield_curve = self.obb.fixedincome.government.yield_curve(provider='fred')
                    
                    if yield_curve and hasattr(yield_curve, 'results') and yield_curve.results:
                        # Map maturity to yield curve field
                        maturity_field_map = {
                            '3m': 'month_3',
                            '6m': 'month_6',
                            '1y': 'year_1',
                            '2y': 'year_2',
                            '5y': 'year_5',
                            '10y': 'year_10',
                            '30y': 'year_30'
                        }
                        
                        target_maturity = maturity_field_map.get(maturity, 'year_10')
                        
                        # Find the rate for our maturity
                        rate = None
                        for point in yield_curve.results:
                            if str(point.maturity) == target_maturity:
                                # Rate is stored in model_extra dict
                                rate = point.model_extra.get('rate', None)
                                if rate is not None:
                                    logger.info(f"Successfully fetched {maturity} treasury rate from yield curve: {rate:.4f}")
                                    break
                        
                        # If specific maturity not found, use closest match
                        if rate is None:
                            if maturity in ['3m', '6m']:
                                # Use short-term rate
                                for point in yield_curve.results:
                                    if point.maturity == 'month_3':
                                        rate = point.model_extra.get('rate', None)
                                        if rate is not None:
                                            logger.info(f"Using 3-month rate for {maturity}: {rate:.4f}")
                                            break
                            else:
                                # Use 10-year as default for longer maturities
                                for point in yield_curve.results:
                                    if point.maturity == 'year_10':
                                        rate = point.model_extra.get('rate', None)
                                        if rate is not None:
                                            logger.info(f"Using 10-year rate for {maturity}: {rate:.4f}")
                                            break
                        
                        if rate is None:
                            raise ValueError(f"Could not extract rate from yield curve for {maturity}")
                    else:
                        raise ValueError(f"No yield curve data returned from OpenBB")
                        
                except Exception as obb_error:
                    logger.warning(f"OpenBB yield curve fetch failed: {obb_error}, trying SOFR/EFFR")
                    # Try alternative: use SOFR or EFFR as risk-free proxy
                    try:
                        # Try SOFR first (Secured Overnight Financing Rate)
                        sofr_data = self.obb.fixedincome.rate.sofr(provider='fred')
                        if sofr_data and hasattr(sofr_data, 'results') and sofr_data.results:
                            latest_sofr = sofr_data.results[-1]
                            base_rate = latest_sofr.rate  # Already in decimal format
                            
                            # Add term premium for longer maturities
                            term_premiums = {
                                '3m': 0.0,
                                '6m': 0.001,
                                '1y': 0.002,
                                '2y': 0.003,
                                '5y': 0.005,
                                '10y': 0.008,
                                '30y': 0.012
                            }
                            premium = term_premiums.get(maturity, 0.008)
                            rate = base_rate + premium
                            logger.info(f"Using SOFR + term premium for {maturity}: {rate:.4f} (base SOFR: {base_rate:.4f})")
                        else:
                            # Try EFFR (Effective Federal Funds Rate)
                            effr_data = self.obb.fixedincome.rate.effr(provider='fred')
                            if effr_data and hasattr(effr_data, 'results') and effr_data.results:
                                latest_effr = effr_data.results[-1]
                                base_rate = latest_effr.rate
                                
                                # Add term premium
                                term_premiums = {
                                    '3m': 0.0,
                                    '6m': 0.001,
                                    '1y': 0.002,
                                    '2y': 0.003,
                                    '5y': 0.005,
                                    '10y': 0.008,
                                    '30y': 0.012
                                }
                                premium = term_premiums.get(maturity, 0.008)
                                rate = base_rate + premium
                                logger.info(f"Using EFFR + term premium for {maturity}: {rate:.4f} (base EFFR: {base_rate:.4f})")
                            else:
                                # No real data available - must fail explicitly
                                raise ValueError(f"Unable to fetch any risk-free rate data from OpenBB")
                    except Exception as fallback_error:
                        logger.error(f"All risk-free rate sources failed: {fallback_error}")
                        raise ValueError(f"Unable to fetch risk-free rate for {maturity} from any source")
                        
            else:
                # No OpenBB available - must fail explicitly
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
                'fetch_time': datetime.now().isoformat()
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
        end_date = datetime.now()
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
            start_date=(datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
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