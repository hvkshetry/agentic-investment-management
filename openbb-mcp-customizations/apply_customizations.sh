#!/bin/bash

# Script to apply OpenBB MCP customizations

echo "OpenBB MCP Server Customization Script"
echo "======================================"

# Find the OpenBB MCP server installation
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
OPENBB_MCP_PATH="$SITE_PACKAGES/openbb_mcp_server"

if [ ! -d "$OPENBB_MCP_PATH" ]; then
    echo "Error: OpenBB MCP server not found at $OPENBB_MCP_PATH"
    echo "Please install it first: pip install openbb-mcp-server"
    exit 1
fi

echo "Found OpenBB MCP server at: $OPENBB_MCP_PATH"

# Backup original files
echo "Creating backups..."
for file in main.py utils/settings.py utils/config.py; do
    if [ -f "$OPENBB_MCP_PATH/$file" ]; then
        cp "$OPENBB_MCP_PATH/$file" "$OPENBB_MCP_PATH/$file.backup"
        echo "  Backed up $file"
    fi
done

# Copy customized files
echo "Applying customizations..."
cp openbb_mcp_server/curated_tools.py "$OPENBB_MCP_PATH/"
echo "  Created curated_tools.py"

cp openbb_mcp_server/main.py "$OPENBB_MCP_PATH/"
echo "  Updated main.py"

cp openbb_mcp_server/settings.py "$OPENBB_MCP_PATH/utils/"
echo "  Updated utils/settings.py"

cp openbb_mcp_server/config.py "$OPENBB_MCP_PATH/utils/"
echo "  Updated utils/config.py"

echo ""
echo "✅ Customizations applied successfully!"
echo ""
echo "Next steps:"
echo "1. Configure API keys in ~/.openbb_platform/user_settings.json"
echo "2. Run: openbb-mcp --no-tool-discovery"
echo ""
echo "To revert changes, restore from .backup files"