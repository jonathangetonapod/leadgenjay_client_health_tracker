#!/bin/bash

# Instantly.ai MCP Server Setup Script
# This script automates the installation process for team members

set -e  # Exit on error

echo "=================================================="
echo "Instantly.ai MCP Server - Setup Script"
echo "=================================================="
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Found Python $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
echo ""
echo "Installing dependencies..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ Dependencies installed"

# Get the absolute path to this directory
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_PATH="$INSTALL_DIR/venv/bin/python"
SERVER_PATH="$INSTALL_DIR/mcp_server.py"

# Make server executable
chmod +x "$SERVER_PATH"

# Detect OS and set config path
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CONFIG_DIR="$HOME/.config/Claude"
else
    echo "⚠️  Unknown OS type: $OSTYPE"
    CONFIG_DIR="$HOME/.config/Claude"
fi

CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

echo ""
echo "=================================================="
echo "Configuration"
echo "=================================================="
echo "Install directory: $INSTALL_DIR"
echo "Python path: $PYTHON_PATH"
echo "Server path: $SERVER_PATH"
echo "Config file: $CONFIG_FILE"
echo ""

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Check if config file exists
if [ -f "$CONFIG_FILE" ]; then
    echo "⚠️  Config file already exists at:"
    echo "   $CONFIG_FILE"
    echo ""
    echo "You need to manually add this MCP server to your config."
    echo ""
    echo "Add this to the 'mcpServers' section:"
    echo ""
    cat <<EOF
    "instantly-leads": {
      "command": "$PYTHON_PATH",
      "args": ["$SERVER_PATH"]
    }
EOF
    echo ""
else
    echo "Creating new config file..."
    cat > "$CONFIG_FILE" <<EOF
{
  "mcpServers": {
    "instantly-leads": {
      "command": "$PYTHON_PATH",
      "args": ["$SERVER_PATH"]
    }
  }
}
EOF
    echo "✅ Config file created"
fi

echo ""
echo "=================================================="
echo "Setup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Make sure you have access to the Google Sheet"
echo "2. Restart Claude Desktop"
echo "3. Test it with: 'Show me the client list'"
echo ""
echo "If you see any issues, check INSTALL.md for troubleshooting."
echo ""
