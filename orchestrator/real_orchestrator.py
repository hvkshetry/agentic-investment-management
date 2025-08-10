#!/usr/bin/env python3
"""
Real Investment Orchestrator with MCP Integration
Coordinates agents and MCP servers for comprehensive investment analysis
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

from artifact_store import ArtifactStore, ArtifactKind

logger = logging.getLogger(__name__)

class WorkflowType(str, Enum):
    """Available workflow types"""
    REBALANCE_TLH = "rebalance_tlh"
    CASH_WITHDRAWAL = "cash_withdrawal" 
    DAILY_CHECK = "daily_check"
    HEDGE_OVERLAY = "hedge_overlay"
    RESEARCH = "research"

@dataclass
class WorkflowStep:
    """Represents a step in a workflow"""
    name: str
    agent: str
    tools: List[str]
    inputs: List[str]  # Artifact IDs or kinds to consume
    outputs: str  # Artifact kind to produce
    gate: Optional[str] = None  # Gate condition

class RealOrchestrator:
    """Orchestrates real MCP tool calls and agent coordination"""
    
    def __init__(self):
        self.artifact_store = ArtifactStore()
        self.gates = {
            "risk_gate": self._check_risk_gate,
            "tax_gate": self._check_tax_gate
        }
        
    def get_workflow(self, workflow_type: WorkflowType) -> List[WorkflowStep]:
        """Get workflow steps for a specific type"""
        
        if workflow_type == WorkflowType.REBALANCE_TLH:
            return [
                WorkflowStep(
                    name="Get Portfolio State",
                    agent="orchestrator",
                    tools=["mcp__portfolio-state__get_portfolio_state"],
                    inputs=[],
                    outputs=ArtifactKind.PORTFOLIO_SNAPSHOT
                ),
                WorkflowStep(
                    name="Analyze Market Context",
                    agent="macro-analyst",
                    tools=["mcp__openbb-curated__economy_fred_series",
                           "mcp__openbb-curated__economy_cpi",
                           "mcp__openbb-curated__economy_interest_rates"],
                    inputs=[],
                    outputs=ArtifactKind.MARKET_CONTEXT
                ),
                WorkflowStep(
                    name="Generate Optimization Candidates",
                    agent="portfolio-manager",
                    tools=["mcp__portfolio-optimization__optimize_portfolio_advanced"],
                    inputs=[ArtifactKind.PORTFOLIO_SNAPSHOT, ArtifactKind.MARKET_CONTEXT],
                    outputs=ArtifactKind.OPTIMIZATION_CANDIDATE
                ),
                WorkflowStep(
                    name="Risk Analysis",
                    agent="risk-analyst",
                    tools=["mcp__risk-analyzer__analyze_portfolio_risk_from_state"],
                    inputs=[ArtifactKind.OPTIMIZATION_CANDIDATE],
                    outputs=ArtifactKind.RISK_REPORT,
                    gate="risk_gate"
                ),
                WorkflowStep(
                    name="Tax Impact Analysis",
                    agent="tax-advisor",
                    tools=["mcp__tax-calculator__calculate_tax_implications"],
                    inputs=[ArtifactKind.OPTIMIZATION_CANDIDATE],
                    outputs=ArtifactKind.TAX_IMPACT,
                    gate="tax_gate"
                ),
                WorkflowStep(
                    name="Create Decision Memo",
                    agent="orchestrator",
                    tools=[],
                    inputs=[ArtifactKind.OPTIMIZATION_CANDIDATE, 
                           ArtifactKind.RISK_REPORT,
                           ArtifactKind.TAX_IMPACT],
                    outputs=ArtifactKind.DECISION_MEMO
                )
            ]
            
        elif workflow_type == WorkflowType.CASH_WITHDRAWAL:
            return [
                WorkflowStep(
                    name="Get Portfolio State",
                    agent="orchestrator",
                    tools=["mcp__portfolio-state__get_portfolio_state"],
                    inputs=[],
                    outputs=ArtifactKind.PORTFOLIO_SNAPSHOT
                ),
                WorkflowStep(
                    name="Optimize Withdrawal",
                    agent="tax-advisor",
                    tools=["mcp__tax-calculator__optimize_tax_efficient_sale"],
                    inputs=[ArtifactKind.PORTFOLIO_SNAPSHOT],
                    outputs=ArtifactKind.TRADE_LIST
                ),
                WorkflowStep(
                    name="Verify Risk Limits",
                    agent="risk-analyst",
                    tools=["mcp__risk-analyzer__analyze_portfolio_risk_from_state"],
                    inputs=[ArtifactKind.TRADE_LIST],
                    outputs=ArtifactKind.RISK_REPORT,
                    gate="risk_gate"
                )
            ]
            
        elif workflow_type == WorkflowType.DAILY_CHECK:
            return [
                WorkflowStep(
                    name="Get Portfolio State",
                    agent="orchestrator",
                    tools=["mcp__portfolio-state__get_portfolio_state"],
                    inputs=[],
                    outputs=ArtifactKind.PORTFOLIO_SNAPSHOT
                ),
                WorkflowStep(
                    name="Market Scan",
                    agent="market-scanner",
                    tools=["mcp__openbb-curated__news_world",
                           "mcp__openbb-curated__index_price_historical"],
                    inputs=[],
                    outputs=ArtifactKind.MARKET_CONTEXT
                ),
                WorkflowStep(
                    name="Risk Check",
                    agent="risk-analyst",
                    tools=["mcp__risk-analyzer__analyze_portfolio_risk_from_state"],
                    inputs=[ArtifactKind.PORTFOLIO_SNAPSHOT],
                    outputs=ArtifactKind.RISK_REPORT
                )
            ]
            
        else:
            return []
            
    async def execute_workflow(
        self,
        workflow_type: WorkflowType,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a complete workflow"""
        
        # Start new run
        run_id = self.artifact_store.start_run()
        logger.info(f"Starting workflow: {workflow_type.value} (Run: {run_id})")
        
        # Get workflow steps
        steps = self.get_workflow(workflow_type)
        
        # Execute each step
        results = {
            "run_id": run_id,
            "workflow": workflow_type.value,
            "started_at": datetime.now().isoformat(),
            "steps": [],
            "status": "in_progress"
        }
        
        for step in steps:
            logger.info(f"Executing step: {step.name}")
            
            try:
                # Gather input artifacts
                inputs = self._gather_inputs(step.inputs)
                
                # Execute step (this would call actual MCP tools)
                artifact = await self._execute_step(step, inputs, parameters)
                
                # Check gate if specified
                if step.gate:
                    gate_passed = self.gates[step.gate](artifact)
                    if not gate_passed:
                        logger.warning(f"Gate {step.gate} failed for step {step.name}")
                        results["status"] = "failed"
                        results["failure_reason"] = f"Gate {step.gate} failed"
                        break
                        
                results["steps"].append({
                    "name": step.name,
                    "artifact_id": artifact["id"],
                    "status": "completed"
                })
                
            except Exception as e:
                logger.error(f"Step {step.name} failed: {e}")
                results["steps"].append({
                    "name": step.name,
                    "status": "failed",
                    "error": str(e)
                })
                results["status"] = "failed"
                break
                
        if results["status"] == "in_progress":
            results["status"] = "completed"
            
        results["completed_at"] = datetime.now().isoformat()
        
        # Generate final report
        self._generate_workflow_report(results, workflow_type)
        
        return results
        
    def _gather_inputs(self, input_kinds: List[str]) -> List[Dict[str, Any]]:
        """Gather input artifacts for a step"""
        inputs = []
        
        for kind_str in input_kinds:
            if kind_str in [k.value for k in ArtifactKind]:
                kind = ArtifactKind(kind_str)
                artifact = self.artifact_store.get_latest_by_kind(kind)
                if artifact:
                    inputs.append(artifact)
            else:
                # It's an artifact ID
                artifact = self.artifact_store.get_artifact(kind_str)
                if artifact:
                    inputs.append(artifact)
                    
        return inputs
        
    async def _execute_step(
        self,
        step: WorkflowStep,
        inputs: List[Dict[str, Any]],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a workflow step"""
        
        # In a real implementation, this would:
        # 1. Call the actual MCP tools listed in step.tools
        # 2. Process the results
        # 3. Create an artifact of the specified output kind
        
        # For now, create a placeholder artifact
        payload = {
            "step": step.name,
            "agent": step.agent,
            "tools_called": step.tools,
            "inputs_used": [i["id"] for i in inputs],
            "parameters": parameters,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add mock data based on artifact kind
        if step.outputs == ArtifactKind.PORTFOLIO_SNAPSHOT:
            payload["positions"] = []
            payload["total_value"] = 1000000
            payload["allocation"] = {}
            
        elif step.outputs == ArtifactKind.OPTIMIZATION_CANDIDATE:
            payload["weights"] = {"SPY": 0.4, "AGG": 0.3, "GLD": 0.2, "VNQ": 0.1}
            payload["metrics"] = {
                "expected_return": 0.08,
                "volatility": 0.12,
                "sharpe": 0.52,
                "var_95": -0.02,
                "max_drawdown": -0.15
            }
            payload["method"] = "HRP"
            
        elif step.outputs == ArtifactKind.RISK_REPORT:
            payload["var_95"] = -0.02
            payload["cvar_95"] = -0.035
            payload["max_drawdown"] = -0.15
            payload["stress_tests"] = {
                "2008_crisis": -0.25,
                "covid_crash": -0.18,
                "rate_shock_300bp": -0.12
            }
            payload["status"] = "pass"
            
        elif step.outputs == ArtifactKind.TAX_IMPACT:
            payload["federal_tax"] = 15000
            payload["state_tax"] = 5000
            payload["niit"] = 1000
            payload["total_tax"] = 21000
            payload["stcg"] = 10000
            payload["ltcg"] = 40000
            payload["wash_sale_risk"] = False
            payload["status"] = "pass"
            
        return self.artifact_store.create_artifact(
            kind=step.outputs,
            created_by=step.agent,
            payload=payload,
            depends_on=[i["id"] for i in inputs],
            confidence=0.85
        )
        
    def _check_risk_gate(self, artifact: Dict[str, Any]) -> bool:
        """Check if risk gate passes"""
        payload = artifact.get("payload", {})
        
        # Check VaR limit
        var_95 = abs(payload.get("var_95", 0))
        if var_95 > 0.025:  # 2.5% daily VaR limit
            return False
            
        # Check drawdown limit
        max_dd = abs(payload.get("max_drawdown", 0))
        if max_dd > 0.20:  # 20% max drawdown limit
            return False
            
        return payload.get("status") == "pass"
        
    def _check_tax_gate(self, artifact: Dict[str, Any]) -> bool:
        """Check if tax gate passes"""
        payload = artifact.get("payload", {})
        
        # Check wash sale risk
        if payload.get("wash_sale_risk", False):
            return False
            
        return payload.get("status") == "pass"
        
    def _generate_workflow_report(self, results: Dict[str, Any], workflow_type: WorkflowType):
        """Generate human-readable report for workflow"""
        
        report = f"""# {workflow_type.value.replace('_', ' ').title()} Workflow Report

## Run Information
- **Run ID**: {results['run_id']}
- **Started**: {results['started_at']}
- **Completed**: {results.get('completed_at', 'N/A')}
- **Status**: {results['status']}

## Steps Executed
"""
        
        for step in results['steps']:
            status_icon = "✅" if step['status'] == 'completed' else "❌"
            report += f"\n{status_icon} **{step['name']}**\n"
            if 'artifact_id' in step:
                report += f"   - Artifact: {step['artifact_id'][:8]}...\n"
            if 'error' in step:
                report += f"   - Error: {step['error']}\n"
                
        if results['status'] == 'failed':
            report += f"\n## Failure Reason\n{results.get('failure_reason', 'Unknown')}\n"
            
        self.artifact_store.generate_report(
            title=workflow_type.value,
            content=report,
            report_type="Workflow"
        )

async def main():
    """Example usage"""
    orchestrator = RealOrchestrator()
    
    # Execute a rebalancing workflow
    results = await orchestrator.execute_workflow(
        WorkflowType.REBALANCE_TLH,
        parameters={"target_risk": "moderate"}
    )
    
    print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())