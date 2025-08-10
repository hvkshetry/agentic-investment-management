#!/usr/bin/env python3
"""
Improved Market Data Pipeline with separate handling for new tickers
Handles tickers with limited history separately to avoid data quality degradation
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
import logging
import warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("data_pipeline_improved")

class ImprovedMarketDataPipeline:
    """
    Enhanced pipeline that handles tickers with limited history separately
    """
    
    def __init__(self, min_history_days: int = 252):
        self.min_history_days = min_history_days  # Minimum days for established tickers
        self.ticker_history_cache = {}  # Cache ticker history lengths
        
        # Import yfinance
        try:
            import yfinance as yf
            self.yf = yf
            self.yf_available = True
            logger.info("yfinance loaded successfully")
        except ImportError:
            self.yf_available = False
            raise ImportError("yfinance required. Install with: pip install yfinance")
    
    def check_ticker_history(self, ticker: str, target_days: int = 730) -> Tuple[int, Optional[str], Optional[str]]:
        """
        Check how much history a ticker has available
        
        Returns:
            Tuple of (days_available, first_date, last_date)
        """
        if ticker in self.ticker_history_cache:
            return self.ticker_history_cache[ticker]
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=target_days)
            
            # Download data to check availability
            data = self.yf.download(
                ticker, 
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                progress=False
            )
            
            if data.empty:
                result = (0, None, None)
            else:
                actual_days = len(data)
                first_date = data.index[0].strftime('%Y-%m-%d')
                last_date = data.index[-1].strftime('%Y-%m-%d')
                result = (actual_days, first_date, last_date)
            
            # Cache the result
            self.ticker_history_cache[ticker] = result
            return result
            
        except Exception as e:
            logger.error(f"Error checking history for {ticker}: {e}")
            return (0, None, None)
    
    def categorize_tickers(self, tickers: List[str], target_days: int = 504) -> Dict[str, List[str]]:
        """
        Categorize tickers based on their available history
        
        Returns:
            Dict with 'established', 'new', and 'invalid' ticker lists
        """
        categorized = {
            'established': [],  # >= min_history_days
            'new': [],          # < min_history_days but > 0
            'invalid': []       # No data available
        }
        
        logger.info(f"Categorizing {len(tickers)} tickers based on history availability...")
        
        for ticker in tickers:
            days_available, first_date, last_date = self.check_ticker_history(ticker, target_days)
            
            if days_available == 0:
                categorized['invalid'].append(ticker)
                logger.warning(f"❌ {ticker}: No data available")
            elif days_available < self.min_history_days:
                categorized['new'].append(ticker)
                logger.info(f"🆕 {ticker}: Only {days_available} days (from {first_date})")
            else:
                categorized['established'].append(ticker)
                logger.debug(f"✅ {ticker}: {days_available} days available")
        
        # Log summary
        logger.info(f"Ticker categorization complete:")
        logger.info(f"  - Established (>={self.min_history_days} days): {len(categorized['established'])} tickers")
        logger.info(f"  - New (<{self.min_history_days} days): {len(categorized['new'])} tickers")
        logger.info(f"  - Invalid (no data): {len(categorized['invalid'])} tickers")
        
        return categorized
    
    def fetch_equity_data_improved(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_quality_score: float = 0.7
    ) -> Dict[str, Any]:
        """
        Enhanced fetch that handles new tickers separately
        
        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            min_quality_score: Minimum acceptable quality score
        
        Returns:
            Dictionary with combined data and quality metrics
        """
        # Default dates
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=504)).strftime('%Y-%m-%d')
        
        # Calculate target days
        target_days = (datetime.strptime(end_date, '%Y-%m-%d') - 
                      datetime.strptime(start_date, '%Y-%m-%d')).days
        
        # Categorize tickers
        categorized = self.categorize_tickers(tickers, target_days)
        
        all_prices = {}
        all_returns = {}
        quality_issues = []
        fetch_metadata = {}
        
        # 1. Fetch established tickers together (full history)
        if categorized['established']:
            logger.info(f"\nFetching {len(categorized['established'])} established tickers together...")
            try:
                established_data = self.yf.download(
                    categorized['established'],
                    start=start_date,
                    end=end_date,
                    progress=False
                )
                
                if not established_data.empty:
                    # Handle MultiIndex columns
                    if isinstance(established_data.columns, pd.MultiIndex):
                        prices = established_data['Adj Close'] if 'Adj Close' in established_data.columns.levels[0] else established_data['Close']
                    else:
                        prices = established_data[['Adj Close']] if 'Adj Close' in established_data.columns else established_data[['Close']]
                        prices.columns = categorized['established']
                    
                    # Store prices
                    for ticker in categorized['established']:
                        if ticker in prices.columns:
                            all_prices[ticker] = prices[ticker]
                            all_returns[ticker] = prices[ticker].pct_change().dropna()
                            fetch_metadata[ticker] = {
                                'days_fetched': len(prices[ticker]),
                                'category': 'established',
                                'first_date': prices[ticker].index[0].strftime('%Y-%m-%d'),
                                'last_date': prices[ticker].index[-1].strftime('%Y-%m-%d')
                            }
                    
                    logger.info(f"✅ Fetched {len(established_data)} days for established tickers")
                    
            except Exception as e:
                logger.error(f"Error fetching established tickers: {e}")
                quality_issues.append(f"Failed to fetch established tickers: {str(e)[:50]}")
        
        # 2. Fetch new tickers individually (limited history)
        if categorized['new']:
            logger.info(f"\nFetching {len(categorized['new'])} new tickers individually...")
            for ticker in categorized['new']:
                try:
                    # Get actual available range for this ticker
                    days_available, first_available, _ = self.check_ticker_history(ticker, target_days)
                    
                    if days_available > 0 and first_available:
                        # Fetch from first available date
                        ticker_data = self.yf.download(
                            ticker,
                            start=first_available,
                            end=end_date,
                            progress=False
                        )
                        
                        if not ticker_data.empty:
                            # Extract price
                            if isinstance(ticker_data.columns, pd.MultiIndex):
                                price = ticker_data['Adj Close'] if 'Adj Close' in ticker_data.columns.levels[0] else ticker_data['Close']
                            else:
                                price = ticker_data['Adj Close'] if 'Adj Close' in ticker_data.columns else ticker_data['Close']
                            
                            all_prices[ticker] = price
                            all_returns[ticker] = price.pct_change().dropna()
                            fetch_metadata[ticker] = {
                                'days_fetched': len(price),
                                'category': 'new',
                                'first_date': price.index[0].strftime('%Y-%m-%d'),
                                'last_date': price.index[-1].strftime('%Y-%m-%d'),
                                'warning': f'Limited history: only {days_available} days available'
                            }
                            
                            logger.info(f"✅ {ticker}: Fetched {days_available} days (from {first_available})")
                            quality_issues.append(f"{ticker}: Limited to {days_available} days of history")
                            
                except Exception as e:
                    logger.error(f"Error fetching {ticker}: {e}")
                    quality_issues.append(f"Failed to fetch {ticker}: {str(e)[:50]}")
        
        # 3. Report invalid tickers
        if categorized['invalid']:
            for ticker in categorized['invalid']:
                quality_issues.append(f"{ticker}: No data available")
                logger.warning(f"⚠️ {ticker}: Skipped (no data available)")
        
        # 4. Combine all data into aligned DataFrames
        if all_prices:
            # Create combined DataFrames
            # Use the date range from established tickers as the base
            if categorized['established'] and all_prices:
                base_ticker = categorized['established'][0]
                if base_ticker in all_prices:
                    base_index = all_prices[base_ticker].index
                else:
                    # Create a date range
                    base_index = pd.date_range(start=start_date, end=end_date, freq='B')
            else:
                base_index = pd.date_range(start=start_date, end=end_date, freq='B')
            
            # Align all prices to the same index
            prices_df = pd.DataFrame(index=base_index)
            returns_df = pd.DataFrame(index=base_index[1:])  # Returns have one less row
            
            for ticker in tickers:
                if ticker in all_prices:
                    # Reindex to align dates
                    prices_df[ticker] = all_prices[ticker].reindex(base_index, method='ffill')
                    if ticker in all_returns:
                        returns_df[ticker] = all_returns[ticker].reindex(base_index[1:])
            
            # Drop rows where all values are NaN
            prices_df = prices_df.dropna(how='all')
            returns_df = returns_df.dropna(how='all')
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(
                prices_df, 
                returns_df, 
                categorized, 
                fetch_metadata
            )
            
            # Check if quality meets minimum threshold
            if quality_score < min_quality_score:
                warning_msg = f"Data quality score {quality_score:.2%} is below threshold {min_quality_score:.2%}"
                logger.warning(f"⚠️ {warning_msg}")
                quality_issues.insert(0, warning_msg)
            
            result = {
                'prices': prices_df,
                'returns': returns_df,
                'log_returns': np.log(prices_df / prices_df.shift(1)).dropna(),
                'metadata': {
                    'tickers': tickers,
                    'start_date': start_date,
                    'end_date': end_date,
                    'fetch_time': datetime.now().isoformat(),
                    'ticker_categories': categorized,
                    'ticker_metadata': fetch_metadata
                },
                'quality': {
                    'overall_score': quality_score,
                    'issues': quality_issues,
                    'established_tickers': len(categorized['established']),
                    'new_tickers': len(categorized['new']),
                    'invalid_tickers': len(categorized['invalid']),
                    'min_history_days': min([m['days_fetched'] for m in fetch_metadata.values()]) if fetch_metadata else 0,
                    'max_history_days': max([m['days_fetched'] for m in fetch_metadata.values()]) if fetch_metadata else 0
                },
                'statistics': {
                    'mean_returns': returns_df.mean().to_dict() if not returns_df.empty else {},
                    'volatility': returns_df.std().to_dict() if not returns_df.empty else {},
                    'correlation_matrix': returns_df.corr().values.tolist() if not returns_df.empty else [],
                    'sample_size': len(returns_df)
                }
            }
            
            logger.info(f"\n📊 Final Data Quality: {quality_score:.2%}")
            logger.info(f"   - Established tickers used: {len(categorized['established'])}/{len(tickers)}")
            logger.info(f"   - Data points: {len(prices_df)} days x {len(prices_df.columns)} tickers")
            
            return result
            
        else:
            raise ValueError(f"No valid data could be fetched for any of the tickers: {tickers}")
    
    def _calculate_quality_score(
        self, 
        prices_df: pd.DataFrame, 
        returns_df: pd.DataFrame,
        categorized: Dict[str, List[str]],
        fetch_metadata: Dict[str, Dict]
    ) -> float:
        """
        Calculate quality score with awareness of ticker categories
        """
        scores = {}
        
        # 1. Sample adequacy (based on established tickers only)
        if categorized['established']:
            established_days = [fetch_metadata[t]['days_fetched'] 
                              for t in categorized['established'] 
                              if t in fetch_metadata]
            if established_days:
                avg_established_days = np.mean(established_days)
                scores['sample_adequacy'] = min(1.0, avg_established_days / self.min_history_days)
            else:
                scores['sample_adequacy'] = 0.5
        else:
            # No established tickers, use overall average
            all_days = [m['days_fetched'] for m in fetch_metadata.values()]
            avg_days = np.mean(all_days) if all_days else 0
            scores['sample_adequacy'] = min(1.0, avg_days / self.min_history_days) * 0.7  # Penalty
        
        # 2. Completeness (missing data)
        missing_pct = prices_df.isnull().sum().sum() / prices_df.size if prices_df.size > 0 else 1.0
        scores['completeness'] = 1.0 - missing_pct
        
        # 3. Coverage (how many tickers have data)
        total_tickers = len(categorized['established']) + len(categorized['new']) + len(categorized['invalid'])
        valid_tickers = len(categorized['established']) + len(categorized['new'])
        scores['coverage'] = valid_tickers / total_tickers if total_tickers > 0 else 0
        
        # 4. Stability (penalize if too many new tickers)
        new_ticker_ratio = len(categorized['new']) / total_tickers if total_tickers > 0 else 0
        scores['stability'] = 1.0 - (new_ticker_ratio * 0.5)  # 50% penalty for new tickers
        
        # 5. Statistical validity (enough data for calculations)
        min_days = min([m['days_fetched'] for m in fetch_metadata.values()]) if fetch_metadata else 0
        scores['statistical_validity'] = min(1.0, min_days / 60)  # At least 60 days for stats
        
        # Calculate weighted overall score
        weights = {
            'sample_adequacy': 0.30,
            'completeness': 0.20,
            'coverage': 0.20,
            'stability': 0.15,
            'statistical_validity': 0.15
        }
        
        overall_score = sum(scores.get(k, 0) * v for k, v in weights.items())
        
        # Log component scores
        logger.debug("Quality Score Components:")
        for component, score in scores.items():
            logger.debug(f"  - {component}: {score:.2%}")
        
        return round(overall_score, 3)


# Test the improved pipeline
if __name__ == "__main__":
    pipeline = ImprovedMarketDataPipeline(min_history_days=252)
    
    # Test with known problematic tickers
    test_tickers = [
        'VOO', 'SPY', 'AAPL', 'MSFT',  # Established
        'GEV',  # New (spun off in 2024)
        'INVALID_TEST'  # Invalid
    ]
    
    print("\n" + "="*80)
    print("TESTING IMPROVED DATA PIPELINE")
    print("="*80)
    
    result = pipeline.fetch_equity_data_improved(
        tickers=test_tickers,
        start_date=(datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
    )
    
    print(f"\nQuality Score: {result['quality']['overall_score']:.2%}")
    print(f"Issues Found: {len(result['quality']['issues'])}")
    for issue in result['quality']['issues'][:5]:  # Show first 5 issues
        print(f"  - {issue}")
    
    print(f"\nTicker Categories:")
    print(f"  - Established: {result['quality']['established_tickers']}")
    print(f"  - New: {result['quality']['new_tickers']}")
    print(f"  - Invalid: {result['quality']['invalid_tickers']}")