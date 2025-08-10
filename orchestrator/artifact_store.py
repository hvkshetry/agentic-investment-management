#!/usr/bin/env python3
"""
Artifact Storage System for Investment Management Orchestration
Manages structured artifacts with lineage tracking
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ArtifactKind(str, Enum):
    """Types of artifacts produced by the system"""
    MARKET_CONTEXT = "market_context"
    PORTFOLIO_SNAPSHOT = "portfolio_snapshot"  
    OPTIMIZATION_CANDIDATE = "optimization_candidate"
    TRADE_LIST = "trade_list"
    RISK_REPORT = "risk_report"
    TAX_IMPACT = "tax_impact"
    DECISION_MEMO = "decision_memo"
    PORTFOLIO_STATE = "portfolio_state"
    MISSING_DATA = "missing_data"
    PLAN = "plan"

class ArtifactStore:
    """Manages artifact storage and retrieval with lineage tracking"""
    
    def __init__(self, base_path: str = "./runs"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.current_run_path = None
        self.index = {}
        
    def start_run(self) -> str:
        """Start a new run and create its directory"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.current_run_path = self.base_path / timestamp
        self.current_run_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize run index
        self.index = {
            "run_id": timestamp,
            "started_at": datetime.now().isoformat(),
            "artifacts": []
        }
        
        logger.info(f"Started new run: {timestamp}")
        return timestamp
        
    def create_artifact(
        self,
        kind: ArtifactKind,
        created_by: str,
        payload: Dict[str, Any],
        depends_on: List[str] = None,
        confidence: float = 0.0
    ) -> Dict[str, Any]:
        """Create and store a new artifact"""
        
        if not self.current_run_path:
            self.start_run()
            
        artifact = {
            "id": str(uuid.uuid4()),
            "kind": kind.value,
            "schema_version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "depends_on": depends_on or [],
            "confidence": confidence,
            "payload": payload
        }
        
        # Store artifact
        artifact_path = self.current_run_path / f"{artifact['id']}.json"
        with open(artifact_path, 'w') as f:
            json.dump(artifact, f, indent=2, default=str)
            
        # Update index
        self.index["artifacts"].append({
            "id": artifact["id"],
            "kind": kind.value,
            "created_by": created_by,
            "created_at": artifact["created_at"],
            "path": str(artifact_path.relative_to(self.base_path))
        })
        
        # Save index
        self._save_index()
        
        logger.info(f"Created artifact: {kind.value} by {created_by} (ID: {artifact['id'][:8]}...)")
        return artifact
        
    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an artifact by ID"""
        if not self.current_run_path:
            return None
            
        artifact_path = self.current_run_path / f"{artifact_id}.json"
        if artifact_path.exists():
            with open(artifact_path, 'r') as f:
                return json.load(f)
        return None
        
    def get_artifacts_by_kind(self, kind: ArtifactKind) -> List[Dict[str, Any]]:
        """Get all artifacts of a specific kind from current run"""
        if not self.current_run_path:
            return []
            
        artifacts = []
        for item in self.index.get("artifacts", []):
            if item["kind"] == kind.value:
                artifact = self.get_artifact(item["id"])
                if artifact:
                    artifacts.append(artifact)
                    
        return artifacts
        
    def get_latest_by_kind(self, kind: ArtifactKind) -> Optional[Dict[str, Any]]:
        """Get the most recent artifact of a specific kind"""
        artifacts = self.get_artifacts_by_kind(kind)
        return artifacts[-1] if artifacts else None
        
    def _save_index(self):
        """Save the current run index"""
        if self.current_run_path:
            index_path = self.current_run_path / "index.json"
            with open(index_path, 'w') as f:
                json.dump(self.index, f, indent=2, default=str)
                
    def create_decision_memo(
        self,
        selected_candidate: Dict[str, Any],
        alternatives: List[Dict[str, Any]],
        rationale: str,
        risks: List[str],
        triggers: List[str]
    ) -> Dict[str, Any]:
        """Create a decision memo artifact"""
        
        payload = {
            "selected": selected_candidate,
            "alternatives": alternatives,
            "rationale": rationale,
            "key_risks": risks,
            "reversal_triggers": triggers,
            "comparison": self._create_comparison_table(selected_candidate, alternatives)
        }
        
        return self.create_artifact(
            kind=ArtifactKind.DECISION_MEMO,
            created_by="orchestrator",
            payload=payload,
            depends_on=[selected_candidate.get("id")] + [a.get("id") for a in alternatives],
            confidence=selected_candidate.get("confidence", 0.85)
        )
        
    def _create_comparison_table(
        self,
        selected: Dict[str, Any],
        alternatives: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create comparison table for decision memo"""
        
        all_candidates = [selected] + alternatives
        comparison = {
            "candidates": [],
            "winner": selected.get("id")
        }
        
        for candidate in all_candidates:
            metrics = candidate.get("payload", {}).get("metrics", {})
            comparison["candidates"].append({
                "id": candidate.get("id"),
                "method": candidate.get("payload", {}).get("method", "Unknown"),
                "expected_return": metrics.get("expected_return", 0),
                "volatility": metrics.get("volatility", 0),
                "sharpe": metrics.get("sharpe", 0),
                "var_95": metrics.get("var_95", 0),
                "max_drawdown": metrics.get("max_drawdown", 0)
            })
            
        return comparison
        
    def generate_report(self, title: str, content: str, report_type: str = "Analysis"):
        """Generate a human-readable report"""
        if not self.current_run_path:
            self.start_run()
            
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"{report_type}_{title}_{timestamp}.md"
        
        # Save to both runs directory and reports directory
        for directory in [self.current_run_path, Path("./reports")]:
            directory.mkdir(parents=True, exist_ok=True)
            report_path = directory / filename
            
            with open(report_path, 'w') as f:
                f.write(content)
                
        logger.info(f"Generated report: {filename}")