from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ZOOM_DIR = DATA_DIR / "zoom_participants"

HOST_KEYWORDS = ["Support Team", "Daphnie", "Leon", "John"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_phone(phone) -> str | None:
    if pd.isna(phone):
        return None
    digits = re.sub(r"[^0-9]", "", str(phone))
    if digits.startswith("60"):
        digits = "0" + digits[2:]
    elif digits.startswith("6") and len(digits) > 10:
        digits = "0" + digits[1:]
    if len(digits) < 10:
        return None
    return digits


def parse_purchase_date(date_str) -> pd.Timestamp:
    if pd.isna(date_str):
        return pd.NaT
    s = str(date_str).strip()
    # Already ISO format (YYYY-MM-DD)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return pd.Timestamp(s)
    # Slash-delimited: could be DD/MM/YYYY or M/D/YYYY
    parts = re.split(r"[/\-]", s)
    if len(parts) != 3:
        return pd.NaT
    a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
    year = c if c > 100 else c + 2000
    if a > 12:
        # First number can't be a month → DD/MM/YYYY
        return pd.Timestamp(year=year, month=b, day=a)
    if b > 12:
        # Second number can't be a month → MM/DD/YYYY (a=month, b=day)
        return pd.Timestamp(year=year, month=a, day=b)
    # Ambiguous — use year as context
    if year <= 2025:
        return pd.Timestamp(year=year, month=b, day=a)  # DD/MM/YYYY
    else:
        return pd.Timestamp(year=year, month=a, day=b)  # M/D/YYYY


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

@st.cache_data
def load_leads() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "leads.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["norm_phone"] = df["phone"].apply(normalize_phone)
    df["norm_email"] = df["email"].str.strip().str.lower()
    return df


@st.cache_data
def load_purchases() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "purchases.csv")
    df["date"] = df["date"].apply(parse_purchase_date)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["payment_complete"] = df["payment_complete"].astype(str).str.strip().str.lower() == "true"
    df["norm_phone"] = df["phone"].apply(normalize_phone)
    df["norm_email"] = df["email"].str.strip().str.lower()
    return df


@st.cache_data
def load_meta_ads() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "meta_ads.csv")
    for col in ["amount_spent", "results", "link_clicks", "impressions", "reach"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data
def load_objections() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "objections.csv")


@st.cache_data
def load_webinars() -> dict:
    webinars = {}
    for fp in sorted(ZOOM_DIR.glob("participants_*.csv")):
        if "__1_" in fp.name:
            continue

        # Extract meeting_id and date from filename
        # Pattern: participants_{meeting_id}_{YYYY}_{MM}_{DD}.csv
        match = re.match(r"participants_(\d+)_(\d{4})_(\d{2})_(\d{2})\.csv", fp.name)
        if not match:
            continue
        meeting_id = match.group(1)
        date_str = f"{match.group(2)}-{match.group(3)}-{match.group(4)}"

        # Read metadata from row 1 (header row 0, data row 1)
        meta = pd.read_csv(fp, nrows=1, encoding="utf-8-sig")
        meeting_duration = int(meta["Duration (minutes)"].iloc[0])

        # Read participant data (skip metadata header + values + blank row)
        participants = pd.read_csv(fp, skiprows=3, encoding="utf-8-sig")

        # Filter out hosts/admins
        name_col = participants.columns[0]  # "Name (original name)"
        is_host = participants[name_col].str.contains(
            "|".join(HOST_KEYWORDS), case=False, na=False
        )
        participants = participants[~is_host].copy()

        duration_col = "Duration (minutes)"
        participants[duration_col] = pd.to_numeric(participants[duration_col], errors="coerce")

        waiting_col = "In waiting room"

        # Waiting room bounces: joined waiting room but stayed < 5 min total
        waiting_room_bounces = int(
            ((participants[waiting_col].str.strip().str.lower() == "yes")
             & (participants[duration_col] < 5)).sum()
        )

        # Group by email to get unique attendees
        grouped = participants.groupby("Email", dropna=True).agg(
            total_minutes=(duration_col, "sum")
        ).reset_index()

        unique_attendees = len(grouped)
        avg_duration = round(grouped["total_minutes"].mean(), 1) if unique_attendees > 0 else 0

        stayed_120plus = int((grouped["total_minutes"] >= 120).sum())
        stayed_120plus_pct = round(stayed_120plus / unique_attendees * 100, 1) if unique_attendees > 0 else 0

        left_30min = int((grouped["total_minutes"] <= 30).sum())
        left_30min_pct = round(left_30min / unique_attendees * 100, 1) if unique_attendees > 0 else 0

        key = f"{date_str}_{meeting_id}"
        webinars[key] = {
            "meeting_id": meeting_id,
            "date": date_str,
            "meeting_duration": meeting_duration,
            "unique_attendees": unique_attendees,
            "avg_duration": avg_duration,
            "stayed_120plus_pct": stayed_120plus_pct,
            "left_30min_pct": left_30min_pct,
            "waiting_room_bounces": waiting_room_bounces,
            "participants": grouped,
        }

    return webinars


@st.cache_data
def load_participant_detail(date_str: str, meeting_id: str) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Load raw participant rows for a specific webinar session (for drop-off curves)."""
    y, m, d = date_str.split("-")
    fp = ZOOM_DIR / f"participants_{meeting_id}_{y}_{m}_{d}.csv"
    if not fp.exists():
        return pd.DataFrame(), pd.NaT

    meta = pd.read_csv(fp, nrows=1, encoding="utf-8-sig")
    start_time = pd.to_datetime(meta["Start time"].iloc[0])

    df = pd.read_csv(fp, skiprows=3, encoding="utf-8-sig")
    name_col = df.columns[0]
    is_host = df[name_col].str.contains("|".join(HOST_KEYWORDS), case=False, na=False)
    df = df[~is_host].copy()

    df["join_time"] = pd.to_datetime(df["Join time"], format="%m/%d/%Y %I:%M:%S %p")
    df["leave_time"] = pd.to_datetime(df["Leave time"], format="%m/%d/%Y %I:%M:%S %p")
    df["join_min"] = (df["join_time"] - start_time).dt.total_seconds() / 60
    df["leave_min"] = (df["leave_time"] - start_time).dt.total_seconds() / 60

    return df, start_time


def load_config() -> dict:
    with open(DATA_DIR / "config.json") as f:
        return json.load(f)


def load_all() -> dict:
    leads = load_leads()
    purchases = load_purchases()

    # Mark leads that converted to a purchase (match on email or phone)
    purchase_emails = set(purchases["norm_email"].dropna())
    purchase_phones = set(purchases["norm_phone"].dropna())
    leads["converted"] = (
        leads["norm_email"].isin(purchase_emails)
        | leads["norm_phone"].isin(purchase_phones)
    )

    return {
        "leads": leads,
        "purchases": purchases,
        "meta": load_meta_ads(),
        "objections": load_objections(),
        "webinars": load_webinars(),
        "config": load_config(),
    }


if __name__ == "__main__":
    # Quick verification — run outside Streamlit so skip caching
    st.cache_data = lambda func: func  # no-op decorator

    data = load_all()
    print(f"Leads:       {len(data['leads']):,} rows")
    print(f"Purchases:   {len(data['purchases']):,} rows")
    print(f"Meta ads:    {len(data['meta']):,} rows")
    print(f"Objections:  {len(data['objections']):,} rows")
    print(f"Webinars:    {len(data['webinars'])} sessions")
    print(f"Converted:   {data['leads']['converted'].sum():,} leads matched a purchase")
    print()
    for key, w in data["webinars"].items():
        print(f"  {key}: {w['unique_attendees']} attendees, "
              f"avg {w['avg_duration']}min, "
              f"{w['stayed_120plus_pct']}% stayed 120+, "
              f"{w['waiting_room_bounces']} waiting room bounces")
