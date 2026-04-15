#!/usr/bin/env python3
"""Fetch purchases data from the public Google Sheet and save as data/purchases.csv.

Usage:
    python scripts/fetch_purchases_data.py
    python scripts/fetch_purchases_data.py --dry-run
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "purchases.csv"

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds
MIN_ROWS = 10

REQUIRED_COLUMNS = {
    "Invoice Number", "Name", "Email", "Mobile Number",
    "Year / Month", "Status", "Initial Course Fee", "Payment Complete",
}

# Sheet-column → dashboard-CSV column
COLUMN_MAP = {
    "Year / Month": "date",
    "Name": "name",
    "Email": "email",
    "Mobile Number": "phone",
    "Initial Course Fee": "amount",
    "Status": "status",
    "Source": "payment_method",
    "Payment Complete": "payment_complete",
    "UTM Campaign": "utm_campaign",
    "UTM Content": "utm_content",
    "NOTE": "notes",
}

OUTPUT_COLUMNS = [
    "date", "name", "email", "phone", "amount", "status",
    "payment_method", "payment_complete", "utm_campaign",
    "utm_content", "notes",
]


def build_export_url(edit_url: str) -> str:
    """Convert a sheet edit URL to its CSV-export URL."""
    m = re.match(
        r"https://docs\.google\.com/spreadsheets/d/([^/]+)/edit\?gid=(\d+)",
        edit_url.strip(),
    )
    if not m:
        raise ValueError(
            "PURCHASES_SHEET_URL must look like "
            "https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit?gid=<TAB_ID>"
        )
    sheet_id, gid = m.group(1), m.group(2)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def fetch_csv(export_url: str) -> str:
    """GET the CSV content with retry + backoff. Exits on permission errors."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(export_url, timeout=30, allow_redirects=True)
        except requests.RequestException as e:
            wait = BACKOFF_BASE * (2 ** attempt)
            print(f"  Network error ({e}); retrying in {wait}s...")
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            return resp.text

        if resp.status_code in (401, 403, 404):
            print(
                f"HTTP {resp.status_code} from Google Sheets. "
                "Make sure the sheet is set to 'Anyone with link can view'."
            )
            sys.exit(1)

        wait = BACKOFF_BASE * (2 ** attempt)
        print(f"  HTTP {resp.status_code}; retrying in {wait}s...")
        time.sleep(wait)

    print(f"Failed to fetch sheet after {MAX_RETRIES} attempts.")
    sys.exit(1)


def validate_csv(text: str) -> tuple[bool, list[str], pd.DataFrame]:
    """Parse + validate. Return (ok, warnings, df). df is empty on parse failure."""
    warnings: list[str] = []
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as e:
        return False, [f"CSV parse failed: {e}"], pd.DataFrame()

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        warnings.append(f"Missing required columns: {sorted(missing)}")

    if len(df) < MIN_ROWS:
        warnings.append(f"Only {len(df)} rows (expected >= {MIN_ROWS}).")

    return (len(warnings) == 0), warnings, df


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Map sheet columns to dashboard-CSV columns."""
    # Drop rows without an invoice number (blank spacer rows at the bottom)
    df = df[df["Invoice Number"].notna() & (df["Invoice Number"].astype(str).str.strip() != "")].copy()

    renamed = df.rename(columns=COLUMN_MAP)
    for col in OUTPUT_COLUMNS:
        if col not in renamed.columns:
            renamed[col] = ""

    # Strip time component: "12/11/2025 22:00:00" -> "12/11/2025"
    renamed["date"] = renamed["date"].astype(str).str.split(" ").str[0]

    return renamed[OUTPUT_COLUMNS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch purchases CSV from Google Sheets")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate only; do not write")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()

    sheet_url = os.getenv("PURCHASES_SHEET_URL")
    if not sheet_url:
        print("Error: PURCHASES_SHEET_URL is not set. See .env.example.")
        sys.exit(1)

    export_url = build_export_url(sheet_url)
    print(f"Fetching: {export_url}")
    text = fetch_csv(export_url)

    ok, warnings, df = validate_csv(text)
    if not ok:
        print("Validation failed:")
        for w in warnings:
            print(f"  - {w}")
        print("Existing data/purchases.csv was NOT overwritten.")
        sys.exit(1)

    out_df = transform(df)
    print(f"Rows fetched: {len(df)}")
    print(f"Columns found: {len(df.columns)}")
    print(f"Rows after filtering blanks: {len(out_df)}")

    if args.dry_run:
        print("Dry run — not writing.")
        print(out_df.head(5).to_string(index=False))
        return

    out_df.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH.relative_to(OUTPUT_PATH.parent.parent)}")


if __name__ == "__main__":
    main()
