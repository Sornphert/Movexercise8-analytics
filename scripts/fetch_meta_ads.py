#!/usr/bin/env python3
"""Fetch Meta Ads insights and save as data/meta_ads.csv.

Usage:
    python scripts/fetch_meta_ads.py                          # last 30 days
    python scripts/fetch_meta_ads.py --days 90                # custom lookback
    python scripts/fetch_meta_ads.py --from 2025-11-01 --to 2026-04-14
    python scripts/fetch_meta_ads.py --dry-run                # preview only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

API_VERSION = "v25.0"
GRAPH_BASE = f"https://graph.facebook.com/{API_VERSION}"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "meta_ads.csv"

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds

BACKFILL_START_DATE = "2025-10-01"
DEDUP_KEYS = ["reporting_starts", "ad_name"]

INSIGHTS_FIELDS = ",".join([
    "campaign_name",
    "adset_name",
    "ad_name",
    "spend",
    "impressions",
    "reach",
    "clicks",
    "cpm",
    "actions",
    "quality_ranking",
    "engagement_rate_ranking",
    "conversion_rate_ranking",
])

# Meta API ranking enums -> human-readable strings used in the existing CSV.
# The dashboard filters on the literal "-" string for missing rankings, so
# every "missing" case must map to "-" exactly.
RANKING_MAP = {
    "ABOVE_AVERAGE": "Above average",
    "AVERAGE": "Average",
    "BELOW_AVERAGE_35": "Below average - Bottom 35% of ads",
    "BELOW_AVERAGE_20": "Below average - Bottom 20% of ads",
    "BELOW_AVERAGE_10": "Below average - Bottom 10% of ads",
    "UNKNOWN": "-",
    "": "-",
}

LEAD_ACTION_PIXEL = "offsite_conversion.fb_pixel_lead"
LEAD_ACTION_FALLBACK = "lead"

OUTPUT_COLUMNS = [
    "reporting_starts", "reporting_ends",
    "campaign_name", "adset_name", "ad_name",
    "amount_spent", "results", "link_clicks",
    "impressions", "reach", "cpm",
    "quality_ranking", "engagement_ranking", "conversion_ranking",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Meta Ads insights for the MOVEXERCISE8 dashboard"
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Number of days to look back (default: 30)",
    )
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and preview without writing the CSV",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--append", action="store_true",
        help="Merge fetched rows into the existing CSV; dedupes on (reporting_starts, ad_name)",
    )
    mode.add_argument(
        "--backfill", action="store_true",
        help=f"Fill in older data: pulls from {BACKFILL_START_DATE} up to the earliest "
             f"date already in the CSV, then merges (implies --append)",
    )
    return parser.parse_args()


def resolve_date_range(args: argparse.Namespace) -> tuple[str, str]:
    if args.from_date and args.to_date:
        since = date.fromisoformat(args.from_date)
        until = date.fromisoformat(args.to_date)
    else:
        until = date.today()
        since = until - timedelta(days=args.days)
    return since.isoformat(), until.isoformat()


def resolve_backfill_range() -> tuple[str, str]:
    """Compute (since, until) for --backfill from the existing CSV."""
    if not OUTPUT_PATH.exists():
        print(f"Error: --backfill requires an existing {OUTPUT_PATH.name} to anchor against.")
        sys.exit(1)

    existing = pd.read_csv(OUTPUT_PATH)
    if existing.empty or "reporting_starts" not in existing.columns:
        print(f"Error: {OUTPUT_PATH.name} has no rows or no 'reporting_starts' column.")
        sys.exit(1)

    earliest_str = existing["reporting_starts"].dropna().astype(str).min()
    earliest = date.fromisoformat(earliest_str)
    since = date.fromisoformat(BACKFILL_START_DATE)
    until = earliest - timedelta(days=1)

    if until < since:
        print(f"Already backfilled to {BACKFILL_START_DATE} (earliest row: {earliest_str}). Nothing to do.")
        sys.exit(0)

    return since.isoformat(), until.isoformat()


def merge_with_existing(new_df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Concat new rows onto the existing CSV and dedupe on (reporting_starts, ad_name).
    Newer fetched rows win on conflict (keep="last").

    Returns (final_df, dropped_duplicates, existing_row_count).
    """
    if not OUTPUT_PATH.exists():
        return new_df, 0, 0

    existing = pd.read_csv(OUTPUT_PATH)
    existing_count = len(existing)
    combined = pd.concat([existing, new_df], ignore_index=True)
    deduped = combined.drop_duplicates(subset=DEDUP_KEYS, keep="last").reset_index(drop=True)
    dropped = len(combined) - len(deduped)
    return deduped, dropped, existing_count


def http_get(url: str, params: dict) -> dict:
    """GET with exponential backoff. Exits on auth errors."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=120)
        except requests.RequestException as e:
            wait = BACKOFF_BASE * (2 ** attempt)
            print(f"  Network error ({e}); retrying in {wait}s...")
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code in (401, 403):
            print(
                "Invalid or expired token. Generate a new System User token "
                "at business.facebook.com/settings"
            )
            sys.exit(1)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            print(f"  Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        wait = BACKOFF_BASE * (2 ** attempt)
        body = resp.text[:200] if resp.text else ""
        print(f"  HTTP {resp.status_code}; retrying in {wait}s... {body}")
        time.sleep(wait)

    print(f"Failed to fetch insights after {MAX_RETRIES} attempts.")
    sys.exit(1)


def fetch_insights(ad_account_id: str, access_token: str, since: str, until: str) -> list[dict]:
    """Walk all pages of /insights and return the combined row list."""
    url = f"{GRAPH_BASE}/{ad_account_id}/insights"
    params = {
        "access_token": access_token,
        "level": "ad",
        "fields": INSIGHTS_FIELDS,
        "time_range": json.dumps({"since": since, "until": until}),
        "time_increment": 1,
        "limit": 100,
    }

    rows: list[dict] = []
    page = 1
    while True:
        data = http_get(url, params)
        batch = data.get("data", [])
        rows.extend(batch)
        print(f"  Page {page}: {len(batch)} rows (total {len(rows)})")

        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        # Meta's "next" URL already contains the cursor; pass it directly.
        url = next_url
        params = {}
        page += 1

    return rows


def extract_lead_count(actions: list[dict] | None):
    """Prefer pixel-based leads; fall back to generic 'lead' action."""
    if not actions:
        return pd.NA

    by_type: dict[str, float] = {}
    for a in actions:
        t = a.get("action_type", "")
        try:
            by_type[t] = float(a.get("value", 0))
        except (TypeError, ValueError):
            continue

    if LEAD_ACTION_PIXEL in by_type:
        return by_type[LEAD_ACTION_PIXEL]
    if LEAD_ACTION_FALLBACK in by_type:
        return by_type[LEAD_ACTION_FALLBACK]
    return pd.NA


def map_ranking(value) -> str:
    if value is None:
        return "-"
    return RANKING_MAP.get(str(value), "-")


def build_dataframe(rows: list[dict]) -> pd.DataFrame:
    records = []
    for r in rows:
        records.append({
            "reporting_starts": r.get("date_start", ""),
            "reporting_ends": r.get("date_stop", ""),
            "campaign_name": r.get("campaign_name", ""),
            "adset_name": r.get("adset_name", ""),
            "ad_name": r.get("ad_name", ""),
            "amount_spent": r.get("spend"),
            "results": extract_lead_count(r.get("actions")),
            "link_clicks": r.get("clicks"),
            "impressions": r.get("impressions"),
            "reach": r.get("reach"),
            "cpm": r.get("cpm"),
            "quality_ranking": map_ranking(r.get("quality_ranking")),
            "engagement_ranking": map_ranking(r.get("engagement_rate_ranking")),
            "conversion_ranking": map_ranking(r.get("conversion_rate_ranking")),
        })

    df = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    return df


def main() -> None:
    args = parse_args()
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    access_token = os.getenv("META_ACCESS_TOKEN")
    ad_account_id = os.getenv("META_AD_ACCOUNT_ID")

    missing = []
    if not access_token:
        missing.append("META_ACCESS_TOKEN")
    if not ad_account_id:
        missing.append("META_AD_ACCOUNT_ID")
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Create a .env file with these values (see .env.example)")
        sys.exit(1)

    if args.backfill:
        since, until = resolve_backfill_range()
        mode_label = "backfill (merge)"
    else:
        since, until = resolve_date_range(args)
        mode_label = "append (merge)" if args.append else "overwrite"

    print(f"Fetching {since} -> {until}")
    print(f"Account: {ad_account_id}")
    print(f"Mode:    {mode_label}")
    print()

    rows = fetch_insights(ad_account_id, access_token, since, until)

    if not rows:
        print("No insights returned for this date range.")
        print(f"Existing {OUTPUT_PATH.name} was NOT modified.")
        sys.exit(1)

    new_df = build_dataframe(rows)

    merging = args.append or args.backfill
    if merging:
        final_df, dropped, existing_count = merge_with_existing(new_df)
    else:
        final_df, dropped, existing_count = new_df, 0, 0

    if args.dry_run:
        print()
        print("Dry run — not writing.")
        if merging:
            print(f"Existing rows:    {existing_count:,}")
            print(f"Fetched rows:     {len(new_df):,}")
            print(f"Duplicates dropped: {dropped:,}")
            print(f"Final rows:       {len(final_df):,}")
        print(new_df.head(5).to_string(index=False))
        return

    final_df.to_csv(OUTPUT_PATH, index=False)

    fetched_spend = pd.to_numeric(new_df["amount_spent"], errors="coerce").sum()
    fetched_leads = pd.to_numeric(new_df["results"], errors="coerce").sum()

    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  Date range:        {since} -> {until}")
    print(f"  Mode:              {mode_label}")
    print(f"  Fetched rows:      {len(new_df):,}")
    if merging:
        print(f"  Existing rows:     {existing_count:,}")
        print(f"  Duplicates dropped: {dropped:,}")
    print(f"  Final file rows:   {len(final_df):,}")
    print(f"  Fetched spend:     {fetched_spend:,.2f}")
    print(f"  Fetched leads:     {int(fetched_leads):,}")
    print(f"  Output:            {OUTPUT_PATH.relative_to(OUTPUT_PATH.parent.parent)}")
    print()


if __name__ == "__main__":
    main()
