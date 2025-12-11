# Instantly MCP Server Setup Guide

## What is this?

This MCP (Model Context Protocol) server allows Claude to automatically fetch lead responses and campaign statistics from Instantly.ai. Instead of manually logging into Instantly for each client, your team can now ask Claude to pull the data automatically!

**Time savings:** 15-20 minutes per client → 2-3 minutes per client

## What Claude can do with this MCP

1. **List all clients** - See all 54 workspaces you manage
2. **Get lead responses** - Pull interested leads with their email addresses, replies, and timestamps
3. **Get campaign stats** - Fetch emails sent, reply rates, opportunities, etc.
4. **Get workspace info** - Fetch detailed workspace information including actual workspace names, plan details, and metadata

## Setup Instructions

### Step 1: Install the MCP Server in Claude Desktop

1. Open Claude Desktop
2. Open Settings → Developer → Edit Config
3. Add this configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "instantly-leads": {
      "command": "python3",
      "args": [
        "/Users/jonathangarces/Desktop/leadgenjay_client_health_tracker/mcp_server.py"
      ]
    }
  }
}
```

4. Save the file
5. Restart Claude Desktop
6. Look for a 🔨 (hammer) icon in Claude - this means the MCP is connected!

### Step 2: Test it out!

Try these example questions in Claude:

**1. List all clients:**
```
Show me all available clients
```

**2. Get lead responses by client name (fuzzy matching):**
```
Show me interested leads for Prism PR from the last 30 days
```

**3. Get lead responses by exact workspace ID:**
```
Get lead responses for workspace 23dbc003-ebe2-4950-96f3-78761de5cf85
```

**4. Get campaign statistics:**
```
What are the campaign stats for Search Atlas in the last 7 days?
```

**5. Get workspace details:**
```
Get workspace info for Prism PR
```

**6. Create a client recap (combines multiple tools):**
```
Create a client recap for Prism PR for the last 30 days.
Include campaign stats and all interested lead responses with their emails.
```

## Available Tools

### 1. `get_client_list()`
Lists all 54 clients with their workspace IDs and friendly names.

**Example:**
```
Claude: "Show me all clients"
```

**Returns:**
```json
{
  "total_clients": 54,
  "clients": [
    {
      "workspace_id": "23dbc003-ebe2-4950-96f3-78761de5cf85",
      "client_name": "Rick Pendrick - Prism PR"
    },
    ...
  ]
}
```

### 2. `get_lead_responses(workspace_id, days=7)`
Gets interested lead responses for a specific client.

**Parameters:**
- `workspace_id` (required): Client name OR exact workspace ID
- `days` (optional): Number of days to look back (default: 7)
- `start_date` (optional): Custom start date in ISO format
- `end_date` (optional): Custom end date in ISO format

**Smart Lookup:**
- Supports exact workspace ID: `"23dbc003-ebe2-4950-96f3-78761de5cf85"`
- Supports fuzzy name matching: `"prism"`, `"ABC Corp"`, etc.
- If multiple matches, Claude will show options and ask you to clarify

**Example:**
```
Claude: "Get lead responses for Prism PR from last 30 days"
```

**Returns:**
```json
{
  "workspace_id": "23dbc003-ebe2-4950-96f3-78761de5cf85",
  "start_date": "2025-11-11T00:00:00Z",
  "end_date": "2025-12-11T23:59:59Z",
  "total_leads": 59,
  "leads": [
    {
      "email": "jmurray@denverpost.com",
      "reply_summary": "Thanks, Rick. I'll take a look!",
      "subject": "Re: Colorado Study",
      "timestamp": "2025-12-11T19:14:53.000Z",
      "lead_id": "jmurray@denverpost.com",
      "thread_id": "33-ySmpAq3W0Ls8V9k6r4njWZu"
    },
    ...
  ]
}
```

**Key fields:**
- `email`: Lead's email address (PRIMARY - use this for follow-ups!)
- `reply_summary`: Cleaned summary of their response
- `reply_body`: Full email text (not shown above but available)
- `subject`: Email subject line
- `timestamp`: When they replied

### 3. `get_campaign_stats(workspace_id, days=7)`
Gets campaign analytics for a specific client.

**Parameters:**
- Same as `get_lead_responses()`

**Example:**
```
Claude: "Get campaign stats for Prism PR"
```

**Returns:**
```json
{
  "workspace_id": "23dbc003-ebe2-4950-96f3-78761de5cf85",
  "start_date": "2025-12-04",
  "end_date": "2025-12-11",
  "emails_sent": 61770,
  "replies": 313,
  "opportunities": 126,
  "reply_rate": 0.51
}
```

### 4. `get_workspace_info(workspace_id)`
Gets detailed workspace information from the Instantly API.

**Parameters:**
- `workspace_id` (required): Client name OR exact workspace ID

**What it does:**
- Fetches the actual workspace name from Instantly (useful when Column C in the sheet is empty or unclear)
- Returns plan details, organization domain, and other metadata
- Supports the same smart lookup as other tools

**Example:**
```
Claude: "Get workspace info for Prism PR"
```

**Returns:**
```json
{
  "workspace_id": "23dbc003-ebe2-4950-96f3-78761de5cf85",
  "workspace_name": "Rick Pendrick - Prism PR",
  "owner": "78cdafee-624d-4da0-af14-929814969b26",
  "plan_id": "pid_ls_v1",
  "org_logo_url": "https://...",
  "org_client_domain": "example.com",
  "plan_id_crm": null,
  "plan_id_leadfinder": "pid_free",
  "timestamp_created": "2024-11-17T22:49:16.723Z",
  "timestamp_updated": "2025-07-23T17:51:58.824Z",
  "default_opportunity_value": 250
}
```

**Use cases:**
- Finding the actual workspace name when it's not in your Google Sheet
- Checking what plan/features a client has access to
- Getting organization details for client records

## Real-World Use Cases

### 1. Weekly Client Recaps
```
Create a weekly recap for ABC Corp. Include:
- Campaign stats (emails sent, replies, opportunities)
- All interested lead responses with their email addresses
- Format it as an email I can send to the client
```

### 2. Bulk Recaps for All Clients
```
I need to send recaps to all my top 5 clients. For each:
1. Prism PR
2. Search Atlas
3. Jobsdone
4. kargerandco
5. Satori Coach

Pull last 7 days of campaign stats and lead responses.
Format each as a separate email.
```

### 3. Quick Lead Count
```
How many interested leads did we get for Prism PR this week?
```

### 4. Lead Follow-up List
```
Give me a list of all email addresses from interested leads
for Search Atlas in the last 30 days. I need to follow up with them.
```

### 5. Performance Comparison
```
Compare campaign performance for the last 30 days:
- Prism PR
- Search Atlas
- Jobsdone

Show me emails sent, reply rates, and number of interested leads.
```

## How It Works

1. **Google Sheets Integration:** The MCP reads your client list from the Google Sheet (Column A = workspace ID, Column B = API key, Column C = client name)

2. **Instantly API:** For each query, it:
   - Looks up the correct workspace and API key
   - Calls Instantly's API to fetch data
   - Filters out your team's emails (only shows external lead responses)
   - Returns cleaned, structured data to Claude

3. **Smart Lookup:** You can search by:
   - Exact workspace ID (most reliable)
   - Client name (fuzzy matching - "prism" matches "Rick Pendrick - Prism PR")
   - Partial workspace ID

4. **Data Filtering:** Automatically excludes:
   - Emails FROM your team (@prism, @leadgenjay, @pendrick domains)
   - System emails (noreply, paypal, etc.)
   - Only shows genuine external lead responses

## Troubleshooting

### "Tool not found" error
- Make sure you restarted Claude Desktop after adding the config
- Check that the file path in the config matches your actual location
- Look for the 🔨 icon in Claude - if it's missing, the MCP isn't connected

### "Workspace not found" error
- Try listing all clients first: "Show me all clients"
- Use the exact workspace ID from the list
- If using a client name, make sure it's spelled correctly (fuzzy matching should still work)

### "Multiple matches found" error
- Claude will show you all matching clients
- Use the exact workspace ID from the list to be specific

### Rate limit errors
- Instantly limits: 20 requests per minute
- If you hit this, wait a minute and try again
- For large date ranges (30+ days), the MCP may take a bit longer

## Files in this Project

- `mcp_server.py` - Main MCP server (exposes tools to Claude)
- `mcp_functions.py` - Core functions (Google Sheets + Instantly API)
- `fetch_interested_leads.py` - Lead fetching logic with filtering
- `requirements.txt` - Python dependencies
- `test_*.py` - Test scripts (you can ignore these)

## Questions?

If you run into issues:
1. Check that Claude Desktop is restarted
2. Verify the file path in the config
3. Test with a simple query like "Show me all clients"
4. Check the Google Sheet is still accessible

That's it! You're ready to automate your client recaps! 🚀
