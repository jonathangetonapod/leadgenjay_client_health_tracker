# Lead Management MCP Server Setup Guide (Instantly + Bison)

## What is this?

This MCP (Model Context Protocol) server allows Claude to automatically fetch lead responses and campaign statistics from **both Instantly.ai and Bison**. Instead of manually logging into each platform for each client, your team can now ask Claude to pull the data automatically!

**Time savings:** 15-20 minutes per client → 2-3 minutes per client

## What Claude can do with this MCP

### Instantly.ai (56 clients)
1. **List all Instantly clients** - See all workspaces you manage
2. **Get lead responses** - Pull interested leads with their email addresses, replies, and timestamps
3. **Get campaign stats** - Fetch emails sent, reply rates, opportunities, etc.
4. **Get workspace info** - Fetch detailed workspace information including actual workspace names, plan details, and metadata

### Bison (24 clients)
1. **List all Bison clients** - See all Bison workspaces
2. **Get lead responses** - Pull interested leads marked in Bison with their emails and replies
3. **Get campaign stats** - Fetch emails sent, opens, replies, interested leads, bounces, and unsubscribes

### Unified Tools
1. **Get all clients** - See all 80 clients across both platforms in one list

## Setup Instructions

### Step 1: Install the MCP Server in Claude Desktop

1. Open Claude Desktop
2. Open Settings → Developer → Edit Config
3. Add this configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lead-management": {
      "command": "python3",
      "args": [
        "/Users/jonathangarces/Desktop/leadgenjay_client_health_tracker/mcp_server.py"
      ]
    }
  }
}
```

**Note:** The server name changed from `instantly-leads` to `lead-management` to reflect support for both platforms.

4. Save the file
5. Restart Claude Desktop
6. Look for a 🔨 (hammer) icon in Claude - this means the MCP is connected!

### Step 2: Test it out!

Try these example questions in Claude:

#### Unified Queries (Both Platforms)

**1. List ALL clients from both platforms:**
```
Show me all available clients across both Instantly and Bison
```

**2. Compare platforms for a specific client:**
```
Get lead responses for Jeff Mikolai from both Instantly and Bison for the last 30 days
```

#### Instantly Queries

**3. Get Instantly lead responses by client name:**
```
Show me interested leads for Prism PR from the last 30 days
```

**4. Get Instantly campaign statistics:**
```
What are the campaign stats for Search Atlas in the last 7 days?
```

**5. Get Instantly workspace details:**
```
Get workspace info for Prism PR
```

#### Bison Queries

**6. List all Bison clients:**
```
Show me all Bison clients
```

**7. Get Bison lead responses:**
```
Show me interested leads from Bison for Jeff Mikolai from the last 30 days
```

**8. Get Bison campaign statistics:**
```
What are the Bison campaign stats for Derek Hobbs in the last 7 days?
```

#### Advanced Use Cases

**9. Create a unified client recap:**
```
Create a client recap for Jeff Mikolai for the last 30 days.
Include stats and lead responses from BOTH Instantly and Bison.
```

**10. Multi-platform performance comparison:**
```
Compare campaign performance across both platforms:
- Show me total emails sent on each platform
- Which platform has more interested leads?
- What are the reply rates on each?
```

## Available Tools

### Unified Tools

#### `get_all_clients()`
Lists ALL 80 clients from both Instantly (56) and Bison (24) platforms.

**Example:**
```
Claude: "Show me all clients across both platforms"
```

**Returns:**
```json
{
  "total_clients": 80,
  "instantly_clients": [...],
  "bison_clients": [...],
  "clients": [
    {
      "client_name": "Prism PR",
      "platform": "instantly",
      "workspace_id": "23dbc003-..."
    },
    {
      "client_name": "Jeff Mikolai",
      "platform": "bison"
    },
    ...
  ]
}
```

### Aggregated Analytics Tools

#### `get_all_platform_stats(days=7)`
Get combined statistics from BOTH platforms - total emails sent, replies, interested leads across all 80 clients.

**Parameters:**
- `days` (optional): Number of days to look back (default: 7)

**Example:**
```
Claude: "Show me aggregated stats from both platforms for the last 30 days"
```

**Returns:**
```json
{
  "date_range": {
    "days": 30,
    "start_date": "2025-11-12",
    "end_date": "2025-12-12"
  },
  "total_stats": {
    "total_emails_sent": 125000,
    "total_replies": 3500,
    "total_interested_leads": 850,
    "reply_rate": 2.8,
    "clients_processed": 80
  },
  "platform_breakdown": {
    "instantly": {
      "clients": 56,
      "emails_sent": 95000,
      "replies": 2600,
      "opportunities": 650,
      "reply_rate": 2.74
    },
    "bison": {
      "clients": 24,
      "emails_sent": 30000,
      "replies": 900,
      "interested": 200,
      "reply_rate": 3.0
    }
  }
}
```

**Use cases:**
- Weekly performance reports
- Compare platform effectiveness
- Track overall campaign health

#### `get_top_performing_clients(limit=10, metric="interested_leads", days=7)`
Find your best performing clients across both platforms, ranked by any metric.

**Parameters:**
- `limit` (optional): Number of top clients to return (default: 10)
- `metric` (optional): Sort by `interested_leads`, `emails_sent`, `replies`, or `reply_rate` (default: interested_leads)
- `days` (optional): Number of days to look back (default: 7)

**Example:**
```
Claude: "Show me my top 5 clients by interested leads this month"
```

**Returns:**
```json
{
  "metric": "interested_leads",
  "days": 30,
  "limit": 5,
  "top_clients": [
    {
      "rank": 1,
      "client_name": "Prism PR",
      "platform": "instantly",
      "metric_value": 85,
      "stats": {...}
    },
    {
      "rank": 2,
      "client_name": "Search Atlas",
      "platform": "instantly",
      "metric_value": 72,
      "stats": {...}
    },
    ...
  ]
}
```

**Use cases:**
- Identify top performers for case studies
- Reward/recognize high-performing campaigns
- Learn what works from successful clients

#### `get_underperforming_clients(threshold=5, metric="interested_leads", days=7)`
Find clients below a performance threshold who need attention or optimization.

**Parameters:**
- `threshold` (optional): Minimum value - clients below this are underperforming (default: 5)
- `metric` (optional): Check `interested_leads`, `emails_sent`, `replies`, or `reply_rate` (default: interested_leads)
- `days` (optional): Number of days to look back (default: 7)

**Example:**
```
Claude: "Which clients have less than 3 interested leads this week?"
```

**Returns:**
```json
{
  "metric": "interested_leads",
  "threshold": 3,
  "days": 7,
  "total_underperforming": 12,
  "underperforming_clients": [
    {
      "client_name": "Client ABC",
      "platform": "bison",
      "metric_value": 0,
      "stats": {...}
    },
    {
      "client_name": "Client XYZ",
      "platform": "instantly",
      "metric_value": 1,
      "stats": {...}
    },
    ...
  ]
}
```

**Use cases:**
- Proactive client support
- Identify campaigns needing optimization
- Schedule check-ins with struggling clients

#### `get_weekly_summary()`
Generate a comprehensive weekly report with overall stats, top 5 performers, underperformers, and AI-generated insights.

**Parameters:**
- None (always last 7 days)

**Example:**
```
Claude: "Give me my weekly summary"
```

**Returns:**
```json
{
  "period": "Last 7 days",
  "generated_at": "2025-12-12 14:30:00",
  "overall_stats": {
    "total_emails_sent": 35000,
    "total_replies": 950,
    "total_interested_leads": 220,
    "reply_rate": 2.71,
    "clients_processed": 80
  },
  "platform_breakdown": {...},
  "top_5_performers": [...],
  "underperformers": {
    "count": 8,
    "clients": [...]
  },
  "insights": [
    "Instantly sent 15,000 more emails than Bison",
    "Bison has a better reply rate (3.2%) vs Instantly (2.5%)",
    "Top performer: Prism PR (instantly) with 42 interested leads",
    "8 clients need attention (less than 3 interested leads)"
  ]
}
```

**Use cases:**
- Monday morning status reports
- Weekly team meetings
- Quick performance overview
- Identify trends and action items

### Instantly Tools

#### `get_client_list()`
Lists all 56 Instantly clients with their workspace IDs and friendly names.

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

### Bison Tools

#### `get_bison_client_list()`
Lists all 24 Bison clients.

**Example:**
```
Claude: "Show me all Bison clients"
```

**Returns:**
```json
{
  "total_clients": 24,
  "clients": [
    {"client_name": "Jeff Mikolai"},
    {"client_name": "Derek Hobbs"},
    {"client_name": "Aaron Oravec"},
    ...
  ]
}
```

#### `get_bison_lead_responses(client_name, days=7)`
Gets interested lead responses from Bison for a specific client.

**Parameters:**
- `client_name` (required): Client name (supports fuzzy matching)
- `days` (optional): Number of days to look back (default: 7)
- `start_date` (optional): Custom start date in YYYY-MM-DD format
- `end_date` (optional): Custom end date in YYYY-MM-DD format

**Smart Lookup:**
- Supports exact client name: `"Jeff Mikolai"`
- Supports fuzzy matching: `"jeff"`, `"mikolai"`, etc.
- If multiple matches, Claude will show options and ask you to clarify

**Example:**
```
Claude: "Get Bison lead responses for Jeff Mikolai from last 30 days"
```

**Returns:**
```json
{
  "client_name": "Jeff Mikolai",
  "start_date": "2025-11-12",
  "end_date": "2025-12-12",
  "total_leads": 15,
  "leads": [
    {
      "email": "contact@example.com",
      "from_name": "John Smith",
      "reply_body": "Yes, I'm interested in learning more...",
      "subject": "Re: Your service inquiry",
      "date_received": "2025-12-11T15:30:00.000000Z",
      "interested": true,
      "read": true,
      "reply_id": 12345
    },
    ...
  ]
}
```

**Key fields:**
- `email`: Lead's email address (PRIMARY - use this for follow-ups!)
- `from_name`: Name of the person who replied
- `reply_body`: Full text of their reply
- `subject`: Email subject line
- `date_received`: When they replied
- `interested`: Whether marked as interested in Bison (always true for this query)

#### `get_bison_campaign_stats(client_name, days=7)`
Gets campaign statistics from Bison for a specific client.

**Parameters:**
- Same as `get_bison_lead_responses()`

**Example:**
```
Claude: "Get Bison campaign stats for Derek Hobbs"
```

**Returns:**
```json
{
  "client_name": "Derek Hobbs",
  "start_date": "2025-12-05",
  "end_date": "2025-12-12",
  "emails_sent": 1200,
  "total_leads_contacted": 800,
  "opened": 450,
  "opened_percentage": 56.25,
  "unique_replies_per_contact": 85,
  "unique_replies_per_contact_percentage": 10.63,
  "bounced": 15,
  "bounced_percentage": 1.25,
  "unsubscribed": 8,
  "unsubscribed_percentage": 1.0,
  "interested": 42,
  "interested_percentage": 5.25
}
```

**Key metrics:**
- `emails_sent`: Total emails sent
- `total_leads_contacted`: Unique leads contacted
- `opened`: Number of opens
- `unique_replies_per_contact`: Number of unique leads who replied (1 reply per lead)
- `interested`: Number of leads marked as interested
- All metrics include percentage values

## Real-World Use Cases

### 1. Unified Client Recap (Both Platforms)
```
Create a unified recap for Jeff Mikolai for the last 30 days.
Include:
- Campaign stats from BOTH Instantly and Bison
- All interested lead responses with their email addresses from both platforms
- Compare performance across platforms
- Format it as an email I can send to the client
```

### 2. Cross-Platform Performance Analysis
```
Compare Jeff Mikolai's performance across both platforms for the last 30 days:
- Which platform sent more emails?
- Which has a better reply rate?
- Which generated more interested leads?
- Show me total counts and percentages
```

### 3. Weekly Client Recaps (Single Platform)
```
Create a weekly recap for Prism PR on Instantly. Include:
- Campaign stats (emails sent, replies, opportunities)
- All interested lead responses with their email addresses
- Format it as an email I can send to the client
```

### 4. Bulk Recaps for Bison Clients
```
I need to send recaps to my top 3 Bison clients. For each:
1. Jeff Mikolai
2. Derek Hobbs
3. Aaron Oravec

Pull last 7 days of campaign stats and lead responses.
Format each as a separate email.
```

### 5. Quick Lead Count Across Platforms
```
How many interested leads did we get total across both platforms this week?
Break it down by platform.
```

### 6. Lead Follow-up List (Multi-Platform)
```
Give me a unified list of all email addresses from interested leads
across BOTH Instantly and Bison in the last 30 days.
I need to follow up with them. Deduplicate if the same lead appears on both platforms.
```

### 7. Platform Migration Analysis
```
For clients that are on both platforms, compare their performance:
- Show me which clients appear on both Instantly and Bison
- Compare their metrics side-by-side
- Help me decide if we should consolidate to one platform
```

## How It Works

1. **Google Sheets Integration:** The MCP reads client lists from TWO tabs in your Google Sheet:
   - **Instantly tab (GID: 928115249):** Column A = workspace ID, Column B = API key, Column C = client name
   - **Bison tab (GID: 1631680229):** Column A = client name, Column B = API key

2. **Dual API Integration:** For each query, it:
   - Determines which platform (Instantly or Bison) based on the tool you use
   - Looks up the correct workspace/client and API key
   - Calls the appropriate API (Instantly or Bison) to fetch data
   - Returns cleaned, structured data to Claude

3. **Smart Lookup:** You can search by:
   - **Instantly:** Exact workspace ID, client name (fuzzy matching - "prism" matches "Rick Pendrick - Prism PR"), or partial workspace ID
   - **Bison:** Exact client name or fuzzy matching (e.g., "jeff" matches "Jeff Mikolai")

4. **Data Filtering (Instantly only):** Automatically excludes:
   - Emails FROM your team (@prism, @leadgenjay, @pendrick domains)
   - System emails (noreply, paypal, etc.)
   - Only shows genuine external lead responses

5. **Bison Filtering:** Uses the `status=interested` filter to only fetch leads marked as interested in Bison, then filters by date range

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
