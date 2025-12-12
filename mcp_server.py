#!/usr/bin/env python3
"""
MCP Server for Lead Management (Instantly.ai + Bison)
Exposes tools to query client lead responses and campaign statistics from both platforms.
"""

import asyncio
import json
import sys
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp_functions import (
    get_client_list, get_lead_responses, get_campaign_stats, get_workspace_info,
    get_bison_client_list, get_bison_lead_responses, get_bison_campaign_stats,
    get_all_clients,
    get_all_platform_stats, get_top_performing_clients, get_underperforming_clients, get_weekly_summary
)

# CRITICAL: Redirect all print() to stderr to avoid breaking MCP JSON protocol
# MCP requires ONLY valid JSON-RPC messages on stdout
import builtins
_original_print = builtins.print
def _stderr_print(*args, **kwargs):
    kwargs['file'] = sys.stderr
    _original_print(*args, **kwargs)
builtins.print = _stderr_print

# Create MCP server
server = Server("lead-management")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="get_client_list",
            description=(
                "Get a list of all available clients/workspaces. "
                "Returns workspace IDs and friendly client names. "
                "Use this first to see available clients before querying specific data."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_lead_responses",
            description=(
                "Get positive lead responses for a specific client. "
                "Returns interested leads with their email addresses, reply summaries, "
                "and timestamps. Supports lookup by exact workspace_id OR fuzzy client name. "
                "Example: 'prism', 'ABC Corp', or '23dbc003-ebe2-4950-96f3-78761de5cf85'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "Client name or workspace ID (supports fuzzy matching)"
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format (optional, overrides 'days')"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format (optional, overrides 'days')"
                    }
                },
                "required": ["workspace_id"]
            }
        ),
        Tool(
            name="get_campaign_stats",
            description=(
                "Get campaign statistics for a specific client. "
                "Returns emails sent, replies, opportunities, and reply rate. "
                "Supports lookup by exact workspace_id OR fuzzy client name."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "Client name or workspace ID (supports fuzzy matching)"
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format (optional, overrides 'days')"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format (optional, overrides 'days')"
                    }
                },
                "required": ["workspace_id"]
            }
        ),
        Tool(
            name="get_workspace_info",
            description=(
                "Get detailed workspace information from Instantly API. "
                "Returns workspace name, plan details, domain, timestamps, and other metadata. "
                "Useful for getting the actual workspace name when it's not in the Google Sheet. "
                "Supports lookup by exact workspace_id OR fuzzy client name."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "Client name or workspace ID (supports fuzzy matching)"
                    }
                },
                "required": ["workspace_id"]
            }
        ),
        # Bison tools
        Tool(
            name="get_bison_client_list",
            description=(
                "Get a list of all Bison clients. "
                "Returns client names from the Bison workspace tab. "
                "Use this to see available Bison clients before querying specific data."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_bison_lead_responses",
            description=(
                "Get interested lead responses from Bison for a specific client. "
                "Returns leads marked as 'interested' with their email addresses, reply text, "
                "and timestamps. Supports fuzzy client name matching. "
                "Example: 'ABC Corp', 'XYZ Company', etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "client_name": {
                        "type": "string",
                        "description": "Client name (supports fuzzy matching)"
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (optional, overrides 'days')"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (optional, overrides 'days')"
                    }
                },
                "required": ["client_name"]
            }
        ),
        Tool(
            name="get_bison_campaign_stats",
            description=(
                "Get campaign statistics from Bison for a specific client. "
                "Returns emails sent, opens, replies, interested leads, bounces, and unsubscribes. "
                "Supports fuzzy client name matching."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "client_name": {
                        "type": "string",
                        "description": "Client name (supports fuzzy matching)"
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (optional, overrides 'days')"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (optional, overrides 'days')"
                    }
                },
                "required": ["client_name"]
            }
        ),
        # Unified tools
        Tool(
            name="get_all_clients",
            description=(
                "Get a unified list of ALL clients from both Instantly and Bison platforms. "
                "Shows which platform each client is on. "
                "Use this to see all clients across both platforms at once."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        # Aggregated Analytics tools
        Tool(
            name="get_all_platform_stats",
            description=(
                "Get aggregated statistics from BOTH Instantly and Bison platforms combined. "
                "Shows total emails sent, replies, interested leads, and platform breakdown. "
                "Perfect for seeing overall performance across all clients."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_top_performing_clients",
            description=(
                "Get top performing clients across both platforms ranked by a specific metric. "
                "Supports metrics: interested_leads, emails_sent, replies, reply_rate. "
                "Use this to identify your best performing clients."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Number of top clients to return (default: 10)",
                        "default": 10
                    },
                    "metric": {
                        "type": "string",
                        "description": "Metric to sort by: interested_leads, emails_sent, replies, reply_rate (default: interested_leads)",
                        "default": "interested_leads"
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_underperforming_clients",
            description=(
                "Get clients performing below a threshold across both platforms. "
                "Helps identify clients that need attention or optimization. "
                "Supports same metrics as top_performing_clients."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "description": "Minimum value for the metric - clients below this are underperforming (default: 5)",
                        "default": 5
                    },
                    "metric": {
                        "type": "string",
                        "description": "Metric to check: interested_leads, emails_sent, replies, reply_rate (default: interested_leads)",
                        "default": "interested_leads"
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (default: 7)",
                        "default": 7
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_weekly_summary",
            description=(
                "Generate a comprehensive weekly summary across all clients and both platforms. "
                "Includes overall stats, top 5 performers, underperformers, and key insights. "
                "Perfect for weekly reports and quick status updates."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from Claude."""

    try:
        if name == "get_client_list":
            result = get_client_list()
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_lead_responses":
            workspace_id = arguments.get("workspace_id")
            days = arguments.get("days", 7)
            start_date = arguments.get("start_date")
            end_date = arguments.get("end_date")

            result = get_lead_responses(
                workspace_id=workspace_id,
                days=days,
                start_date=start_date,
                end_date=end_date
            )
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_campaign_stats":
            workspace_id = arguments.get("workspace_id")
            days = arguments.get("days", 7)
            start_date = arguments.get("start_date")
            end_date = arguments.get("end_date")

            result = get_campaign_stats(
                workspace_id=workspace_id,
                days=days,
                start_date=start_date,
                end_date=end_date
            )
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_workspace_info":
            workspace_id = arguments.get("workspace_id")

            result = get_workspace_info(workspace_id=workspace_id)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        # Bison tools
        elif name == "get_bison_client_list":
            result = get_bison_client_list()
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_bison_lead_responses":
            client_name = arguments.get("client_name")
            days = arguments.get("days", 7)
            start_date = arguments.get("start_date")
            end_date = arguments.get("end_date")

            result = get_bison_lead_responses(
                client_name=client_name,
                days=days,
                start_date=start_date,
                end_date=end_date
            )
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_bison_campaign_stats":
            client_name = arguments.get("client_name")
            days = arguments.get("days", 7)
            start_date = arguments.get("start_date")
            end_date = arguments.get("end_date")

            result = get_bison_campaign_stats(
                client_name=client_name,
                days=days,
                start_date=start_date,
                end_date=end_date
            )
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        # Unified tools
        elif name == "get_all_clients":
            result = get_all_clients()
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        # Aggregated Analytics tools
        elif name == "get_all_platform_stats":
            days = arguments.get("days", 7)

            result = get_all_platform_stats(days=days)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_top_performing_clients":
            limit = arguments.get("limit", 10)
            metric = arguments.get("metric", "interested_leads")
            days = arguments.get("days", 7)

            result = get_top_performing_clients(
                limit=limit,
                metric=metric,
                days=days
            )
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_underperforming_clients":
            threshold = arguments.get("threshold", 5)
            metric = arguments.get("metric", "interested_leads")
            days = arguments.get("days", 7)

            result = get_underperforming_clients(
                threshold=threshold,
                metric=metric,
                days=days
            )
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        elif name == "get_weekly_summary":
            result = get_weekly_summary()
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        error_msg = f"Error executing {name}: {str(e)}"
        return [TextContent(
            type="text",
            text=json.dumps({"error": error_msg}, indent=2)
        )]


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
