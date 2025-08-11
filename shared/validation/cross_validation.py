#!/usr/bin/env python3
"""
Combinatorial Purged Cross-Validation for financial time series.
Avoids data leakage in time series validation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class CombinatorialPurgedCV:
    """
    Implements combinatorial purged cross-validation from Advances in Financial Machine Learning.
    Pure mechanical implementation - interpretation by agents.
    """
    
    def __init__(self, n_splits: int = 10, embargo_pct: float = 0.01):
        """
        Initialize cross-validator.
        
        Args:
            n_splits: Number of CV splits
            embargo_pct: Percentage of data to embargo after test set
        """
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct
    
    def split(self, X: pd.DataFrame) -> List[tuple]:
        """
        Generate train/test splits with purging and embargo.
        
        Args:
            X: Data to split (returns or prices)
            
        Yields:
            Tuples of (train_indices, test_indices)
        """
        n_samples = len(X)
        embargo_size = int(n_samples * self.embargo_pct)
        indices = np.arange(n_samples)
        
        # Generate test sets
        test_starts = self._get_test_starts(n_samples)
        
        for test_start, test_end in test_starts:
            # Define test indices
            test_indices = indices[test_start:test_end]
            
            # Define train indices with purging
            train_mask = np.ones(n_samples, dtype=bool)
            
            # Remove test period
            train_mask[test_start:test_end] = False
            
            # Add embargo after test period
            embargo_end = min(test_end + embargo_size, n_samples)
            train_mask[test_end:embargo_end] = False
            
            # Add embargo before test period (for look-ahead bias)
            embargo_start = max(0, test_start - embargo_size)
            train_mask[embargo_start:test_start] = False
            
            train_indices = indices[train_mask]
            
            if len(train_indices) > 0 and len(test_indices) > 0:
                yield train_indices, test_indices
    
    def _get_test_starts(self, n_samples: int) -> List[tuple]:
        """
        Get test period start and end indices.
        
        Args:
            n_samples: Total number of samples
            
        Returns:
            List of (start, end) tuples for test periods
        """
        test_size = n_samples // self.n_splits
        test_starts = []
        
        for i in range(self.n_splits):
            start = i * test_size
            end = min((i + 1) * test_size, n_samples)
            test_starts.append((start, end))
        
        return test_starts