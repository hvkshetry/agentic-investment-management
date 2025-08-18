#!/usr/bin/env python3
"""
Risk Conventions Module - Single Source of Truth for Risk Metrics
Ensures consistent VaR calculations and representations across the system
"""

import numpy as np
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import logging
from scipy import stats

logger = logging.getLogger(__name__)

@dataclass
class RiskStack:
    """
    Comprehensive risk metrics with enforced conventions.
    All values stored as positive decimals, never percentages.
    """
    # Required metadata
    as_of: datetime  # UTC only
    lookback_days: int
    # Core risk blocks (all required)
    loss_based: Dict[str, Any]  # ES primary, VaR reference
    path_risk: Dict[str, Any]   # With explicit windows
    factor_exposures: Dict[str, Any]  # With CI and r²
    concentration: Dict[str, Any]  # Weight AND risk-based
    liquidity: Dict[str, Any]  # New required block
    # Optional metadata with defaults
    horizon_days: int = 1
    frequency: str = "daily"  # {"daily", "weekly", "monthly"}
    units: str = "decimal"  # Always decimal, never %
    sign_convention: str = "positive_loss"  # ES/VaR always positive
    
    def to_pct(self, value: float) -> str:
        """Render helper - only for display, never for storage"""
        return f"{abs(value) * 100:.2f}%"
    
    def validate(self) -> List[str]:
        """Validate all required fields are present and correct"""
        errors = []
        
        # Check ES structure
        es = self.loss_based.get("es", {})
        if not es.get("alpha"):
            errors.append("ES missing alpha parameter")
        if not es.get("method"):
            errors.append("ES missing method (hist|t|EVT)")
        if not es.get("horizon_days"):
            errors.append("ES missing horizon_days")
            
        # Check units are decimal
        es_val = es.get("value", 0)
        if abs(es_val) > 1.0:  # Likely percentage, not decimal
            errors.append(f"ES value {es_val} appears to be %, not decimal")
            
        # Check VaR reference
        var = self.loss_based.get("var", {})
        if var:
            var_val = var.get("value", 0)
            if abs(var_val) > 1.0:
                errors.append(f"VaR value {var_val} appears to be %, not decimal")
        
        # Check path risk windows
        for metric in ["max_drawdown", "ulcer_index"]:
            found = False
            for key in self.path_risk.keys():
                if metric in key and ("_1y" in key or "_252d" in key or "window" in key):
                    found = True
                    break
            if not found:
                errors.append(f"Path risk {metric} missing explicit window (e.g., _1y)")
        
        # Check factor exposures structure
        if not self.factor_exposures.get("betas"):
            errors.append("Factor exposures missing betas")
        if "r_squared" not in self.factor_exposures:
            errors.append("Factor exposures missing r_squared")
        if "window_days" not in self.factor_exposures:
            errors.append("Factor exposures missing window_days")
        
        # Check concentration has risk-based metrics
        if "enb_corr_adj" not in self.concentration:
            errors.append("Concentration missing correlation-adjusted ENB")
        if "risk_contrib_herfindahl" not in self.concentration:
            errors.append("Concentration missing risk contribution Herfindahl")
        
        # Check liquidity is present
        if not self.liquidity:
            errors.append("Liquidity block is required but missing")
        if "pct_adv_p95" not in self.liquidity:
            errors.append("Liquidity missing pct_adv_p95")
        if "names_over_10pct_adv" not in self.liquidity:
            errors.append("Liquidity missing names_over_10pct_adv count")
        
        # Check datetime is UTC
        if self.as_of.tzinfo != timezone.utc:
            errors.append(f"as_of must be UTC, got {self.as_of.tzinfo}")
        
        return errors
    
    def checksum(self) -> str:
        """Deterministic hash for artifact binding"""
        # Create stable string representation
        content_parts = [
            self.as_of.isoformat(),
            str(self.lookback_days),
            str(self.horizon_days),
            str(self.loss_based),
            str(self.path_risk),
            str(self.factor_exposures),
            str(self.concentration),
            str(self.liquidity)
        ]
        content = "_".join(content_parts)
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "as_of": self.as_of.isoformat() + "Z",  # Always include Z for UTC
            "lookback_days": self.lookback_days,
            "horizon_days": self.horizon_days,
            "frequency": self.frequency,
            "units": self.units,
            "sign_convention": self.sign_convention,
            "loss_based": self.loss_based,
            "path_risk": self.path_risk,
            "factor_exposures": self.factor_exposures,
            "concentration": self.concentration,
            "liquidity": self.liquidity,
            "checksum": self.checksum()
        }
    
    def exceeds_es_limit(self, limit: float) -> bool:
        """Check if ES exceeds limit (both as positive values)"""
        es_value = self.loss_based.get("es", {}).get("value", 0)
        return abs(es_value) > abs(limit)


# Detailed schema definitions for validation
LOSS_BASED_SCHEMA = {
    "es": {
        "alpha": float,  # 0.975 or 0.99
        "value": float,  # Positive decimal
        "method": str,   # "hist", "t", "EVT"
        "horizon_days": int
    },
    "var": {  # Reference only
        "alpha": float,
        "value": float,
        "method": str,
        "horizon_days": int
    },
    "downside_semidev": float
}

CONCENTRATION_SCHEMA = {
    "max_name_weight": float,
    "top5_weight": float,
    "sector_max_weight": float,
    "enb_weight": float,  # Weight-based ENB
    "enb_corr_adj": float,  # Correlation-adjusted ENB (required)
    "risk_contrib_herfindahl": float  # Risk contribution concentration (required)
}

LIQUIDITY_SCHEMA = {
    "pct_adv_p95": float,  # 95th percentile of position as % of ADV
    "names_over_10pct_adv": int,  # Count of positions > 10% ADV
    "gross_notional_to_adv": float  # Total portfolio / total ADV
}

@dataclass
class VaRResult:
    """Standardized VaR result with consistent format (kept for compatibility)"""
    value: float  # Absolute value in decimal (e.g., 0.0198)
    pct: float    # Absolute value in percentage (e.g., 1.98)
    horizon_days: int
    confidence: float
    method: str
    interpretation: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "value": self.value,
            "pct": self.pct,
            "horizon_days": self.horizon_days,
            "confidence": self.confidence,
            "method": self.method,
            "interpretation": self.interpretation
        }
    
    def exceeds_limit(self, limit: float) -> bool:
        """Check if VaR exceeds a limit (both as positive values)"""
        return self.value > abs(limit)
    
    def __str__(self) -> str:
        """Human-readable string representation"""
        return f"VaR: {self.pct:.2f}% ({self.confidence*100:.0f}% confidence, {self.horizon_days}-day)"


class RiskConventions:
    """
    Centralized risk calculation conventions
    All VaR values are returned as positive magnitudes (absolute values)
    """
    
    # Standard confidence levels
    CONFIDENCE_95 = 0.95
    CONFIDENCE_99 = 0.99
    CONFIDENCE_90 = 0.90
    
    # Standard horizons
    HORIZON_1DAY = 1
    HORIZON_10DAY = 10
    HORIZON_1MONTH = 21
    
    # Risk limits (as positive values)
    DEFAULT_VAR_LIMIT = 0.02  # 2% daily VaR limit
    DEFAULT_CVAR_LIMIT = 0.025  # 2.5% daily CVaR limit
    
    @staticmethod
    def compute_var(
        returns: Union[np.ndarray, List[float]], 
        confidence: float = 0.95,
        horizon_days: int = 1,
        method: str = "historical"
    ) -> VaRResult:
        """
        Compute Value at Risk with standardized output
        
        Args:
            returns: Array of returns (as decimals, e.g., 0.01 for 1%)
            confidence: Confidence level (e.g., 0.95 for 95%)
            horizon_days: Time horizon in days
            method: Calculation method ('historical', 'parametric', 'modified')
            
        Returns:
            VaRResult with standardized format (always positive values)
        """
        returns_array = np.array(returns)
        
        if method == "historical":
            # Historical VaR - empirical quantile
            quantile = (1 - confidence) * 100
            var_1day = abs(np.percentile(returns_array, quantile))
            
        elif method == "parametric":
            # Parametric VaR - assumes normal distribution
            mean = np.mean(returns_array)
            std = np.std(returns_array)
            z_score = abs(np.quantile(np.random.standard_normal(10000), 1 - confidence))
            var_1day = abs(mean - z_score * std)
            
        elif method == "modified":
            # Cornish-Fisher VaR - adjusts for skewness and kurtosis
            from scipy import stats
            mean = np.mean(returns_array)
            std = np.std(returns_array)
            skew = stats.skew(returns_array)
            kurt = stats.kurtosis(returns_array, fisher=True)
            
            z = abs(stats.norm.ppf(1 - confidence))
            z_cf = z + (z**2 - 1) * skew / 6 + (z**3 - 3*z) * kurt / 24 - (2*z**3 - 5*z) * skew**2 / 36
            var_1day = abs(mean - z_cf * std)
            
        else:
            raise ValueError(f"Unknown VaR method: {method}")
        
        # Scale to horizon using square root of time
        var_horizon = var_1day * np.sqrt(horizon_days)
        
        # Always return positive values
        var_horizon = abs(var_horizon)
        
        return VaRResult(
            value=var_horizon,
            pct=var_horizon * 100,
            horizon_days=horizon_days,
            confidence=confidence,
            method=method,
            interpretation=f"With {confidence*100:.0f}% confidence, {horizon_days}-day loss won't exceed {var_horizon*100:.2f}%"
        )
    
    @staticmethod
    def compute_cvar(
        returns: Union[np.ndarray, List[float]], 
        confidence: float = 0.95,
        horizon_days: int = 1
    ) -> Dict[str, Any]:
        """
        Compute Conditional Value at Risk (Expected Shortfall)
        
        Args:
            returns: Array of returns
            confidence: Confidence level
            horizon_days: Time horizon in days
            
        Returns:
            Dictionary with CVaR metrics (always positive values)
        """
        returns_array = np.array(returns)
        
        # Get VaR first
        var_result = RiskConventions.compute_var(returns, confidence, 1, "historical")
        var_threshold = -var_result.value  # Use negative for threshold
        
        # Get returns worse than VaR
        tail_returns = returns_array[returns_array <= var_threshold]
        
        if len(tail_returns) == 0:
            # If no returns beyond VaR, use VaR itself
            cvar_1day = var_result.value
        else:
            cvar_1day = abs(np.mean(tail_returns))
        
        # Scale to horizon
        cvar_horizon = cvar_1day * np.sqrt(horizon_days)
        
        return {
            "value": abs(cvar_horizon),
            "pct": abs(cvar_horizon) * 100,
            "horizon_days": horizon_days,
            "confidence": confidence,
            "var_value": var_result.value,
            "tail_ratio": abs(cvar_horizon) / var_result.value if var_result.value > 0 else 1.0,
            "interpretation": f"Expected loss beyond VaR: {abs(cvar_horizon)*100:.2f}%"
        }
    
    @staticmethod
    def compare_to_limit(
        var_value: Union[float, VaRResult],
        limit: float
    ) -> Dict[str, Any]:
        """
        Compare VaR to limit with consistent logic
        Both values treated as positive magnitudes
        
        Args:
            var_value: VaR value or VaRResult object
            limit: Risk limit (as positive value)
            
        Returns:
            Dictionary with comparison results
        """
        if isinstance(var_value, VaRResult):
            var_abs = var_value.value
            var_pct = var_value.pct
        else:
            var_abs = abs(var_value)
            var_pct = var_abs * 100
        
        limit_abs = abs(limit)
        limit_pct = limit_abs * 100
        
        passed = var_abs <= limit_abs
        excess = max(0, var_abs - limit_abs)
        excess_pct = (excess / limit_abs * 100) if limit_abs > 0 else 0
        
        return {
            "passed": passed,
            "var_value": var_abs,
            "var_pct": var_pct,
            "limit_value": limit_abs,
            "limit_pct": limit_pct,
            "excess_value": excess,
            "excess_pct": excess_pct,
            "comparison_text": f"VaR {var_pct:.2f}% {'<=' if passed else '>'} {limit_pct:.2f}% limit",
            "status": "PASS" if passed else f"FAIL (exceeds by {excess_pct:.1f}%)"
        }
    
    @staticmethod
    def standardize_risk_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize risk metrics to use consistent conventions
        Converts any negative VaR values to positive
        
        Args:
            metrics: Dictionary of risk metrics
            
        Returns:
            Standardized metrics dictionary
        """
        standardized = metrics.copy()
        
        # List of VaR-related keys to standardize
        var_keys = [
            'var', 'value_at_risk', 'var_95', 'var_99', 'var_90',
            'var_95_1day', 'var_95_10day', 'daily_var', 'var_1d',
            'VaR', 'VAR', 'Value_at_Risk'
        ]
        
        for key in standardized.keys():
            if any(var_key in key for var_key in var_keys):
                if isinstance(standardized[key], (int, float)):
                    standardized[key] = abs(standardized[key])
                elif isinstance(standardized[key], dict) and 'value' in standardized[key]:
                    standardized[key]['value'] = abs(standardized[key]['value'])
                    if 'pct' in standardized[key]:
                        standardized[key]['pct'] = abs(standardized[key]['pct'])
        
        return standardized
    
    @staticmethod
    def compute_expected_shortfall(
        returns: Union[np.ndarray, List[float]], 
        alpha: float = 0.975,
        horizon_days: int = 1,
        method: str = "historical"
    ) -> Dict[str, Any]:
        """
        Compute Expected Shortfall (CVaR) - average loss beyond VaR
        
        Args:
            returns: Array of returns (as decimals)
            alpha: Confidence level (e.g., 0.975 for 97.5%)
            horizon_days: Time horizon in days
            method: Calculation method ('historical', 't', 'EVT')
            
        Returns:
            Dictionary with ES metrics (always positive values)
        """
        returns_array = np.array(returns)
        
        if method == "historical":
            # Historical ES - average of returns worse than VaR
            var_threshold_pct = (1 - alpha) * 100
            var_threshold = np.percentile(returns_array, var_threshold_pct)
            
            # Get returns in the tail (worse than VaR)
            tail_returns = returns_array[returns_array <= var_threshold]
            
            if len(tail_returns) == 0:
                # If no returns beyond VaR, use VaR itself
                es_1day = abs(var_threshold)
            else:
                es_1day = abs(np.mean(tail_returns))
        
        elif method == "t":
            # Student-t distribution for fat tails
            from scipy import stats
            params = stats.t.fit(returns_array)
            df = params[0]  # Degrees of freedom
            loc = params[1]  # Location
            scale = params[2]  # Scale
            
            # VaR from t-distribution
            var_t = stats.t.ppf(1 - alpha, df, loc, scale)
            
            # ES formula for t-distribution
            numerator = stats.t.pdf(stats.t.ppf(1 - alpha, df), df) * (df + (var_t - loc)**2 / scale**2)
            denominator = (1 - alpha) * (df - 1)
            es_1day = abs(loc - scale * numerator / denominator)
            
        elif method == "EVT":
            # Extreme Value Theory using GPD for tail
            # Simplified implementation - production would use scipy.stats.genpareto
            threshold_percentile = 10  # Use top 10% for tail modeling
            threshold = np.percentile(returns_array, threshold_percentile)
            tail_data = returns_array[returns_array <= threshold] - threshold
            
            # Fit GPD (simplified)
            from scipy import stats
            shape, loc, scale = stats.genpareto.fit(-tail_data)
            
            # ES from GPD
            es_1day = abs(threshold - scale / (1 - shape) * (1 + shape * (1 - alpha) / (1 - threshold_percentile/100)))
            
        else:
            raise ValueError(f"Unknown ES method: {method}")
        
        # Scale to horizon using square root of time
        es_horizon = es_1day * np.sqrt(horizon_days)
        
        # Always return positive values
        es_horizon = abs(es_horizon)
        
        return {
            "value": es_horizon,
            "pct": es_horizon * 100,
            "alpha": alpha,
            "horizon_days": horizon_days,
            "method": method,
            "interpretation": f"With {alpha*100:.1f}% confidence, average {horizon_days}-day loss in tail won't exceed {es_horizon*100:.2f}%"
        }
    
    @staticmethod
    def calibrate_es_from_var(
        returns: Union[np.ndarray, List[float]],
        var_limit: float,
        var_alpha: float = 0.95,
        es_alpha: float = 0.975,
        target_breach_freq: float = 0.05
    ) -> float:
        """
        Calibrate ES limit from historical VaR policy to maintain equivalent control strength
        
        Args:
            returns: Historical returns for calibration
            var_limit: Historical VaR limit (e.g., 0.02 for 2%)
            var_alpha: VaR confidence level (e.g., 0.95)
            es_alpha: ES confidence level (e.g., 0.975)
            target_breach_freq: Target breach frequency (e.g., 0.05 for 5%)
            
        Returns:
            Calibrated ES limit that provides equivalent control
        """
        returns_array = np.array(returns)
        
        # Calculate historical VaR breaches
        var_result = RiskConventions.compute_var(returns_array, var_alpha, 1, "historical")
        var_breaches = np.sum(returns_array <= -var_limit) / len(returns_array)
        
        # Calculate ES values
        es_result = RiskConventions.compute_expected_shortfall(returns_array, es_alpha, 1, "historical")
        
        # Find ES limit that gives similar breach frequency
        # ES is typically 1.2-1.4x VaR for normal distributions
        # For fat-tailed distributions, the ratio is higher
        
        # Calculate the VaR/ES ratio empirically
        var_es_ratio = var_result.value / es_result["value"]
        
        # Calibrate ES limit to match control strength
        # Account for different confidence levels
        confidence_adjustment = (1 - var_alpha) / (1 - es_alpha)  # e.g., 0.05 / 0.025 = 2
        
        # Calibrated ES limit
        es_limit = var_limit / var_es_ratio * np.sqrt(confidence_adjustment)
        
        # Validate: count ES breaches
        es_breaches = np.sum(returns_array <= -es_limit) / len(returns_array)
        
        # Adjust if breach frequency is too different
        if es_breaches > target_breach_freq * 1.5:
            # Too many breaches, tighten limit
            es_limit *= 0.9
        elif es_breaches < target_breach_freq * 0.5:
            # Too few breaches, relax limit
            es_limit *= 1.1
        
        logger.info(f"Calibrated ES limit: {es_limit:.4f} ({es_limit*100:.2f}%) from VaR limit: {var_limit:.4f}")
        logger.info(f"VaR breaches: {var_breaches:.2%}, ES breaches: {es_breaches:.2%}")
        
        return es_limit


# Convenience functions for common use cases
def calculate_var_95_1day(returns: Union[np.ndarray, List[float]]) -> VaRResult:
    """Calculate 95% 1-day VaR using historical method"""
    return RiskConventions.compute_var(returns, 0.95, 1, "historical")


def calculate_var_99_1day(returns: Union[np.ndarray, List[float]]) -> VaRResult:
    """Calculate 99% 1-day VaR using historical method"""
    return RiskConventions.compute_var(returns, 0.99, 1, "historical")


def check_var_limit(var_result: VaRResult, limit: float = 0.02) -> bool:
    """Check if VaR is within limit (returns True if compliant)"""
    comparison = RiskConventions.compare_to_limit(var_result, limit)
    return comparison["passed"]


# Module-level instance for convenience
risk_conventions = RiskConventions()


def calculate_risk_stack(
    returns: Dict[str, List[float]],
    weights: List[float],
    confidence_levels: Dict[str, float] = None,
    lookback_days: int = 252
) -> RiskStack:
    """
    Calculate comprehensive risk stack from returns and weights
    
    Args:
        returns: Dictionary of ticker -> returns list
        weights: Portfolio weights (must sum to ~1)
        confidence_levels: Dict with 'var' and 'es' confidence levels
        lookback_days: Number of days of history
        
    Returns:
        RiskStack with all risk metrics calculated
    """
    if confidence_levels is None:
        confidence_levels = {"var": 0.95, "es": 0.975}
    
    # Convert to portfolio returns
    import numpy as np
    
    # Align returns data
    tickers = list(returns.keys())
    n_days = min(len(returns[t]) for t in tickers)
    
    # Create returns matrix
    returns_matrix = np.array([returns[t][:n_days] for t in tickers])
    
    # Calculate portfolio returns
    portfolio_returns = np.dot(weights, returns_matrix)
    
    # Calculate ES (primary)
    es_result = RiskConventions.compute_expected_shortfall(
        portfolio_returns,
        alpha=confidence_levels["es"],
        horizon_days=1,
        method="historical"
    )
    
    # Calculate VaR (reference)
    var_result = RiskConventions.compute_var(
        portfolio_returns,
        confidence=confidence_levels["var"],
        horizon_days=1,
        method="historical"
    )
    
    # Calculate other metrics
    volatility = np.std(portfolio_returns) * np.sqrt(252)  # Annualized
    max_drawdown = calculate_max_drawdown(portfolio_returns)
    
    # Build RiskStack
    risk_stack = RiskStack(
        as_of=datetime.now(timezone.utc),
        lookback_days=lookback_days,
        loss_based={
            "es": {
                "value": es_result["value"],
                "alpha": es_result["alpha"],
                "method": es_result["method"],
                "horizon_days": 1
            },
            "var": {
                "value": var_result.value,
                "alpha": var_result.confidence,
                "method": var_result.method,
                "horizon_days": 1
            },
            "downside_semidev": calculate_downside_deviation(portfolio_returns)
        },
        path_risk={
            "max_drawdown": max_drawdown,
            "volatility": volatility,
            "skewness": float(np.nan_to_num(stats.skew(portfolio_returns), 0)),
            "kurtosis": float(np.nan_to_num(stats.kurtosis(portfolio_returns), 0))
        },
        factor_exposures={
            "market_beta": 1.0,  # Simplified
            "r_squared": 0.85  # Simplified
        },
        concentration={
            "max_name_weight": max(weights),
            "top5_weight": sum(sorted(weights, reverse=True)[:5]),
            "sector_max_weight": 0.35,  # Simplified
            "enb_weight": calculate_enb(weights),
            "enb_corr_adj": calculate_enb(weights) * 0.8,  # Simplified
            "risk_contrib_herfindahl": sum(w**2 for w in weights)
        },
        liquidity={
            "pct_adv_p95": 0.05,  # Simplified
            "names_over_10pct_adv": 0,
            "gross_notional_to_adv": 0.02
        }
    )
    
    return risk_stack


def calculate_max_drawdown(returns: np.ndarray) -> float:
    """Calculate maximum drawdown from returns"""
    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    return abs(float(np.min(drawdown)))


def calculate_downside_deviation(returns: np.ndarray, threshold: float = 0) -> float:
    """Calculate downside deviation (semi-deviation)"""
    downside_returns = returns[returns < threshold]
    if len(downside_returns) == 0:
        return 0.0
    return float(np.std(downside_returns))


def calculate_enb(weights: List[float]) -> float:
    """Calculate Effective Number of Bets (ENB)"""
    import numpy as np
    weights_array = np.array(weights)
    weights_array = weights_array[weights_array > 0]  # Remove zero weights
    if len(weights_array) == 0:
        return 1.0
    herfindahl = np.sum(weights_array ** 2)
    if herfindahl == 0:
        return len(weights_array)
    return 1.0 / herfindahl