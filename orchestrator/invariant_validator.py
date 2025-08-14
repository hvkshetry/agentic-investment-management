#!/usr/bin/env python3
"""
Invariant Validator - Cross-artifact consistency validation
Ensures all artifacts in a session maintain consistent values and references
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from .tax_ledger_manager import TaxLedgerManager

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of invariant validation"""
    passed: bool
    errors: List[str]
    warnings: List[str]
    checks_performed: int
    artifacts_validated: List[str]

class InvariantValidator:
    """
    Validates consistency across all artifacts in a session
    """
    
    def __init__(self, session_directory: str):
        """
        Initialize with session directory
        
        Args:
            session_directory: Path to session directory (e.g., ./runs/20250813_143022/)
        """
        self.session_directory = Path(session_directory)
        self.tax_ledger_manager = TaxLedgerManager(session_directory)
        self.artifacts = {}
        self.errors = []
        self.warnings = []
        self.checks_performed = 0
        
    def load_artifacts(self) -> Dict[str, Any]:
        """
        Load all JSON artifacts from session directory
        
        Returns:
            Dictionary of artifacts keyed by filename
        """
        artifacts = {}
        
        for json_file in self.session_directory.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    artifacts[json_file.name] = json.load(f)
                    logger.info(f"Loaded artifact: {json_file.name}")
            except Exception as e:
                logger.error(f"Failed to load {json_file.name}: {e}")
                self.errors.append(f"Failed to load {json_file.name}: {e}")
                
        self.artifacts = artifacts
        return artifacts
        
    def validate_all(self) -> ValidationResult:
        """
        Run all validation checks
        
        Returns:
            ValidationResult with all findings
        """
        # Load artifacts
        self.load_artifacts()
        
        if not self.artifacts:
            return ValidationResult(
                passed=False,
                errors=["No artifacts found in session directory"],
                warnings=[],
                checks_performed=0,
                artifacts_validated=[]
            )
        
        # Run validation checks
        self.validate_portfolio_value_consistency()
        self.validate_tax_consistency()
        self.validate_allocation_math()
        self.validate_stress_test_variation()
        self.validate_risk_metrics_consistency()
        self.validate_execution_guidance()
        self.validate_symbol_validity()
        self.validate_date_consistency()
        self.validate_concentration_limits()
        
        return ValidationResult(
            passed=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            checks_performed=self.checks_performed,
            artifacts_validated=list(self.artifacts.keys())
        )
        
    def validate_portfolio_value_consistency(self):
        """
        Ensure all artifacts use the same portfolio value
        """
        self.checks_performed += 1
        portfolio_values = []
        
        # Extract portfolio values from different artifacts
        for name, artifact in self.artifacts.items():
            if 'portfolio_snapshot' in name:
                value = self._extract_value(artifact, ['payload', 'total_value'])
                if value:
                    portfolio_values.append(('portfolio_snapshot', value))
                    
            elif 'risk' in name:
                value = self._extract_value(artifact, ['payload', 'portfolio_value'])
                if value:
                    portfolio_values.append((name, value))
                    
            elif 'tax' in name:
                value = self._extract_value(artifact, ['payload', 'portfolio_summary', 'total_value'])
                if value:
                    portfolio_values.append((name, value))
                    
        # Check consistency
        if portfolio_values:
            base_value = portfolio_values[0][1]
            for source, value in portfolio_values[1:]:
                # Allow small rounding differences (< $100)
                if abs(value - base_value) > 100:
                    self.errors.append(
                        f"Portfolio value mismatch: {source} shows ${value:,.2f} "
                        f"vs baseline ${base_value:,.2f}"
                    )
                    
    def validate_tax_consistency(self):
        """
        Ensure all tax references match the tax ledger
        """
        self.checks_performed += 1
        
        # Get tax ledger values
        tax_summary = self.tax_ledger_manager.get_summary_for_artifacts()
        if not tax_summary:
            self.warnings.append("No tax ledger found - cannot validate tax consistency")
            return
            
        ledger_tax_savings = tax_summary.get('tax_savings', 0)
        ledger_net_benefit = tax_summary.get('net_tax_benefit', 0)
        
        # Check each artifact
        for name, artifact in self.artifacts.items():
            if 'tax' in name:
                continue  # Skip the tax artifact itself
                
            # Look for tax values in artifacts
            self._check_tax_value(artifact, name, 'tax_savings', ledger_tax_savings)
            self._check_tax_value(artifact, name, 'net_tax_benefit', ledger_net_benefit)
            self._check_tax_value(artifact, name, 'net_after_tax_benefit', ledger_net_benefit)
            
    def _check_tax_value(self, artifact: Dict, name: str, field: str, expected: float):
        """Helper to check tax values in nested structures"""
        def search_dict(obj, target_key, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if key == target_key and isinstance(value, (int, float)):
                        if abs(value - expected) > 1.0:  # Allow $1 rounding
                            self.errors.append(
                                f"Tax mismatch in {name} at {new_path}: "
                                f"${value:,.2f} != ${expected:,.2f} (ledger)"
                            )
                    search_dict(value, target_key, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    search_dict(item, target_key, f"{path}[{i}]")
                    
        search_dict(artifact, field)
        
    def validate_allocation_math(self):
        """
        Ensure allocations sum to 100% and are internally consistent
        """
        self.checks_performed += 1
        
        for name, artifact in self.artifacts.items():
            # Check various allocation fields
            allocations = []
            
            # Portfolio snapshot allocations
            if 'asset_allocation' in str(artifact):
                alloc = self._extract_value(artifact, ['payload', 'asset_allocation'])
                if alloc and isinstance(alloc, dict):
                    total = sum(v for v in alloc.values() if isinstance(v, (int, float)))
                    if abs(total - 1.0) > 0.01 and abs(total - 100.0) > 0.01:
                        self.errors.append(
                            f"Allocation doesn't sum to 100% in {name}: {total:.2%}"
                        )
                        
    def validate_stress_test_variation(self):
        """
        Ensure stress tests show different results for different candidates
        """
        self.checks_performed += 1
        
        stress_results = {}
        
        # Extract stress test results
        for name, artifact in self.artifacts.items():
            if 'risk' in name:
                scenarios = self._extract_value(
                    artifact, 
                    ['payload', 'stress_test_results']
                )
                if scenarios:
                    stress_results[name] = scenarios
                    
        # Check for identical results across candidates
        if len(stress_results) > 1:
            results_list = list(stress_results.values())
            first_result = str(results_list[0])
            
            all_identical = all(str(r) == first_result for r in results_list[1:])
            if all_identical:
                self.errors.append(
                    "CRITICAL: All candidates show identical stress test results - "
                    "stress tests not using candidate-specific weights"
                )
                
    def validate_risk_metrics_consistency(self):
        """
        Ensure risk metrics are consistent within reasonable bounds
        """
        self.checks_performed += 1
        
        for name, artifact in self.artifacts.items():
            if 'risk' in name:
                # Check VaR is negative (loss)
                var_95 = self._extract_value(artifact, ['payload', 'var_95'])
                if var_95 and var_95 > 0:
                    self.warnings.append(
                        f"VaR should be negative (loss) in {name}: {var_95}"
                    )
                    
                # Check Sharpe ratio is reasonable
                sharpe = self._extract_value(artifact, ['payload', 'metrics', 'sharpe'])
                if sharpe and (sharpe < -2 or sharpe > 5):
                    self.warnings.append(
                        f"Unrealistic Sharpe ratio in {name}: {sharpe}"
                    )
                    
    def validate_execution_guidance(self):
        """
        Ensure execution guidance matches instrument types
        """
        self.checks_performed += 1
        
        for name, artifact in self.artifacts.items():
            if 'trade' in name or 'final' in name:
                trades = self._extract_value(artifact, ['payload', 'trades']) or \
                        self._extract_value(artifact, ['payload', 'buy_orders']) or []
                        
                for trade in trades:
                    if isinstance(trade, dict):
                        symbol = trade.get('symbol', '')
                        
                        # Check mutual funds don't have limit orders
                        if symbol in ['VWLUX', 'VMLUX', 'VWIUX']:
                            if 'limit' in str(trade).lower():
                                self.errors.append(
                                    f"Mutual fund {symbol} cannot use limit orders in {name}"
                                )
                                
    def validate_symbol_validity(self):
        """
        Check for outdated or invalid symbols
        """
        self.checks_performed += 1
        
        # Known outdated symbols
        outdated_symbols = {
            'ANTM': 'ELV',
            'FB': 'META',
            'TWTR': 'Delisted'
        }
        
        for name, artifact in self.artifacts.items():
            content = str(artifact)
            for old_symbol, new_symbol in outdated_symbols.items():
                if old_symbol in content:
                    self.errors.append(
                        f"Outdated symbol {old_symbol} found in {name} "
                        f"(should be {new_symbol})"
                    )
                    
    def validate_date_consistency(self):
        """
        Ensure dates are consistent with session date
        """
        self.checks_performed += 1
        
        # Extract session date from directory name
        session_date_str = self.session_directory.name  # e.g., "20250813_143022"
        try:
            session_year = int(session_date_str[:4])
            session_month = int(session_date_str[4:6])
        except:
            session_year = datetime.now().year
            session_month = datetime.now().month
            
        for name, artifact in self.artifacts.items():
            content = str(artifact)
            
            # Check for hardcoded old years
            if "2024" in content and session_year > 2024:
                self.errors.append(
                    f"Outdated year 2024 found in {name} (session year is {session_year})"
                )
                
            # Check for future years that don't make sense
            if str(session_year + 2) in content:
                self.warnings.append(
                    f"Far future year {session_year + 2} found in {name}"
                )
                
    def validate_concentration_limits(self):
        """
        Validate concentration checks are correct
        """
        self.checks_performed += 1
        
        for name, artifact in self.artifacts.items():
            if 'gate' in name:
                # Look for the problematic pattern
                content = str(artifact)
                
                # Check for logically impossible comparisons
                import re
                pattern = r'(\d+\.?\d*)%.*<.*(\d+\.?\d*)%.*limit'
                matches = re.findall(pattern, content)
                
                for match in matches:
                    value = float(match[0])
                    limit = float(match[1])
                    
                    if value > limit and 'PASS' in content:
                        self.errors.append(
                            f"Gate logic error in {name}: {value}% > {limit}% "
                            "but marked as PASS"
                        )
                        
    def _extract_value(self, obj: Any, path: List[str]) -> Any:
        """
        Extract value from nested dictionary using path
        
        Args:
            obj: Object to extract from
            path: List of keys to traverse
            
        Returns:
            Value at path or None
        """
        current = obj
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
        
    def generate_report(self) -> str:
        """
        Generate human-readable validation report
        
        Returns:
            Formatted report string
        """
        result = self.validate_all()
        
        report = "# Invariant Validation Report\n\n"
        report += f"**Session**: {self.session_directory.name}\n"
        report += f"**Artifacts Validated**: {len(result.artifacts_validated)}\n"
        report += f"**Checks Performed**: {result.checks_performed}\n\n"
        
        if result.passed:
            report += "✅ **PASSED**: All invariants satisfied\n\n"
        else:
            report += f"❌ **FAILED**: {len(result.errors)} errors found\n\n"
            
        if result.errors:
            report += "## Errors (Must Fix)\n"
            for error in result.errors:
                report += f"- {error}\n"
            report += "\n"
            
        if result.warnings:
            report += "## Warnings (Should Review)\n"
            for warning in result.warnings:
                report += f"- {warning}\n"
            report += "\n"
            
        report += "## Artifacts Validated\n"
        for artifact in result.artifacts_validated:
            report += f"- {artifact}\n"
            
        return report