#!/usr/bin/env python3
"""
Parallel Orchestration System for Multi-Agent Investment Analysis
Coordinates multiple specialist agents for comprehensive analysis
"""

import json
import asyncio
import concurrent.futures
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class AgentType(str, Enum):
    """Available specialist agents"""
    MACRO = "macro-analyst"
    EQUITY = "equity-analyst"
    FIXED_INCOME = "fixed-income-analyst"
    PORTFOLIO = "portfolio-manager"
    RISK = "risk-analyst"
    TAX = "tax-advisor"
    MARKET_SCANNER = "market-scanner"

class AnalysisRequest(BaseModel):
    """User analysis request"""
    query: str
    tickers: Optional[List[str]] = Field(default=None)
    portfolio: Optional[Dict[str, float]] = Field(default=None)
    risk_tolerance: str = Field(default="moderate", pattern="^(conservative|moderate|aggressive)$")
    time_horizon: str = Field(default="medium", pattern="^(short|medium|long)$")
    tax_status: Optional[Dict[str, Any]] = Field(default=None)

class AgentTask(BaseModel):
    """Task definition for an agent"""
    agent_type: AgentType
    priority: int = Field(ge=1, le=3, description="1=highest, 3=lowest")
    task_description: str
    required_tools: List[str]
    expected_output: str
    dependencies: List[AgentType] = Field(default_factory=list)
    timeout_seconds: int = Field(default=30)

class AgentResponse(BaseModel):
    """Standardized agent response"""
    agent: str
    timestamp: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    signal: Optional[str] = Field(pattern="^(bullish|neutral|bearish)$")
    analysis: Dict[str, Any]
    recommendations: List[str]
    risks: List[str]
    metrics: Optional[Dict[str, float]]

class ParallelOrchestrator:
    """Orchestrates parallel execution of investment analysis agents"""
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.agent_configs = self._load_agent_configs()
        
    def _load_agent_configs(self) -> Dict[str, Dict]:
        """Load agent configurations and capabilities"""
        return {
            AgentType.MACRO: {
                "tools": ["economy_gdp_real", "economy_cpi", "economy_interest_rates"],
                "expertise": "economic conditions"
            },
            AgentType.EQUITY: {
                "tools": ["equity_fundamental_income", "equity_analyst_estimates"],
                "expertise": "stock analysis"
            },
            AgentType.FIXED_INCOME: {
                "tools": ["fixedincome_yield_curve", "fixedincome_spreads"],
                "expertise": "bond markets"
            },
            AgentType.PORTFOLIO: {
                "tools": ["portfolio_optimize_sharpe", "etf_search"],
                "expertise": "asset allocation"
            },
            AgentType.RISK: {
                "tools": ["risk_calculate_var", "risk_stress_test"],
                "expertise": "risk measurement"
            },
            AgentType.TAX: {
                "tools": ["tax_calculate", "tax_harvest"],
                "expertise": "tax optimization"
            },
            AgentType.MARKET_SCANNER: {
                "tools": ["news_market", "crypto_price_historical"],
                "expertise": "market monitoring"
            }
        }
    
    def analyze_query(self, request: AnalysisRequest) -> List[AgentTask]:
        """Determine which agents to deploy based on query"""
        
        tasks = []
        query_lower = request.query.lower()
        
        # Always start with market scanner for context
        tasks.append(AgentTask(
            agent_type=AgentType.MARKET_SCANNER,
            priority=1,
            task_description="Scan current market conditions and news",
            required_tools=["news_market"],
            expected_output="market sentiment and key themes"
        ))
        
        # Macro analysis for economic questions
        if any(word in query_lower for word in ["economy", "gdp", "inflation", "rates", "fed"]):
            tasks.append(AgentTask(
                agent_type=AgentType.MACRO,
                priority=1,
                task_description="Analyze macroeconomic environment",
                required_tools=["economy_gdp_real", "economy_cpi"],
                expected_output="economic assessment and implications"
            ))
        
        # Equity analysis for stock questions
        if request.tickers or any(word in query_lower for word in ["stock", "equity", "share", "company"]):
            tasks.append(AgentTask(
                agent_type=AgentType.EQUITY,
                priority=1,
                task_description=f"Analyze stocks: {request.tickers or 'sector leaders'}",
                required_tools=["equity_fundamental_income"],
                expected_output="valuation and recommendations"
            ))
        
        # Portfolio analysis for allocation questions
        if request.portfolio or any(word in query_lower for word in ["portfolio", "allocation", "rebalance"]):
            tasks.append(AgentTask(
                agent_type=AgentType.PORTFOLIO,
                priority=2,
                task_description="Optimize portfolio allocation",
                required_tools=["portfolio_optimize_sharpe"],
                expected_output="optimal weights and expected returns",
                dependencies=[AgentType.RISK]
            ))
        
        # Risk analysis for any investment decision
        if request.portfolio or request.tickers:
            tasks.append(AgentTask(
                agent_type=AgentType.RISK,
                priority=1,
                task_description="Calculate risk metrics and stress test",
                required_tools=["risk_calculate_var"],
                expected_output="risk assessment and hedging recommendations"
            ))
        
        # Tax analysis if tax status provided
        if request.tax_status or "tax" in query_lower:
            tasks.append(AgentTask(
                agent_type=AgentType.TAX,
                priority=2,
                task_description="Analyze tax implications",
                required_tools=["tax_calculate"],
                expected_output="tax impact and optimization strategies"
            ))
        
        # Fixed income for bond questions
        if any(word in query_lower for word in ["bond", "yield", "duration", "credit"]):
            tasks.append(AgentTask(
                agent_type=AgentType.FIXED_INCOME,
                priority=1,
                task_description="Analyze fixed income opportunities",
                required_tools=["fixedincome_yield_curve"],
                expected_output="duration positioning and credit recommendations"
            ))
        
        return tasks
    
    async def execute_agent_task(self, task: AgentTask) -> AgentResponse:
        """Execute a single agent task (simulated)"""
        
        # In production, this would call actual agent via Task tool
        # Simulating agent execution here
        await asyncio.sleep(1)  # Simulate processing time
        
        return AgentResponse(
            agent=task.agent_type.value,
            timestamp=datetime.now(),
            confidence=0.85,
            signal="neutral",
            analysis={
                "task": task.task_description,
                "findings": f"Analysis from {task.agent_type.value}"
            },
            recommendations=[f"Recommendation from {task.agent_type.value}"],
            risks=[f"Risk identified by {task.agent_type.value}"],
            metrics={"sample_metric": 0.75}
        )
    
    async def execute_parallel(self, tasks: List[AgentTask]) -> List[AgentResponse]:
        """Execute agent tasks in parallel with dependency management"""
        
        # Sort by priority
        tasks.sort(key=lambda x: x.priority)
        
        # Group by priority level for parallel execution
        priority_groups = {}
        for task in tasks:
            if task.priority not in priority_groups:
                priority_groups[task.priority] = []
            priority_groups[task.priority].append(task)
        
        all_responses = []
        completed_agents = set()
        
        # Execute each priority group
        for priority in sorted(priority_groups.keys()):
            group_tasks = priority_groups[priority]
            
            # Filter tasks whose dependencies are met
            ready_tasks = [
                task for task in group_tasks
                if all(dep in completed_agents for dep in task.dependencies)
            ]
            
            # Execute ready tasks in parallel
            if ready_tasks:
                responses = await asyncio.gather(
                    *[self.execute_agent_task(task) for task in ready_tasks]
                )
                all_responses.extend(responses)
                
                # Mark agents as completed
                for task in ready_tasks:
                    completed_agents.add(task.agent_type)
        
        return all_responses
    
    def synthesize_responses(
        self,
        responses: List[AgentResponse],
        request: AnalysisRequest
    ) -> Dict[str, Any]:
        """Synthesize multiple agent responses into coherent advice"""
        
        # Aggregate signals
        signals = [r.signal for r in responses if r.signal]
        signal_counts = {
            "bullish": signals.count("bullish"),
            "neutral": signals.count("neutral"),
            "bearish": signals.count("bearish")
        }
        consensus_signal = max(signal_counts, key=signal_counts.get)
        
        # Weight confidence by agent expertise
        weighted_confidence = sum(r.confidence for r in responses) / len(responses)
        
        # Collect all recommendations and risks
        all_recommendations = []
        all_risks = []
        for response in responses:
            all_recommendations.extend(response.recommendations)
            all_risks.extend(response.risks)
        
        # Remove duplicates while preserving order
        recommendations = list(dict.fromkeys(all_recommendations))
        risks = list(dict.fromkeys(all_risks))
        
        # Build synthesis
        synthesis = {
            "timestamp": datetime.now().isoformat(),
            "query": request.query,
            "consensus": {
                "signal": consensus_signal,
                "confidence": weighted_confidence,
                "agreement_score": max(signal_counts.values()) / len(signals) if signals else 0
            },
            "recommendations": recommendations[:5],  # Top 5
            "risks": risks[:5],  # Top 5
            "agent_responses": len(responses),
            "analysis_summary": self._create_summary(responses),
            "action_plan": self._create_action_plan(consensus_signal, recommendations, risks)
        }
        
        return synthesis
    
    def _create_summary(self, responses: List[AgentResponse]) -> Dict[str, str]:
        """Create summary from agent responses"""
        
        summary = {}
        for response in responses:
            agent_name = response.agent
            # Extract key finding from each agent
            if response.analysis:
                key_finding = list(response.analysis.values())[0] if response.analysis else "No findings"
                summary[agent_name] = str(key_finding)[:100]  # Truncate for brevity
        
        return summary
    
    def _create_action_plan(
        self,
        signal: str,
        recommendations: List[str],
        risks: List[str]
    ) -> Dict[str, Any]:
        """Create actionable plan based on synthesis"""
        
        plan = {
            "immediate_actions": [],
            "monitoring_items": [],
            "hedging_strategies": []
        }
        
        # Define actions based on signal
        if signal == "bullish":
            plan["immediate_actions"] = [
                "Review portfolio allocation for risk-on positioning",
                "Consider increasing equity exposure",
                "Evaluate growth sectors"
            ]
        elif signal == "bearish":
            plan["immediate_actions"] = [
                "Review defensive positioning",
                "Consider reducing risk exposure",
                "Evaluate hedging strategies"
            ]
        else:  # neutral
            plan["immediate_actions"] = [
                "Maintain current allocation",
                "Focus on security selection",
                "Monitor for directional signals"
            ]
        
        # Add monitoring based on risks
        if risks:
            plan["monitoring_items"] = risks[:3]
        
        # Add hedging if high risk
        if len(risks) > 3:
            plan["hedging_strategies"] = [
                "Consider protective puts",
                "Review stop-loss levels",
                "Diversify concentration risks"
            ]
        
        return plan

async def orchestrate_analysis(request: AnalysisRequest) -> Dict[str, Any]:
    """Main orchestration function"""
    
    orchestrator = ParallelOrchestrator(max_workers=5)
    
    # Determine which agents to deploy
    tasks = orchestrator.analyze_query(request)
    
    print(f"Deploying {len(tasks)} agents for analysis...")
    
    # Execute tasks in parallel
    responses = await orchestrator.execute_parallel(tasks)
    
    # Synthesize results
    synthesis = orchestrator.synthesize_responses(responses, request)
    
    return synthesis

def main():
    """Example usage"""
    
    # Example request
    request = AnalysisRequest(
        query="Should I rebalance my portfolio given current inflation concerns?",
        portfolio={"SPY": 0.6, "AGG": 0.3, "GLD": 0.1},
        risk_tolerance="moderate",
        time_horizon="medium"
    )
    
    # Run orchestration
    result = asyncio.run(orchestrate_analysis(request))
    
    # Output results
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()