#!/usr/bin/env python3
"""
Mandatory Round-2 Gate System with Traceable Lineage
Ensures all revised allocations undergo proper validation
Tracks decision provenance and enforces audit trail
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RevisionReason(Enum):
    """Reasons for portfolio revision requiring Round-2 gate"""
    RISK_BREACH = "risk_breach"
    TAX_OPTIMIZATION = "tax_optimization"
    COMPLIANCE_VIOLATION = "compliance_violation"
    REBALANCE_TRIGGER = "rebalance_trigger"
    MARKET_EVENT = "market_event"
    USER_OVERRIDE = "user_override"
    CONSTRAINT_RELAXATION = "constraint_relaxation"
    
    
@dataclass
class LineageRecord:
    """Traceable lineage for portfolio decisions"""
    revision_id: str
    parent_id: Optional[str]  # Previous allocation this derives from
    timestamp: datetime
    revision_reason: RevisionReason
    triggering_metrics: Dict[str, Any]
    constraints_modified: Dict[str, Any]
    agent_chain: List[str]  # Agents involved in revision
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "revision_id": self.revision_id,
            "parent_id": self.parent_id,
            "timestamp": self.timestamp.isoformat() + "Z",
            "revision_reason": self.revision_reason.value,
            "triggering_metrics": self.triggering_metrics,
            "constraints_modified": self.constraints_modified,
            "agent_chain": self.agent_chain
        }
    
    def checksum(self) -> str:
        """Generate deterministic checksum for audit"""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class Round2GateResult:
    """Result of Round-2 gate validation"""
    passed: bool
    gate_id: str
    timestamp: datetime
    lineage: LineageRecord
    validation_results: Dict[str, Any]
    es_check: Dict[str, Any]  # ES-primary risk check
    tax_reconciliation: Dict[str, Any]
    liquidity_check: Dict[str, Any]
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def requires_halt(self) -> bool:
        """Check if failures require HALT"""
        critical_failures = [
            "es_limit_breach",
            "liquidity_crisis", 
            "tax_inconsistency",
            "missing_lineage"
        ]
        return any(crit in str(self.failures).lower() for crit in critical_failures)
    
    def to_artifact(self) -> Dict[str, Any]:
        """Create immutable artifact for audit trail"""
        return {
            "gate_id": self.gate_id,
            "timestamp": self.timestamp.isoformat() + "Z",
            "passed": self.passed,
            "lineage_checksum": self.lineage.checksum(),
            "es_limit": self.es_check.get("limit"),
            "es_value": self.es_check.get("value"),
            "tax_artifact_id": self.tax_reconciliation.get("artifact_id"),
            "liquidity_score": self.liquidity_check.get("score"),
            "failures": self.failures,
            "warnings": self.warnings,
            "halt_required": self.requires_halt
        }


class Round2Gate:
    """
    Mandatory Round-2 validation gate for revised allocations.
    Enforces ES-primary risk limits, tax consistency, and lineage tracking.
    """
    
    def __init__(self, 
                 es_limit: float = 0.025,
                 es_alpha: float = 0.975,
                 enforce_lineage: bool = True):
        """
        Initialize Round-2 gate with ES-primary configuration.
        
        Args:
            es_limit: Expected Shortfall limit (positive decimal)
            es_alpha: ES confidence level (e.g., 0.975 for 97.5%)
            enforce_lineage: Require traceable lineage for all revisions
        """
        self.es_limit = es_limit
        self.es_alpha = es_alpha
        self.enforce_lineage = enforce_lineage
        self.gate_log = []  # Audit trail of all gate checks
        
        # Load RiskStack for ES validation
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent.parent / "shared"))
        from risk_conventions import RiskStack, RiskConventions
        self.RiskStack = RiskStack
        self.RiskConventions = RiskConventions
        
    def validate_revision(self,
                          revised_allocation: Dict[str, float],
                          lineage: LineageRecord,
                          risk_stack: Optional[Any] = None,
                          tax_report: Optional[Dict[str, Any]] = None,
                          market_data: Optional[Any] = None) -> Round2GateResult:
        """
        Validate revised allocation through Round-2 gate.
        
        Args:
            revised_allocation: New portfolio weights
            lineage: Traceable lineage record
            risk_stack: Current RiskStack with ES metrics
            tax_report: Tax impact analysis
            market_data: Current market data for liquidity checks
            
        Returns:
            Round2GateResult with pass/fail and detailed validation
        """
        gate_id = self._generate_gate_id()
        timestamp = datetime.now(timezone.utc)
        failures = []
        warnings = []
        
        # 1. Validate lineage
        if self.enforce_lineage:
            lineage_valid, lineage_msg = self._validate_lineage(lineage)
            if not lineage_valid:
                failures.append(f"Lineage validation failed: {lineage_msg}")
        
        # 2. ES-primary risk check
        es_check = self._validate_es_limit(revised_allocation, risk_stack, market_data)
        if not es_check["passed"]:
            failures.append(f"ES limit breach: {es_check['value']:.3f} > {es_check['limit']:.3f}")
        
        # 3. Tax reconciliation
        tax_reconciliation = self._validate_tax_consistency(
            revised_allocation, 
            lineage.parent_id,
            tax_report
        )
        if not tax_reconciliation["consistent"]:
            failures.append(f"Tax inconsistency: {tax_reconciliation['discrepancy']}")
        
        # 4. Liquidity check
        liquidity_check = self._validate_liquidity(revised_allocation, market_data)
        if liquidity_check["score"] < 0.3:
            failures.append(f"Liquidity crisis: score {liquidity_check['score']:.2f}")
        elif liquidity_check["score"] < 0.5:
            warnings.append(f"Low liquidity: score {liquidity_check['score']:.2f}")
        
        # 5. Concentration checks
        concentration_issues = self._validate_concentration(revised_allocation)
        if concentration_issues:
            warnings.extend(concentration_issues)
        
        # Create result
        result = Round2GateResult(
            passed=len(failures) == 0,
            gate_id=gate_id,
            timestamp=timestamp,
            lineage=lineage,
            validation_results={
                "allocation": revised_allocation,
                "total_weight": sum(revised_allocation.values()),
                "num_positions": len([w for w in revised_allocation.values() if w > 0.001])
            },
            es_check=es_check,
            tax_reconciliation=tax_reconciliation,
            liquidity_check=liquidity_check,
            failures=failures,
            warnings=warnings
        )
        
        # Log gate check
        self.gate_log.append(result.to_artifact())
        
        # Save to file if failed
        if not result.passed:
            self._save_failure_report(result)
        
        return result
    
    def _validate_lineage(self, lineage: LineageRecord) -> Tuple[bool, str]:
        """Validate lineage has required fields and proper chain"""
        if not lineage.revision_id:
            return False, "Missing revision_id"
        
        if lineage.parent_id is None and lineage.revision_reason != RevisionReason.USER_OVERRIDE:
            return False, "Missing parent_id for non-override revision"
        
        if not lineage.agent_chain:
            return False, "No agents in decision chain"
        
        # Check for required agents based on revision reason
        required_agents = {
            RevisionReason.RISK_BREACH: ["risk-analyst"],
            RevisionReason.TAX_OPTIMIZATION: ["tax-strategist"],
            RevisionReason.COMPLIANCE_VIOLATION: ["compliance-officer"]
        }
        
        if lineage.revision_reason in required_agents:
            required = required_agents[lineage.revision_reason]
            if not any(agent in lineage.agent_chain for agent in required):
                return False, f"Missing required agent for {lineage.revision_reason.value}"
        
        return True, "Valid lineage"
    
    def _validate_es_limit(self, 
                           allocation: Dict[str, float],
                           risk_stack: Optional[Any],
                           market_data: Optional[Any]) -> Dict[str, Any]:
        """Validate Expected Shortfall is within limit"""
        
        if risk_stack and hasattr(risk_stack, 'loss_based'):
            # Use provided RiskStack
            es_value = risk_stack.loss_based.get("es", {}).get("value", 0)
            es_alpha = risk_stack.loss_based.get("es", {}).get("alpha", self.es_alpha)
        elif market_data:
            # Calculate ES from allocation and market data
            try:
                # Get returns for allocated assets
                tickers = list(allocation.keys())
                weights = list(allocation.values())
                
                # This would call data pipeline in production
                returns = self._fetch_returns(tickers, market_data)
                portfolio_returns = returns @ weights
                
                es_result = self.RiskConventions.compute_expected_shortfall(
                    portfolio_returns,
                    alpha=self.es_alpha,
                    horizon_days=1,
                    method="historical"
                )
                es_value = es_result["value"]
                es_alpha = self.es_alpha
            except Exception as e:
                logger.error(f"Failed to calculate ES: {e}")
                return {
                    "passed": False,
                    "value": None,
                    "limit": self.es_limit,
                    "error": str(e)
                }
        else:
            # No data to validate ES
            return {
                "passed": False,
                "value": None,
                "limit": self.es_limit,
                "error": "No risk data provided"
            }
        
        return {
            "passed": es_value <= self.es_limit,
            "value": es_value,
            "limit": self.es_limit,
            "alpha": es_alpha,
            "breach_magnitude": max(0, es_value - self.es_limit)
        }
    
    def _validate_tax_consistency(self,
                                  allocation: Dict[str, float],
                                  parent_id: Optional[str],
                                  tax_report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Ensure tax calculations are consistent with allocation changes"""
        
        if not tax_report:
            return {
                "consistent": False,
                "artifact_id": None,
                "discrepancy": "No tax report provided"
            }
        
        # Check tax report matches allocation
        tax_positions = tax_report.get("positions", {})
        allocation_symbols = set(allocation.keys())
        tax_symbols = set(tax_positions.keys())
        
        if allocation_symbols != tax_symbols:
            missing = allocation_symbols - tax_symbols
            extra = tax_symbols - allocation_symbols
            return {
                "consistent": False,
                "artifact_id": tax_report.get("artifact_id"),
                "discrepancy": f"Position mismatch - missing: {missing}, extra: {extra}"
            }
        
        # Check tax calculations are recent
        tax_timestamp = tax_report.get("timestamp")
        if tax_timestamp:
            # Handle both 'Z' suffix and '+00:00' timezone
            if tax_timestamp.endswith("Z"):
                tax_dt = datetime.fromisoformat(tax_timestamp.replace("Z", "+00:00"))
            else:
                tax_dt = datetime.fromisoformat(tax_timestamp)
            if datetime.now(timezone.utc) - tax_dt > timedelta(minutes=5):
                return {
                    "consistent": False,
                    "artifact_id": tax_report.get("artifact_id"),
                    "discrepancy": "Stale tax calculations (>5 minutes old)"
                }
        
        # Verify tax impact reconciles
        reported_impact = tax_report.get("total_tax_impact", 0)
        calculated_impact = tax_report.get("calculated_impact", 0)
        
        if abs(reported_impact - calculated_impact) > 100:  # $100 tolerance
            return {
                "consistent": False,
                "artifact_id": tax_report.get("artifact_id"),
                "discrepancy": f"Tax impact mismatch: ${reported_impact:.2f} vs ${calculated_impact:.2f}"
            }
        
        return {
            "consistent": True,
            "artifact_id": tax_report.get("artifact_id"),
            "total_impact": reported_impact,
            "wash_sales": tax_report.get("wash_sale_violations", [])
        }
    
    def _validate_liquidity(self,
                           allocation: Dict[str, float],
                           market_data: Optional[Any]) -> Dict[str, Any]:
        """Check liquidity constraints"""
        
        # Simplified liquidity scoring
        liquidity_score = 1.0
        issues = []
        
        # Check for concentrated positions
        max_weight = max(allocation.values()) if allocation else 0
        if max_weight > 0.15:
            liquidity_score *= 0.7
            issues.append(f"Concentrated position: {max_weight:.1%}")
        
        # Check number of positions
        num_positions = len([w for w in allocation.values() if w > 0.001])
        if num_positions < 10:
            liquidity_score *= 0.8
            issues.append(f"Low diversification: {num_positions} positions")
        
        # In production, would check ADV (Average Daily Volume)
        # and position size vs ADV ratios
        
        return {
            "score": liquidity_score,
            "issues": issues,
            "pct_adv_p95": None,  # Would calculate in production
            "names_over_10pct_adv": 0
        }
    
    def _validate_concentration(self, allocation: Dict[str, float]) -> List[str]:
        """Check concentration metrics"""
        issues = []
        
        # Top 5 concentration
        weights = sorted(allocation.values(), reverse=True)
        top5_weight = sum(weights[:5]) if len(weights) >= 5 else sum(weights)
        
        if top5_weight > 0.5:
            issues.append(f"High top-5 concentration: {top5_weight:.1%}")
        
        # Single position limits
        for symbol, weight in allocation.items():
            if weight > 0.10:
                issues.append(f"Position exceeds 10% limit: {symbol} = {weight:.1%}")
        
        return issues
    
    def _generate_gate_id(self) -> str:
        """Generate unique gate check ID"""
        timestamp = datetime.now(timezone.utc).isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:12]
    
    def _fetch_returns(self, tickers: List[str], market_data: Any) -> Any:
        """Fetch returns data (placeholder for production)"""
        # In production, would use data_pipeline
        import numpy as np
        return np.random.normal(0, 0.01, (252, len(tickers)))
    
    def _save_failure_report(self, result: Round2GateResult):
        """Save detailed failure report for audit"""
        report_dir = Path("reports/round2_failures")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"gate_failure_{result.gate_id}_{result.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = report_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(result.to_artifact(), f, indent=2)
        
        logger.warning(f"Round-2 gate failure saved to {filepath}")
    
    def get_audit_trail(self, 
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Retrieve audit trail of gate checks"""
        trail = self.gate_log
        
        if start_date:
            trail = [g for g in trail 
                    if datetime.fromisoformat(g["timestamp"].replace("Z", "+00:00")) >= start_date]
        
        if end_date:
            trail = [g for g in trail 
                    if datetime.fromisoformat(g["timestamp"].replace("Z", "+00:00")) <= end_date]
        
        return trail
    
    def enforce_halt(self, result: Round2GateResult) -> Dict[str, Any]:
        """Enforce HALT when critical failures detected"""
        if not result.requires_halt:
            return {"halt": False, "reason": "No critical failures"}
        
        halt_order = {
            "halt": True,
            "gate_id": result.gate_id,
            "timestamp": result.timestamp.isoformat() + "Z",
            "reason": result.failures[0] if result.failures else "Unknown",
            "lineage_id": result.lineage.revision_id,
            "required_actions": self._determine_required_actions(result)
        }
        
        # Log halt order
        logger.critical(f"HALT enforced: {halt_order['reason']}")
        
        return halt_order
    
    def _determine_required_actions(self, result: Round2GateResult) -> List[str]:
        """Determine required actions to resolve halt"""
        actions = []
        
        if "es_limit_breach" in str(result.failures):
            actions.append("Reduce portfolio risk to bring ES below limit")
            actions.append("Review and potentially adjust ES limit with risk committee")
        
        if "liquidity_crisis" in str(result.failures):
            actions.append("Reduce concentrated positions")
            actions.append("Increase number of holdings for diversification")
        
        if "tax_inconsistency" in str(result.failures):
            actions.append("Recompute tax impact with current allocation")
            actions.append("Reconcile tax calculations with reported values")
        
        if "missing_lineage" in str(result.failures):
            actions.append("Provide complete lineage record for revision")
            actions.append("Ensure all required agents participated in decision")
        
        return actions