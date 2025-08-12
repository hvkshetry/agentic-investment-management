#!/bin/bash

# Repository Cleanup Script for Public Deployment
# WARNING: This script will remove sensitive data and reorganize files

echo "🚨 Repository Cleanup for Public Deployment"
echo "============================================"
echo ""
echo "This script will:"
echo "1. Remove sensitive files (API keys, personal data)"
echo "2. Organize documentation"
echo "3. Consolidate test files"
echo "4. Clean up development artifacts"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 1
fi

echo ""
echo "📁 Creating backup before cleanup..."
backup_dir="../investing_backup_$(date +%Y%m%d_%H%M%S)"
cp -r . "$backup_dir"
echo "Backup created at: $backup_dir"

echo ""
echo "🧹 Step 1: Removing sensitive files..."
# Remove sensitive personal data
rm -f portfolio/ubs.csv
rm -f portfolio/vanguard.csv
rm -f .env  # Should already be gitignored
rm -f oracle/debug.json
rm -f oracle/debug.py

echo ""
echo "📚 Step 2: Creating documentation structure..."
mkdir -p documentation/development
mkdir -p documentation/technical-notes
mkdir -p documentation/analysis
mkdir -p documentation/api-reference

# Move development documentation
mv -f COMPLETE_IMPLEMENTATION_SUMMARY.md documentation/development/ 2>/dev/null || true
mv -f CODE_REVIEW_FIXES_PHASE*.md documentation/development/ 2>/dev/null || true
mv -f IMPLEMENTATION_COMPLETE.md documentation/development/ 2>/dev/null || true
mv -f IMPLEMENTATION_SUMMARY.md documentation/development/ 2>/dev/null || true
mv -f FINAL_TEST_RESULTS.md documentation/development/ 2>/dev/null || true
mv -f FINAL_TODO_COMPLETION_SUMMARY.md documentation/development/ 2>/dev/null || true
mv -f TESTING_VERIFICATION_REPORT.md documentation/development/ 2>/dev/null || true
mv -f TEST_INTEGRITY_AUDIT.md documentation/development/ 2>/dev/null || true

# Move technical notes
mv -f MCP_PARAMETER_TYPE_FIXES.md documentation/technical-notes/ 2>/dev/null || true
mv -f MCP_TOOL_NAME_FIXES.md documentation/technical-notes/ 2>/dev/null || true
mv -f mcp_parameter_fixes_summary.md documentation/technical-notes/ 2>/dev/null || true
mv -f PYDANTIC_MODELS_IMPLEMENTATION.md documentation/technical-notes/ 2>/dev/null || true

# Move analysis reports
mv -f OPENBB_OPTIMIZATION_COMPLETE.md documentation/analysis/ 2>/dev/null || true
mv -f OPENBB_OPTIMIZATION_FINAL_REPORT.md documentation/analysis/ 2>/dev/null || true
mv -f mutual_fund_pricing_analysis.md documentation/analysis/ 2>/dev/null || true
mv -f data_dependencies_summary.md documentation/analysis/ 2>/dev/null || true
mv -f historical_data_vs_backtesting.md documentation/analysis/ 2>/dev/null || true

# Remove outdated/duplicate documentation
rm -f GEMINI.md
rm -f ARCHITECTURE_IMPROVEMENT.md
rm -f INTEGRATION.md
rm -f UNIFIED_DATA_SERVICE_DESIGN.md
rm -f backtesting_integration_plan.md

echo ""
echo "🧪 Step 3: Organizing test files..."
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/system
mkdir -p tests/oracle

# Move and organize test files
mv -f test_suite.py tests/system/ 2>/dev/null || true
mv -f test_simple.py tests/system/ 2>/dev/null || true
mv -f test_integrated_system.py tests/integration/ 2>/dev/null || true

# Move component tests
mv -f test_data_integrity.py tests/unit/ 2>/dev/null || true
mv -f test_portfolio_state_integration.py tests/integration/ 2>/dev/null || true
mv -f test_mcp_schema.py tests/unit/ 2>/dev/null || true
mv -f test_unified_data_service.py tests/integration/ 2>/dev/null || true

# Remove development/debug test files
rm -f test_*_fix.py
rm -f test_fixes.py
rm -f test_all_fixes.py
rm -f test_data_quality_investigation.py
rm -f test_improved_pipeline_full.py
rm -f test_final_with_improvements.py
rm -f test_integrated_enhancements.py
rm -f test_openbb_optimization*.py

# Move existing tests directory contents
if [ -d "tests" ]; then
    mv -f tests/*.py tests/unit/ 2>/dev/null || true
fi

echo ""
echo "🗑️ Step 4: Removing development artifacts..."
# Remove deployment scripts
rm -f git_push_command.txt
rm -f push_to_github.ps1
rm -f push_to_github.bat

# Clean up backup files
find portfolio-state-mcp-server/state/ -name "portfolio_state_backup_*.json" -type f | head -n -5 | xargs rm -f

# Remove test result JSON files
rm -f test_results_*.json

# Clear cache files
echo "{}" > shared/cache/market_data_cache.json

echo ""
echo "✅ Step 5: Adding __init__.py files to server directories..."
touch portfolio-mcp-server/__init__.py
touch portfolio-state-mcp-server/__init__.py
touch policy-events-mcp-server/__init__.py
touch risk-mcp-server/__init__.py
touch tax-mcp-server/__init__.py
touch tax-optimization-mcp-server/__init__.py

echo ""
echo "📝 Step 6: Creating production example files..."
# Create example portfolio CSV
cat > portfolio/example_portfolio.csv << 'EOF'
Symbol,Shares,Cost Basis,Purchase Date
AAPL,100,15000.00,2023-01-15
MSFT,50,12500.00,2023-02-20
SPY,75,30000.00,2023-03-10
EOF

echo ""
echo "🔒 Step 7: Updating .gitignore..."
cat >> .gitignore << 'EOF'

# Additional cleanup entries
git_push_command.txt
push_to_github.*
*_backup_*.json
test_results_*.json
debug.json
debug.py
/openbb/
EOF

echo ""
echo "✨ Cleanup Complete!"
echo ""
echo "Summary of changes:"
echo "- Removed sensitive files (.env, personal CSVs)"
echo "- Organized documentation into /documentation/"
echo "- Consolidated test files into /tests/"
echo "- Removed development artifacts"
echo "- Added __init__.py to server directories"
echo "- Created example portfolio file"
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Review git history for sensitive data: git log --oneline"
echo "2. If sensitive data exists in history, use: git filter-branch or BFG Repo-Cleaner"
echo "3. Regenerate all API keys that were exposed"
echo "4. Update requirements.txt to add openbb-finra and openbb-stockgrid"
echo "5. Review the changes and commit when ready"
echo ""
echo "Backup saved at: $backup_dir"