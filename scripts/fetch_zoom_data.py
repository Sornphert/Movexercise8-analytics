#!/usr/bin/env python3
"""Fetch Zoom participant data and save as CSVs for the dashboard.

Usage:
    python scripts/fetch_zoom_data.py                     # last 7 days
    python scripts/fetch_zoom_data.py --days 30           # last 30 days
    python scripts/fetch_zoom_data.py --from 2026-03-01 --to 2026-04-14
    python scripts/fetch_zoom_data.py --meeting-id 84337077884
    python scripts/fetch_zoom_data.py --dry-run           # preview only
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.zoom.us/v2"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "zoom_participants"
TOPIC_FILTER = "MOVEXERCISE8"  # Only fetch meetings with this in the topic

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds


class ZoomClient:
    def __init__(self, account_id: str, client_id: str, client_secret: str, host_email: str):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.host_email = host_email
        self.access_token: str | None = None
        self._resolved_user_id: str | None = None

    def authenticate(self) -> None:
        """Get access token via Server-to-Server OAuth."""
        resp = requests.post(
            "https://zoom.us/oauth/token",
            params={"grant_type": "account_credentials", "account_id": self.account_id},
            auth=(self.client_id, self.client_secret),
        )
        if resp.status_code != 200:
            print(f"Authentication failed ({resp.status_code}): {resp.text}")
            sys.exit(1)
        self.access_token = resp.json()["access_token"]
        print("Authenticated with Zoom API")

    def _request(self, method: str, path: str, params: dict | None = None) -> dict:
        """Make an authenticated API request with retry and rate-limit handling."""
        if not self.access_token:
            self.authenticate()

        url = f"{BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        for attempt in range(MAX_RETRIES):
            resp = requests.request(method, url, headers=headers, params=params)

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"  Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            if resp.status_code == 401:
                if attempt == 0:
                    print("  Token expired, re-authenticating...")
                    self.authenticate()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    continue
                print(f"Auth error: {resp.text}")
                raise RuntimeError(f"Zoom API auth failed: {resp.status_code}")

            if resp.status_code >= 400:
                raise RuntimeError(f"Zoom API error {resp.status_code}: {resp.text}")

            # Transient error — retry with backoff
            wait = BACKOFF_BASE * (2 ** attempt)
            print(f"  Request failed ({resp.status_code}), retrying in {wait}s...")
            time.sleep(wait)

        raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {url}")

    def _get_user_id(self) -> str:
        """Return the user identifier for API calls (email works directly)."""
        return self.host_email

    def list_past_meetings(self, from_date: date, to_date: date) -> list[dict]:
        """List past meetings for the host within the date range."""
        user_id = self._get_user_id()
        meetings: list[dict] = []
        next_page_token = ""

        # Zoom API limits date range to 30 days per request — chunk if needed
        chunk_start = from_date
        while chunk_start <= to_date:
            chunk_end = min(chunk_start + timedelta(days=29), to_date)

            params = {
                "type": "past",
                "from": chunk_start.isoformat(),
                "to": chunk_end.isoformat(),
                "page_size": 300,
            }

            while True:
                if next_page_token:
                    params["next_page_token"] = next_page_token

                data = self._request("GET", f"/report/users/{user_id}/meetings", params=params)
                meetings.extend(data.get("meetings", []))

                next_page_token = data.get("next_page_token", "")
                if not next_page_token:
                    break

            chunk_start = chunk_end + timedelta(days=1)
            next_page_token = ""

        return meetings

    def get_meeting_detail(self, meeting_id: str) -> dict:
        """Get metadata for a single past meeting."""
        return self._request("GET", f"/past_meetings/{meeting_id}")

    def get_participants(self, meeting_identifier: str) -> list[dict]:
        """Fetch all participants for a meeting occurrence.

        Pass the occurrence UUID (not the numeric meeting ID) to get
        instance-specific data for recurring meetings. UUIDs that contain
        "/" or start with "/" must be double URL-encoded per Zoom docs.
        """
        from urllib.parse import quote

        if meeting_identifier.startswith("/") or "//" in meeting_identifier:
            encoded = quote(quote(meeting_identifier, safe=""), safe="")
        else:
            encoded = quote(meeting_identifier, safe="")

        participants: list[dict] = []
        next_page_token = ""

        while True:
            params = {"page_size": 300}
            if next_page_token:
                params["next_page_token"] = next_page_token

            data = self._request(
                "GET", f"/report/meetings/{encoded}/participants", params=params
            )
            participants.extend(data.get("participants", []))

            next_page_token = data.get("next_page_token", "")
            if not next_page_token:
                break

        return participants


def format_time(iso_str: str) -> str:
    """Convert ISO 8601 timestamp to Zoom export format: MM/DD/YYYY HH:MM:SS AM/PM."""
    if not iso_str:
        return ""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.strftime("%m/%d/%Y %I:%M:%S %p")


def build_csv(meeting: dict, participants: list[dict]) -> str:
    """Build CSV content matching the exact format of manual Zoom exports."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Row 1: Meeting metadata header
    topic = meeting.get("topic", "")
    meeting_id = meeting.get("id", "")
    host_name = meeting.get("host", meeting.get("user_name", ""))
    host_email = meeting.get("host_email", meeting.get("user_email", ""))
    host_display = f"{host_name} ({host_email})" if host_name else host_email
    duration = meeting.get("duration", 0)
    start_time = format_time(meeting.get("start_time", ""))
    end_time = format_time(meeting.get("end_time", ""))
    participant_count = meeting.get("participants_count", len(participants))

    writer.writerow([
        "Topic", "ID", "Host", "Duration (minutes)",
        "Start time", "End time", "Participants",
    ])

    # Row 2: Meeting metadata values
    writer.writerow([
        topic, meeting_id, host_display, duration,
        start_time, end_time, participant_count,
    ])

    # Row 3: Blank
    writer.writerow([])

    # Row 4: Participant column headers (exact names from manual exports)
    writer.writerow([
        "Name (original name)", "Email", "Join time", "Leave time",
        "Duration (minutes)", "Guest", "Recording disclaimer response",
        "In waiting room",
    ])

    # Rows 4+: Participant data
    for p in participants:
        name = p.get("name", p.get("user_name", ""))
        email = p.get("user_email", p.get("email", ""))
        join_time = format_time(p.get("join_time", ""))
        leave_time = format_time(p.get("leave_time", ""))
        # API returns duration in seconds — convert to minutes
        dur_seconds = p.get("duration", 0)
        dur_minutes = round(dur_seconds / 60) if dur_seconds else 0
        # Fields not available from API — use safe defaults
        guest = "Yes"
        recording_disclaimer = ""
        # NOTE: "In waiting room" is not available from the Zoom API.
        # This means waiting_room_bounces in the dashboard will always be 0
        # for meetings fetched via this script (vs manual Zoom CSV exports).
        in_waiting_room = "No"

        writer.writerow([
            name, email, join_time, leave_time, dur_minutes,
            guest, recording_disclaimer, in_waiting_room,
        ])

    return output.getvalue()


def save_csv(meeting: dict, participants: list[dict], output_dir: Path) -> tuple[str, str]:
    """Save meeting data as CSV. Returns (filepath, status)."""
    meeting_id = str(meeting.get("id", ""))
    start_time = meeting.get("start_time", "")

    if start_time:
        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y_%m_%d")
    else:
        date_str = "unknown"

    filename = f"participants_{meeting_id}_{date_str}.csv"
    filepath = output_dir / filename

    csv_content = build_csv(meeting, participants)

    if filepath.exists():
        # Another occurrence on the same date already wrote this file.
        # Keep whichever occurrence had more participants (the others are
        # usually brief test sessions or accidental starts on the same day).
        try:
            existing_lines = filepath.read_text(encoding="utf-8-sig").splitlines()
            existing_count = max(len(existing_lines) - 4, 0)  # minus metadata + blank + header
        except OSError:
            existing_count = 0
        if len(participants) <= existing_count:
            return str(filepath), "skipped"

    # Write with UTF-8 BOM to match manual Zoom exports
    filepath.write_text(csv_content, encoding="utf-8-sig")
    return str(filepath), "created"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Zoom participant data for the MOVEXERCISE8 dashboard"
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--meeting-id", help="Fetch a single meeting by ID")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List meetings without downloading",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()

    # Load credentials
    account_id = os.getenv("ZOOM_ACCOUNT_ID")
    client_id = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    host_email = os.getenv("ZOOM_HOST_EMAIL", "daphniek2021@gmail.com")

    missing = []
    if not account_id:
        missing.append("ZOOM_ACCOUNT_ID")
    if not client_id:
        missing.append("ZOOM_CLIENT_ID")
    if not client_secret:
        missing.append("ZOOM_CLIENT_SECRET")
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Create a .env file with these values (see .env.example)")
        sys.exit(1)

    # Determine date range
    if args.from_date and args.to_date:
        from_date = date.fromisoformat(args.from_date)
        to_date = date.fromisoformat(args.to_date)
    else:
        to_date = date.today()
        from_date = to_date - timedelta(days=args.days)

    print(f"Date range: {from_date} to {to_date}")
    print(f"Host: {host_email}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    client = ZoomClient(account_id, client_id, client_secret, host_email)
    client.authenticate()

    # Fetch meetings
    if args.meeting_id:
        print(f"Fetching single meeting: {args.meeting_id}")
        try:
            meeting = client.get_meeting_detail(args.meeting_id)
            meetings = [meeting]
        except RuntimeError as e:
            print(f"Error fetching meeting {args.meeting_id}: {e}")
            sys.exit(1)
    else:
        print(f"Fetching meetings from {from_date} to {to_date}...")
        all_meetings = client.list_past_meetings(from_date, to_date)
        meetings = [
            m for m in all_meetings
            if TOPIC_FILTER.lower() in m.get("topic", "").lower()
        ]
        print(f"Found {len(all_meetings)} total meeting(s), {len(meetings)} match '{TOPIC_FILTER}'")

    if not meetings:
        print("No meetings found in this date range.")
        return

    # Process each meeting
    created = 0
    skipped = 0
    errors = 0

    for meeting in meetings:
        meeting_id = meeting.get("id", meeting.get("uuid", "unknown"))
        topic = meeting.get("topic", "")
        start = meeting.get("start_time", "")
        print(f"\n  [{meeting_id}] {topic}")
        print(f"    Start: {start}")

        if args.dry_run:
            # Check if file would be skipped
            if start:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y_%m_%d")
            else:
                date_str = "unknown"
            filepath = OUTPUT_DIR / f"participants_{meeting_id}_{date_str}.csv"
            status = "exists" if filepath.exists() else "would create"
            print(f"    -> {status}: {filepath.name}")
            continue

        try:
            # Use UUID (per-occurrence) not meeting ID so recurring
            # meetings return instance-specific participants.
            identifier = meeting.get("uuid") or str(meeting_id)
            participants = client.get_participants(identifier)
            print(f"    Participants: {len(participants)}")

            filepath, status = save_csv(meeting, participants, OUTPUT_DIR)
            print(f"    -> {status}: {Path(filepath).name}")

            if status == "created":
                created += 1
            else:
                skipped += 1
        except RuntimeError as e:
            print(f"    -> ERROR: {e}")
            errors += 1

    # Summary
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  Meetings checked: {len(meetings)}")
    if not args.dry_run:
        print(f"  Files created:    {created}")
        print(f"  Files skipped:    {skipped}")
        if errors:
            print(f"  Errors:           {errors}")
    print()


if __name__ == "__main__":
    main()
