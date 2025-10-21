# Investment Committee Memo - 20251001_115851

## Executive Summary
Evaluated integration strategies for SEC filing section extraction. edgar-crawler offers the most reliable parsing of inline XBRL and legacy filings. Recommend treating it as an upstream dependency with a thin wrapper that adapts its file-based workflow to our MCP needs while preserving auditability and enabling future upstream updates.

## Decision Context
**Request**: Determine whether to integrate edgar-crawler directly or port its logic into our existing parser.
**Portfolio Value**: Not available from current example dataset.
**ES Level**: Not available (example portfolio state lacks risk metrics). No breach detected, but risk status unverified.
**Status**: ⚠️ Monitor – Unable to confirm ES < 2.5% because portfolio state lacks expected shortfall data.

## Market Analysis
Not applicable for this engineering decision. Market conditions do not materially influence tooling selection today.

## Portfolio Assessment
Our automated tooling stack is primarily Python 3.12 within the OpenBB MCP server. Reliability and regulatory accuracy outweigh concerns about adding a well-scoped dependency. Existing custom parser struggles with modern inline XBRL because of brittle regex anchors, lack of header normalization, and insufficient HTML cleaning.

## Risk Considerations
- **Integration Risk**: External dependency (GPLv3) must be vetted and pinned; wrapper must manage temporary files securely.
- **Operational Risk**: Need to instrument Expected Shortfall reporting within tooling flows; current data gap prevents automatic halt trigger checks.
- **Maintenance Risk**: Vendoring or rewriting core logic inflates long-term maintenance burden; prefer upstream updates instead.

## Recommendations
1. Adopt edgar-crawler as a managed dependency; build an async-friendly wrapper that writes cached filings to temp storage and rehydrates structured JSON.
2. Harden risk monitoring: ensure real portfolio state import includes ES metric ahead of production rollout.
3. Keep the existing custom parser as fallback until new integration proves stable across regression suite.

## Implementation Plan
1. Prototype wrapper in a feature branch, using OpenBB `SecBaseFiling.download_file()` for caching and piping content into edgar-crawler's `ExtractItems`.
2. Add regression tests mirroring our highest-volume filing types, asserting parity with edgar-crawler CLI outputs.
3. Update deployment manifests (`requirements.txt` / `pyproject.toml`) to pin edgar-crawler and allied dependencies; document temp-file handling for MCP runtime.
4. Deprecate custom regex-based section locator after we confirm the wrapper meets latency and accuracy targets.

---
*Generated: 2025-10-01 11:58:52*
*Smart Connections will automatically link related documents.*
