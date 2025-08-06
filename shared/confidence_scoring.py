#!/usr/bin/env python3
"""
Confidence Scoring Framework
Provides transparency and quality metrics for all MCP server responses
Addresses reviewer feedback from ~/investing/feedback.md
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger("confidence_scoring")

@dataclass
class ConfidenceMetrics:
    """Container for confidence scoring components"""
    overall_score: float
    data_quality: float
    sample_adequacy: float
    model_stability: float
    parameter_certainty: float
    warnings: List[str]
    methodology: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'overall_score': round(self.overall_score, 3),
            'components': {
                'data_quality': round(self.data_quality, 3),
                'sample_adequacy': round(self.sample_adequacy, 3),
                'model_stability': round(self.model_stability, 3),
                'parameter_certainty': round(self.parameter_certainty, 3)
            },
            'warnings': self.warnings,
            'methodology': self.methodology
        }

class ConfidenceScorer:
    """
    Evaluates confidence in financial calculations and model outputs
    Per reviewer requirement: "Return confidence scores based on data quality"
    """
    
    def __init__(self):
        self.min_sample_size = 252  # 1 year of trading days
        self.optimal_sample_size = 756  # 3 years
        self.max_condition_number = 1000
        self.min_r_squared = 0.3
        self.min_t_stat = 2.0
    
    def score_portfolio_optimization(
        self,
        sample_size: int,
        condition_number: float,
        optimization_status: bool,
        constraint_violations: float = 0,
        covariance_method: str = 'sample'
    ) -> ConfidenceMetrics:
        """
        Score confidence in portfolio optimization results
        
        Args:
            sample_size: Number of observations used
            condition_number: Condition number of covariance matrix
            optimization_status: Whether optimization converged
            constraint_violations: Sum of constraint violations
            covariance_method: Method used for covariance estimation
        
        Returns:
            ConfidenceMetrics object with scores and warnings
        """
        warnings = []
        
        # Sample adequacy (0-1 scale)
        sample_score = min(1.0, sample_size / self.optimal_sample_size)
        if sample_size < self.min_sample_size:
            warnings.append(f"Small sample size: {sample_size} days (recommend {self.min_sample_size}+)")
            sample_score *= 0.5  # Heavy penalty
        
        # Model stability based on condition number
        if condition_number < 100:
            stability_score = 1.0
        elif condition_number < self.max_condition_number:
            stability_score = 1.0 - (condition_number - 100) / (self.max_condition_number - 100) * 0.5
        else:
            stability_score = 0.3
            warnings.append(f"High condition number ({condition_number:.0f}): Matrix near-singular")
        
        # Optimization convergence
        convergence_score = 1.0 if optimization_status else 0.5
        if not optimization_status:
            warnings.append("Optimization did not fully converge")
        
        # Constraint adherence
        constraint_score = max(0.3, 1.0 - constraint_violations)
        if constraint_violations > 0.01:
            warnings.append(f"Constraint violations: {constraint_violations:.3f}")
        
        # Method quality bonus
        method_bonus = {
            'ledoit_wolf': 0.15,
            'oracle_shrinkage': 0.15,
            'exp_weighted': 0.10,
            'robust': 0.10,
            'sample': 0.0
        }.get(covariance_method, 0.0)
        
        # Calculate overall score
        weights = {
            'sample': 0.25,
            'stability': 0.30,
            'convergence': 0.25,
            'constraints': 0.20
        }
        
        base_score = (
            sample_score * weights['sample'] +
            stability_score * weights['stability'] +
            convergence_score * weights['convergence'] +
            constraint_score * weights['constraints']
        )
        
        overall_score = min(1.0, base_score + method_bonus)
        
        # Add interpretation warning
        if overall_score < 0.6:
            warnings.append("Low confidence: Results should be interpreted with caution")
        elif overall_score < 0.8:
            warnings.append("Moderate confidence: Consider additional validation")
        
        return ConfidenceMetrics(
            overall_score=overall_score,
            data_quality=sample_score,
            sample_adequacy=sample_score,
            model_stability=stability_score,
            parameter_certainty=convergence_score,
            warnings=warnings,
            methodology=f"Covariance: {covariance_method}, Optimization: {'converged' if optimization_status else 'partial'}"
        )
    
    def score_risk_calculation(
        self,
        sample_size: int,
        distribution_test_pvalue: float,
        tail_observations: int,
        methodology: str = 'historical'
    ) -> ConfidenceMetrics:
        """
        Score confidence in risk metrics (VaR, CVaR, etc.)
        
        Args:
            sample_size: Number of observations
            distribution_test_pvalue: P-value from normality/distribution test
            tail_observations: Number of observations in the tail (for VaR/CVaR)
            methodology: Risk calculation method
        
        Returns:
            ConfidenceMetrics object
        """
        warnings = []
        
        # Sample adequacy
        sample_score = min(1.0, sample_size / self.optimal_sample_size)
        if sample_size < self.min_sample_size:
            warnings.append(f"Insufficient history: {sample_size} days")
            sample_score *= 0.6
        
        # Distribution fit quality
        if distribution_test_pvalue < 0.01:
            dist_score = 0.4
            warnings.append("Poor distribution fit: Consider fat-tail models")
        elif distribution_test_pvalue < 0.05:
            dist_score = 0.7
            warnings.append("Marginal distribution fit")
        else:
            dist_score = 1.0
        
        # Tail observation adequacy (for extreme risk measures)
        min_tail_obs = 30
        tail_score = min(1.0, tail_observations / min_tail_obs)
        if tail_observations < min_tail_obs:
            warnings.append(f"Few tail observations ({tail_observations}): High uncertainty in extreme risk")
        
        # Method quality
        method_scores = {
            'historical': 0.7,
            'parametric': 0.6,
            'monte_carlo': 0.8,
            'evt': 0.9,  # Extreme Value Theory
            'conditional': 0.85
        }
        method_score = method_scores.get(methodology, 0.5)
        
        # Overall calculation
        overall_score = (
            sample_score * 0.30 +
            dist_score * 0.25 +
            tail_score * 0.25 +
            method_score * 0.20
        )
        
        if overall_score < 0.6:
            warnings.append("Low confidence in risk estimates")
        
        return ConfidenceMetrics(
            overall_score=overall_score,
            data_quality=(sample_score + dist_score) / 2,
            sample_adequacy=sample_score,
            model_stability=tail_score,
            parameter_certainty=method_score,
            warnings=warnings,
            methodology=f"Risk method: {methodology}"
        )
    
    def score_tax_calculation(
        self,
        data_completeness: float,
        calculation_complexity: str,
        jurisdiction_support: bool,
        edge_cases_handled: List[str]
    ) -> ConfidenceMetrics:
        """
        Score confidence in tax calculations
        
        Args:
            data_completeness: Fraction of required data provided (0-1)
            calculation_complexity: 'simple', 'moderate', 'complex'
            jurisdiction_support: Whether jurisdiction is fully supported
            edge_cases_handled: List of handled edge cases
        
        Returns:
            ConfidenceMetrics object
        """
        warnings = []
        
        # Data completeness
        data_score = data_completeness
        if data_completeness < 0.95:
            warnings.append(f"Incomplete data: {(1-data_completeness)*100:.1f}% missing")
        
        # Complexity handling
        complexity_scores = {
            'simple': 1.0,
            'moderate': 0.85,
            'complex': 0.7
        }
        complexity_score = complexity_scores.get(calculation_complexity, 0.6)
        
        # Jurisdiction support
        jurisdiction_score = 1.0 if jurisdiction_support else 0.6
        if not jurisdiction_support:
            warnings.append("Jurisdiction partially supported: Manual review recommended")
        
        # Edge case coverage
        important_cases = ['NIIT', 'AMT', 'wash_sales', 'qualified_dividends', 'trust_income']
        covered = sum(1 for case in important_cases if case in edge_cases_handled)
        coverage_score = covered / len(important_cases)
        
        missing_cases = [case for case in important_cases if case not in edge_cases_handled]
        if missing_cases:
            warnings.append(f"Not handling: {', '.join(missing_cases)}")
        
        # Overall score
        overall_score = (
            data_score * 0.35 +
            complexity_score * 0.20 +
            jurisdiction_score * 0.25 +
            coverage_score * 0.20
        )
        
        if overall_score < 0.8:
            warnings.append("Consider professional tax advice for verification")
        
        return ConfidenceMetrics(
            overall_score=overall_score,
            data_quality=data_score,
            sample_adequacy=1.0,  # Not applicable for tax
            model_stability=jurisdiction_score,
            parameter_certainty=coverage_score,
            warnings=warnings,
            methodology=f"Tax complexity: {calculation_complexity}"
        )
    
    def add_confidence_to_response(
        self,
        result: Dict[str, Any],
        confidence: ConfidenceMetrics,
        calculation_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Wrap any server response with confidence metadata
        
        Args:
            result: Original calculation result
            confidence: Confidence metrics
            calculation_details: Optional additional details
        
        Returns:
            Enhanced response with confidence scoring
        """
        enhanced = {
            'result': result,
            'confidence': confidence.to_dict()
        }
        
        if calculation_details:
            enhanced['calculation_details'] = calculation_details
        
        # Add high-level summary
        score = confidence.overall_score
        if score >= 0.9:
            enhanced['confidence_level'] = 'HIGH'
        elif score >= 0.7:
            enhanced['confidence_level'] = 'MODERATE'
        elif score >= 0.5:
            enhanced['confidence_level'] = 'LOW'
        else:
            enhanced['confidence_level'] = 'VERY_LOW'
        
        return enhanced

# Singleton for import
confidence_scorer = ConfidenceScorer()

if __name__ == "__main__":
    # Test confidence scoring
    scorer = ConfidenceScorer()
    
    # Test portfolio optimization confidence
    print("Testing portfolio optimization confidence:")
    portfolio_confidence = scorer.score_portfolio_optimization(
        sample_size=180,  # Less than recommended
        condition_number=1500,  # High
        optimization_status=True,
        constraint_violations=0.001,
        covariance_method='ledoit_wolf'
    )
    print(f"Score: {portfolio_confidence.overall_score:.2f}")
    print(f"Warnings: {portfolio_confidence.warnings}")
    
    # Test risk calculation confidence
    print("\nTesting risk calculation confidence:")
    risk_confidence = scorer.score_risk_calculation(
        sample_size=500,
        distribution_test_pvalue=0.03,
        tail_observations=25,
        methodology='historical'
    )
    print(f"Score: {risk_confidence.overall_score:.2f}")
    print(f"Warnings: {risk_confidence.warnings}")
    
    # Test tax calculation confidence
    print("\nTesting tax calculation confidence:")
    tax_confidence = scorer.score_tax_calculation(
        data_completeness=0.98,
        calculation_complexity='complex',
        jurisdiction_support=True,
        edge_cases_handled=['NIIT', 'qualified_dividends']
    )
    print(f"Score: {tax_confidence.overall_score:.2f}")
    print(f"Warnings: {tax_confidence.warnings}")