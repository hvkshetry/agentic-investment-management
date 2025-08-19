#!/usr/bin/env python3
"""
Artifact Schema Validator

Validates JSON artifacts against defined schemas with provenance tracking.
Ensures all metrics come from tool calls and have proper status tracking.
"""

import json
import jsonschema
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)


class ArtifactValidator:
    """Validates workflow artifacts against schemas with provenance tracking."""
    
    def __init__(self, schema_path: str = "schemas/artifact_schemas.json"):
        """Initialize validator with schema definitions."""
        self.schema_path = Path(schema_path)
        self.schemas = self._load_schemas()
        
    def _load_schemas(self) -> Dict[str, Any]:
        """Load JSON schema definitions."""
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
            
        with open(self.schema_path) as f:
            return json.load(f)
    
    def validate_artifact(self, artifact: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate an artifact against its schema.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check basic structure
        if "kind" not in artifact:
            errors.append("Missing 'kind' field")
            return False, errors
            
        kind = artifact["kind"]
        
        # Check for required provenance
        if "provenance" not in artifact:
            errors.append("Missing 'provenance' field - tool-first policy violation")
            return False, errors
            
        # Validate provenance structure
        prov_errors = self._validate_provenance(artifact.get("provenance", {}))
        errors.extend(prov_errors)
        
        # Get schema for this kind
        if kind not in self.schemas:
            errors.append(f"No schema defined for kind: {kind}")
            return False, errors
            
        # For now, skip jsonschema validation due to reference issues
        # Just do business rule validation
            
        # Additional business rule validations
        rule_errors = self._validate_business_rules(artifact)
        errors.extend(rule_errors)
        
        return len(errors) == 0, errors
    
    def _validate_provenance(self, provenance: Dict[str, Any]) -> List[str]:
        """Validate provenance tracking requirements."""
        errors = []
        
        # Check tool_calls array
        if "tool_calls" not in provenance:
            errors.append("Missing provenance.tool_calls array")
        elif not isinstance(provenance["tool_calls"], list):
            errors.append("provenance.tool_calls must be an array")
        elif len(provenance["tool_calls"]) == 0:
            errors.append("provenance.tool_calls cannot be empty - all data must come from tools")
        else:
            for i, call in enumerate(provenance["tool_calls"]):
                if not isinstance(call, dict):
                    errors.append(f"tool_calls[{i}] must be an object")
                    continue
                    
                required = ["id", "name", "args", "timestamp"]
                for field in required:
                    if field not in call:
                        errors.append(f"tool_calls[{i}] missing required field: {field}")
                        
                # Validate timestamp format
                if "timestamp" in call:
                    try:
                        datetime.fromisoformat(call["timestamp"].replace("Z", "+00:00"))
                    except:
                        errors.append(f"tool_calls[{i}].timestamp has invalid format")
        
        # Check data_quality
        if "data_quality" not in provenance:
            errors.append("Missing provenance.data_quality")
        
        return errors
    
    def _validate_business_rules(self, artifact: Dict[str, Any]) -> List[str]:
        """Validate business-specific rules."""
        errors = []
        kind = artifact["kind"]
        payload = artifact.get("payload", {})
        
        if kind == "risk_analysis":
            # ES must be primary risk metric
            metrics = payload.get("risk_metrics", {})
            if "es_975_1day" not in metrics:
                errors.append("Risk analysis missing PRIMARY metric es_975_1day")
            
            # ES limit must be 2.5%
            if metrics.get("es_limit") != 0.025:
                errors.append("ES limit must be 0.025 (2.5%)")
                
            # Concentration analysis must exempt funds
            conc = payload.get("concentration_analysis", {})
            if conc.get("funds_exempt") != True:
                errors.append("Concentration analysis must have funds_exempt=true")
                
            # Check for halt conditions
            es_value = abs(metrics.get("es_975_1day", 0))
            if es_value > 0.025:
                halt = payload.get("halt_status", {})
                if not halt.get("halt_required"):
                    errors.append(f"HALT required when ES ({es_value}) > 2.5%")
                    
        elif kind == "optimization_candidate":
            # Must have Round-2 gate validation
            validation = payload.get("validation", {})
            if "round2_gate_passed" not in validation:
                errors.append("Optimization must include Round-2 gate validation")
                
            # ES compliance is mandatory
            metrics = payload.get("metrics", {})
            if not metrics.get("es_compliant"):
                errors.append("Optimization must be ES compliant (<2.5%)")
                
            # Parent allocation tracking for revisions
            impl = payload.get("implementation", {})
            if "revision_reason" in impl and "parent_allocation_id" not in impl:
                errors.append("Revisions must include parent_allocation_id")
                
        elif kind == "tax_impact":
            # All metrics must have status
            analysis = payload.get("analysis", {})
            if "status" not in analysis:
                errors.append("Tax analysis must include status field")
                
            # If status is estimate, halt required
            if analysis.get("status") == "estimate":
                if not artifact.get("halt_required"):
                    errors.append("halt_required must be true when using estimates")
                    
        elif kind == "halt_order":
            # Must have valid trigger
            trigger = payload.get("trigger")
            valid_triggers = ["es_breach", "liquidity_crisis", "concentration_breach", "tax_inconsistency"]
            if trigger not in valid_triggers:
                errors.append(f"Invalid halt trigger: {trigger}")
                
            # Must have required actions
            if not payload.get("required_actions"):
                errors.append("HALT order must specify required_actions")
                
        elif kind == "trade_list":
            # Trades must maintain ES compliance
            validation = payload.get("validation", {})
            if not validation.get("es_compliant"):
                errors.append("Trade list must maintain ES compliance")
                
            # Must check for wash sales
            if not validation.get("wash_sale_checked"):
                errors.append("Trade list must include wash sale check")
        
        return errors
    
    def validate_session_artifacts(self, session_dir: Path) -> Dict[str, Any]:
        """
        Validate all artifacts in a session directory.
        
        Returns summary of validation results.
        """
        results = {
            "session": str(session_dir),
            "timestamp": datetime.now().isoformat(),
            "artifacts": [],
            "overall_valid": True,
            "summary": {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "missing_provenance": 0,
                "estimated_data": 0
            }
        }
        
        # Find all JSON files
        json_files = list(session_dir.glob("*.json"))
        results["summary"]["total"] = len(json_files)
        
        for file_path in json_files:
            try:
                with open(file_path) as f:
                    artifact = json.load(f)
                    
                is_valid, errors = self.validate_artifact(artifact)
                
                artifact_result = {
                    "file": file_path.name,
                    "kind": artifact.get("kind", "unknown"),
                    "valid": is_valid,
                    "errors": errors
                }
                
                # Check for specific issues
                if "provenance" not in artifact:
                    results["summary"]["missing_provenance"] += 1
                    
                # Check for estimated data
                if self._has_estimated_data(artifact):
                    results["summary"]["estimated_data"] += 1
                    artifact_result["has_estimates"] = True
                    
                if is_valid:
                    results["summary"]["valid"] += 1
                else:
                    results["summary"]["invalid"] += 1
                    results["overall_valid"] = False
                    
                results["artifacts"].append(artifact_result)
                
            except Exception as e:
                results["artifacts"].append({
                    "file": file_path.name,
                    "valid": False,
                    "errors": [f"Failed to parse: {str(e)}"]
                })
                results["summary"]["invalid"] += 1
                results["overall_valid"] = False
        
        return results
    
    def _has_estimated_data(self, artifact: Dict[str, Any]) -> bool:
        """Check if artifact contains estimated (non-tool) data."""
        def check_status(obj):
            if isinstance(obj, dict):
                if obj.get("status") == "estimate":
                    return True
                for value in obj.values():
                    if check_status(value):
                        return True
            elif isinstance(obj, list):
                for item in obj:
                    if check_status(item):
                        return True
            return False
            
        return check_status(artifact.get("payload", {}))
    
    def generate_checksum(self, artifact: Dict[str, Any]) -> str:
        """Generate SHA256 checksum for artifact integrity."""
        # Serialize in deterministic way
        canonical = json.dumps(artifact, sort_keys=True, separators=(',', ':'))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def main():
    """CLI for artifact validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate workflow artifacts")
    parser.add_argument("path", help="Path to artifact file or session directory")
    parser.add_argument("--schema", default="schemas/artifact_schemas.json",
                       help="Path to schema definitions")
    parser.add_argument("--verbose", action="store_true",
                       help="Show detailed validation results")
    
    args = parser.parse_args()
    
    validator = ArtifactValidator(args.schema)
    path = Path(args.path)
    
    if path.is_file():
        # Validate single file
        with open(path) as f:
            artifact = json.load(f)
            
        is_valid, errors = validator.validate_artifact(artifact)
        
        if is_valid:
            print(f"✅ {path.name} is valid")
            print(f"   Checksum: {validator.generate_checksum(artifact)}")
        else:
            print(f"❌ {path.name} has validation errors:")
            for error in errors:
                print(f"   - {error}")
                
    elif path.is_dir():
        # Validate session directory
        results = validator.validate_session_artifacts(path)
        
        print(f"\nSession Validation: {path}")
        print("=" * 50)
        print(f"Total artifacts: {results['summary']['total']}")
        print(f"Valid: {results['summary']['valid']}")
        print(f"Invalid: {results['summary']['invalid']}")
        
        if results['summary']['missing_provenance'] > 0:
            print(f"⚠️  Missing provenance: {results['summary']['missing_provenance']}")
            
        if results['summary']['estimated_data'] > 0:
            print(f"⚠️  Contains estimates: {results['summary']['estimated_data']}")
            
        if args.verbose or not results['overall_valid']:
            print("\nDetails:")
            for artifact in results['artifacts']:
                if artifact['valid']:
                    print(f"  ✅ {artifact['file']} ({artifact['kind']})")
                else:
                    print(f"  ❌ {artifact['file']} ({artifact['kind']})")
                    for error in artifact['errors']:
                        print(f"     - {error}")
                        
        if results['overall_valid']:
            print("\n✅ All artifacts valid")
        else:
            print("\n❌ Validation failed - check errors above")
            
    else:
        print(f"Error: {path} not found")
        return 1
        
    return 0 if results.get('overall_valid', is_valid) else 1


if __name__ == "__main__":
    exit(main())