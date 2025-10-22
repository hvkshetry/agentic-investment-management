# Known Issues

**Last Updated**: 2025-01-20

## Schema Compliance (Non-Critical)

### Issue: halt_status Format in orchestrator/real_orchestrator.py

**Location**: `/home/hvksh/investing/orchestrator/real_orchestrator.py:175-181`

**Current Format** (in mock orchestrator):
```python
halt_status = {
    "required": ...,
    "reason": ...
}
```

**Required Format** (per `schemas/artifact_schemas.json:42-75`):
```python
halt_status = {
    "halt_required": bool,
    "es_breach": bool,
    "liquidity_breach": bool,
    "concentration_breach": bool,
    "reasons": [...]
}
```

**Impact**: Low - This is in the mock orchestrator code used for testing/examples. The production risk server (`risk_mcp_server_v3.py`) has been fixed and is schema-compliant.

**Status**: Deferred (mock orchestrator not used in production workflows)

**Fix Priority**: Low (update when refactoring orchestrator)

**Recommended Fix**:
```python
# In orchestrator/real_orchestrator.py around line 291-302
elif step.outputs == ArtifactKind.RISK_REPORT:
    payload["halt_status"] = {
        "halt_required": False,  # Mock data
        "es_breach": False,
        "liquidity_breach": False,
        "concentration_breach": False,
        "reasons": []
    }
```

---

## Notes

All critical issues from Codex review have been resolved:
- ✅ API keys permanently removed from git history
- ✅ SEC parser `include_tables` parameter fixed
- ✅ Risk server ES metrics schema compliance complete
- ✅ Risk server `halt_status` schema compliance complete

This file tracks minor issues and tech debt for future cleanup.
