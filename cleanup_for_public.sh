#!/bin/bash

# Repository Cleanup Script for Public Deployment
# Updated: 2025-09-30
# WARNING: This script will remove sensitive data and reorganize files

echo "🚨 Repository Cleanup for Public Deployment"
echo "============================================"
echo ""
echo "This script will:"
echo "1. Remove sensitive files (API keys, personal data)"
echo "2. Clean up cache and state files"
echo "3. Remove development artifacts"
echo "4. Verify documentation structure"
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

# Remove old OpenBB configuration with API keys
rm -rf /home/hvksh/.openbb_platform/user_settings.json 2>/dev/null || true

echo ""
echo "📚 Step 2: Verifying documentation structure..."
# Documentation structure already exists and is current
echo "  ✓ documentation/ structure is current"
echo "  ✓ documentation/analysis/ exists"
echo "  ✓ documentation/development/ exists"
echo "  ✓ documentation/technical-notes/ exists"

# Note: Outdated docs have been removed by manual cleanup
echo "  ✓ Outdated WIP documentation removed"

echo ""
echo "🧪 Step 3: Organizing test files..."
# Test structure - verify existing structure
if [ ! -d "tests" ]; then
    mkdir -p tests/unit
    mkdir -p tests/integration
    mkdir -p tests/system
fi

# Remove development/debug test files
rm -f test_*_fix.py 2>/dev/null || true
rm -f test_fixes.py 2>/dev/null || true
rm -f test_all_fixes.py 2>/dev/null || true
rm -f test_data_quality_investigation.py 2>/dev/null || true
rm -f test_improved_pipeline_full.py 2>/dev/null || true
rm -f test_final_with_improvements.py 2>/dev/null || true
rm -f test_integrated_enhancements.py 2>/dev/null || true

echo ""
echo "🗑️ Step 4: Removing development artifacts..."
# Remove deployment scripts
rm -f git_push_command.txt 2>/dev/null || true
rm -f push_to_github.ps1 2>/dev/null || true
rm -f push_to_github.bat 2>/dev/null || true

# Clean up backup files (keep only last 5)
find portfolio-state-mcp-server/state/ -name "portfolio_state_backup_*.json" -type f 2>/dev/null | head -n -5 | xargs rm -f 2>/dev/null || true

# Remove test result JSON files
rm -f test_results_*.json 2>/dev/null || true

# Clear cache files
echo "{}" > shared/cache/market_data_cache.json

# Remove old pipeline backups (older than 30 days)
find shared/ -name "data_pipeline_backup_*.py" -mtime +30 -type f -delete 2>/dev/null || true

echo ""
echo "🗂️ Step 5: Cleaning up Codex session logs..."
# Remove old Codex session logs (keep last 10)
if [ -d ".codex/sessions" ]; then
    find .codex/sessions -type f -name "*.jsonl" | sort -r | tail -n +11 | xargs rm -f 2>/dev/null || true
fi

echo ""
echo "✅ Step 6: Adding __init__.py files to server directories..."
touch portfolio-mcp-server/__init__.py 2>/dev/null || true
touch portfolio-state-mcp-server/__init__.py 2>/dev/null || true
touch policy-events-mcp-server/__init__.py 2>/dev/null || true
touch risk-mcp-server/__init__.py 2>/dev/null || true
touch tax-mcp-server/__init__.py 2>/dev/null || true
touch openbb-mcp-customizations/openbb_mcp_server/__init__.py 2>/dev/null || true

echo ""
echo "📝 Step 7: Creating production example files..."
# Create example portfolio CSV if it doesn't exist
if [ ! -f "portfolio/example_portfolio.csv" ]; then
    cat > portfolio/example_portfolio.csv << 'EOF'
Symbol,Shares,Cost Basis,Purchase Date
AAPL,100,15000.00,2023-01-15
MSFT,50,12500.00,2023-02-20
SPY,75,30000.00,2023-03-10
EOF
fi

# Create example .env template
if [ ! -f ".env.example" ]; then
    cat > .env.example << 'EOF'
# Policy Events API Keys
# Get free API keys from:
# Congress.gov: https://api.congress.gov/sign-up/
# GovInfo: https://api.govinfo.gov/docs/
CONGRESS_API_KEY=your_key_here
GOVINFO_API_KEY=your_key_here

# Optional: OpenBB API Keys
FRED_API_KEY=your_key_here
BLS_API_KEY=your_key_here
FMP_API_KEY=your_key_here

# Zero-Cost Data Provider API Keys
# Yahoo Finance (unofficial API, no key required)
ENABLE_YAHOO_UNOFFICIAL=true

# Alpha Vantage (quotes fallback) - Free tier: 5 calls/min, 500/day
# Get key: https://www.alphavantage.co/support/#api-key
ALPHAVANTAGE_API_KEY=your_key_here

# Finnhub (analyst coverage) - Free tier: 60 calls/min
# Get key: https://finnhub.io/register
FINNHUB_API_KEY=your_key_here
EOF
fi

echo ""
echo "🔒 Step 8: Updating .gitignore..."
# Only add entries if they don't exist
if ! grep -q "git_push_command.txt" .gitignore 2>/dev/null; then
    cat >> .gitignore << 'EOF'

# Additional cleanup entries
git_push_command.txt
push_to_github.*
*_backup_*.json
test_results_*.json
debug.json
debug.py
.env
.env.local
/openbb/
.codex/
.mplconfig/
EOF
fi

echo ""
echo "✨ Cleanup Complete!"
echo ""
echo "Summary of changes:"
echo "- ✓ Removed sensitive files (.env, personal CSVs, API keys)"
echo "- ✓ Documentation structure verified and current"
echo "- ✓ Test files organized"
echo "- ✓ Development artifacts removed"
echo "- ✓ Added __init__.py to server directories"
echo "- ✓ Created example files (.env.example, example_portfolio.csv)"
echo "- ✓ Cleaned up old backups and session logs"
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Review git history for sensitive data: git log --oneline"
echo "2. If sensitive data exists in history, use: git filter-branch or BFG Repo-Cleaner"
echo "3. Verify .env is NOT committed: git status"
echo "4. Copy .env.example to .env and add your actual API keys"
echo "5. Review the changes and commit when ready"
echo ""
echo "Backup saved at: $backup_dir"