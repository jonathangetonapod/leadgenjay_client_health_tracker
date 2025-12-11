"""
MCP-ready functions that combine Google Sheets + Instantly API.
These will be the tools exposed to Claude via MCP.
"""

import csv
from io import StringIO
import requests
from fetch_interested_leads import fetch_interested_leads
from datetime import datetime, timedelta


# Google Sheet configuration
DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1CNejGg-egkp28ItSRfW7F_CkBXgYevjzstJ1QlrAyAY/edit"
)
SHEET_GID_INSTANTLY = "928115249"  # Instantly workspaces tab


def load_workspaces_from_sheet(sheet_url: str = DEFAULT_SHEET_URL, gid: str = SHEET_GID_INSTANTLY):
    """
    Reads a public/view-only Google Sheet tab as CSV and returns workspace configs.

    Returns:
        [
            {"workspace_id": "ABC Corp", "api_key": "..."},
            {"workspace_id": "XYZ Ltd", "api_key": "..."},
            ...
        ]
    """
    # Normalize URL to the "base" without /edit...
    if "/edit" in sheet_url:
        base = sheet_url.split("/edit", 1)[0]
    else:
        base = sheet_url

    csv_url = f"{base}/export?format=csv&gid={gid}"
    print(f"[Sheets] Fetching workspace list from Google Sheet...")

    resp = requests.get(csv_url, timeout=30)
    resp.raise_for_status()

    text = resp.text
    reader = csv.reader(StringIO(text))
    rows = list(reader)

    workspaces = []
    for idx, row in enumerate(rows):
        if len(row) < 2:
            continue
        raw_wid = (row[0] or "").strip()
        raw_key = (row[1] or "").strip()
        raw_workspace_name = (row[2] or "").strip() if len(row) > 2 else ""  # Column C
        raw_client_name = (row[3] or "").strip() if len(row) > 3 else ""  # Column D

        # Skip empty
        if not raw_wid or not raw_key:
            continue

        # Heuristic to skip header row
        if idx == 0 and (
            "workspace" in raw_wid.lower()
            or "id" in raw_wid.lower()
            or "api" in raw_key.lower()
        ):
            continue

        # Prefer Column D (Client Name) for display, but keep both for searching
        display_name = raw_client_name or raw_workspace_name or raw_wid

        workspaces.append({
            "workspace_id": raw_wid,
            "api_key": raw_key,
            "client_name": display_name,  # For display (Column D > Column C > ID)
            "workspace_name": raw_workspace_name,  # Column C - for search
            "person_name": raw_client_name,  # Column D - for search
        })

    print(f"[Sheets] Loaded {len(workspaces)} workspaces")
    return workspaces


def fetch_workspace_details(api_key: str):
    """
    Fetch workspace details from Instantly API.

    Args:
        api_key: Instantly API key

    Returns:
        {
            "id": "workspace-uuid",
            "name": "My Workspace",
            "owner": "user-uuid",
            "plan_id": "pid_hg_v1",
            "org_logo_url": "https://...",
            "org_client_domain": "example.com",
            ...
        }
    """
    url = "https://api.instantly.ai/api/v2/workspaces/current"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[API] Failed to fetch workspace details: {e}")
        return None


def get_client_list(sheet_url: str = DEFAULT_SHEET_URL, include_details: bool = False):
    """
    MCP Tool: Get list of all available clients/workspaces.

    Args:
        sheet_url: Google Sheet URL (optional)
        include_details: If True, fetches workspace names from API for entries without names

    Returns:
        {
            "total_clients": int,
            "clients": [
                {
                    "workspace_id": "23dbc003-ebe2-4950...",
                    "client_name": "ABC Corp",
                    "workspace_name": "ABC Corp" (if include_details=True),
                    "plan_id": "pid_hg_v1" (if include_details=True)
                },
                ...
            ]
        }
    """
    workspaces = load_workspaces_from_sheet(sheet_url)

    clients = []
    for w in workspaces:
        client_entry = {
            "workspace_id": w["workspace_id"],
            "client_name": w["client_name"]
        }

        # If include_details is True and client_name is same as workspace_id,
        # fetch the actual workspace name from API
        if include_details and w["client_name"] == w["workspace_id"]:
            print(f"[API] Fetching details for {w['workspace_id'][:8]}...")
            details = fetch_workspace_details(w["api_key"])
            if details:
                client_entry["workspace_name"] = details.get("name", w["workspace_id"])
                client_entry["plan_id"] = details.get("plan_id")
                client_entry["org_domain"] = details.get("org_client_domain")
            else:
                client_entry["workspace_name"] = w["workspace_id"]

        clients.append(client_entry)

    return {
        "total_clients": len(clients),
        "clients": clients
    }


def get_lead_responses(
    workspace_id: str,
    start_date: str = None,
    end_date: str = None,
    days: int = 7,
    sheet_url: str = DEFAULT_SHEET_URL
):
    """
    MCP Tool: Get positive lead responses for a specific client/workspace.

    Args:
        workspace_id: Client name or workspace ID (e.g., "ABC Corp")
        start_date: Start date in ISO format (optional if using 'days')
        end_date: End date in ISO format (optional if using 'days')
        days: Number of days to look back (default: 7)
        sheet_url: Google Sheet URL (optional)

    Returns:
        {
            "workspace_id": str,
            "start_date": str,
            "end_date": str,
            "total_leads": int,
            "leads": [
                {
                    "email": str,
                    "reply_summary": str,
                    "subject": str,
                    "timestamp": str
                }
            ]
        }
    """
    # Load workspaces from sheet
    workspaces = load_workspaces_from_sheet(sheet_url)

    # Find the workspace by ID or name
    # Try exact match on workspace_id first
    workspace = None
    search_term = workspace_id.lower()

    # 1. Try exact workspace_id match
    for w in workspaces:
        if w["workspace_id"].lower() == search_term:
            workspace = w
            break

    # 2. Try fuzzy match on client_name, workspace_name, or person_name
    if not workspace:
        matches = []
        for w in workspaces:
            # Search in client_name (display), workspace_name (Column C), and person_name (Column D)
            if (search_term in w["client_name"].lower() or
                search_term in w.get("workspace_name", "").lower() or
                search_term in w.get("person_name", "").lower()):
                matches.append(w)

        if len(matches) == 1:
            workspace = matches[0]
        elif len(matches) > 1:
            match_list = [f"{w['client_name']} ({w['workspace_id']})" for w in matches]
            raise ValueError(
                f"Multiple matches found for '{workspace_id}':\n" +
                "\n".join(f"  - {m}" for m in match_list) +
                "\n\nPlease use the exact workspace_id or be more specific."
            )

    # 3. Try fuzzy match on workspace_id
    if not workspace:
        for w in workspaces:
            if search_term in w["workspace_id"].lower():
                workspace = w
                break

    if not workspace:
        # Show first 10 available clients
        available = [f"{w['client_name']} ({w['workspace_id'][:8]}...)" for w in workspaces[:10]]
        available_str = '\n'.join(f"  - {a}" for a in available)
        raise ValueError(
            f"Workspace '{workspace_id}' not found.\n\n"
            f"Available clients (showing first 10):\n{available_str}\n\n"
            f"Use get_client_list() to see all {len(workspaces)} clients."
        )

    print(f"[MCP] Found workspace: {workspace['workspace_id']}")

    # Handle date range
    if not start_date or not end_date:
        end = datetime.now()
        start = end - timedelta(days=days)
        start_date = start.strftime("%Y-%m-%dT00:00:00Z")
        end_date = end.strftime("%Y-%m-%dT23:59:59Z")

    # Fetch interested leads
    results = fetch_interested_leads(
        api_key=workspace["api_key"],
        start_date=start_date,
        end_date=end_date
    )

    return {
        "workspace_id": workspace["workspace_id"],
        "start_date": start_date,
        "end_date": end_date,
        "total_leads": results["total_count"],
        "leads": results["leads"]
    }


def get_campaign_stats(
    workspace_id: str,
    start_date: str = None,
    end_date: str = None,
    days: int = 7,
    sheet_url: str = DEFAULT_SHEET_URL
):
    """
    MCP Tool: Get campaign statistics for a specific client/workspace.

    Uses the existing analytics endpoint from app.py.

    Args:
        workspace_id: Client name or workspace ID
        start_date: Start date in ISO format (optional)
        end_date: End date in ISO format (optional)
        days: Number of days to look back (default: 7)
        sheet_url: Google Sheet URL (optional)

    Returns:
        {
            "workspace_id": str,
            "start_date": str,
            "end_date": str,
            "emails_sent": int,
            "replies": int,
            "opportunities": int,
            "reply_rate": float
        }
    """
    # Load workspaces
    workspaces = load_workspaces_from_sheet(sheet_url)

    # Find the workspace by ID or name (same logic as get_lead_responses)
    workspace = None
    search_term = workspace_id.lower()

    # 1. Try exact workspace_id match
    for w in workspaces:
        if w["workspace_id"].lower() == search_term:
            workspace = w
            break

    # 2. Try fuzzy match on client_name, workspace_name, or person_name
    if not workspace:
        matches = []
        for w in workspaces:
            # Search in client_name (display), workspace_name (Column C), and person_name (Column D)
            if (search_term in w["client_name"].lower() or
                search_term in w.get("workspace_name", "").lower() or
                search_term in w.get("person_name", "").lower()):
                matches.append(w)

        if len(matches) == 1:
            workspace = matches[0]
        elif len(matches) > 1:
            match_list = [f"{w['client_name']} ({w['workspace_id']})" for w in matches]
            raise ValueError(
                f"Multiple matches found for '{workspace_id}':\n" +
                "\n".join(f"  - {m}" for m in match_list) +
                "\n\nPlease use the exact workspace_id or be more specific."
            )

    # 3. Try fuzzy match on workspace_id
    if not workspace:
        for w in workspaces:
            if search_term in w["workspace_id"].lower():
                workspace = w
                break

    if not workspace:
        # Show first 10 available clients
        available = [f"{w['client_name']} ({w['workspace_id'][:8]}...)" for w in workspaces[:10]]
        available_str = '\n'.join(f"  - {a}" for a in available)
        raise ValueError(
            f"Workspace '{workspace_id}' not found.\n\n"
            f"Available clients (showing first 10):\n{available_str}\n\n"
            f"Use get_client_list() to see all {len(workspaces)} clients."
        )

    # Handle date range
    if not start_date or not end_date:
        end = datetime.now()
        start = end - timedelta(days=days)
        start_date = start.strftime("%Y-%m-%d")
        end_date = end.strftime("%Y-%m-%d")

    # Call Instantly analytics API
    url = "https://api.instantly.ai/api/v2/campaigns/analytics/overview"
    headers = {"Authorization": f"Bearer {workspace['api_key']}"}
    params = {
        "start_date": start_date,
        "end_date": end_date
    }

    print(f"[MCP] Fetching campaign stats for {workspace['workspace_id']}...")

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()

    return {
        "workspace_id": workspace["workspace_id"],
        "start_date": start_date,
        "end_date": end_date,
        "emails_sent": data.get("emails_sent_count", 0),
        "replies": data.get("reply_count_unique", 0),
        "opportunities": data.get("total_opportunities", 0),
        "reply_rate": data.get("reply_rate", 0)
    }


def get_workspace_info(
    workspace_id: str,
    sheet_url: str = DEFAULT_SHEET_URL
):
    """
    MCP Tool: Get detailed workspace information from Instantly API.

    Args:
        workspace_id: Client name or workspace ID
        sheet_url: Google Sheet URL (optional)

    Returns:
        {
            "workspace_id": str,
            "workspace_name": str,
            "owner": str,
            "plan_id": str,
            "org_logo_url": str,
            "org_client_domain": str,
            "plan_id_crm": str,
            "timestamp_created": str,
            "timestamp_updated": str
        }
    """
    # Load workspaces
    workspaces = load_workspaces_from_sheet(sheet_url)

    # Find the workspace (same lookup logic as other functions)
    workspace = None
    search_term = workspace_id.lower()

    # 1. Try exact workspace_id match
    for w in workspaces:
        if w["workspace_id"].lower() == search_term:
            workspace = w
            break

    # 2. Try fuzzy match on client_name, workspace_name, or person_name
    if not workspace:
        matches = []
        for w in workspaces:
            # Search in client_name (display), workspace_name (Column C), and person_name (Column D)
            if (search_term in w["client_name"].lower() or
                search_term in w.get("workspace_name", "").lower() or
                search_term in w.get("person_name", "").lower()):
                matches.append(w)

        if len(matches) == 1:
            workspace = matches[0]
        elif len(matches) > 1:
            match_list = [f"{w['client_name']} ({w['workspace_id']})" for w in matches]
            raise ValueError(
                f"Multiple matches found for '{workspace_id}':\n" +
                "\n".join(f"  - {m}" for m in match_list) +
                "\n\nPlease use the exact workspace_id or be more specific."
            )

    # 3. Try fuzzy match on workspace_id
    if not workspace:
        for w in workspaces:
            if search_term in w["workspace_id"].lower():
                workspace = w
                break

    if not workspace:
        raise ValueError(f"Workspace '{workspace_id}' not found.")

    print(f"[MCP] Fetching workspace info for {workspace['workspace_id']}...")

    # Fetch workspace details from API
    details = fetch_workspace_details(workspace["api_key"])

    if not details:
        raise ValueError(f"Failed to fetch workspace details for {workspace_id}")

    return {
        "workspace_id": details.get("id", workspace["workspace_id"]),
        "workspace_name": details.get("name"),
        "owner": details.get("owner"),
        "plan_id": details.get("plan_id"),
        "org_logo_url": details.get("org_logo_url"),
        "org_client_domain": details.get("org_client_domain"),
        "plan_id_crm": details.get("plan_id_crm"),
        "plan_id_leadfinder": details.get("plan_id_leadfinder"),
        "plan_id_verification": details.get("plan_id_verification"),
        "plan_id_website_visitor": details.get("plan_id_website_visitor"),
        "plan_id_inbox_placement": details.get("plan_id_inbox_placement"),
        "timestamp_created": details.get("timestamp_created"),
        "timestamp_updated": details.get("timestamp_updated"),
        "default_opportunity_value": details.get("default_opportunity_value")
    }


# Test the functions
if __name__ == "__main__":
    print("="*80)
    print("TESTING MCP FUNCTIONS")
    print("="*80)

    # Test 1: Get client list
    print("\n1. Getting client list...")
    try:
        clients = get_client_list()
        print(f"✅ Found {clients['total_clients']} clients:")
        for c in clients['clients'][:5]:
            print(f"   - {c['workspace_id']}")
        if clients['total_clients'] > 5:
            print(f"   ... and {clients['total_clients'] - 5} more")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 2: Get lead responses for first client
    if clients['clients']:
        print(f"\n2. Getting lead responses for first client...")
        first_client = clients['clients'][0]['workspace_id']
        try:
            leads = get_lead_responses(first_client, days=30)
            print(f"✅ {first_client}: {leads['total_leads']} interested leads")
            if leads['leads']:
                print(f"   Sample: {leads['leads'][0]['email']}")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Test 3: Get campaign stats
        print(f"\n3. Getting campaign stats for first client...")
        try:
            stats = get_campaign_stats(first_client, days=30)
            print(f"✅ {stats['workspace_id']}:")
            print(f"   - Emails sent: {stats['emails_sent']:,}")
            print(f"   - Replies: {stats['replies']}")
            print(f"   - Opportunities: {stats['opportunities']}")
        except Exception as e:
            print(f"❌ Error: {e}")
