#!/usr/bin/env python3
"""
Correlation Service - Single source of truth for correlation calculations
Eliminates duplicate correlation calculations across risk, portfolio, and tax servers
Provides caching to avoid redundant API calls
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)

class CorrelationService:
    """Centralized service for correlation calculations"""
    
    def __init__(self, data_pipeline=None, cache_ttl_minutes: int = 60):
        """
        Initialize correlation service
        
        Args:
            data_pipeline: MarketDataPipeline instance for fetching data
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        # Import data pipeline if not provided
        if data_pipeline is None:
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
            from data_pipeline import MarketDataPipeline
            data_pipeline = MarketDataPipeline()
        
        self.data_pipeline = data_pipeline
        self.cache = {}
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        
        # Cache file for persistence across server restarts
        self.cache_file = "/home/hvksh/investing/shared/cache/correlation_cache.json"
        self._load_cache()
    
    def _get_cache_key(self, tickers: List[str], lookback_days: int) -> str:
        """Generate cache key for correlation request"""
        sorted_tickers = sorted(tickers)
        return f"{','.join(sorted_tickers)}_{lookback_days}"
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cached data is still valid"""
        if not cache_entry:
            return False
        
        cached_time = datetime.fromisoformat(cache_entry['timestamp'])
        return datetime.now() - cached_time < self.cache_ttl
    
    def _load_cache(self):
        """Load cache from file if it exists"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    # Convert back to proper format
                    for key, value in cache_data.items():
                        if self._is_cache_valid(value):
                            self.cache[key] = value
                logger.info(f"Loaded {len(self.cache)} valid correlation entries from cache")
        except Exception as e:
            logger.warning(f"Could not load correlation cache: {e}")
    
    def _save_cache(self):
        """Save cache to file"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            # Only save valid entries
            valid_cache = {
                key: value for key, value in self.cache.items()
                if self._is_cache_valid(value)
            }
            with open(self.cache_file, 'w') as f:
                json.dump(valid_cache, f)
        except Exception as e:
            logger.warning(f"Could not save correlation cache: {e}")
    
    def get_correlation_matrix(
        self,
        tickers: List[str],
        lookback_days: int = 252,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get correlation matrix for given tickers
        
        Args:
            tickers: List of ticker symbols
            lookback_days: Number of days to look back for correlation calculation
            use_cache: Whether to use cached results
        
        Returns:
            Correlation matrix as pandas DataFrame
        """
        # Check cache
        cache_key = self._get_cache_key(tickers, lookback_days)
        if use_cache and cache_key in self.cache:
            if self._is_cache_valid(self.cache[cache_key]):
                logger.info(f"Using cached correlation matrix for {len(tickers)} tickers")
                return pd.DataFrame(
                    self.cache[cache_key]['matrix'],
                    index=tickers,
                    columns=tickers
                )
        
        # Fetch data and calculate
        logger.info(f"Calculating correlation matrix for {len(tickers)} tickers over {lookback_days} days")
        
        try:
            # Fetch historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(lookback_days * 1.5))  # Extra buffer
            
            data = self.data_pipeline.fetch_equity_data(
                tickers=tickers,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            # Calculate returns
            returns = data['returns']
            
            # Calculate correlation matrix
            corr_matrix = returns.corr()
            
            # Cache the result
            self.cache[cache_key] = {
                'matrix': corr_matrix.values.tolist(),
                'timestamp': datetime.now().isoformat(),
                'tickers': tickers,
                'lookback_days': lookback_days
            }
            self._save_cache()
            
            return corr_matrix
            
        except Exception as e:
            logger.error(f"Failed to calculate correlation matrix: {e}")
            # Fail loudly - no fallback to synthetic data
            raise ValueError(f"Unable to calculate correlation matrix for {tickers}: {e}")
    
    def find_correlated_pairs(
        self,
        tickers: List[str],
        threshold: float = 0.95,
        lookback_days: int = 252
    ) -> List[Dict[str, Any]]:
        """
        Find pairs of tickers with correlation above threshold
        
        Args:
            tickers: List of ticker symbols
            threshold: Correlation threshold (e.g., 0.95)
            lookback_days: Number of days for correlation calculation
        
        Returns:
            List of correlated pairs with their correlation values
        """
        corr_matrix = self.get_correlation_matrix(tickers, lookback_days)
        
        pairs = []
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                correlation = corr_matrix.iloc[i, j]
                if abs(correlation) >= threshold:
                    pairs.append({
                        'ticker1': tickers[i],
                        'ticker2': tickers[j],
                        'correlation': float(correlation),
                        'is_positive': correlation > 0
                    })
        
        # Sort by absolute correlation (highest first)
        pairs.sort(key=lambda x: abs(x['correlation']), reverse=True)
        
        logger.info(f"Found {len(pairs)} pairs with correlation >= {threshold}")
        return pairs
    
    def get_diversification_ratio(
        self,
        tickers: List[str],
        weights: np.ndarray,
        lookback_days: int = 252
    ) -> float:
        """
        Calculate diversification ratio for a portfolio
        DR = (sum of weighted volatilities) / (portfolio volatility)
        
        Args:
            tickers: List of ticker symbols
            weights: Portfolio weights
            lookback_days: Number of days for calculation
        
        Returns:
            Diversification ratio (higher is better, 1 = no diversification)
        """
        # Get correlation matrix
        corr_matrix = self.get_correlation_matrix(tickers, lookback_days)
        
        # Get individual volatilities
        data = self.data_pipeline.fetch_equity_data(
            tickers=tickers,
            start_date=(datetime.now() - timedelta(days=int(lookback_days * 1.5))).strftime('%Y-%m-%d')
        )
        
        returns = data['returns']
        volatilities = returns.std().values
        
        # Calculate weighted average volatility
        weighted_vol_sum = np.sum(weights * volatilities)
        
        # Calculate portfolio volatility
        cov_matrix = returns.cov().values
        portfolio_variance = weights @ cov_matrix @ weights
        portfolio_vol = np.sqrt(portfolio_variance)
        
        # Diversification ratio
        if portfolio_vol > 0:
            return float(weighted_vol_sum / portfolio_vol)
        else:
            return 1.0
    
    def get_correlation_risk_metrics(
        self,
        tickers: List[str],
        weights: Optional[np.ndarray] = None,
        lookback_days: int = 252
    ) -> Dict[str, Any]:
        """
        Get comprehensive correlation risk metrics
        
        Args:
            tickers: List of ticker symbols
            weights: Portfolio weights (optional)
            lookback_days: Number of days for calculation
        
        Returns:
            Dictionary with correlation risk metrics
        """
        corr_matrix = self.get_correlation_matrix(tickers, lookback_days)
        
        # Create upper triangle mask
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        upper_triangle = corr_matrix.where(mask)
        
        # Calculate metrics
        correlations = upper_triangle.stack().dropna()
        
        metrics = {
            'average_correlation': float(correlations.mean()),
            'max_correlation': float(correlations.max()),
            'min_correlation': float(correlations.min()),
            'median_correlation': float(correlations.median()),
            'correlation_std': float(correlations.std()),
            'high_correlation_pairs': []
        }
        
        # Find highly correlated pairs (>0.7)
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                corr = corr_matrix.iloc[i, j]
                if abs(corr) > 0.7:
                    pair_weight = None
                    if weights is not None:
                        pair_weight = float(weights[i] + weights[j])
                    
                    metrics['high_correlation_pairs'].append({
                        'pair': f"{tickers[i]}-{tickers[j]}",
                        'correlation': float(corr),
                        'combined_weight': pair_weight
                    })
        
        # Add diversification ratio if weights provided
        if weights is not None:
            metrics['diversification_ratio'] = self.get_diversification_ratio(
                tickers, weights, lookback_days
            )
        
        # Add concentration risk metric
        if len(correlations) > 0:
            high_corr_count = (abs(correlations) > 0.7).sum()
            total_pairs = len(correlations)
            metrics['concentration_risk'] = float(high_corr_count / total_pairs) if total_pairs > 0 else 0
        
        return metrics
    
    def find_replacement_candidates(
        self,
        ticker: str,
        candidate_tickers: List[str],
        min_correlation: float = 0.85,
        lookback_days: int = 252
    ) -> List[Dict[str, Any]]:
        """
        Find replacement candidates for tax-loss harvesting
        
        Args:
            ticker: Ticker to replace
            candidate_tickers: List of potential replacements
            min_correlation: Minimum correlation required
            lookback_days: Number of days for calculation
        
        Returns:
            List of replacement candidates sorted by correlation
        """
        # Include original ticker in correlation calculation
        all_tickers = [ticker] + candidate_tickers
        corr_matrix = self.get_correlation_matrix(all_tickers, lookback_days)
        
        # Get correlations with the target ticker
        target_correlations = corr_matrix.loc[ticker, candidate_tickers]
        
        # Filter and sort candidates
        candidates = []
        for candidate in candidate_tickers:
            correlation = target_correlations[candidate]
            if correlation >= min_correlation:
                candidates.append({
                    'ticker': candidate,
                    'correlation': float(correlation),
                    'is_suitable': True
                })
        
        # Sort by correlation (highest first)
        candidates.sort(key=lambda x: x['correlation'], reverse=True)
        
        logger.info(f"Found {len(candidates)} replacement candidates for {ticker} with correlation >= {min_correlation}")
        return candidates

# Singleton instance
_correlation_service = None

def get_correlation_service(data_pipeline=None) -> CorrelationService:
    """Get or create the singleton CorrelationService instance"""
    global _correlation_service
    if _correlation_service is None:
        _correlation_service = CorrelationService(data_pipeline)
    return _correlation_service