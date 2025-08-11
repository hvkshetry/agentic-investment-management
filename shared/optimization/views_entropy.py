#!/usr/bin/env python3
"""
Entropy pooling for incorporating market views into portfolio optimization.
Based on Meucci's approach - mechanical implementation for agent interpretation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from scipy.optimize import minimize
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)


class ViewsEntropyPooling:
    """
    Incorporate subjective views into market distributions using entropy pooling.
    Mechanical execution - Macro Analyst provides views, Portfolio Manager interprets.
    """
    
    def __init__(self):
        """Initialize entropy pooling engine."""
        self.prior_distribution = None
        self.posterior_distribution = None
    
    def incorporate_views(self,
                         historical_returns: pd.DataFrame,
                         views: List[Dict[str, Any]],
                         confidence_levels: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Incorporate views into return distribution using entropy pooling.
        
        Args:
            historical_returns: Historical return data
            views: List of view dictionaries with structure:
                   {'type': 'absolute'/'relative',
                    'assets': list of assets,
                    'view_return': expected return,
                    'confidence': confidence level}
            confidence_levels: Optional confidence for each view
            
        Returns:
            Dict with posterior distribution and statistics
        """
        # Extract prior distribution from historical data
        self.prior_distribution = self._extract_prior(historical_returns)
        
        # Process views into constraints
        constraints = self._process_views(views, historical_returns)
        
        # Solve entropy minimization problem
        posterior_probs = self._entropy_minimization(
            self.prior_distribution['probabilities'],
            constraints
        )
        
        # Calculate posterior statistics
        posterior_stats = self._calculate_posterior_stats(
            historical_returns, posterior_probs
        )
        
        # Calculate view-adjusted expected returns
        adjusted_returns = self._calculate_adjusted_returns(
            historical_returns, posterior_probs
        )
        
        # Calculate confidence-weighted covariance
        adjusted_covariance = self._calculate_adjusted_covariance(
            historical_returns, posterior_probs
        )
        
        return {
            'adjusted_returns': adjusted_returns,
            'adjusted_covariance': adjusted_covariance,
            'posterior_probabilities': posterior_probs,
            'posterior_stats': posterior_stats,
            'entropy_reduction': self._calculate_entropy_reduction(
                self.prior_distribution['probabilities'], posterior_probs
            ),
            'effective_views': len([v for v in views if v.get('confidence', 0) > 0.5])
        }
    
    def black_litterman_views(self,
                             market_weights: Dict[str, float],
                             covariance: pd.DataFrame,
                             views: List[Dict[str, Any]],
                             tau: float = 0.05) -> Dict[str, Any]:
        """
        Black-Litterman model for combining market equilibrium with views.
        
        Args:
            market_weights: Market capitalization weights
            covariance: Asset covariance matrix
            views: List of views
            tau: Uncertainty parameter
            
        Returns:
            Black-Litterman adjusted returns and covariance
        """
        assets = list(covariance.index)
        n_assets = len(assets)
        
        # Calculate equilibrium returns (reverse optimization)
        market_weights_array = np.array([market_weights.get(a, 0) for a in assets])
        equilibrium_returns = self._implied_returns(market_weights_array, covariance.values)
        
        # Process views into P matrix and Q vector
        P, Q, omega = self._create_view_matrices(views, assets, covariance)
        
        if P is None or len(P) == 0:
            # No valid views, return equilibrium
            return {
                'adjusted_returns': pd.Series(equilibrium_returns, index=assets),
                'adjusted_covariance': covariance,
                'confidence': 0.0
            }
        
        # Black-Litterman formula
        tau_sigma = tau * covariance.values
        
        # Posterior expected returns
        A = np.linalg.inv(np.linalg.inv(tau_sigma) + P.T @ np.linalg.inv(omega) @ P)
        posterior_returns = A @ (np.linalg.inv(tau_sigma) @ equilibrium_returns + P.T @ np.linalg.inv(omega) @ Q)
        
        # Posterior covariance
        posterior_cov = covariance.values + A
        
        return {
            'adjusted_returns': pd.Series(posterior_returns, index=assets),
            'adjusted_covariance': pd.DataFrame(posterior_cov, index=assets, columns=assets),
            'confidence': self._calculate_view_confidence(P, Q, omega),
            'equilibrium_returns': pd.Series(equilibrium_returns, index=assets)
        }
    
    def scenario_based_views(self,
                           scenarios: List[Dict[str, Any]],
                           probabilities: List[float]) -> Dict[str, Any]:
        """
        Incorporate scenario-based views from Macro Analyst.
        
        Args:
            scenarios: List of scenario dictionaries with returns for each asset
            probabilities: Probability of each scenario
            
        Returns:
            Scenario-weighted returns and risk metrics
        """
        if not scenarios:
            return {'error': 'No scenarios provided'}
        
        # Normalize probabilities
        probabilities = np.array(probabilities)
        probabilities = probabilities / probabilities.sum()
        
        # Extract assets
        assets = list(scenarios[0].get('returns', {}).keys())
        n_scenarios = len(scenarios)
        
        # Build scenario return matrix
        scenario_returns = np.zeros((n_scenarios, len(assets)))
        for i, scenario in enumerate(scenarios):
            returns = scenario.get('returns', {})
            scenario_returns[i] = [returns.get(asset, 0) for asset in assets]
        
        # Calculate probability-weighted expected returns
        expected_returns = probabilities @ scenario_returns
        
        # Calculate scenario-based covariance
        centered_returns = scenario_returns - expected_returns
        covariance = np.zeros((len(assets), len(assets)))
        for i in range(n_scenarios):
            covariance += probabilities[i] * np.outer(centered_returns[i], centered_returns[i])
        
        # Calculate tail risk metrics
        var_95 = np.percentile(scenario_returns, 5, axis=0, weights=probabilities)
        cvar_95 = self._calculate_cvar(scenario_returns, probabilities, 0.05)
        
        return {
            'expected_returns': pd.Series(expected_returns, index=assets),
            'covariance': pd.DataFrame(covariance, index=assets, columns=assets),
            'var_95': pd.Series(var_95, index=assets),
            'cvar_95': pd.Series(cvar_95, index=assets),
            'scenario_probabilities': probabilities.tolist(),
            'dominant_scenario': scenarios[np.argmax(probabilities)].get('name', 'Unknown')
        }
    
    def confidence_scaling(self,
                         base_views: Dict[str, Any],
                         market_volatility: float,
                         view_accuracy_history: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Scale view confidence based on market conditions and historical accuracy.
        
        Args:
            base_views: Base views with returns and covariance
            market_volatility: Current market volatility level
            view_accuracy_history: Historical accuracy of views (optional)
            
        Returns:
            Confidence-scaled views
        """
        # Calculate base confidence
        base_confidence = 1.0
        
        # Adjust for market volatility (reduce confidence in volatile markets)
        vol_adjustment = np.exp(-2 * market_volatility)  # Exponential decay
        
        # Adjust for historical accuracy if available
        if view_accuracy_history and len(view_accuracy_history) > 0:
            historical_accuracy = np.mean(view_accuracy_history)
            accuracy_adjustment = historical_accuracy
        else:
            accuracy_adjustment = 0.5  # Neutral if no history
        
        # Combined confidence
        final_confidence = base_confidence * vol_adjustment * accuracy_adjustment
        final_confidence = np.clip(final_confidence, 0.1, 1.0)  # Keep between 10% and 100%
        
        # Scale returns by confidence
        scaled_returns = base_views.get('adjusted_returns', pd.Series()) * final_confidence
        
        # Increase covariance to reflect lower confidence
        confidence_multiplier = 1 / final_confidence if final_confidence > 0 else 10
        scaled_covariance = base_views.get('adjusted_covariance', pd.DataFrame()) * confidence_multiplier
        
        return {
            'scaled_returns': scaled_returns,
            'scaled_covariance': scaled_covariance,
            'confidence_level': float(final_confidence),
            'volatility_adjustment': float(vol_adjustment),
            'accuracy_adjustment': float(accuracy_adjustment),
            'recommendation': self._get_confidence_recommendation(final_confidence)
        }
    
    def _extract_prior(self, historical_returns: pd.DataFrame) -> Dict[str, Any]:
        """
        Extract prior distribution from historical data.
        
        Returns:
            Prior distribution parameters
        """
        n_observations = len(historical_returns)
        
        # Equal probability prior (can be enhanced with regime detection)
        probabilities = np.ones(n_observations) / n_observations
        
        return {
            'probabilities': probabilities,
            'mean': historical_returns.mean(),
            'covariance': historical_returns.cov(),
            'n_observations': n_observations
        }
    
    def _process_views(self,
                      views: List[Dict[str, Any]],
                      historical_returns: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Process views into optimization constraints.
        
        Returns:
            List of constraint dictionaries
        """
        constraints = []
        
        for view in views:
            view_type = view.get('type', 'absolute')
            assets = view.get('assets', [])
            view_return = view.get('view_return', 0)
            confidence = view.get('confidence', 0.5)
            
            if view_type == 'absolute':
                # Absolute return view on specific assets
                for asset in assets:
                    if asset in historical_returns.columns:
                        constraints.append({
                            'type': 'equality',
                            'asset': asset,
                            'value': view_return,
                            'confidence': confidence
                        })
            
            elif view_type == 'relative':
                # Relative view between assets
                if len(assets) >= 2 and all(a in historical_returns.columns for a in assets):
                    constraints.append({
                        'type': 'relative',
                        'assets': assets,
                        'value': view_return,
                        'confidence': confidence
                    })
        
        return constraints
    
    def _entropy_minimization(self,
                            prior_probs: np.ndarray,
                            constraints: List[Dict[str, Any]]) -> np.ndarray:
        """
        Minimize relative entropy subject to view constraints.
        
        Returns:
            Posterior probabilities
        """
        n = len(prior_probs)
        
        # Objective: minimize relative entropy
        def entropy(p):
            # Add small epsilon to avoid log(0)
            p_safe = np.maximum(p, 1e-10)
            prior_safe = np.maximum(prior_probs, 1e-10)
            return np.sum(p_safe * np.log(p_safe / prior_safe))
        
        # Gradient of entropy
        def entropy_grad(p):
            p_safe = np.maximum(p, 1e-10)
            prior_safe = np.maximum(prior_probs, 1e-10)
            return np.log(p_safe / prior_safe) + 1
        
        # Constraints
        opt_constraints = [
            {'type': 'eq', 'fun': lambda p: np.sum(p) - 1},  # Probabilities sum to 1
            {'type': 'ineq', 'fun': lambda p: p}  # Non-negative probabilities
        ]
        
        # Add view constraints (simplified)
        # In practice, would translate views to constraints on expected values
        
        # Solve optimization
        result = minimize(
            entropy,
            prior_probs,
            method='SLSQP',
            jac=entropy_grad,
            constraints=opt_constraints,
            options={'disp': False}
        )
        
        if result.success:
            posterior = result.x
            # Ensure valid probability distribution
            posterior = np.maximum(posterior, 0)
            posterior = posterior / posterior.sum()
            return posterior
        else:
            logger.warning("Entropy minimization failed, returning prior")
            return prior_probs
    
    def _calculate_posterior_stats(self,
                                  returns: pd.DataFrame,
                                  posterior_probs: np.ndarray) -> Dict[str, Any]:
        """
        Calculate statistics of posterior distribution.
        
        Returns:
            Posterior statistics
        """
        # Ensure posterior_probs has correct shape
        if len(posterior_probs) != len(returns):
            if len(posterior_probs) > len(returns):
                posterior_probs = posterior_probs[:len(returns)]
            else:
                padding = np.ones(len(returns) - len(posterior_probs)) / (len(returns) - len(posterior_probs))
                posterior_probs = np.concatenate([posterior_probs, padding])
        
        # Weighted mean
        posterior_mean = (returns.T @ posterior_probs).to_dict()
        
        # Weighted covariance - use proper matrix multiplication
        centered = returns - returns.mean()
        # Convert to numpy for proper matrix multiplication
        centered_np = centered.values
        posterior_cov_np = centered_np.T @ np.diag(posterior_probs) @ centered_np
        posterior_cov = pd.DataFrame(posterior_cov_np, index=returns.columns, columns=returns.columns)
        
        # Effective sample size
        ess = 1 / np.sum(posterior_probs ** 2)
        
        return {
            'mean': posterior_mean,
            'covariance': posterior_cov.to_dict(),
            'effective_sample_size': float(ess),
            'max_weight': float(np.max(posterior_probs)),
            'weight_concentration': float(np.sum(posterior_probs ** 2))
        }
    
    def _calculate_adjusted_returns(self,
                                   returns: pd.DataFrame,
                                   posterior_probs: np.ndarray) -> pd.Series:
        """
        Calculate probability-weighted adjusted returns.
        
        Returns:
            Adjusted expected returns
        """
        # Ensure posterior_probs has correct shape
        if len(posterior_probs) != len(returns):
            # Reshape or truncate as needed
            if len(posterior_probs) > len(returns):
                posterior_probs = posterior_probs[:len(returns)]
            else:
                # Pad with equal weights for missing
                padding = np.ones(len(returns) - len(posterior_probs)) / (len(returns) - len(posterior_probs))
                posterior_probs = np.concatenate([posterior_probs, padding])
        
        return returns.T @ posterior_probs
    
    def _calculate_adjusted_covariance(self,
                                      returns: pd.DataFrame,
                                      posterior_probs: np.ndarray) -> pd.DataFrame:
        """
        Calculate probability-weighted covariance matrix.
        
        Returns:
            Adjusted covariance matrix
        """
        # Ensure posterior_probs has correct shape
        if len(posterior_probs) != len(returns):
            if len(posterior_probs) > len(returns):
                posterior_probs = posterior_probs[:len(returns)]
            else:
                padding = np.ones(len(returns) - len(posterior_probs)) / (len(returns) - len(posterior_probs))
                posterior_probs = np.concatenate([posterior_probs, padding])
        
        # Calculate weighted mean
        weighted_mean = returns.T @ posterior_probs
        
        # Center returns - broadcast correctly
        centered = returns.subtract(weighted_mean, axis='columns')
        
        # Weighted covariance - use numpy for proper matrix multiplication
        centered_np = centered.values
        weighted_cov_np = centered_np.T @ np.diag(posterior_probs) @ centered_np
        weighted_cov = pd.DataFrame(weighted_cov_np, index=returns.columns, columns=returns.columns)
        
        return weighted_cov
    
    def _calculate_entropy_reduction(self,
                                    prior: np.ndarray,
                                    posterior: np.ndarray) -> float:
        """
        Calculate reduction in entropy from prior to posterior.
        
        Returns:
            Entropy reduction (positive means information gain)
        """
        prior_entropy = -np.sum(prior * np.log(np.maximum(prior, 1e-10)))
        posterior_entropy = -np.sum(posterior * np.log(np.maximum(posterior, 1e-10)))
        return float(prior_entropy - posterior_entropy)
    
    def _implied_returns(self,
                        weights: np.ndarray,
                        covariance: np.ndarray,
                        risk_aversion: float = 2.5) -> np.ndarray:
        """
        Calculate implied equilibrium returns from market weights.
        
        Returns:
            Implied returns vector
        """
        return risk_aversion * covariance @ weights
    
    def _create_view_matrices(self,
                            views: List[Dict[str, Any]],
                            assets: List[str],
                            covariance: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Create P, Q, and Omega matrices for Black-Litterman model.
        
        Returns:
            Tuple of (P matrix, Q vector, Omega matrix)
        """
        valid_views = []
        
        for view in views:
            if view.get('confidence', 0) > 0:
                valid_views.append(view)
        
        if not valid_views:
            return None, None, None
        
        n_views = len(valid_views)
        n_assets = len(assets)
        
        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)
        omega_diag = np.zeros(n_views)
        
        for i, view in enumerate(valid_views):
            view_assets = view.get('assets', [])
            view_return = view.get('view_return', 0)
            confidence = view.get('confidence', 0.5)
            
            # Build P matrix row
            if view.get('type') == 'relative' and len(view_assets) >= 2:
                # Relative view: asset1 - asset2 = view_return
                if view_assets[0] in assets and view_assets[1] in assets:
                    idx1 = assets.index(view_assets[0])
                    idx2 = assets.index(view_assets[1])
                    P[i, idx1] = 1
                    P[i, idx2] = -1
            else:
                # Absolute view
                for asset in view_assets:
                    if asset in assets:
                        idx = assets.index(asset)
                        P[i, idx] = 1 / len(view_assets)
            
            Q[i] = view_return
            
            # Uncertainty inversely proportional to confidence
            omega_diag[i] = (1 - confidence) * 0.1  # Scale factor
        
        omega = np.diag(omega_diag)
        
        return P, Q, omega
    
    def _calculate_view_confidence(self,
                                  P: np.ndarray,
                                  Q: np.ndarray,
                                  omega: np.ndarray) -> float:
        """
        Calculate overall confidence in views.
        
        Returns:
            Confidence score (0-1)
        """
        if omega is None or len(omega) == 0:
            return 0.0
        
        # Average inverse of uncertainty
        avg_precision = np.mean(1 / np.diag(omega))
        # Normalize to 0-1 range
        confidence = 1 - np.exp(-avg_precision)
        
        return float(confidence)
    
    def _calculate_cvar(self,
                       returns: np.ndarray,
                       probabilities: np.ndarray,
                       alpha: float = 0.05) -> np.ndarray:
        """
        Calculate Conditional Value at Risk (CVaR).
        
        Returns:
            CVaR for each asset
        """
        n_scenarios, n_assets = returns.shape
        cvar = np.zeros(n_assets)
        
        for i in range(n_assets):
            asset_returns = returns[:, i]
            # Sort returns and probabilities
            sorted_idx = np.argsort(asset_returns)
            sorted_returns = asset_returns[sorted_idx]
            sorted_probs = probabilities[sorted_idx]
            
            # Find VaR threshold
            cumsum = np.cumsum(sorted_probs)
            var_idx = np.where(cumsum >= alpha)[0][0] if np.any(cumsum >= alpha) else -1
            
            # Calculate CVaR as expected value below VaR
            if var_idx >= 0:
                cvar[i] = np.sum(sorted_returns[:var_idx+1] * sorted_probs[:var_idx+1]) / np.sum(sorted_probs[:var_idx+1])
            else:
                cvar[i] = np.mean(sorted_returns)
        
        return cvar
    
    def _get_confidence_recommendation(self, confidence: float) -> str:
        """
        Get recommendation based on confidence level.
        
        Returns:
            Recommendation string
        """
        if confidence < 0.3:
            return 'low_conviction_reduce_position_sizes'
        elif confidence < 0.6:
            return 'moderate_conviction_normal_sizing'
        else:
            return 'high_conviction_can_increase_sizes'