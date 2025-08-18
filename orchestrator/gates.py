#!/usr/bin/env python3
"""
Gate System for Investment Workflow Validation
Enforces risk and tax constraints before allowing trades
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from shared.risk_conventions import RiskConventions, VaRResult
from .position_lookthrough import PositionLookthrough

logger = logging.getLogger(__name__)

@dataclass
class GateResult:
    """Result of a gate check"""
    passed: bool
    reason: str
    details: Dict[str, Any]

class RiskGate:
    """Risk validation gates for portfolio decisions"""
    
    # Risk limits (all as positive values)
    MAX_DAILY_VAR = 0.02  # 2.0% daily VaR (reduced from 2.5% per institutional standards)
    MAX_DRAWDOWN = 0.20    # 20% maximum drawdown
    MAX_SINGLE_COMPANY = 0.10  # 10% concentration limit for single companies (not funds)
    MIN_SHARPE = 0.3       # Minimum Sharpe ratio
    MAX_CORRELATION = 0.85  # Maximum correlation clustering
    
    @classmethod
    def check(cls, risk_report: Dict[str, Any]) -> GateResult:
        """Check if risk metrics pass all gates"""
        
        payload = risk_report.get("payload", {})
        failures = []
        proof_fields = {}  # Track actual values for transparency
        
        # Standardize VaR check using RiskConventions
        var_95_raw = payload.get("var_95", 0)
        var_95 = abs(var_95_raw)  # Ensure positive value
        
        # Use RiskConventions for comparison
        var_comparison = RiskConventions.compare_to_limit(var_95, cls.MAX_DAILY_VAR)
        proof_fields["var_check"] = var_comparison
        
        if not var_comparison["passed"]:
            failures.append(f"VaR {var_comparison['var_pct']:.2f}% exceeds {var_comparison['limit_pct']:.2f}% limit by {var_comparison['excess_pct']:.1f}%")
            
        # Check drawdown limit
        max_dd = abs(payload.get("max_drawdown", 0))
        proof_fields["drawdown_check"] = {
            "observed_value": max_dd,
            "limit": cls.MAX_DRAWDOWN,
            "passed": max_dd <= cls.MAX_DRAWDOWN
        }
        if max_dd > cls.MAX_DRAWDOWN:
            failures.append(f"Drawdown {max_dd:.2%} exceeds {cls.MAX_DRAWDOWN:.2%} limit")
            
        # Check Sharpe ratio
        sharpe = payload.get("metrics", {}).get("sharpe", 0)
        proof_fields["sharpe_check"] = {
            "observed_value": sharpe,
            "minimum": cls.MIN_SHARPE,
            "passed": sharpe >= cls.MIN_SHARPE
        }
        if sharpe < cls.MIN_SHARPE:
            failures.append(f"Sharpe {sharpe:.2f} below minimum {cls.MIN_SHARPE:.2f}")
            
        # NEW: Use look-through analysis for concentration check
        positions = payload.get("positions", {})
        lookthrough = PositionLookthrough(concentration_limit=cls.MAX_SINGLE_COMPANY)
        
        # Check if positions are funds or individual stocks
        for symbol, weight in positions.items():
            # Skip concentration check for diversified funds
            if lookthrough.is_fund(symbol):
                logger.info(f"{symbol} is a fund at {weight:.2%} weight - applying look-through analysis")
            else:
                # Direct holding of individual stock
                if weight > cls.MAX_SINGLE_COMPANY:
                    failures.append(f"Single company position too concentrated: {symbol} = {weight:.2%} > {cls.MAX_SINGLE_COMPANY:.2%}")
        
        # Perform look-through concentration analysis
        concentration_result = lookthrough.check_concentration_limits(positions)
        if not concentration_result.passed:
            for symbol, concentration in concentration_result.violations:
                failures.append(f"Look-through concentration violation: {symbol} = {concentration:.2%} > {cls.MAX_SINGLE_COMPANY:.2%}")
                
        # Check stress tests
        stress_tests = payload.get("stress_tests", {})
        for scenario, impact in stress_tests.items():
            if abs(impact) > 0.30:  # 30% loss in stress scenario
                failures.append(f"Stress test failure: {scenario} = {impact:.2%}")
                
        if failures:
            return GateResult(
                passed=False,
                reason="; ".join(failures),
                details={
                    "failures": failures, 
                    "metrics": payload,
                    "proof_fields": proof_fields,  # Include proof fields for transparency
                    "concentration_analysis": {
                        "max_company_exposure": concentration_result.max_concentration,
                        "max_company_symbol": concentration_result.max_concentration_symbol,
                        "violations": concentration_result.violations
                    } if 'concentration_result' in locals() else {}
                }
            )
            
        return GateResult(
            passed=True,
            reason="All risk checks passed",
            details={
                "metrics": payload,
                "proof_fields": proof_fields,  # Include proof fields for transparency
                "concentration_analysis": {
                    "max_company_exposure": concentration_result.max_concentration,
                    "max_company_symbol": concentration_result.max_concentration_symbol,
                    "passed": True
                } if 'concentration_result' in locals() else {}
            }
        )

class TaxGate:
    """Tax validation gates for trading decisions"""
    
    # Tax thresholds
    MAX_TAX_DRAG = 0.02     # 2% tax drag on returns
    WASH_SALE_WINDOW = 30   # Days for wash sale rule
    LTCG_THRESHOLD = 365    # Days for long-term capital gains
    
    @classmethod
    def check(cls, tax_impact: Dict[str, Any], trade_list: Dict[str, Any] = None) -> GateResult:
        """Check if tax implications are acceptable"""
        
        payload = tax_impact.get("payload", {})
        failures = []
        
        # Check wash sale risk
        if payload.get("wash_sale_risk", False):
            violations = payload.get("wash_sale_violations", [])
            failures.append(f"Wash sale risk detected: {violations}")
            
        # Check tax efficiency
        total_tax = payload.get("total_tax", 0)
        portfolio_value = payload.get("portfolio_value", 1000000)
        tax_drag = total_tax / portfolio_value if portfolio_value > 0 else 0
        
        if tax_drag > cls.MAX_TAX_DRAG:
            failures.append(f"Tax drag too high: {tax_drag:.2%} > {cls.MAX_TAX_DRAG:.2%}")
            
        # Check STCG vs LTCG ratio
        stcg = payload.get("stcg", 0)
        ltcg = payload.get("ltcg", 0)
        total_gains = stcg + ltcg
        
        if total_gains > 0:
            stcg_ratio = stcg / total_gains
            if stcg_ratio > 0.5:  # More than 50% short-term gains
                failures.append(f"Too many short-term gains: {stcg_ratio:.2%}")
                
        # Check holding period opportunities
        near_ltcg = payload.get("positions_near_ltcg", [])
        if near_ltcg and trade_list:
            trades = trade_list.get("payload", {}).get("trades", [])
            for trade in trades:
                if trade["action"] == "SELL" and trade["ticker"] in near_ltcg:
                    days_to_ltcg = near_ltcg[trade["ticker"]]
                    if days_to_ltcg <= 45:
                        failures.append(f"Consider waiting {days_to_ltcg} days for LTCG on {trade['ticker']}")
                        
        if failures:
            return GateResult(
                passed=False,
                reason="; ".join(failures),
                details={"failures": failures, "tax_impact": payload}
            )
            
        return GateResult(
            passed=True,
            reason="Tax implications acceptable",
            details={"tax_impact": payload}
        )

class ComplianceGate:
    """Compliance and regulatory gates"""
    
    @classmethod
    def check(cls, portfolio: Dict[str, Any], trades: Dict[str, Any]) -> GateResult:
        """Check compliance requirements"""
        
        failures = []
        
        # Check for restricted securities
        restricted = ["PRIVATE", "RESTRICTED", "INSIDER"]
        trade_list = trades.get("payload", {}).get("trades", [])
        
        for trade in trade_list:
            if any(r in trade.get("ticker", "") for r in restricted):
                failures.append(f"Restricted security: {trade['ticker']}")
                
        # Check for pattern day trading
        day_trades = trades.get("payload", {}).get("day_trades_count", 0)
        if day_trades > 3:
            failures.append(f"Pattern day trading violation: {day_trades} trades")
            
        # Check account minimums
        portfolio_value = portfolio.get("payload", {}).get("total_value", 0)
        if portfolio_value < 25000 and day_trades > 0:
            failures.append(f"Insufficient equity for day trading: ${portfolio_value:,.2f}")
            
        if failures:
            return GateResult(
                passed=False,
                reason="; ".join(failures),
                details={"failures": failures}
            )
            
        return GateResult(
            passed=True,
            reason="Compliance checks passed",
            details={}
        )

class GateSystem:
    """Coordinated gate system for all validations"""
    
    def __init__(self):
        self.risk_gate = RiskGate()
        self.tax_gate = TaxGate()
        self.compliance_gate = ComplianceGate()
        
    def check_all_gates(
        self,
        risk_report: Dict[str, Any],
        tax_impact: Dict[str, Any],
        portfolio: Dict[str, Any],
        trades: Dict[str, Any]
    ) -> Tuple[bool, List[GateResult]]:
        """Check all gates and return results"""
        
        results = []
        
        # Check risk gate
        risk_result = self.risk_gate.check(risk_report)
        results.append(("Risk", risk_result))
        logger.info(f"Risk gate: {risk_result.passed} - {risk_result.reason}")
        
        # Check tax gate
        tax_result = self.tax_gate.check(tax_impact, trades)
        results.append(("Tax", tax_result))
        logger.info(f"Tax gate: {tax_result.passed} - {tax_result.reason}")
        
        # Check compliance gate
        compliance_result = self.compliance_gate.check(portfolio, trades)
        results.append(("Compliance", compliance_result))
        logger.info(f"Compliance gate: {compliance_result.passed} - {compliance_result.reason}")
        
        # All must pass
        all_passed = all(result.passed for _, result in results)
        
        return all_passed, results
        
    def generate_gate_report(self, results: List[Tuple[str, GateResult]]) -> str:
        """Generate human-readable gate report"""
        
        report = "# Gate Validation Report\n\n"
        
        for gate_name, result in results:
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            report += f"## {gate_name} Gate: {status}\n"
            report += f"**Reason**: {result.reason}\n"
            
            if not result.passed and "failures" in result.details:
                report += "\n**Failures**:\n"
                for failure in result.details["failures"]:
                    report += f"- {failure}\n"
                    
            report += "\n"
            
        return report