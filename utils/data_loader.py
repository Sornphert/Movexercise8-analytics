from __future__ import annotations

import json
import re
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ZOOM_DIR = DATA_DIR / "zoom_participants"

HOST_KEYWORDS = ["Support Team", "Daphnie", "Leon", "John"]
MIN_ATTEND_MINUTES = 20  # Minimum total minutes to count as "attended"

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _get_sheets_client() -> gspread.Client | None:
    """Return an authenticated gspread client, or None if not configured."""
    try:
        if "gcp_service_account" not in st.secrets:
            return None
    except Exception:
        return None
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SHEETS_SCOPES,
    )
    return gspread.authorize(creds)


def _load_leads_from_sheets() -> pd.DataFrame | None:
    """Pull leads from Google Sheets. Returns None on any failure."""
    try:
        client = _get_sheets_client()
        if client is None:
            return None
        sheet_id = st.secrets["sheets"]["leads_sheet_id"]
        gid = int(st.secrets["sheets"]["leads_worksheet_gid"])
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = next(ws for ws in spreadsheet.worksheets() if ws.id == gid)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)

        # Map sheet headers to the dashboard's expected column names
        rename_map = {
            "Date and Time": "date",
            "Full Name": "name",
            "Email": "email",
            "Phone Number": "phone",
            "UTM Campain": "utm_campaign",  # typo preserved in sheet
            "UTM Content": "utm_content",
        }
        df = df.rename(columns=rename_map)

        # Keep only the columns the dashboard uses
        keep = ["date", "name", "email", "phone", "utm_campaign", "utm_content"]
        df = df[[c for c in keep if c in df.columns]]
        return df
    except Exception as e:
        st.warning(f"Google Sheets fetch failed: {e}")
        return None


def _load_purchases_from_sheets() -> pd.DataFrame | None:
    """Pull purchases from Google Sheets. Returns None on any failure."""
    try:
        client = _get_sheets_client()
        if client is None:
            return None
        if "purchases_sheet_id" not in st.secrets.get("sheets", {}):
            return None
        sheet_id = st.secrets["sheets"]["purchases_sheet_id"]
        gid = int(st.secrets["sheets"]["purchases_worksheet_gid"])
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = next(ws for ws in spreadsheet.worksheets() if ws.id == gid)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)

        # Drop spacer rows at the bottom (no invoice number)
        if "Invoice Number" in df.columns:
            invoice = df["Invoice Number"].astype(str).str.strip()
            df = df[(invoice != "") & (invoice.str.lower() != "nan")].copy()

        rename_map = {
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
        df = df.rename(columns=rename_map)

        keep = [
            "date", "name", "email", "phone", "amount", "status",
            "payment_method", "payment_complete", "utm_campaign",
            "utm_content", "notes",
        ]
        for col in keep:
            if col not in df.columns:
                df[col] = ""
        df = df[keep]

        # Strip time component: "12/11/2025 22:00:00" -> "12/11/2025"
        df["date"] = df["date"].astype(str).str.split(" ").str[0]
        return df
    except Exception as e:
        st.warning(f"Google Sheets fetch for purchases failed: {e}")
        return None


def _load_ebook_survey_from_sheets() -> pd.DataFrame | None:
    """Pull the e-book survey responses from Google Sheets. Returns None on failure."""
    try:
        client = _get_sheets_client()
        if client is None:
            return None
        if "ebook_sheet_id" not in st.secrets.get("sheets", {}):
            return None
        sheet_id = st.secrets["sheets"]["ebook_sheet_id"]
        gid = int(st.secrets["sheets"]["ebook_worksheet_gid"])
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = next(ws for ws in spreadsheet.worksheets() if ws.id == gid)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)

        rename_map = {
            "Date and Time": "date",
            "Full Name": "name",
            "Phone Number": "phone",
            "Child Age": "child_age",
            "Role": "role",
            "Main reason for joining webinar": "reason_join",
            "Biggest challenge with child": "challenge",
            "Experience with webinar": "experience",
            "Conisder joining M8": "intent",  # typo preserved in sheet
            "What stops you from joining M8": "objection",
            "Best way to understand M8": "preferred_followup",
            "Anything to say": "comments",
        }
        df = df.rename(columns=rename_map)

        keep = list(rename_map.values())
        for col in keep:
            if col not in df.columns:
                df[col] = ""
        df = df[keep]

        # Drop spacer rows: anything without a phone or a name
        phone_str = df["phone"].astype(str).str.strip()
        name_str = df["name"].astype(str).str.strip()
        df = df[(phone_str != "") | (name_str != "")].copy()
        return df
    except Exception as e:
        st.warning(f"Google Sheets fetch for ebook survey failed: {e}")
        return None


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

@st.cache_data(ttl=300)
def load_leads() -> pd.DataFrame:
    df = _load_leads_from_sheets()
    if df is None:
        st.warning("Using cached CSV for leads — Google Sheets unavailable.")
        df = pd.read_csv(DATA_DIR / "leads.csv")

    # Sheet uses DD/MM/YYYY; CSV uses YYYY-MM-DD. dayfirst=True handles both.
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df["norm_phone"] = df["phone"].apply(normalize_phone)
    df["norm_email"] = df["email"].astype(str).str.strip().str.lower()
    return df


def _is_refund(notes) -> bool:
    if not isinstance(notes, str):
        return False
    return "refund" in notes.lower()


@st.cache_data(ttl=300)
def load_purchases() -> pd.DataFrame:
    df = _load_purchases_from_sheets()
    if df is None:
        st.warning("Using cached CSV for purchases — Google Sheets unavailable.")
        df = pd.read_csv(DATA_DIR / "purchases.csv")
    df["date"] = df["date"].apply(parse_purchase_date)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["payment_complete"] = df["payment_complete"].astype(str).str.strip().str.lower() == "true"
    df["norm_phone"] = df["phone"].apply(normalize_phone)
    df["norm_email"] = df["email"].str.strip().str.lower()
    df["is_refund"] = df["notes"].apply(_is_refund)
    return df


@st.cache_data(ttl=300)
def load_ebook_survey() -> pd.DataFrame:
    """Load the e-book survey from Google Sheets, with normalized phone + age bucket."""
    df = _load_ebook_survey_from_sheets()
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "date", "name", "phone", "child_age", "role", "reason_join", "challenge",
            "experience", "intent", "objection", "preferred_followup", "comments",
            "norm_phone", "age_bucket",
        ])

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df["norm_phone"] = df["phone"].apply(normalize_phone)

    # Lazy import to avoid circular dep with utils.metrics
    from utils.metrics import parse_child_age_bucket
    df["age_bucket"] = df["child_age"].apply(parse_child_age_bucket)
    return df


@st.cache_data
def load_meta_ads() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "meta_ads.csv")
    for col in ["amount_spent", "results", "link_clicks", "impressions", "reach"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _parse_webinar_start_date(label) -> pd.Timestamp | None:
    """Extract the start date from a human-written webinar date label.

    Examples: "Mar 9-10 2026" → 2026-03-09, "Dec 2025→Mar 2026" → 2025-12-01,
    "Feb-Mar 2026" → 2026-02-01.
    """
    if pd.isna(label):
        return None
    s = str(label).strip()
    # Take part before arrow (e.g. "Dec 2025→Mar 2026" → "Dec 2025")
    s = s.split("→")[0].strip()
    # Find year from the split part first, fall back to full label
    year_m = re.search(r"(\d{4})", s)
    if not year_m:
        year_m = re.search(r"(\d{4})\s*$", str(label).strip())
        if not year_m:
            return None
    year = year_m.group(1)
    # Try "Mon DD" at start — (?!\d) ensures DD isn't part of a year like "2025"
    md = re.match(r"([A-Za-z]+)\s+(\d{1,2})(?!\d)", s)
    if md:
        try:
            return pd.to_datetime(f"{md.group(1)} {md.group(2)} {year}")
        except Exception:
            pass
    # Month only (e.g. "Dec 2025", "Feb-Mar 2026")
    mo = re.match(r"([A-Za-z]+)", s)
    if mo:
        try:
            return pd.to_datetime(f"{mo.group(1)} 1 {year}")
        except Exception:
            pass
    return None


@st.cache_data(ttl=300)
def load_objections() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "objections.csv")

    # Name field has phone embedded with newline (e.g. "Logavani\n+60 14-773 5680")
    clean_names = []
    extracted_phones = []
    for raw in df["name"]:
        if pd.isna(raw):
            clean_names.append(raw)
            extracted_phones.append(None)
            continue
        parts = str(raw).split("\n")
        clean_names.append(parts[0].strip())
        phone_part = parts[1].strip() if len(parts) > 1 else None
        extracted_phones.append(phone_part)
    df["name"] = clean_names
    df["phone"] = extracted_phones
    df["norm_phone"] = df["phone"].apply(normalize_phone)

    # Parse child_age as numeric ("N/S" and blanks become NaN)
    df["child_age"] = pd.to_numeric(df["child_age"], errors="coerce")

    # Parse webinar_date labels into a proper datetime for date-range filtering.
    # Labels are human-written: "Mar 9-10 2026", "Dec 2025→Mar 2026", etc.
    df["_filter_date"] = df["webinar_date"].apply(_parse_webinar_start_date)

    return df


@st.cache_data
def load_webinars() -> dict:
    # Scheduled webinar start-of-content time (e.g., "20:00"). The Zoom meeting
    # room opens earlier (7:30–7:45pm) — we anchor all minute calculations to
    # the scheduled start so minute 120 = the real offer moment.
    try:
        with open(DATA_DIR / "config.json") as _cf:
            _cfg = json.load(_cf)
        _sched_hh, _sched_mm = _cfg.get("webinar_scheduled_start", "20:00").split(":")
        _sched_hh, _sched_mm = int(_sched_hh), int(_sched_mm)
    except Exception:
        _sched_hh, _sched_mm = 20, 0

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

        # Drop pre-registered rows that never actually joined (Zoom lists them
        # with missing Join time or 0 duration). We only count real attendees.
        if "Join time" in participants.columns:
            joined_mask = participants["Join time"].notna() & (participants["Join time"].astype(str).str.strip() != "")
            participants = participants[joined_mask].copy()
        participants = participants[participants[duration_col].fillna(0) > 0].copy()

        waiting_col = "In waiting room"

        # Waiting room bounces: joined waiting room but stayed < 5 min total
        # NOTE: CSVs from scripts/fetch_zoom_data.py set "In waiting room" to "No"
        # for all rows because the Zoom API doesn't expose this field. This metric
        # will be 0 for API-fetched meetings (only accurate for manual CSV exports).
        waiting_room_bounces = int(
            ((participants[waiting_col].str.strip().str.lower() == "yes")
             & (participants[duration_col] < 5)).sum()
        )

        # Group by email to get unique attendees
        grouped = participants.groupby("Email", dropna=True).agg(
            total_minutes=(duration_col, "sum")
        ).reset_index()

        # Only count attendees who stayed at least MIN_ATTEND_MINUTES total
        qualified_emails = set(grouped.loc[grouped["total_minutes"] >= MIN_ATTEND_MINUTES, "Email"])
        grouped = grouped[grouped["total_minutes"] >= MIN_ATTEND_MINUTES].reset_index(drop=True)
        participants = participants[participants["Email"].isin(qualified_emails)].copy()

        unique_attendees = len(grouped)
        avg_duration = round(grouped["total_minutes"].mean(), 1) if unique_attendees > 0 else 0

        stayed_120plus = int((grouped["total_minutes"] >= 120).sum())
        stayed_120plus_pct = round(stayed_120plus / unique_attendees * 100, 1) if unique_attendees > 0 else 0

        left_30min = int((grouped["total_minutes"] <= 30).sum())
        left_30min_pct = round(left_30min / unique_attendees * 100, 1) if unique_attendees > 0 else 0

        # Per-session offer minute: 120 min after the SCHEDULED webinar start
        # (e.g., 8:00pm) but measured relative to the Zoom room's Start time.
        # The Zoom room typically opens 15–30 min before the scheduled content
        # start, so the real offer moment is at (scheduled − zoom_start) + 120
        # minutes on the Zoom-relative timeline.
        # Zoom CSV "Start time" / "Join time" / "Leave time" are all in UTC.
        # For relative-minute math we keep UTC (differences are tz-invariant).
        # For offset vs the scheduled local start (e.g. 8:00 PM MYT), convert to +8.
        zoom_start_utc = pd.to_datetime(meta["Start time"].iloc[0])
        zoom_start_local = zoom_start_utc + pd.Timedelta(hours=8)
        offer_minute = 120
        try:
            scheduled_same_day = pd.Timestamp(
                year=zoom_start_local.year, month=zoom_start_local.month, day=zoom_start_local.day,
                hour=_sched_hh, minute=_sched_mm,
            )
            offset_min = (scheduled_same_day - zoom_start_local).total_seconds() / 60
            # Clamp to [0, 60] — if zoom_start is AFTER scheduled, treat as 0 offset
            offer_minute = 120 + max(0, min(60, offset_min))
        except Exception:
            offer_minute = 120

        # Present at offer minute: unique emails whose ANY join interval spans it.
        present_at_offer = 0
        peak_attendance = 0
        if unique_attendees > 0 and {"Join time", "Leave time"}.issubset(participants.columns):
            jt = pd.to_datetime(participants["Join time"], format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
            lt = pd.to_datetime(participants["Leave time"], format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
            join_min = (jt - zoom_start_utc).dt.total_seconds() / 60
            leave_min = (lt - zoom_start_utc).dt.total_seconds() / 60
            spans_offer = (join_min <= offer_minute) & (leave_min > offer_minute)
            present_emails = participants.loc[spans_offer, "Email"].dropna().unique()
            present_at_offer = int(len(present_emails))

            # Peak concurrent attendance across the entire session (unique emails
            # present at each minute mark).
            max_mark = int(leave_min.max()) if not leave_min.empty else 0
            if max_mark > 0:
                emails_series = participants["Email"].reset_index(drop=True)
                jm = join_min.reset_index(drop=True)
                lm = leave_min.reset_index(drop=True)
                best = 0
                for t in range(0, max_mark + 1, 5):
                    mask = (jm <= t) & (lm >= t)
                    present_n = emails_series[mask].dropna().nunique()
                    if present_n > best:
                        best = present_n
                peak_attendance = int(best)

        key = f"{date_str}_{meeting_id}"
        webinars[key] = {
            "meeting_id": meeting_id,
            "date": date_str,
            "meeting_duration": meeting_duration,
            "unique_attendees": unique_attendees,
            "avg_duration": avg_duration,
            "stayed_120plus_pct": stayed_120plus_pct,
            "left_30min_pct": left_30min_pct,
            "present_at_offer": present_at_offer,
            "offer_minute": offer_minute,
            "peak_attendance": peak_attendance,
            "waiting_room_bounces": waiting_room_bounces,
            "participants": grouped,
        }

    return webinars


def infer_webinar_for_purchase(
    purchase_date: pd.Timestamp,
    webinar_dates: list[pd.Timestamp],
    max_days_back: int = 14,
) -> str | None:
    """Most-recent webinar on/before purchase_date, within max_days_back."""
    if pd.isna(purchase_date) or not webinar_dates:
        return None
    eligible = [wd for wd in webinar_dates if wd <= purchase_date]
    if not eligible:
        return None
    latest = max(eligible)
    if (purchase_date - latest).days > max_days_back:
        return None
    return latest.strftime("%Y-%m-%d")


def enrich_purchases_with_webinar(
    purchases_df: pd.DataFrame,
    webinars_dict: dict,
) -> pd.DataFrame:
    """Return a copy of purchases_df with an 'inferred_webinar' column."""
    df = purchases_df.copy()
    unique_dates = sorted({pd.Timestamp(w["date"]) for w in webinars_dict.values()})
    df["inferred_webinar"] = df["date"].apply(
        lambda d: infer_webinar_for_purchase(d, unique_dates)
    )
    return df


def infer_webinar_for_lead(
    lead_date: pd.Timestamp,
    webinar_dates: list[pd.Timestamp],
    max_days_forward: int = 9,
) -> str | None:
    """Soonest webinar on/after lead_date within max_days_forward."""
    if pd.isna(lead_date) or not webinar_dates:
        return None
    lead_day = pd.Timestamp(lead_date).normalize()
    eligible = [wd for wd in webinar_dates if wd >= lead_day]
    if not eligible:
        return None
    soonest = min(eligible)
    if (soonest - lead_day).days > max_days_forward:
        return None
    return soonest.strftime("%Y-%m-%d")


def _day1_dates(webinars_dict: dict) -> list[pd.Timestamp]:
    """Day-1 date per meeting_id (earliest session date for each Zoom meeting)."""
    by_meeting: dict[str, list[pd.Timestamp]] = {}
    for w in webinars_dict.values():
        by_meeting.setdefault(w["meeting_id"], []).append(pd.Timestamp(w["date"]))
    return sorted({min(dates) for dates in by_meeting.values()})


def enrich_leads_with_webinar(
    leads_df: pd.DataFrame,
    webinars_dict: dict,
) -> pd.DataFrame:
    """Return a copy of leads_df with a 'registered_for_webinar' column.

    For each lead, the value is the next webinar's Day-1 date (YYYY-MM-DD)
    within 9 days of registration, or 'Unknown' if none.
    """
    df = leads_df.copy()
    day1_dates = _day1_dates(webinars_dict)
    df["registered_for_webinar"] = df["date"].apply(
        lambda d: infer_webinar_for_lead(d, day1_dates) or "Unknown"
    )
    return df


def get_webinar_registration_summary(
    leads_df: pd.DataFrame,
    webinars_dict: dict,
) -> dict:
    """Per Day-1 webinar date: registration count, attendance, show-up rate, avg lead-time.

    Attendee match is email-only (Zoom participant data has no phone field).
    """
    by_meeting: dict[str, list[dict]] = {}
    for w in webinars_dict.values():
        by_meeting.setdefault(w["meeting_id"], []).append(w)

    summary: dict = {}
    for sessions in by_meeting.values():
        sessions_sorted = sorted(sessions, key=lambda x: x["date"])
        day1 = sessions_sorted[0]
        day2 = sessions_sorted[1] if len(sessions_sorted) > 1 else None
        day1_date_str = day1["date"]
        day1_date = pd.Timestamp(day1_date_str)

        day1_emails = set(
            day1["participants"]["Email"].dropna().astype(str).str.strip().str.lower()
        )
        day2_emails: set = set()
        if day2 is not None:
            day2_emails = set(
                day2["participants"]["Email"].dropna().astype(str).str.strip().str.lower()
            )

        if "registered_for_webinar" not in leads_df.columns:
            registered_leads = leads_df.iloc[0:0]
        else:
            registered_leads = leads_df[leads_df["registered_for_webinar"] == day1_date_str]

        registered_count = int(len(registered_leads))
        registered_emails = set(
            registered_leads["norm_email"].dropna().astype(str).str.strip().str.lower()
        )
        registered_emails.discard("")

        d1_attended = len(day1_emails & registered_emails)
        d2_attended = len(day2_emails & registered_emails)
        unique_attended = len((day1_emails | day2_emails) & registered_emails)

        show_up_rate = (
            round(unique_attended / registered_count * 100, 1)
            if registered_count > 0 else 0.0
        )

        avg_days_before = 0.0
        if registered_count > 0:
            diffs = (day1_date - registered_leads["date"]).dt.days.dropna()
            if not diffs.empty:
                avg_days_before = round(float(diffs.mean()), 1)

        summary[day1_date_str] = {
            "registered_count": registered_count,
            "day1_attended": d1_attended,
            "day2_attended": d2_attended,
            "unique_attended": unique_attended,
            "show_up_rate": show_up_rate,
            "avg_days_before_webinar": avg_days_before,
        }

    return summary


def get_webinar_sales_summary(
    purchases_df: pd.DataFrame,
    webinars_dict: dict,
) -> dict:
    """Keyed by webinar date; counts/revenue per attributed webinar."""
    # Unique dates (dedupe same-day sessions)
    webinar_dates = sorted({w["date"] for w in webinars_dict.values()})
    summary = {
        d: {
            "sales_count": 0,
            "total_revenue": 0.0,
            "confirmed_count": 0,
            "installment_count": 0,
            "buyers": [],
        }
        for d in webinar_dates
    }

    if "inferred_webinar" not in purchases_df.columns:
        return summary

    attributed = purchases_df[purchases_df["inferred_webinar"].notna()]
    for date_str, group in attributed.groupby("inferred_webinar"):
        bucket = summary.setdefault(date_str, {
            "sales_count": 0, "total_revenue": 0.0,
            "confirmed_count": 0, "installment_count": 0, "buyers": [],
        })
        bucket["sales_count"] = int(len(group))
        bucket["total_revenue"] = float(group["amount"].fillna(0).sum())
        status = group["status"].astype(str)
        bucket["confirmed_count"] = int((status.str.strip() == "Confirmed").sum())
        bucket["installment_count"] = int(status.str.contains("installment", case=False, na=False).sum())
        bucket["buyers"] = group["name"].dropna().astype(str).unique().tolist()

    return summary


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
    webinars = load_webinars()

    purchases = enrich_purchases_with_webinar(purchases, webinars)
    leads = enrich_leads_with_webinar(leads, webinars)

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
        "webinars": webinars,
        "ebook": load_ebook_survey(),
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

    print()
    print("First 20 purchases with inferred webinar:")
    sample = data["purchases"][["date", "name", "amount", "inferred_webinar"]].head(20)
    print(sample.to_string(index=False))

    print()
    print("Webinar sales summary:")
    summary = get_webinar_sales_summary(data["purchases"], data["webinars"])
    for date_str in sorted(summary):
        s = summary[date_str]
        if s["sales_count"]:
            print(f"  {date_str}: {s['sales_count']} sales, "
                  f"RM {s['total_revenue']:,.0f} "
                  f"({s['confirmed_count']} confirmed, {s['installment_count']} installment)")
