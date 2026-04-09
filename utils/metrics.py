from __future__ import annotations

from datetime import date

import pandas as pd


def calculate_funnel_metrics(leads: pd.DataFrame, purchases: pd.DataFrame) -> dict:
    total_leads = len(leads)
    total_buyers = len(purchases)
    confirmed = int((purchases["status"] == "Confirmed").sum())
    installment = int((purchases["status"] == "Installment").sum())
    deposit = int((purchases["status"] == "Deposit").sum())
    payment_complete = int(purchases["payment_complete"].sum())

    return {
        "total_leads": total_leads,
        "total_buyers": total_buyers,
        "confirmed_buyers": confirmed,
        "installment_buyers": installment,
        "deposit_buyers": deposit,
        "payment_complete_count": payment_complete,
        "conversion_rate": round(total_buyers / total_leads * 100, 2) if total_leads else 0.0,
        "payment_completion_rate": round(payment_complete / total_buyers * 100, 2) if total_buyers else 0.0,
    }


def calculate_revenue_metrics(purchases: pd.DataFrame) -> dict:
    paid = purchases[purchases["amount"] > 0]
    complete = purchases[purchases["payment_complete"] == True]
    incomplete = purchases[purchases["payment_complete"] == False]

    total_revenue = float(paid["amount"].sum())
    collected = float(complete["amount"].sum())
    outstanding = float(incomplete["amount"].sum())

    revenue_by_status = (
        paid.groupby("status")["amount"].sum().to_dict()
    )
    revenue_by_method = (
        paid.groupby("payment_method")["amount"].sum().to_dict()
    )

    return {
        "total_revenue": total_revenue,
        "collected_revenue": collected,
        "outstanding_revenue": outstanding,
        "avg_per_buyer": round(total_revenue / len(paid), 2) if len(paid) else 0.0,
        "total_transactions": len(paid),
        "revenue_by_status": revenue_by_status,
        "revenue_by_method": revenue_by_method,
    }


def calculate_webinar_summary(webinars_dict: dict) -> list[dict]:
    # Group sessions by meeting_id
    by_meeting: dict[str, list] = {}
    for key, w in webinars_dict.items():
        mid = w["meeting_id"]
        by_meeting.setdefault(mid, []).append(w)

    summaries = []
    for mid, sessions in by_meeting.items():
        sessions.sort(key=lambda s: s["date"])
        day1 = sessions[0]
        day2 = sessions[1] if len(sessions) > 1 else None

        day1_att = day1["unique_attendees"]
        day2_att = day2["unique_attendees"] if day2 else 0

        # Weighted average duration across days
        total_att = day1_att + day2_att
        if total_att > 0:
            avg_dur = round(
                (day1["avg_duration"] * day1_att + (day2["avg_duration"] * day2_att if day2 else 0))
                / total_att, 1
            )
        else:
            avg_dur = 0.0

        stayed_pct = round(
            (day1["stayed_120plus_pct"] * day1_att + (day2["stayed_120plus_pct"] * day2_att if day2 else 0))
            / total_att, 1
        ) if total_att > 0 else 0.0

        left_pct = round(
            (day1["left_30min_pct"] * day1_att + (day2["left_30min_pct"] * day2_att if day2 else 0))
            / total_att, 1
        ) if total_att > 0 else 0.0

        # Retention: % of Day 1 attendees who came back for Day 2
        retention = 0.0
        if day2 and day1_att > 0:
            day1_emails = set(day1["participants"]["Email"].dropna())
            day2_emails = set(day2["participants"]["Email"].dropna())
            returned = len(day1_emails & day2_emails)
            retention = round(returned / len(day1_emails) * 100, 1) if day1_emails else 0.0

        bounced = day1["waiting_room_bounces"] + (day2["waiting_room_bounces"] if day2 else 0)
        at_offer = int(day1_att * day1["stayed_120plus_pct"] / 100)

        summaries.append({
            "meeting_id": mid,
            "label": day1["date"],
            "day1_attendees": day1_att,
            "day2_attendees": day2_att,
            "avg_duration": avg_dur,
            "stayed_120plus_pct": stayed_pct,
            "left_30min_pct": left_pct,
            "retention": retention,
            "waiting_bounced": bounced,
            "at_offer": at_offer,
        })

    summaries.sort(key=lambda s: s["label"])
    return summaries


def find_best_worst_webinars(
    event_summaries: list[dict],
) -> tuple[dict | None, dict | None]:
    if not event_summaries:
        return None, None
    best = max(event_summaries, key=lambda e: e["avg_duration"])
    worst = min(event_summaries, key=lambda e: e["avg_duration"])
    return best, worst


def calculate_period_comparison(
    df: pd.DataFrame,
    date_col: str,
    current_days: int = 7,
    previous_days: int = 7,
) -> dict:
    today = pd.Timestamp(date.today())
    current_start = today - pd.Timedelta(days=current_days)
    previous_start = current_start - pd.Timedelta(days=previous_days)

    dates = pd.to_datetime(df[date_col], errors="coerce")
    current_count = int(((dates >= current_start) & (dates <= today)).sum())
    previous_count = int(((dates >= previous_start) & (dates < current_start)).sum())

    if previous_count == 0:
        change_pct = 100.0 if current_count > 0 else 0.0
    else:
        change_pct = round((current_count - previous_count) / previous_count * 100, 1)

    if change_pct > 0:
        direction = "up"
    elif change_pct < 0:
        direction = "down"
    else:
        direction = "flat"

    return {
        "current_count": current_count,
        "previous_count": previous_count,
        "change_pct": change_pct,
        "change_direction": direction,
    }


def get_payment_completion_by_status(purchases: pd.DataFrame) -> list[dict]:
    rows = []
    for status, grp in purchases.groupby("status"):
        total = len(grp)
        complete = int(grp["payment_complete"].sum())
        rows.append({
            "status": status,
            "complete": complete,
            "total": total,
            "pct": round(complete / total * 100, 1) if total else 0.0,
        })
    return rows


def get_top_customers(purchases: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return (
        purchases.nlargest(n, "amount")[["name", "amount", "status", "payment_method"]]
        .reset_index(drop=True)
    )


def get_monthly_revenue(purchases: pd.DataFrame) -> pd.DataFrame:
    df = purchases[purchases["amount"] > 0].copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return (
        df.groupby("month")["amount"].sum()
        .reset_index()
        .rename(columns={"amount": "revenue"})
        .sort_values("month")
        .reset_index(drop=True)
    )


def calculate_lead_to_sale_times(
    leads: pd.DataFrame, purchases: pd.DataFrame,
) -> list[int]:
    """For each buyer, find days between earliest lead registration and purchase."""
    # Build lookup: earliest lead date by norm_email and norm_phone
    email_first = leads.dropna(subset=["norm_email"]).groupby("norm_email")["date"].min()
    phone_first = leads.dropna(subset=["norm_phone"]).groupby("norm_phone")["date"].min()

    days = []
    for _, row in purchases.iterrows():
        lead_date = None
        if pd.notna(row.get("norm_email")) and row["norm_email"] in email_first.index:
            lead_date = email_first[row["norm_email"]]
        if pd.notna(row.get("norm_phone")) and row["norm_phone"] in phone_first.index:
            phone_date = phone_first[row["norm_phone"]]
            if lead_date is None or phone_date < lead_date:
                lead_date = phone_date
        if lead_date is not None and pd.notna(row["date"]):
            diff = (row["date"] - lead_date).days
            if diff >= 0:
                days.append(int(diff))
    return days


def calculate_funnel_stages(
    leads: pd.DataFrame,
    purchases: pd.DataFrame,
    webinars: dict,
    objections: pd.DataFrame,
) -> list[tuple[str, int]]:
    total_leads = len(leads)

    # Unique webinar registrants (using attendee emails as proxy)
    attendee_emails = set()
    for w in webinars.values():
        attendee_emails.update(w["participants"]["Email"].dropna())
    webinar_attended = len(attendee_emails)

    # "Bonus messaged" = objections + buyers (anyone who engaged post-webinar)
    bonus_messaged = len(objections) + len(purchases)

    total_buyers = len(purchases)
    payment_complete = int(purchases["payment_complete"].sum())

    return [
        ("All Leads", total_leads),
        ("Webinar Attended", webinar_attended),
        ("Bonus Messaged", bonus_messaged),
        ("Sale", total_buyers),
        ("Payment Complete", payment_complete),
    ]


def calculate_dropoff_curve(
    participants: pd.DataFrame, interval: int = 15,
) -> pd.DataFrame:
    """Count unique attendees present at each minute mark."""
    if participants.empty:
        return pd.DataFrame(columns=["minute", "attendees"])
    max_min = int(participants["leave_min"].max()) + 1
    marks = list(range(0, max_min + interval, interval))
    rows = []
    for mark in marks:
        present = participants[
            (participants["join_min"] <= mark) & (participants["leave_min"] >= mark)
        ]["Email"].nunique()
        rows.append({"minute": mark, "attendees": present})
    return pd.DataFrame(rows)


def calculate_engagement_trend(event_summaries: list[dict]) -> dict | None:
    """Compare avg_duration of last 3 webinars vs the 3 before that."""
    if len(event_summaries) < 6:
        return None
    recent = event_summaries[-3:]
    previous = event_summaries[-6:-3]
    recent_avg = sum(e["avg_duration"] for e in recent) / 3
    prev_avg = sum(e["avg_duration"] for e in previous) / 3
    change_pct = round((recent_avg - prev_avg) / prev_avg * 100, 1) if prev_avg else 0.0
    return {
        "recent_avg": round(recent_avg, 1),
        "previous_avg": round(prev_avg, 1),
        "change_pct": change_pct,
        "declining": change_pct < 0,
    }


def get_outstanding_payments(purchases: pd.DataFrame) -> pd.DataFrame:
    unpaid = purchases[purchases["payment_complete"] == False].copy()
    today = pd.Timestamp(date.today())
    unpaid["days_overdue"] = (today - unpaid["date"]).dt.days
    return (
        unpaid[["name", "phone", "amount", "status", "date", "days_overdue"]]
        .sort_values("amount", ascending=False)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Failed Leads / Objections
# ---------------------------------------------------------------------------

RECOVERABLE_CATEGORIES = {"Still Considering", "Not Ready / Timing", "Spouse Buy-in"}
POSSIBLY_RECOVERABLE_KEYWORDS = ["deposit", "future", "high intent", "will come back",
                                  "still engaging", "pending", "reserved"]
UNLIKELY_CATEGORIES = {"Went Silent", "Skepticism", "Prefers Physical", "Other"}


def calculate_objection_breakdown(objections: pd.DataFrame) -> pd.DataFrame:
    counts = objections["category"].value_counts().reset_index()
    counts.columns = ["category", "count"]
    total = counts["count"].sum()
    counts["pct"] = (counts["count"] / total * 100).round(1)
    return counts


def calculate_objection_by_webinar(objections: pd.DataFrame) -> pd.DataFrame:
    ct = pd.crosstab(objections["webinar_date"], objections["category"])
    # Melt into long format for grouped bar chart
    ct = ct.reset_index().melt(id_vars="webinar_date", var_name="category", value_name="count")
    return ct[ct["count"] > 0].reset_index(drop=True)


def classify_recoverability(objections: pd.DataFrame) -> pd.DataFrame:
    df = objections.copy()

    def _classify(row):
        cat = row.get("category", "")
        notes = str(row.get("notes", "")).lower()
        if cat in RECOVERABLE_CATEGORIES:
            return "Recoverable"
        if cat == "Financial Constraint":
            if any(kw in notes for kw in POSSIBLY_RECOVERABLE_KEYWORDS):
                return "Possibly Recoverable"
            return "Unlikely"
        return "Unlikely"

    df["recoverable"] = df.apply(_classify, axis=1)
    return df


def calculate_child_profile(objections: pd.DataFrame) -> dict:
    # Age distribution — bucket into ranges
    ages = objections["child_age"].dropna()
    if len(ages):
        def _age_bucket(a):
            if a <= 3:
                return "0–3"
            if a <= 6:
                return "4–6"
            if a <= 9:
                return "7–9"
            if a <= 12:
                return "10–12"
            return "13+"

        bucket_order = ["0–3", "4–6", "7–9", "10–12", "13+"]
        buckets = ages.apply(_age_bucket).value_counts().reindex(bucket_order, fill_value=0)
        age_df = buckets.reset_index()
        age_df.columns = ["age_group", "count"]
    else:
        age_df = pd.DataFrame(columns=["age_group", "count"])

    # Top child issues — split comma-separated values and count
    issues = objections["child_issue"].dropna()
    issue_counts: dict[str, int] = {}
    for val in issues:
        for part in str(val).split(","):
            part = part.strip()
            if part and not part.lower().startswith("not stated"):
                issue_counts[part] = issue_counts.get(part, 0) + 1
    issue_df = (
        pd.DataFrame(list(issue_counts.items()), columns=["issue", "count"])
        .sort_values("count", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    return {"age_distribution": age_df, "top_issues": issue_df}


def calculate_objection_summary(objections: pd.DataFrame) -> dict:
    total = len(objections)
    breakdown = calculate_objection_breakdown(objections)
    top_cat = breakdown.iloc[0]["category"] if len(breakdown) else "N/A"
    top_pct = breakdown.iloc[0]["pct"] if len(breakdown) else 0.0

    classified = classify_recoverability(objections)
    recoverable = int((classified["recoverable"] != "Unlikely").sum())
    recoverable_pct = round(recoverable / total * 100, 1) if total else 0.0

    webinar_batches = objections["webinar_date"].nunique()

    return {
        "total": total,
        "top_category": top_cat,
        "top_category_pct": top_pct,
        "recoverable_count": recoverable,
        "recoverable_pct": recoverable_pct,
        "webinar_batches": webinar_batches,
    }
