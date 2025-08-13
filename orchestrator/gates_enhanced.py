#!/usr/bin/env python3
"""
Enhanced Gate System for Investment Workflow Validation
Reads from config files and includes Realism and Credibility gates
"""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)

@dataclass
class GateResult:
    """Result of a gate check"""
    passed: bool
    reason: str
    details: Dict[str, Any]

class ConfigLoader:
    """Load gate configurations from YAML files"""
    
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return {}
        
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    @classmethod
    def get_risk_config(cls) -> Dict[str, Any]:
        """Load risk limits configuration"""
        return cls.load_config("config/policy/risk_limits.yaml")
    
    @classmethod
    def get_tax_config(cls) -> Dict[str, Any]:
        """Load tax limits configuration"""
        return cls.load_config("config/policy/tax_limits.yaml")
    
    @classmethod
    def get_compliance_config(cls) -> Dict[str, Any]:
        """Load compliance rules configuration"""
        return cls.load_config("config/policy/compliance_rules.yaml")

class RiskGate:
    """Risk validation gates for portfolio decisions"""
    
    def __init__(self):
        """Initialize with config or defaults"""
        config = ConfigLoader.get_risk_config()
        limits = config.get("portfolio_limits", {})
        position_limits = config.get("position_limits", {})
        
        # Portfolio-level limits
        self.MAX_DAILY_VAR = limits.get("max_daily_var_95", 0.02)
        self.MAX_DRAWDOWN = limits.get("max_drawdown", 0.20)
        self.MIN_SHARPE = limits.get("min_sharpe", 0.85)
        
        # Position-level limits
        self.MAX_SINGLE_POSITION = position_limits.get("max_single_position", 0.10)
        self.MIN_POSITIONS = position_limits.get("min_positions", 20)
        self.MAX_CORRELATION = config.get("correlation_limits", {}).get("max_correlation", 0.85)
        
        # Stress test limits
        self.stress_limits = config.get("stress_tests", {})
    
    def check(self, risk_report: Dict[str, Any]) -> GateResult:
        """Check if risk metrics pass all gates"""
        
        payload = risk_report.get("payload", {})
        failures = []
        
        # Check VaR limit
        var_95 = abs(payload.get("var_95", 0))
        if var_95 > self.MAX_DAILY_VAR:
            failures.append(f"VaR exceeds limit: {var_95:.2%} > {self.MAX_DAILY_VAR:.2%}")
            
        # Check drawdown limit
        max_dd = abs(payload.get("max_drawdown", 0))
        if max_dd > self.MAX_DRAWDOWN:
            failures.append(f"Drawdown exceeds limit: {max_dd:.2%} > {self.MAX_DRAWDOWN:.2%}")
            
        # Check Sharpe ratio
        sharpe = payload.get("metrics", {}).get("sharpe", 0)
        if sharpe < self.MIN_SHARPE:
            failures.append(f"Sharpe below minimum: {sharpe:.2f} < {self.MIN_SHARPE:.2f}")
            
        # Check concentration
        positions = payload.get("positions", {})
        for symbol, weight in positions.items():
            if weight > self.MAX_SINGLE_POSITION:
                failures.append(f"Position too concentrated: {symbol} = {weight:.2%}")
                
        # Check diversification
        if len(positions) < self.MIN_POSITIONS:
            failures.append(f"Insufficient diversification: {len(positions)} < {self.MIN_POSITIONS} positions")
                
        # Check stress tests against configured limits
        stress_tests = payload.get("stress_tests", {})
        for scenario, impact in stress_tests.items():
            limit = self.stress_limits.get(scenario, -0.35)  # Default 35% loss limit
            if impact < limit:
                failures.append(f"Stress test failure: {scenario} = {impact:.2%} < {limit:.2%}")
                
        if failures:
            return GateResult(
                passed=False,
                reason="; ".join(failures),
                details={"failures": failures, "metrics": payload}
            )
            
        return GateResult(
            passed=True,
            reason="All risk checks passed",
            details={"metrics": payload}
        )

class TaxGate:
    """Tax validation gates for trading decisions"""
    
    def __init__(self):
        """Initialize with config or defaults"""
        config = ConfigLoader.get_tax_config()
        efficiency = config.get("tax_efficiency", {})
        capital_gains = config.get("capital_gains", {})
        wash_sale = config.get("wash_sale", {})
        
        self.MAX_TAX_DRAG = efficiency.get("max_tax_drag", 0.02)
        self.MAX_STCG_RATIO = efficiency.get("max_stcg_ratio", 0.30)
        self.WASH_SALE_WINDOW = wash_sale.get("blackout_days", 31)
        self.LTCG_THRESHOLD = capital_gains.get("ltcg_threshold_days", 365)
        self.LTCG_WAIT_WINDOW = capital_gains.get("ltcg_wait_window", 45)
    
    def check(self, tax_impact: Dict[str, Any], trade_list: Dict[str, Any] = None) -> GateResult:
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
        
        if tax_drag > self.MAX_TAX_DRAG:
            failures.append(f"Tax drag too high: {tax_drag:.2%} > {self.MAX_TAX_DRAG:.2%}")
            
        # Check STCG vs LTCG ratio
        stcg = payload.get("stcg", 0)
        ltcg = payload.get("ltcg", 0)
        total_gains = stcg + ltcg
        
        if total_gains > 0:
            stcg_ratio = stcg / total_gains
            if stcg_ratio > self.MAX_STCG_RATIO:
                failures.append(f"Too many short-term gains: {stcg_ratio:.2%} > {self.MAX_STCG_RATIO:.2%}")
                
        # Check holding period opportunities
        near_ltcg = payload.get("positions_near_ltcg", {})
        if near_ltcg and trade_list:
            trades = trade_list.get("payload", {}).get("trades", [])
            for trade in trades:
                if trade["action"] == "SELL" and trade["ticker"] in near_ltcg:
                    days_to_ltcg = near_ltcg[trade["ticker"]]
                    if days_to_ltcg <= self.LTCG_WAIT_WINDOW:
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
    
    def __init__(self):
        """Initialize with config or defaults"""
        config = ConfigLoader.get_compliance_config()
        self.restricted = config.get("restricted_securities", {}).get("blacklist", [])
        self.trading_rules = config.get("trading_rules", {})
        self.account_rules = config.get("account_rules", {})
    
    def check(self, portfolio: Dict[str, Any], trades: Dict[str, Any]) -> GateResult:
        """Check compliance requirements"""
        
        failures = []
        
        # Check for restricted securities
        trade_list = trades.get("payload", {}).get("trades", [])
        
        for trade in trade_list:
            ticker = trade.get("ticker", "")
            if any(r in ticker for r in self.restricted):
                failures.append(f"Restricted security: {ticker}")
                
        # Check for pattern day trading
        pdt_rules = self.trading_rules.get("pattern_day_trading", {})
        day_trades = trades.get("payload", {}).get("day_trades_count", 0)
        max_day_trades = pdt_rules.get("max_day_trades_per_5_days", 3)
        
        if day_trades > max_day_trades:
            failures.append(f"Pattern day trading violation: {day_trades} > {max_day_trades}")
            
        # Check account minimums
        portfolio_value = portfolio.get("payload", {}).get("total_value", 0)
        min_account_value = self.account_rules.get("min_account_value", 25000)
        
        if portfolio_value < min_account_value and day_trades > 0:
            failures.append(f"Insufficient equity for day trading: ${portfolio_value:,.2f} < ${min_account_value:,.2f}")
            
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

class RealismGate:
    """Prevent statistically implausible optimizations"""
    
    def __init__(self):
        """Initialize with config or defaults"""
        config = ConfigLoader.get_risk_config()
        realism = config.get("realism_checks", {})
        position_limits = config.get("position_limits", {})
        
        self.MAX_EXPECTED_SHARPE = realism.get("max_expected_sharpe", 3.0)
        self.MAX_EXPECTED_RETURN = realism.get("max_expected_return", 0.50)
        self.MIN_EXPECTED_RETURN = realism.get("min_expected_return", -0.10)
        self.MAX_SINGLE_POSITION = position_limits.get("max_single_position", 0.10)
        self.MIN_POSITIONS = position_limits.get("min_positions", 20)
    
    def check(self, optimization_candidate: Dict[str, Any]) -> GateResult:
        """Check if optimization is realistic"""
        
        payload = optimization_candidate.get("payload", {})
        failures = []
        
        # Check expected Sharpe ratio
        expected_sharpe = payload.get("expected_sharpe", 0)
        if expected_sharpe > self.MAX_EXPECTED_SHARPE:
            failures.append(f"Unrealistic Sharpe: {expected_sharpe:.2f} > {self.MAX_EXPECTED_SHARPE:.2f}")
            
        # Check expected return
        expected_return = payload.get("expected_return", 0)
        if expected_return > self.MAX_EXPECTED_RETURN:
            failures.append(f"Unrealistic return: {expected_return:.2%} > {self.MAX_EXPECTED_RETURN:.2%}")
        if expected_return < self.MIN_EXPECTED_RETURN:
            failures.append(f"Negative expected return: {expected_return:.2%}")
            
        # Check position concentration (prevent 25% GEV!)
        allocations = payload.get("allocations", {})
        for symbol, weight in allocations.items():
            if weight > self.MAX_SINGLE_POSITION:
                failures.append(f"Excessive concentration: {symbol} = {weight:.2%} > {self.MAX_SINGLE_POSITION:.2%}")
                
        # Check diversification
        if len(allocations) < self.MIN_POSITIONS:
            failures.append(f"Insufficient diversification: {len(allocations)} < {self.MIN_POSITIONS}")
            
        # Check if optimization is too different from current
        rebalancing_turnover = payload.get("turnover", 0)
        if rebalancing_turnover > 2.0:  # 200% turnover
            failures.append(f"Excessive turnover: {rebalancing_turnover:.2%}")
            
        if failures:
            return GateResult(
                passed=False,
                reason="; ".join(failures),
                details={"failures": failures, "optimization": payload}
            )
            
        return GateResult(
            passed=True,
            reason="Optimization is realistic",
            details={"optimization": payload}
        )

class CredibilityGate:
    """Ensure multi-source validation for market claims"""
    
    def __init__(self):
        """Initialize with minimum source requirements"""
        self.MIN_SOURCES_POLICY = 2
        self.MIN_SOURCES_NEWS = 2
        self.MIN_CONFIDENCE_SINGLE_SOURCE = 0.5
    
    def check(self, market_scan: Dict[str, Any], equity_analysis: Dict[str, Any] = None) -> GateResult:
        """Check if market claims are credible"""
        
        failures = []
        
        # Check policy event sources
        if market_scan:
            policy_events = market_scan.get("payload", {}).get("policy_events", [])
            for event in policy_events:
                sources = event.get("sources", [])
                if len(sources) < self.MIN_SOURCES_POLICY and event.get("impact", "low") == "high":
                    failures.append(f"Policy event '{event.get('title', 'Unknown')}' needs {self.MIN_SOURCES_POLICY} sources, has {len(sources)}")
        
        # Check news-based claims
        if equity_analysis:
            recommendations = equity_analysis.get("payload", {}).get("recommendations", [])
            for rec in recommendations:
                if rec.get("based_on") == "news":
                    sources = rec.get("sources", [])
                    confidence = rec.get("confidence", 0)
                    
                    if len(sources) < self.MIN_SOURCES_NEWS and confidence > self.MIN_CONFIDENCE_SINGLE_SOURCE:
                        failures.append(f"Recommendation for {rec.get('ticker')} needs more sources (has {len(sources)})")
        
        if failures:
            return GateResult(
                passed=False,
                reason="; ".join(failures),
                details={"failures": failures}
            )
            
        return GateResult(
            passed=True,
            reason="Claims are credible",
            details={}
        )

class GateSystem:
    """Coordinated gate system for all validations"""
    
    def __init__(self):
        """Initialize all gates"""
        self.risk_gate = RiskGate()
        self.tax_gate = TaxGate()
        self.compliance_gate = ComplianceGate()
        self.realism_gate = RealismGate()
        self.credibility_gate = CredibilityGate()
        
    def check_all_gates(
        self,
        risk_report: Dict[str, Any],
        tax_impact: Dict[str, Any],
        portfolio: Dict[str, Any],
        trades: Dict[str, Any],
        optimization_candidate: Optional[Dict[str, Any]] = None,
        market_scan: Optional[Dict[str, Any]] = None,
        equity_analysis: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[Tuple[str, GateResult]]]:
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
        
        # Check realism gate if optimization provided
        if optimization_candidate:
            realism_result = self.realism_gate.check(optimization_candidate)
            results.append(("Realism", realism_result))
            logger.info(f"Realism gate: {realism_result.passed} - {realism_result.reason}")
        
        # Check credibility gate if market data provided
        if market_scan or equity_analysis:
            credibility_result = self.credibility_gate.check(market_scan, equity_analysis)
            results.append(("Credibility", credibility_result))
            logger.info(f"Credibility gate: {credibility_result.passed} - {credibility_result.reason}")
        
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