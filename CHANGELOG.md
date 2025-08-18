# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-08-18

### Added
- **Expected Shortfall (ES) Primary Risk Management**: ES at 97.5% confidence is now the binding risk constraint
- **Round-2 Gate System**: Mandatory validation for all portfolio revisions with full lineage tracking
- **Tax Reconciliation System**: Single-source-of-truth for tax calculations with immutable artifacts
- **CVXPY Optimizer**: Proper convex optimization replacing problematic PyPortfolioOpt constraints
- **HALT Protocol**: Automatic trading stop when ES > 2.5% or other critical failures occur
- **Comprehensive Test Suite**: Golden tests validating all critical fixes work together

### Changed
- **Risk Metrics**: VaR relegated to reference only, ES is primary decision metric
- **Agent Prompts**: All agents updated with ES-primary rules and HALT enforcement
- **Data Pipeline**: Removed ALL synthetic/mock data fallbacks - system fails loudly on API errors
- **Tax Calculations**: Recomputed on every portfolio revision for consistency
- **Optimization Constraints**: All constraints properly encoded for DCP compliance

### Fixed
- Sign/unit convention bug causing "-1.98% < -2.0%" comparison failures
- Tax calculation inconsistency showing -$9,062 vs +$1,982 discrepancies
- Missing validation for revised portfolio allocations
- PyPortfolioOpt lambda constraint failures
- Synthetic data being used as fallback when APIs unavailable
- Wash sale rules not being enforced

### Security
- Immutable tax artifacts with SHA256 checksums
- Complete audit trail with lineage tracking
- Mandatory validation gates preventing unauthorized trades

## [1.0.0] - 2025-08-13

### Added
- Initial workflow-driven institutional architecture
- 12 specialized AI agents for different investment domains
- MCP server integration for portfolio state, risk, tax, and optimization
- Policy gates system for automated compliance
- Session-based artifact management in `./runs/<timestamp>/`
- Pre-built workflows for rebalancing, daily checks, and portfolio import

### Changed
- Transformed from tool-based to workflow-driven architecture
- Moved from ad-hoc decisions to deterministic DAG execution

### Security
- Added automated policy gates for risk, tax, and compliance
- Implemented multi-source validation requirements