#!/usr/bin/env python3
"""
MCP Server for Instantly.ai Lead Responses
Exposes tools to query client lead responses and campaign statistics.
"""

import asyncio
import json
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp_functions import get_client_list, get_lead_responses, get_campaign_stats, get_workspace_info

# Create MCP server
server = Server("instantly-leads")


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
