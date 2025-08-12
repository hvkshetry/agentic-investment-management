#!/bin/bash
# Installation script for Agentic Investment Management System

echo "======================================"
echo "Agentic Investment Management Setup"
echo "======================================"

# Check Python version
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi

echo "✓ Python version check passed ($python_version)"

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. Please run this script from the project root."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ Pip upgraded"

# Install poetry if not installed
if ! command -v poetry &> /dev/null; then
    echo "Installing Poetry..."
    pip install poetry > /dev/null 2>&1
    echo "✓ Poetry installed"
else
    echo "✓ Poetry already installed"
fi

# Install dependencies
echo "Installing dependencies (this may take a few minutes)..."
if [ -f "poetry.lock" ]; then
    poetry install
else
    poetry install --no-root
fi
echo "✓ Dependencies installed"

# Create necessary directories
echo "Creating directory structure..."
mkdir -p ~/.investing/logs
mkdir -p ~/.investing/cache
mkdir -p ~/.investing/data
mkdir -p ~/.investing/config
echo "✓ Directories created"

# Copy configuration if it doesn't exist
if [ ! -f ~/.investing/config/settings.yaml ]; then
    if [ -f config/settings.yaml ]; then
        cp config/settings.yaml ~/.investing/config/
        echo "✓ Configuration copied to ~/.investing/config/settings.yaml"
        echo "  Please edit this file with your personal tax rates and preferences"
    fi
else
    echo "✓ Configuration already exists at ~/.investing/config/settings.yaml"
fi

# Create a simple test script
cat > test_installation.py << 'EOF'
#!/usr/bin/env python3
"""Test that the installation is working correctly."""

import sys
import importlib

def test_import(module_name):
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

print("Testing installation...")
modules_to_test = [
    ("fastmcp", "MCP Framework"),
    ("openbb", "OpenBB"),
    ("yfinance", "yfinance"),
    ("pypfopt", "PyPortfolioOpt"),
    ("riskfolio", "Riskfolio-Lib"),
    ("pulp", "PuLP"),
    ("shared.atomic_writer", "Atomic Writer"),
    ("shared.money_utils", "Money Utils"),
    ("shared.config", "Config Loader"),
    ("shared.risk_utils", "Risk Utils"),
]

all_passed = True
for module, name in modules_to_test:
    if test_import(module):
        print(f"✓ {name} imported successfully")
    else:
        print(f"✗ Failed to import {name}")
        all_passed = False

if all_passed:
    print("\n✓ All modules imported successfully!")
    sys.exit(0)
else:
    print("\n✗ Some modules failed to import. Please check the installation.")
    sys.exit(1)
EOF

# Run the test
echo ""
echo "Running installation test..."
python3 test_installation.py

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================"
    echo "✓ Installation completed successfully!"
    echo "======================================"
    echo ""
    echo "Next steps:"
    echo "1. Edit ~/.investing/config/settings.yaml with your personal settings"
    echo "2. Activate the virtual environment: source venv/bin/activate"
    echo "3. The MCP servers are ready to be used with your CLI"
    echo ""
else
    echo ""
    echo "✗ Installation test failed. Please check the errors above."
    exit 1
fi

# Clean up test script
rm -f test_installation.py