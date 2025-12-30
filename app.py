import os
import csv
from io import StringIO
from datetime import date
import traceback
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

# Optional default token for local single-workspace testing
INSTANTLY_API_KEY = os.getenv("INSTANTLY_API_KEY")

INSTANTLY_OVERVIEW_URL = "https://api.instantly.ai/api/v2/campaigns/analytics/overview"
INSTANTLY_WORKSPACE_URL = "https://api.instantly.ai/api/v2/workspaces/current"
INSTANTLY_ACCOUNTS_URL = "https://api.instantly.ai/api/v2/accounts"

# Campaign statuses to scan
CAMPAIGN_STATUSES = [0, 1, 2, 3, 4, -99, -1, -2]

# Email Bison API configuration
EMAIL_BISON_BASE_URL = "https://send.leadgenjay.com"
EMAIL_BISON_CAMPAIGNS_URL = f"{EMAIL_BISON_BASE_URL}/api/campaigns"
EMAIL_BISON_STATS_URL = f"{EMAIL_BISON_BASE_URL}/api/campaigns"  # append /{id}/stats
EMAIL_BISON_ACCOUNTS_URL = f"{EMAIL_BISON_BASE_URL}/api/sender-emails"

# Default sheet + tab (gid) – can be overridden by sheet_url query param
DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1CNejGg-egkp28ItSRfW7F_CkBXgYevjzstJ1QlrAyAY/edit"
)
SHEET_GID_INSTANTLY = "928115249"  # Instantly workspaces tab
SHEET_GID_EMAILBISON = "1631680229"  # Email Bison accounts tab

# Health scoring thresholds
MIN_EMAILS_FOR_HEALTH = 2000

# Rate limiting configuration
# Instantly limits: 100 req/10s and 600 req/min (both = 10 req/sec max)
MAX_WORKERS = 8  # Increased for better parallelization while staying under rate limits
REQUEST_DELAY = 0.1  # Small delay between API requests (in make_api_request_with_retry)
MAX_RETRIES = 3  # Maximum retry attempts for 429 errors
RETRY_DELAY = 2  # Initial retry delay in seconds (exponential backoff)

# Workspace name cache to reduce API calls
workspace_cache = {}

HEALTH_RULES = [
    {
        "key": "healthy",
        "label": "🟢 Healthy",
        "description": (
            "At least 1 opportunity in the selected date range and "
            f"{MIN_EMAILS_FOR_HEALTH:,}+ emails sent."
        ),
    },
    {
        "key": "at_risk",
        "label": "🔴 At Risk",
        "description": (
            f"{MIN_EMAILS_FOR_HEALTH:,}+ emails sent in the selected date range "
            "and 0 opportunities. This needs attention."
        ),
    },
    {
        "key": "early",
        "label": "🟡 Early",
        "description": (
            f"Fewer than {MIN_EMAILS_FOR_HEALTH:,} emails sent in the selected "
            "date range. Still warming up / not enough data yet."
        ),
    },
]


def classify_health(emails_sent: int, opportunities: int) -> str:
    """
    Simple health score:
      - 'early'   → emails_sent < MIN_EMAILS_FOR_HEALTH
      - 'at_risk' → emails_sent >= MIN_EMAILS_FOR_HEALTH and opportunities == 0
      - 'healthy' → everything else
    """
    if emails_sent < MIN_EMAILS_FOR_HEALTH:
        return "early"
    if emails_sent >= MIN_EMAILS_FOR_HEALTH and opportunities == 0:
        return "at_risk"
    return "healthy"


app = Flask(__name__)


def load_workspaces_from_sheet(sheet_url: str, gid: str = SHEET_GID_INSTANTLY) -> list[dict]:
    """
    Reads a public/view-only Google Sheet tab as CSV and returns:
      [
        {"workspace_id": "...", "api_key": "..."},
        ...
      ]

    Assumes:
      - Column A: workspace ID
      - Column B: API key
      - Optional header row (we try to skip it).
    """
    # Normalize URL to the “base” without /edit...
    if "/edit" in sheet_url:
        base = sheet_url.split("/edit", 1)[0]
    else:
        base = sheet_url

    csv_url = f"{base}/export?format=csv&gid={gid}"
    print(f"[Sheets] Fetching CSV from: {csv_url}")

    resp = requests.get(csv_url, timeout=30)
    resp.raise_for_status()

    text = resp.text
    reader = csv.reader(StringIO(text))
    rows = list(reader)

    workspaces: list[dict] = []
    for idx, row in enumerate(rows):
        if len(row) < 2:
            continue
        raw_wid = (row[0] or "").strip()
        raw_key = (row[1] or "").strip()

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

        workspaces.append(
            {
                "workspace_id": raw_wid,
                "api_key": raw_key,
            }
        )

    print(f"[Sheets] Loaded {len(workspaces)} workspaces from sheet (gid={gid})")
    return workspaces


def make_api_request_with_retry(url: str, headers: dict, timeout: int = 30) -> requests.Response:
    """
    Make an API request with exponential backoff retry logic for 429 errors.

    Args:
        url: The API endpoint URL
        headers: Request headers
        timeout: Request timeout in seconds

    Returns:
        Response object if successful

    Raises:
        requests.exceptions.HTTPError: If all retries fail or non-429 error occurs
    """
    # Small delay before each request to help with rate limiting
    time.sleep(REQUEST_DELAY)

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)

            # If rate limited (429), retry with exponential backoff
            if resp.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    print(f"[API] Rate limited (429), retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[API] Rate limited (429), max retries exceeded")
                    resp.raise_for_status()

            # For other errors or success, return immediately
            return resp

        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt)
                print(f"[API] Request failed: {e}, retrying in {delay}s")
                time.sleep(delay)
            else:
                raise

    # This shouldn't be reached, but just in case
    raise requests.exceptions.HTTPError("Max retries exceeded")


def fetch_workspace_info(api_key: str) -> dict:
    """
    Calls Instantly /workspaces/current using given API key with retry logic and caching.
    """
    # Check cache first
    if api_key in workspace_cache:
        return workspace_cache[api_key]

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    resp = make_api_request_with_retry(INSTANTLY_WORKSPACE_URL, headers, timeout=30)

    if not resp.ok:
        print(
            "[Instantly] error in /workspaces/current:",
            resp.status_code,
            resp.text,
        )
        resp.raise_for_status()

    data = resp.json()
    result = {
        "workspace_id": data.get("id"),
        "workspace_name": data.get("name"),
    }

    # Cache the result
    workspace_cache[api_key] = result

    return result


def fetch_single_status(
    status: int,
    start_date: str,
    end_date: str,
    headers: dict,
    workspace_label: str | None = None,
) -> tuple[int, dict | None]:
    """
    Fetches analytics for a single campaign status.
    Returns (status, data) tuple. data is None if request failed.
    """
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "campaign_status": status,
    }

    try:
        resp = requests.get(
            INSTANTLY_OVERVIEW_URL,
            headers=headers,
            params=params,
            timeout=30,
        )

        # 400/404 = no campaigns / bad filter → just skip this status
        if resp.status_code in (400, 404):
            print(
                f"[Instantly] {workspace_label or ''} "
                f"status {status}: {resp.status_code} (no campaigns / bad filter)"
            )
            return (status, None)

        # 5xx or 429 = Instantly side issue or rate limit → log + skip
        if resp.status_code >= 500 or resp.status_code == 429:
            print(
                f"[Instantly] {workspace_label or ''} "
                f"status {status}: server error {resp.status_code}, skipping. "
                f"Body: {resp.text}"
            )
            return (status, None)

        # Any other non-OK → treat as real error so we can fix it
        if not resp.ok:
            print(
                f"[Instantly] error for {workspace_label or ''} "
                f"campaign_status={status}: {resp.status_code} {resp.text}"
            )
            resp.raise_for_status()

        data = resp.json()
        return (status, data)
    except Exception as e:
        print(f"[Instantly] Exception fetching status {status} for {workspace_label}: {e}")
        return (status, None)


def aggregate_overview_for_workspace(
    start_date: str,
    end_date: str,
    api_key: str | None = None,
    workspace_label: str | None = None,
) -> dict:
    """
    Loops over all CAMPAIGN_STATUSES, calls Instantly overview for each IN PARALLEL,
    and builds a combined dict by taking the MAX of each numeric metric
    across statuses (not a sum).

    This matches how the Instantly UI shows workspace-level totals like
    "Total sent" for a date range.
    """
    token = api_key or INSTANTLY_API_KEY
    if not token:
        raise RuntimeError("INSTANTLY_API_KEY is not set and no api_key was provided")

    headers = {
        "Authorization": f"Bearer {token}",
    }

    combined_max: dict[str, float] = {}
    by_status: dict[int, dict] = {}

    # Parallelize the 8 status calls
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Submit all status calls
        futures = {
            executor.submit(
                fetch_single_status,
                status,
                start_date,
                end_date,
                headers,
                workspace_label,
            ): status
            for status in CAMPAIGN_STATUSES
        }

        # Collect results as they complete
        for future in as_completed(futures):
            status, data = future.result()

            if data is None:
                continue

            by_status[status] = data

            # Update per-metric max across statuses
            for key, value in data.items():
                if not isinstance(value, (int, float)):
                    continue

                current = combined_max.get(key)
                if current is None or value > current:
                    combined_max[key] = float(value)

    # Cast floats -> ints for cleaner JSON
    combined_ints = {k: int(v) for k, v in combined_max.items()}

    return {
        "combined": combined_ints,
        "by_status": by_status,
    }


# ========== EMAIL BISON FUNCTIONS ==========

def fetch_emailbison_campaigns(api_key: str) -> list[dict]:
    """
    Fetches all campaigns for an Email Bison account.
    Returns a list of campaign objects.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.get(
            EMAIL_BISON_CAMPAIGNS_URL,
            headers=headers,
            timeout=30,
        )

        if not resp.ok:
            print(
                f"[EmailBison] error fetching campaigns: {resp.status_code} {resp.text}"
            )
            resp.raise_for_status()

        data = resp.json()
        campaigns = data.get("data", [])
        print(f"[EmailBison] Found {len(campaigns)} campaigns")
        return campaigns
    except Exception as e:
        print(f"[EmailBison] Exception fetching campaigns: {e}")
        return []


def fetch_emailbison_campaign_stats(
    campaign_id: int,
    api_key: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Fetches stats for a single Email Bison campaign with date range.
    Returns stats dict. All values are strings from the API.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    url = f"{EMAIL_BISON_STATS_URL}/{campaign_id}/stats"
    payload = {
        "start_date": start_date,
        "end_date": end_date,
    }

    try:
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if not resp.ok:
            print(
                f"[EmailBison] error fetching stats for campaign {campaign_id}: "
                f"{resp.status_code} {resp.text}"
            )
            return {}

        data = resp.json()
        return data.get("data", {})
    except Exception as e:
        print(f"[EmailBison] Exception fetching stats for campaign {campaign_id}: {e}")
        return {}


def aggregate_emailbison_account(
    api_key: str,
    start_date: str,
    end_date: str,
    account_label: str = None,
) -> dict:
    """
    Fetches all campaigns for an Email Bison account and aggregates stats.
    Returns combined stats by SUMMING across all campaigns.
    """
    # Get all campaigns
    campaigns = fetch_emailbison_campaigns(api_key)

    if not campaigns:
        print(f"[EmailBison] No campaigns found for {account_label}")
        return {
            "emails_sent": 0,
            "replies": 0,
            "opportunities": 0,
        }

    # Fetch stats for all campaigns in parallel
    totals = {
        "emails_sent": 0,
        "replies": 0,
        "opportunities": 0,
    }

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                fetch_emailbison_campaign_stats,
                campaign["id"],
                api_key,
                start_date,
                end_date,
            ): campaign
            for campaign in campaigns
        }

        for future in as_completed(futures):
            campaign = futures[future]
            stats = future.result()

            if not stats:
                continue

            # Convert string values to integers and sum
            emails_sent = int(stats.get("emails_sent", "0"))
            replies = int(stats.get("unique_replies_per_contact", "0"))
            opportunities = int(stats.get("interested", "0"))

            totals["emails_sent"] += emails_sent
            totals["replies"] += replies
            totals["opportunities"] += opportunities

            print(
                f"[EmailBison] Campaign '{campaign.get('name')}' (ID {campaign['id']}): "
                f"sent={emails_sent} replies={replies} opps={opportunities}"
            )

    print(
        f"[EmailBison] {account_label} TOTAL: "
        f"sent={totals['emails_sent']} replies={totals['replies']} opps={totals['opportunities']}"
    )

    return totals


def process_single_emailbison_account(
    row: dict,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Processes a single Email Bison account: fetches all campaigns and aggregates stats.
    Returns a dict with all the account data.
    """
    api_key = row["api_key"]
    label = row.get("workspace_id", "Unknown Account")

    # For Email Bison, we don't have a separate "workspace name" endpoint
    # So we just use the label from the sheet
    account_name = label

    # Aggregate stats across all campaigns
    stats = aggregate_emailbison_account(
        api_key=api_key,
        start_date=start_date,
        end_date=end_date,
        account_label=account_name,
    )

    emails_sent = stats["emails_sent"]
    replies = stats["replies"]
    opportunities = stats["opportunities"]

    health = classify_health(emails_sent, opportunities)

    print(
        f"[EmailBison] account={account_name} | "
        f"{start_date} -> {end_date} | "
        f"sent={emails_sent} replies={replies} opps={opportunities} "
        f"status={health}"
    )

    summary = {
        "emails_sent": emails_sent,
        "replies": replies,
        "opportunities": opportunities,
        "health": health,
    }

    return {
        "workspace_id": label,
        "workspace_name": account_name,
        "label": label,
        "start_date": start_date,
        "end_date": end_date,
        "combined": stats,
        "summary": summary,
        "health": health,
    }


# ========== INSTANTLY FUNCTIONS ==========

def process_single_workspace(
    row: dict,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Processes a single workspace: fetches info and analytics.
    Returns a dict with all the workspace data.
    """
    api_key = row["api_key"]
    label = row["workspace_id"]

    workspace_name = None
    workspace_id = label

    # Try to get workspace name with this API key
    try:
        info = fetch_workspace_info(api_key)
        workspace_name = info.get("workspace_name") or label
        workspace_id = info.get("workspace_id") or label
    except Exception as e:
        print(f"[Instantly] error fetching workspace info for {label}:", e)
        workspace_name = label

    # Pull overview for this workspace
    overview = aggregate_overview_for_workspace(
        start_date=start_date,
        end_date=end_date,
        api_key=api_key,
        workspace_label=workspace_name,
    )
    combined = overview["combined"]

    emails_sent = combined.get("emails_sent_count", 0)
    opportunities = combined.get("total_opportunities", 0)
    replies = combined.get("reply_count_unique", 0)

    health = classify_health(emails_sent, opportunities)

    print(
        f"[Instantly] workspace={workspace_name} | "
        f"{start_date} -> {end_date} | "
        f"sent={emails_sent} replies={replies} opps={opportunities} "
        f"status={health}"
    )

    summary = {
        "emails_sent": emails_sent,
        "replies": replies,
        "opportunities": opportunities,
        "health": health,
    }

    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "label": label,
        "start_date": start_date,
        "end_date": end_date,
        "combined": combined,
        "summary": summary,
        "health": health,
    }


def fetch_instantly_accounts(api_key: str, limit: int = 100) -> list[dict]:
    """
    Fetches email accounts from Instantly for a workspace with retry logic.
    Returns a list of account objects.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    all_accounts = []
    starting_after = None

    try:
        # Fetch accounts with pagination
        while True:
            params = {"limit": limit}
            if starting_after:
                params["starting_after"] = starting_after

            # Build URL with params
            url = INSTANTLY_ACCOUNTS_URL
            if params:
                param_str = "&".join([f"{k}={v}" for k, v in params.items()])
                url = f"{url}?{param_str}"

            resp = make_api_request_with_retry(url, headers, timeout=30)

            if not resp.ok:
                print(
                    f"[Instantly] error fetching accounts: {resp.status_code} {resp.text}"
                )
                resp.raise_for_status()

            data = resp.json()
            items = data.get("items", [])
            all_accounts.extend(items)

            # Check if there are more pages
            starting_after = data.get("next_starting_after")
            if not starting_after:
                break

        print(f"[Instantly] Found {len(all_accounts)} email accounts")
        return all_accounts
    except Exception as e:
        print(f"[Instantly] Exception fetching accounts: {e}")
        return []


def process_instantly_accounts(
    row: dict,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Processes email accounts for an Instantly workspace.
    Returns account data with health status.
    """
    api_key = row["api_key"]
    label = row["workspace_id"]

    workspace_name = None
    workspace_id = label

    # Try to get workspace name
    try:
        info = fetch_workspace_info(api_key)
        workspace_name = info.get("workspace_name") or label
        workspace_id = info.get("workspace_id") or label
    except Exception as e:
        print(f"[Instantly] error fetching workspace info for {label}:", e)
        workspace_name = label

    # Fetch all email accounts
    accounts = fetch_instantly_accounts(api_key)

    # Map status codes to readable names
    def get_status_name(status_code):
        status_map = {
            1: "Active",
            2: "Paused",
            -1: "Connection Error",
            -2: "Soft Bounce Error",
            -3: "Sending Error",
        }
        return status_map.get(status_code, f"Unknown ({status_code})")

    # Map warmup status
    def get_warmup_status_name(warmup_status):
        if warmup_status == 1:
            return "Active"
        elif warmup_status == 0:
            return "Inactive"
        else:
            return f"Unknown ({warmup_status})"

    # Map provider codes to provider names
    def get_provider_name(provider_code):
        provider_map = {
            1: "Custom IMAP/SMTP",
            2: "Google",
            3: "Microsoft",
            4: "AWS",
        }
        return provider_map.get(provider_code, f"Unknown ({provider_code})")

    # Process accounts into display format
    processed_accounts = []
    status_breakdown = {}
    status_code_breakdown = {}

    for account in accounts:
        status = account.get("status")
        warmup_status = account.get("warmup_status")
        warmup_score = account.get("stat_warmup_score", 0)

        # Track status breakdown for debugging
        status_name = get_status_name(status)
        status_breakdown[status_name] = status_breakdown.get(status_name, 0) + 1

        # Track raw status codes too
        status_code_breakdown[f"code_{status}"] = status_code_breakdown.get(f"code_{status}", 0) + 1

        # Determine health based on status
        if status == 1:  # Active
            health = "healthy"
        elif status == 2:  # Paused
            health = "early"
        elif status in [-1, -2, -3]:  # Any error status (Connection, Soft Bounce, Sending)
            health = "at_risk"
        else:  # Unknown status
            health = "at_risk"

        display_status = get_status_name(status)

        provider_code = account.get("provider_code")

        processed_accounts.append({
            "email": account.get("email", "Unknown"),
            "status": display_status,
            "status_code": status,
            "daily_limit": account.get("daily_limit", 0),
            "warmup_status": get_warmup_status_name(warmup_status),
            "warmup_score": account.get("stat_warmup_score", 0),
            "last_used": account.get("timestamp_last_used", "Never"),
            "health": health,
            "provider_code": provider_code,
            "provider_name": get_provider_name(provider_code),
        })

    print(
        f"[Instantly] workspace={workspace_name} | "
        f"Processed {len(processed_accounts)} email accounts | "
        f"Status breakdown: {status_breakdown} | "
        f"Raw codes: {status_code_breakdown}"
    )

    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "label": label,
        "start_date": start_date,
        "end_date": end_date,
        "accounts": processed_accounts,
        "total_accounts": len(processed_accounts),
    }


def fetch_emailbison_accounts(api_key: str) -> list[dict]:
    """
    Fetches email accounts from Email Bison for a workspace.
    Returns a list of sender email account objects.
    Handles pagination automatically.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    all_accounts = []
    page = 1

    try:
        while True:
            params = {"page": page}

            resp = requests.get(
                EMAIL_BISON_ACCOUNTS_URL,
                headers=headers,
                params=params,
                timeout=30,
            )

            if not resp.ok:
                print(
                    f"[Email Bison] error fetching accounts (page {page}): {resp.status_code} {resp.text}"
                )
                resp.raise_for_status()

            data = resp.json()
            accounts = data.get("data", [])
            all_accounts.extend(accounts)

            # Check if there are more pages
            # Laravel pagination typically includes 'meta' or 'links'
            meta = data.get("meta", {})
            links = data.get("links", {})

            current_page = meta.get("current_page", page)
            last_page = meta.get("last_page", 1)
            next_url = links.get("next")

            print(f"[Email Bison] Fetched page {current_page}/{last_page} ({len(accounts)} accounts)")

            # Break if no more pages
            if not next_url or current_page >= last_page:
                break

            page += 1

        print(f"[Email Bison] Found total of {len(all_accounts)} email accounts across {page} page(s)")
        return all_accounts
    except Exception as e:
        print(f"[Email Bison] Exception fetching accounts: {e}")
        return all_accounts if all_accounts else []


def process_emailbison_accounts(
    row: dict,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Processes email accounts for an Email Bison workspace.
    Returns account data with health status.
    """
    api_key = row["api_key"]
    label = row["workspace_id"]

    workspace_name = label
    workspace_id = label

    # Fetch all email accounts
    accounts = fetch_emailbison_accounts(api_key)

    # Process accounts into display format
    processed_accounts = []
    status_breakdown = {}

    for account in accounts:
        status = account.get("status", "Unknown")

        # Track status breakdown for debugging
        status_breakdown[status] = status_breakdown.get(status, 0) + 1

        # Determine health based on status
        # Email Bison uses string statuses like "Connected", "Disconnected", etc.
        if status == "Connected":
            health = "healthy"
        else:
            health = "at_risk"

        # Extract tags
        tags = account.get("tags", [])
        tag_names = [tag.get("name") for tag in tags if tag.get("name")]

        processed_accounts.append({
            "email": account.get("email", "Unknown"),
            "name": account.get("name", ""),
            "status": status,
            "daily_limit": account.get("daily_limit", 0),
            "emails_sent_count": account.get("emails_sent_count", 0),
            "total_replied_count": account.get("total_replied_count", 0),
            "unique_replied_count": account.get("unique_replied_count", 0),
            "total_opened_count": account.get("total_opened_count", 0),
            "bounced_count": account.get("bounced_count", 0),
            "interested_leads_count": account.get("interested_leads_count", 0),
            "health": health,
            "tags": tag_names,
            "type": account.get("type", ""),
        })

    print(
        f"[Email Bison] workspace={workspace_name} | "
        f"Processed {len(processed_accounts)} email accounts | "
        f"Status breakdown: {status_breakdown}"
    )

    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "label": label,
        "start_date": start_date,
        "end_date": end_date,
        "accounts": processed_accounts,
        "total_accounts": len(processed_accounts),
    }


@app.get("/multi-overview")
def multi_overview():
    """
    GET /multi-overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&sheet_url=...&platform=instantly|emailbison

    Uses a Google Sheet (with workspace_id + api_key) to:
      - Loop through all workspaces IN PARALLEL
      - Pull analytics for the date range (Instantly or Email Bison)
      - Compute per-workspace summary + health status
      - Return a JSON with:
          - totals across all
          - per-workspace rows
          - workspace_count
          - health_rules (for frontend legend)
    """
    try:
        today = date.today()
        default_start = date(today.year, 1, 1).isoformat()
        default_end = today.isoformat()

        start_date = request.args.get("start_date", default_start)
        end_date = request.args.get("end_date", default_end)
        platform = request.args.get("platform", "instantly")
        view = request.args.get("view", "campaign_health")

        sheet_url = request.args.get("sheet_url", DEFAULT_SHEET_URL)

        # Select the correct sheet GID and process function based on platform and view
        if platform == "emailbison":
            sheet_gid = SHEET_GID_EMAILBISON
            if view == "email_accounts":
                process_func = process_emailbison_accounts
            else:
                process_func = process_single_emailbison_account
            platform_name = "Email Bison"
        else:  # Instantly
            sheet_gid = SHEET_GID_INSTANTLY
            if view == "email_accounts":
                process_func = process_instantly_accounts
            else:
                process_func = process_single_workspace
            platform_name = "Instantly"

        print(f"[{platform_name}] Loading workspaces from sheet with gid={sheet_gid}")

        # 1) Load workspaces from sheet
        workspaces = load_workspaces_from_sheet(sheet_url, sheet_gid)

        results = []
        totals = {
            "emails_sent": 0,
            "replies": 0,
            "opportunities": 0,
        }

        # 2) Process all workspaces in parallel with rate limiting
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all workspace processing tasks
            futures = {
                executor.submit(
                    process_func,
                    row,
                    start_date,
                    end_date,
                ): row
                for row in workspaces
            }

            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    workspace_result = future.result()
                    results.append(workspace_result)

                    # Update totals (only for campaign_health view)
                    if view == "campaign_health" and "summary" in workspace_result:
                        summary = workspace_result["summary"]
                        totals["emails_sent"] += summary["emails_sent"]
                        totals["replies"] += summary["replies"]
                        totals["opportunities"] += summary["opportunities"]
                except Exception as e:
                    row = futures[future]
                    print(f"[{platform_name}] Error processing workspace {row['workspace_id']}: {e}")
                    traceback.print_exc()

        return jsonify(
            {
                "sheet_url": sheet_url,
                "start_date": start_date,
                "end_date": end_date,
                "platform": platform,
                "view": view,
                "workspace_count": len(workspaces),
                "totals": totals,
                "workspaces": results,
                "health_rules": HEALTH_RULES,
            }
        )
    except Exception as e:
        print("Error in /multi-overview:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.post("/send-webhook")
def send_webhook():
    """
    POST /send-webhook
    Body:
      {
        "webhook_url": "https://...",
        "workspace": {
          "workspace_id": "...",
          "workspace_name": "...",
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD",
          "emails_sent": 1234,
          "replies": 12,
          "opportunities": 3,
          "health": "at_risk"
        }
      }
    """
    try:
        payload = request.get_json(force=True) or {}
        webhook_url = (payload.get("webhook_url") or "").strip()
        workspace = payload.get("workspace") or {}

        if not webhook_url:
            return jsonify({"success": False, "error": "Missing webhook_url"}), 400

        # You can customize/transform the payload here if needed
        print(f"[Webhook] Sending workspace to {webhook_url}: {workspace}")

        resp = requests.post(webhook_url, json=workspace, timeout=15)

        if not resp.ok:
            print(
                "[Webhook] Error:",
                resp.status_code,
                resp.text,
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "status_code": resp.status_code,
                        "error": resp.text,
                    }
                ),
                502,
            )

        return jsonify({"success": True})
    except Exception as e:
        print("Error in /send-webhook:", e)
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.post("/export-csv")
def export_csv():
    """
    POST /export-csv
    Body:
      {
        "workspaces": [...],
        "view": "campaign_health" | "email_accounts",
        "platform": "instantly" | "emailbison"
      }
    Returns CSV file for download
    """
    try:
        payload = request.get_json(force=True) or {}
        workspaces = payload.get("workspaces", [])
        view = payload.get("view", "campaign_health")
        platform = payload.get("platform", "instantly")

        if not workspaces:
            return jsonify({"error": "No workspace data provided"}), 400

        # Generate CSV based on view type
        output = StringIO()
        writer = csv.writer(output)

        if view == "email_accounts":
            # Email accounts CSV
            writer.writerow([
                "Workspace Name",
                "Workspace ID",
                "Email",
                "Provider",
                "Status",
                "Health",
                "Daily Limit",
                "Warmup Status",
                "Warmup Score",
                "Last Used",
                "Emails Sent",
                "Replies",
                "Interested Leads",
            ])

            for ws in workspaces:
                workspace_name = ws.get("workspace_name", "Unknown")
                workspace_id = ws.get("workspace_id", ws.get("label", "Unknown"))
                accounts = ws.get("accounts", [])

                for acc in accounts:
                    # Check if Email Bison or Instantly
                    is_email_bison = acc.get("emails_sent_count") is not None

                    if is_email_bison:
                        # Get provider from tags (first tag is usually the provider like "Google", "Microsoft")
                        tags = acc.get("tags", [])
                        provider = tags[0] if tags else ""

                        writer.writerow([
                            workspace_name,
                            workspace_id,
                            acc.get("email", ""),
                            provider,  # Provider from tags
                            acc.get("status", ""),
                            acc.get("health", ""),
                            acc.get("daily_limit", 0),
                            "",  # No warmup for Email Bison
                            "",  # No warmup score
                            "",  # No last used
                            acc.get("emails_sent_count", 0),
                            acc.get("unique_replied_count", 0),
                            acc.get("interested_leads_count", 0),
                        ])
                    else:
                        # Instantly
                        writer.writerow([
                            workspace_name,
                            workspace_id,
                            acc.get("email", ""),
                            acc.get("provider_name", ""),
                            acc.get("status", ""),
                            acc.get("health", ""),
                            acc.get("daily_limit", 0),
                            acc.get("warmup_status", ""),
                            acc.get("warmup_score", 0),
                            acc.get("last_used", ""),
                            "",  # No emails sent count for Instantly
                            "",  # No replies for individual accounts
                            "",  # No interested leads for individual accounts
                        ])
        else:
            # Campaign health CSV
            writer.writerow([
                "Workspace Name",
                "Workspace ID",
                "Start Date",
                "End Date",
                "Emails Sent",
                "Replies",
                "Opportunities",
                "Health",
            ])

            for ws in workspaces:
                summary = ws.get("summary", {})
                writer.writerow([
                    ws.get("workspace_name", "Unknown"),
                    ws.get("workspace_id", ws.get("label", "Unknown")),
                    ws.get("start_date", ""),
                    ws.get("end_date", ""),
                    summary.get("emails_sent", 0),
                    summary.get("replies", 0),
                    summary.get("opportunities", 0),
                    ws.get("health", "early"),
                ])

        csv_content = output.getvalue()
        output.close()

        # Return CSV with appropriate headers
        from flask import Response
        timestamp = date.today().isoformat()
        filename = f"{platform}_{view}_{timestamp}.csv"

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        print("Error in /export-csv:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.get("/")
def home():
    """
    Render the frontend – everything else is driven by JS hitting /multi-overview.
    """
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)