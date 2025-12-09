import os
import csv
from io import StringIO
from datetime import date
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

# Optional default token for local single-workspace testing
INSTANTLY_API_KEY = os.getenv("INSTANTLY_API_KEY")

INSTANTLY_OVERVIEW_URL = "https://api.instantly.ai/api/v2/campaigns/analytics/overview"
INSTANTLY_WORKSPACE_URL = "https://api.instantly.ai/api/v2/workspaces/current"

# Campaign statuses to scan
CAMPAIGN_STATUSES = [0, 1, 2, 3, 4, -99, -1, -2]

# Default sheet + tab (gid) – can be overridden by sheet_url query param
DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1CNejGg-egkp28ItSRfW7F_CkBXgYevjzstJ1QlrAyAY/edit"
)
SHEET_GID = "928115249"  # third tab in your sheet

# Health scoring thresholds
MIN_EMAILS_FOR_HEALTH = 2000

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


def load_workspaces_from_sheet(sheet_url: str, gid: str = SHEET_GID) -> list[dict]:
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


def fetch_workspace_info(api_key: str) -> dict:
    """
    Calls Instantly /workspaces/current using given API key.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    resp = requests.get(
        INSTANTLY_WORKSPACE_URL,
        headers=headers,
        timeout=30,
    )

    if not resp.ok:
        print(
            "[Instantly] error in /workspaces/current:",
            resp.status_code,
            resp.text,
        )
        resp.raise_for_status()

    data = resp.json()
    return {
        "workspace_id": data.get("id"),
        "workspace_name": data.get("name"),
    }


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


@app.get("/multi-overview")
def multi_overview():
    """
    GET /multi-overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&sheet_url=...

    Uses a Google Sheet (with workspace_id + api_key) to:
      - Loop through all workspaces IN PARALLEL
      - Pull Instantly analytics for the date range
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

        sheet_url = request.args.get("sheet_url", DEFAULT_SHEET_URL)

        # 1) Load workspaces from sheet
        workspaces = load_workspaces_from_sheet(sheet_url)

        results = []
        totals = {
            "emails_sent": 0,
            "replies": 0,
            "opportunities": 0,
        }

        # 2) Process all workspaces in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all workspace processing tasks
            futures = {
                executor.submit(
                    process_single_workspace,
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

                    # Update totals
                    summary = workspace_result["summary"]
                    totals["emails_sent"] += summary["emails_sent"]
                    totals["replies"] += summary["replies"]
                    totals["opportunities"] += summary["opportunities"]
                except Exception as e:
                    row = futures[future]
                    print(f"[Instantly] Error processing workspace {row['workspace_id']}: {e}")
                    traceback.print_exc()

        return jsonify(
            {
                "sheet_url": sheet_url,
                "start_date": start_date,
                "end_date": end_date,
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


@app.get("/")
def home():
    """
    Render the frontend – everything else is driven by JS hitting /multi-overview.
    """
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)