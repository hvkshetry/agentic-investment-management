# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2025-01-18

### Added
- **Tool-First Data Policy**: Mandatory provenance tracking for all metrics with tool_calls[] arrays
- **Pricing Enrichment Module**: Automatic enrichment of portfolio state with current market prices
- **Artifact Validation Framework**: Schema-based validation with business rule enforcement
- **Comprehensive Test Suite**: Integration tests validating all critical fixes
- **Global Policy Header**: Standardized GLOBAL_HEADER.md for all agent prompts
- **JSON Artifact Schemas**: Formal schema definitions with provenance requirements

### Changed
- **Concentration Risk Policy**: ALL funds (ETFs, Mutual Funds, CEFs) now exempt from concentration limits
- **Agent Prompts**: Updated all critical agents to enforce tool-first data policy
- **Tax Year Support**: Extended validation to include year 2025
- **Risk Reporting**: Updated to show ES as primary metric with VaR as reference only

### Fixed
- Tax MCP server now accepts year 2025 (was rejecting as invalid)
- Tax optimization server stdout pollution causing JSON parsing errors
- Portfolio state tax lots missing current_price and current_value fields
- Agent prompts incorrectly referencing simple_max_position instead of concentration_analysis
- Concentration risk incorrectly flagging funds as violations
- Round-2 gate not properly checking ES limits

### Security
- Enforced tool-first policy prevents data fabrication
- Mandatory provenance tracking provides complete audit trail
- Automatic HALT on estimated data or missing tool calls

## [2.0.0] - 2025-01-17

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