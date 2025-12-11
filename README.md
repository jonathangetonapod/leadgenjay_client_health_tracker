# Instantly.ai MCP Server

MCP (Model Context Protocol) server that integrates Instantly.ai lead response data with Claude Desktop. This tool helps you quickly generate client recaps by fetching interested leads from the Instantly API.

## What It Does

- **Get Client List**: View all 54+ clients with their workspace information
- **Fetch Lead Responses**: Get interested leads with email addresses, reply summaries, and timestamps
- **Campaign Stats**: View analytics for client campaigns
- **Workspace Info**: Get detailed workspace information

## Quick Start for Team Members

### Automated Setup (Recommended)

**Mac/Linux:**
```bash
git clone https://github.com/jonathangetonapod/leadgenjay_client_health_tracker.git
cd leadgenjay_client_health_tracker
./setup.sh
```

**Windows:**
```cmd
git clone https://github.com/jonathangetonapod/leadgenjay_client_health_tracker.git
cd leadgenjay_client_health_tracker
setup.bat
```

### Manual Setup

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

## Usage Examples

Once installed, open Claude Desktop and try:

```
"Show me the client list"

"Get interested leads from the past month for Bit Talent"

"Get lead responses for Budgyt from November 13 to December 11"

"Show me campaign stats for Rick Pendrick"
```

## Requirements

- Claude Desktop ([download](https://claude.ai/download))
- Python 3.10 or higher
- Access to the team's Google Sheet with Instantly workspace data

## Features

### Smart Client Lookup
Search by:
- Person name (Column D): "Rick Pendrick"
- Company name (Column C): "Prism PR"
- Partial matches: "Budgyt"

### Lead Response Filtering
- Only shows **received emails** from leads (not sent emails)
- Automatically removes email signatures and quoted text
- Deduplicates by email address (keeps most recent)
- Filters out auto-replies and system emails

### Performance
- Fast queries (under 5 seconds for most clients)
- Handles 50+ clients efficiently
- Works within Claude Desktop's timeout limits

## Troubleshooting

### MCP Server Not Connecting
1. Make sure you ran the setup script
2. Verify Claude Desktop was restarted
3. Check the config file location matches your OS

### "Workspace not found" Error
- Verify you have access to the Google Sheet
- Try searching by a different name (person name vs company name)

### Rate Limiting
If you see timeouts, the API might be rate-limited. Wait a few seconds and try again.

## Architecture

```
┌─────────────────┐
│ Claude Desktop  │
└────────┬────────┘
         │ MCP Protocol
┌────────▼────────┐
│   mcp_server.py │ ◄── Exposes 4 tools
└────────┬────────┘
         │
┌────────▼────────┐
│mcp_functions.py │ ◄── Core logic
└────────┬────────┘
         │
    ┌────▼─────────────────┐
    │                      │
┌───▼──────┐    ┌─────────▼────────┐
│ Google   │    │  Instantly API   │
│ Sheets   │    │  /emails         │
│          │    │  /workspaces     │
│ (Client  │    │  /leads          │
│  Config) │    │  /campaigns      │
└──────────┘    └──────────────────┘
```

## Files

- `mcp_server.py` - MCP server exposing tools to Claude
- `mcp_functions.py` - Core functions (Google Sheets + Instantly API)
- `fetch_interested_leads.py` - Lead fetching logic
- `setup.sh` / `setup.bat` - Automated setup scripts
- `INSTALL.md` - Detailed installation guide
- `MCP_SETUP.md` - Technical MCP configuration details

## Support

- **Issues**: [GitHub Issues](https://github.com/jonathangetonapod/leadgenjay_client_health_tracker/issues)
- **Questions**: Contact the team admin

## License

Internal tool for team use only.
