# Installation Guide for Team Members

This guide will help you install the Instantly.ai MCP server on your local machine.

## Prerequisites

- **Claude Desktop** installed ([download here](https://claude.ai/download))
- **Python 3.10+** installed
- **Git** installed
- Access to the team's Google Sheet with Instantly workspace data

## Installation Steps

### Step 1: Clone the Repository

```bash
cd ~/Desktop  # or wherever you want to install it
git clone https://github.com/jonathangetonapod/leadgenjay_client_health_tracker.git
cd leadgenjay_client_health_tracker
```

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Mac/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Verify Google Sheet Access

Make sure you have access to the Google Sheet. Ask your admin to share it with you if you don't.

The sheet should have columns:
- **Column A**: Workspace ID
- **Column B**: API Key
- **Column C**: Workspace Name
- **Column D**: Client/Person Name

### Step 4: Configure Claude Desktop

Find your Claude Desktop config file:
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Add this to your config (replace `YOUR_USERNAME` and path with your actual details):

```json
{
  "mcpServers": {
    "instantly-leads": {
      "command": "/Users/YOUR_USERNAME/Desktop/leadgenjay_client_health_tracker/venv/bin/python",
      "args": [
        "/Users/YOUR_USERNAME/Desktop/leadgenjay_client_health_tracker/mcp_server.py"
      ]
    }
  }
}
```

**Windows example:**
```json
{
  "mcpServers": {
    "instantly-leads": {
      "command": "C:\\Users\\YOUR_USERNAME\\Desktop\\leadgenjay_client_health_tracker\\venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\YOUR_USERNAME\\Desktop\\leadgenjay_client_health_tracker\\mcp_server.py"
      ]
    }
  }
}
```

### Step 5: Restart Claude Desktop

1. Quit Claude Desktop completely
2. Reopen Claude Desktop
3. Look for the MCP icon in the bottom right to verify it's connected

### Step 6: Test It!

In Claude Desktop, try:
```
"Show me the client list"
"Get interested leads from the past month for [client name]"
```

## Troubleshooting

### MCP Server Not Connecting

1. Check the paths in your config are correct
2. Make sure the virtual environment was created successfully
3. Verify Python version: `python3 --version` (should be 3.10+)

### "Workspace not found" Error

- Make sure you have access to the Google Sheet
- Check that the sheet URL in `mcp_functions.py` is correct

### Permission Errors

On Mac/Linux, you may need to make the script executable:
```bash
chmod +x mcp_server.py
```

## Need Help?

Contact the team admin or check the [GitHub repository](https://github.com/jonathangetonapod/leadgenjay_client_health_tracker) for issues.
