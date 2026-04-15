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


# ---------------------------------------------------------------------------
# Installment-aware revenue math
# ---------------------------------------------------------------------------

def _drop_refunds(df: pd.DataFrame) -> pd.DataFrame:
    if "is_refund" in df.columns:
        return df[~df["is_refund"]].copy()
    return df.copy()


def installment_plan_length(amount: float) -> int:
    # Anchors: 232 → 12mo, 458 → 6mo, 907 → 3mo. Ranges absorb near-values (470, 910).
    if amount <= 350:
        return 12
    if amount <= 700:
        return 6
    return 3


def months_elapsed(signup: pd.Timestamp, today: pd.Timestamp, plan_length: int) -> int:
    if pd.isna(signup):
        return 0
    # Signup month counts as month 1
    elapsed = (today.year - signup.year) * 12 + (today.month - signup.month) + 1
    return max(0, min(elapsed, plan_length))


def compute_buyer_balance(row, today: pd.Timestamp, course_fee_full: float) -> dict:
    status = str(row.get("status", "")).strip()
    amount = row.get("amount")
    if pd.isna(amount):
        amount = 0.0
    amount = float(amount)

    course_fee = float(course_fee_full)
    if status == "Installment" and amount >= course_fee:
        # Full fee paid upfront despite "Installment" label — treat as done.
        total = amount
        collected = amount
        outstanding = 0.0
    elif status == "Installment":
        plan = installment_plan_length(amount)
        paid_months = months_elapsed(row["date"], today, plan)
        total = amount * plan
        collected = amount * paid_months
        outstanding = total - collected
    elif status == "Deposit":
        total = float(course_fee_full)
        collected = amount
        outstanding = max(0.0, total - collected)
    else:  # Confirmed (or anything else)
        total = amount
        collected = amount if bool(row.get("payment_complete", False)) else 0.0
        outstanding = total - collected

    return {"total": total, "collected": collected, "outstanding": outstanding}


def _balances_frame(purchases: pd.DataFrame, course_fee_full: float, today: pd.Timestamp) -> pd.DataFrame:
    df = _drop_refunds(purchases)
    records = df.apply(
        lambda r: compute_buyer_balance(r, today, course_fee_full), axis=1
    )
    bal = pd.DataFrame(list(records), index=df.index)
    return df.join(bal)


def calculate_revenue_metrics(
    purchases: pd.DataFrame,
    course_fee_full: float = 2688,
    today: pd.Timestamp | None = None,
) -> dict:
    today = today or pd.Timestamp(date.today())
    df = _balances_frame(purchases, course_fee_full, today)

    total_revenue = float(df["total"].sum())
    collected = float(df["collected"].sum())
    outstanding = float(df["outstanding"].sum())

    # This/last month — signup-based (sum of raw `amount` where date in that month)
    this_month = today.to_period("M")
    last_month = (today - pd.DateOffset(months=1)).to_period("M")
    month_periods = df["date"].dt.to_period("M")
    this_month_rev = float(df.loc[month_periods == this_month, "amount"].fillna(0).sum())
    last_month_rev = float(df.loc[month_periods == last_month, "amount"].fillna(0).sum())

    return {
        "total_revenue": total_revenue,
        "collected_revenue": collected,
        "outstanding_revenue": outstanding,
        "avg_per_buyer": round(total_revenue / len(df), 2) if len(df) else 0.0,
        "total_transactions": len(df),
        "this_month_revenue": this_month_rev,
        "last_month_revenue": last_month_rev,
        "this_month_label": this_month.strftime("%b %Y"),
        "last_month_label": last_month.strftime("%b %Y"),
        "revenue_by_status": df.groupby("status")["total"].sum().to_dict(),
        "revenue_by_method": df.groupby("payment_method")["total"].sum().to_dict(),
    }


def get_revenue_by_status(
    purchases: pd.DataFrame,
    course_fee_full: float = 2688,
    today: pd.Timestamp | None = None,
) -> pd.DataFrame:
    today = today or pd.Timestamp(date.today())
    df = _balances_frame(purchases, course_fee_full, today)
    return (
        df.groupby("status")["total"].sum()
        .reset_index()
        .rename(columns={"total": "revenue"})
        .sort_values("revenue", ascending=False)
        .reset_index(drop=True)
    )


def get_revenue_by_payment_method(
    purchases: pd.DataFrame,
    course_fee_full: float = 2688,
    today: pd.Timestamp | None = None,
) -> pd.DataFrame:
    today = today or pd.Timestamp(date.today())
    df = _balances_frame(purchases, course_fee_full, today)
    return (
        df.groupby("payment_method")["total"].sum()
        .reset_index()
        .rename(columns={"total": "revenue"})
        .sort_values("revenue", ascending=False)
        .reset_index(drop=True)
    )


def calculate_webinar_summary(webinars_dict: dict, min_attendees: int = 0) -> list[dict]:
    # Group sessions by meeting_id, dropping tiny sessions (likely personal meetings)
    by_meeting: dict[str, list] = {}
    for key, w in webinars_dict.items():
        if w["unique_attendees"] < min_attendees:
            continue
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
        day1_emails: set = set()
        day2_emails: set = set()
        if day2:
            day1_emails = set(day1["participants"]["Email"].dropna())
            day2_emails = set(day2["participants"]["Email"].dropna())
            if day1_att > 0:
                returned = len(day1_emails & day2_emails)
                retention = round(returned / len(day1_emails) * 100, 1) if day1_emails else 0.0

        # True unique attendees across Day 1 + Day 2 (dedup via email union).
        # Fall back to additive count if email coverage is incomplete.
        if day2:
            if day1_emails and day2_emails and len(day1_emails) == day1_att and len(day2_emails) == day2_att:
                total_unique = len(day1_emails | day2_emails)
            else:
                total_unique = day1_att + day2_att
        else:
            total_unique = day1_att

        bounced = day1["waiting_room_bounces"] + (day2["waiting_room_bounces"] if day2 else 0)
        at_offer = int(day1.get("present_at_offer", round(day1_att * day1["stayed_120plus_pct"] / 100)))

        summaries.append({
            "meeting_id": mid,
            "label": day1["date"],
            "day1_attendees": day1_att,
            "day2_attendees": day2_att,
            "day1_peak": int(day1.get("peak_attendance", 0)),
            "day2_peak": int(day2.get("peak_attendance", 0)) if day2 else 0,
            "total_unique": total_unique,
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
    df = _drop_refunds(purchases)
    rows = []
    for status, grp in df.groupby("status"):
        total = len(grp)
        complete = int(grp["payment_complete"].sum())
        rows.append({
            "status": status,
            "complete": complete,
            "total": total,
            "pct": round(complete / total * 100, 1) if total else 0.0,
        })
    return rows


def get_monthly_revenue(purchases: pd.DataFrame) -> pd.DataFrame:
    df = _drop_refunds(purchases)
    df = df[df["amount"] > 0].copy()
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


def get_outstanding_payments(
    purchases: pd.DataFrame,
    course_fee_full: float = 2688,
    today: pd.Timestamp | None = None,
) -> pd.DataFrame:
    today = today or pd.Timestamp(date.today())
    df = _balances_frame(purchases, course_fee_full, today)
    df = df[df["outstanding"] > 0].copy()
    # The `amount` column in the output = outstanding balance (per user spec).
    df["amount"] = df["outstanding"]
    return (
        df[["name", "phone", "amount", "status", "date"]]
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


# ---------------------------------------------------------------------------
# Cohort Analysis
# ---------------------------------------------------------------------------

def build_monthly_cohorts(
    leads: pd.DataFrame, purchases: pd.DataFrame,
) -> pd.DataFrame:
    """Group leads by registration month, track conversions and revenue."""
    leads_c = leads.copy()
    leads_c["month"] = leads_c["date"].dt.to_period("M").astype(str)

    purchase_emails = set(purchases["norm_email"].dropna())
    purchase_phones = set(purchases["norm_phone"].dropna())

    # Build purchase lookup by email/phone → amount, payment_complete
    purchase_by_email: dict[str, dict] = {}
    purchase_by_phone: dict[str, dict] = {}
    for _, row in purchases.iterrows():
        amt = row["amount"] if pd.notna(row["amount"]) else 0.0
        info = {"amount": amt, "paid": row["payment_complete"]}
        if pd.notna(row.get("norm_email")):
            purchase_by_email[row["norm_email"]] = info
        if pd.notna(row.get("norm_phone")):
            purchase_by_phone[row["norm_phone"]] = info

    rows = []
    for month, grp in leads_c.groupby("month"):
        total = len(grp)
        converted = grp["converted"].sum()
        # Calculate revenue for this cohort
        revenue = 0.0
        paid_count = 0
        for _, lead in grp[grp["converted"]].iterrows():
            info = None
            if pd.notna(lead.get("norm_phone")) and lead["norm_phone"] in purchase_by_phone:
                info = purchase_by_phone[lead["norm_phone"]]
            elif pd.notna(lead.get("norm_email")) and lead["norm_email"] in purchase_by_email:
                info = purchase_by_email[lead["norm_email"]]
            if info:
                revenue += info["amount"]
                if info["paid"]:
                    paid_count += 1

        conv_rate = round(converted / total * 100, 1) if total else 0.0
        rows.append({
            "month": month,
            "leads": total,
            "buyers": int(converted),
            "paid": paid_count,
            "conversion_rate": conv_rate,
            "revenue": revenue,
        })

    return pd.DataFrame(rows).sort_values("month").reset_index(drop=True)


def build_webinar_cohorts(
    leads: pd.DataFrame,
    purchases: pd.DataFrame,
    webinars: dict,
    objections: pd.DataFrame,
) -> pd.DataFrame:
    """Build per-webinar cohort: attendees, buyers matched, objections, conversion."""
    from utils.metrics import calculate_webinar_summary
    summaries = calculate_webinar_summary(webinars)

    # Collect attendee emails per webinar (by meeting_id)
    attendee_emails_by_mid: dict[str, set] = {}
    for key, w in webinars.items():
        mid = w["meeting_id"]
        emails = set(w["participants"]["Email"].dropna().str.strip().str.lower())
        attendee_emails_by_mid.setdefault(mid, set()).update(emails)

    # Purchase lookup by email
    purchase_by_email: dict[str, dict] = {}
    for _, row in purchases.iterrows():
        if pd.notna(row.get("norm_email")):
            purchase_by_email[row["norm_email"]] = {
                "amount": row["amount"],
                "paid": row["payment_complete"],
                "status": row["status"],
            }

    # Map objection webinar_date labels to rough counts
    obj_counts = objections["webinar_date"].value_counts().to_dict()

    rows = []
    for s in summaries:
        mid = s["meeting_id"]
        attendee_emails = attendee_emails_by_mid.get(mid, set())
        total_attendees = s["day1_attendees"]

        # Match attendees to purchases
        buyers = 0
        revenue = 0.0
        paid = 0
        for email in attendee_emails:
            if email in purchase_by_email:
                buyers += 1
                revenue += purchase_by_email[email]["amount"]
                if purchase_by_email[email]["paid"]:
                    paid += 1

        # Match objections — fuzzy match on date label
        obj_count = 0
        label = s["label"]  # e.g. "2026-01-28"
        for obj_label, cnt in obj_counts.items():
            # Check if the webinar date overlaps with the objection label
            if label[5:7] in obj_label and label[8:10] in obj_label:
                obj_count += cnt

        conv_rate = round(buyers / total_attendees * 100, 1) if total_attendees else 0.0
        at_offer = s["at_offer"]
        offer_conv = round(buyers / at_offer * 100, 1) if at_offer else 0.0

        rows.append({
            "webinar_date": label,
            "meeting_id": mid,
            "attendees": total_attendees,
            "day2_attendees": s["day2_attendees"],
            "avg_duration": s["avg_duration"],
            "stayed_120plus_pct": s["stayed_120plus_pct"],
            "at_offer": at_offer,
            "buyers": buyers,
            "objections": obj_count,
            "revenue": revenue,
            "paid": paid,
            "conversion_rate": conv_rate,
            "offer_conversion_rate": offer_conv,
            "retention": s["retention"],
        })

    return pd.DataFrame(rows).sort_values("webinar_date").reset_index(drop=True)


def build_cohort_heatmap(webinar_cohorts: pd.DataFrame) -> pd.DataFrame:
    """Build a stage-based heatmap: rows = webinars, columns = funnel stages as %."""
    rows = []
    for _, r in webinar_cohorts.iterrows():
        att = r["attendees"] if r["attendees"] else 1
        rows.append({
            "webinar": r["webinar_date"],
            "Attended": 100.0,
            "Stayed 120+ min": r["stayed_120plus_pct"],
            "At Offer": round(r["at_offer"] / att * 100, 1),
            "Bought": r["conversion_rate"],
            "Paid": round(r["paid"] / att * 100, 1) if att else 0.0,
        })
    return pd.DataFrame(rows)


def calculate_cohort_summary(
    monthly: pd.DataFrame, webinar: pd.DataFrame,
) -> dict:
    """Summary stats for hero cards."""
    total_months = len(monthly)
    total_webinars = len(webinar)

    best_month = monthly.loc[monthly["conversion_rate"].idxmax()] if len(monthly) else None
    worst_month = monthly.loc[monthly["conversion_rate"].idxmin()] if len(monthly) else None

    best_webinar = webinar.loc[webinar["conversion_rate"].idxmax()] if len(webinar) else None
    avg_conv = round(webinar["conversion_rate"].mean(), 1) if len(webinar) else 0.0

    return {
        "total_months": total_months,
        "total_webinars": total_webinars,
        "best_month": best_month["month"] if best_month is not None else "N/A",
        "best_month_rate": best_month["conversion_rate"] if best_month is not None else 0.0,
        "worst_month": worst_month["month"] if worst_month is not None else "N/A",
        "worst_month_rate": worst_month["conversion_rate"] if worst_month is not None else 0.0,
        "best_webinar_date": best_webinar["webinar_date"] if best_webinar is not None else "N/A",
        "best_webinar_rate": best_webinar["conversion_rate"] if best_webinar is not None else 0.0,
        "avg_webinar_conv": avg_conv,
    }


# ---------------------------------------------------------------------------
# Ad Spend & ROI
# ---------------------------------------------------------------------------

def calculate_ad_overview(meta: pd.DataFrame) -> dict:
    """Overall ad spend summary stats."""
    total_spend = float(meta["amount_spent"].sum())
    total_results = float(meta["results"].sum())
    total_clicks = float(meta["link_clicks"].sum())
    total_impressions = float(meta["impressions"].sum())
    total_reach = float(meta["reach"].sum())

    cpl = round(total_spend / total_results, 2) if total_results else 0.0
    cpc = round(total_spend / total_clicks, 2) if total_clicks else 0.0
    ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions else 0.0

    return {
        "total_spend": total_spend,
        "total_results": int(total_results),
        "total_clicks": int(total_clicks),
        "total_impressions": int(total_impressions),
        "total_reach": int(total_reach),
        "cpl": cpl,
        "cpc": cpc,
        "ctr": ctr,
    }


def calculate_ad_performance(meta: pd.DataFrame) -> pd.DataFrame:
    """Per-ad performance metrics. Only includes ads with spend > 0."""
    active = meta[meta["amount_spent"] > 0].copy()
    active["cpl"] = active.apply(
        lambda r: round(r["amount_spent"] / r["results"], 2)
        if pd.notna(r["results"]) and r["results"] > 0 else None,
        axis=1,
    )
    active["cpc"] = active.apply(
        lambda r: round(r["amount_spent"] / r["link_clicks"], 2)
        if pd.notna(r["link_clicks"]) and r["link_clicks"] > 0 else None,
        axis=1,
    )
    active["ctr"] = active.apply(
        lambda r: round(r["link_clicks"] / r["impressions"] * 100, 2)
        if pd.notna(r["impressions"]) and r["impressions"] > 0 else None,
        axis=1,
    )
    active["creative_type"] = active["ad_name"].apply(
        lambda n: "Video" if "Video" in n else ("Image" if "Image" in n else "Other")
    )
    return active.sort_values("amount_spent", ascending=False).reset_index(drop=True)


def calculate_creative_comparison(meta: pd.DataFrame) -> pd.DataFrame:
    """Compare Video vs Image ad performance."""
    active = meta[meta["amount_spent"] > 0].copy()
    active["creative_type"] = active["ad_name"].apply(
        lambda n: "Video" if "Video" in n else ("Image" if "Image" in n else "Other")
    )
    grouped = active.groupby("creative_type").agg(
        ads=("ad_name", "count"),
        spend=("amount_spent", "sum"),
        results=("results", "sum"),
        clicks=("link_clicks", "sum"),
        impressions=("impressions", "sum"),
    ).reset_index()
    grouped["cpl"] = grouped.apply(
        lambda r: round(r["spend"] / r["results"], 2) if r["results"] > 0 else 0.0, axis=1
    )
    grouped["ctr"] = grouped.apply(
        lambda r: round(r["clicks"] / r["impressions"] * 100, 2) if r["impressions"] > 0 else 0.0, axis=1
    )
    return grouped


def calculate_ad_quality(meta: pd.DataFrame) -> dict:
    """Distribution of quality, engagement, and conversion rankings."""
    active = meta[(meta["amount_spent"] > 0) & (meta["quality_ranking"] != "-")]
    result = {}
    for col in ["quality_ranking", "engagement_ranking", "conversion_ranking"]:
        counts = active[col].value_counts().reset_index()
        counts.columns = ["ranking", "count"]
        result[col] = counts
    return result


def calculate_ad_roi(
    meta: pd.DataFrame,
    leads: pd.DataFrame,
    purchases: pd.DataFrame,
    config: dict,
) -> dict:
    """Calculate ROI by linking ads → leads (via utm_content) → purchases."""
    total_spend = float(meta["amount_spent"].sum())
    total_revenue = float(purchases["amount"].sum())
    roas = round(total_revenue / total_spend, 2) if total_spend else 0.0

    # Track leads attributable to ads via utm_content
    ad_names = set(meta["ad_name"].dropna())
    attributed_leads = leads[leads["utm_content"].isin(ad_names)]
    attributed_count = len(attributed_leads)

    # Match attributed leads to purchases
    purchase_emails = set(purchases["norm_email"].dropna())
    purchase_phones = set(purchases["norm_phone"].dropna())
    attributed_converted = attributed_leads[
        attributed_leads["norm_email"].isin(purchase_emails)
        | attributed_leads["norm_phone"].isin(purchase_phones)
    ]
    attributed_buyers = len(attributed_converted)

    # Revenue from attributed buyers
    attributed_revenue = 0.0
    purchase_by_phone: dict[str, float] = {}
    purchase_by_email: dict[str, float] = {}
    for _, row in purchases.iterrows():
        amt = row["amount"] if pd.notna(row["amount"]) else 0.0
        if pd.notna(row.get("norm_phone")):
            purchase_by_phone[row["norm_phone"]] = amt
        if pd.notna(row.get("norm_email")):
            purchase_by_email[row["norm_email"]] = amt

    seen = set()
    for _, lead in attributed_converted.iterrows():
        key = lead.get("norm_phone") or lead.get("norm_email")
        if key in seen:
            continue
        seen.add(key)
        if pd.notna(lead.get("norm_phone")) and lead["norm_phone"] in purchase_by_phone:
            attributed_revenue += purchase_by_phone[lead["norm_phone"]]
        elif pd.notna(lead.get("norm_email")) and lead["norm_email"] in purchase_by_email:
            attributed_revenue += purchase_by_email[lead["norm_email"]]

    attributed_roas = round(attributed_revenue / total_spend, 2) if total_spend else 0.0
    course_fee = config.get("course_fee_full", 0)
    breakeven_leads = int(total_spend / course_fee) + 1 if course_fee else 0

    return {
        "total_spend": total_spend,
        "total_revenue": total_revenue,
        "roas": roas,
        "attributed_leads": attributed_count,
        "attributed_buyers": attributed_buyers,
        "attributed_revenue": attributed_revenue,
        "attributed_roas": attributed_roas,
        "utm_tracking_pct": round(attributed_count / len(leads) * 100, 1) if len(leads) else 0.0,
        "breakeven_sales": breakeven_leads,
        "actual_sales": len(purchases),
    }


def get_top_ads(meta: pd.DataFrame, n: int = 5, by: str = "results") -> pd.DataFrame:
    """Top N ads by a given metric."""
    active = meta[(meta["amount_spent"] > 0) & (meta["results"] > 0)].copy()
    active["cpl"] = (active["amount_spent"] / active["results"]).round(2)
    return active.nlargest(n, by)[["ad_name", "amount_spent", "results", "cpl"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Webinar diagnostics — per-event deep dives
# ---------------------------------------------------------------------------

def calculate_exit_histogram(
    participants_df: pd.DataFrame,
    bucket_minutes: int = 5,
) -> pd.DataFrame:
    """Histogram of leave-times in fixed-width buckets from minute 0."""
    if participants_df.empty or "leave_min" not in participants_df.columns:
        return pd.DataFrame(columns=["minute_bucket", "bucket_start", "exits"])

    leaves = participants_df["leave_min"].dropna()
    if leaves.empty:
        return pd.DataFrame(columns=["minute_bucket", "bucket_start", "exits"])

    max_min = int(leaves.max()) + bucket_minutes
    edges = list(range(0, max_min + bucket_minutes, bucket_minutes))

    rows = []
    for start in edges[:-1]:
        end = start + bucket_minutes
        count = int(((leaves >= start) & (leaves < end)).sum())
        rows.append({
            "minute_bucket": f"{start}-{end}",
            "bucket_start": start,
            "exits": count,
        })
    return pd.DataFrame(rows)


def calculate_engagement_windows(
    participants_df: pd.DataFrame,
    meeting_duration: int,
) -> list[dict]:
    """Retention across four fixed diagnostic windows.

    present(t)  = rows where join_min <= t AND leave_min > t.
    start_count = peak attendance during [start, end] sampled every minute,
                  so late joiners don't produce >100% retention.
    end_count   = present(end).
    """
    if participants_df.empty:
        labels = [
            "First impression (0-30min)",
            "Content hook (30-90min)",
            "Offer approach (90-120min)",
            "Decision window (120-end)",
        ]
        return [
            {"window": lbl, "start_count": 0, "end_count": 0, "retention_pct": 0.0}
            for lbl in labels
        ]

    joins = participants_df["join_min"].to_numpy()
    leaves = participants_df["leave_min"].to_numpy()

    # Effective end = last integer minute where anyone was still present.
    # Avoids 0% retention on the Decision window when leave_min tops out a hair
    # below the reported meeting duration.
    effective_end = int(min(meeting_duration, max(1, int(leaves.max()))))
    end = max(effective_end, 120)
    boundaries = [
        ("First impression (0-30min)", 0, 30),
        ("Content hook (30-90min)", 30, 90),
        ("Offer approach (90-120min)", 90, 120),
        ("Decision window (120-end)", 120, end),
    ]

    def _present(t: int) -> int:
        return int(((joins <= t) & (leaves >= t)).sum())

    def _peak(a: int, b: int) -> int:
        if b <= a:
            return _present(a)
        return max(_present(t) for t in range(a, b + 1))

    rows = []
    for label, start_t, end_t in boundaries:
        start_count = _peak(start_t, end_t)
        end_count = _present(end_t)
        pct = round(end_count / start_count * 100, 1) if start_count else 0.0
        rows.append({
            "window": label,
            "start_count": start_count,
            "end_count": end_count,
            "retention_pct": pct,
        })
    return rows


def _event_sales(
    purchases_df: pd.DataFrame,
    day1_date: str,
    day2_date: str | None,
) -> pd.DataFrame:
    """Rows in purchases_df whose inferred_webinar matches day1 or day2."""
    if purchases_df.empty or "inferred_webinar" not in purchases_df.columns:
        return purchases_df.iloc[0:0]
    dates = [d for d in [day1_date, day2_date] if d]
    return purchases_df[purchases_df["inferred_webinar"].isin(dates)]


def calculate_offer_conversion(
    event_summary: dict,
    purchases_df: pd.DataFrame,
    all_events: list[dict],
    webinars_dict: dict,
) -> dict:
    """Offer-moment conversion for one event plus the all-time average."""
    mid = event_summary["meeting_id"]
    day1_date, day2_date = get_event_day_dates(webinars_dict, mid)
    sales = len(_event_sales(purchases_df, day1_date, day2_date))
    people = int(event_summary.get("at_offer", 0))
    conv = round(sales / people * 100, 1) if people else 0.0

    others = []
    for ev in all_events:
        ev_mid = ev["meeting_id"]
        ev_d1, ev_d2 = get_event_day_dates(webinars_dict, ev_mid)
        ev_people = int(ev.get("at_offer", 0))
        if ev_people <= 0:
            continue
        ev_sales = len(_event_sales(purchases_df, ev_d1, ev_d2))
        others.append(ev_sales / ev_people * 100)

    avg = round(sum(others) / len(others), 1) if others else 0.0
    return {
        "people_at_offer": people,
        "sales": sales,
        "offer_conversion_pct": conv,
        "all_time_avg_pct": avg,
        "above_avg": conv >= avg,
    }


def calculate_webinar_health(
    event_summary: dict,
    sales_count: int,
) -> str:
    """Traffic-light rating from avg_duration, stayed_120plus_pct, sales."""
    avg_dur = event_summary.get("avg_duration", 0)
    stayed = event_summary.get("stayed_120plus_pct", 0)

    if sales_count == 0:
        return "red"

    failed = 0
    if avg_dur <= 100:
        failed += 1
    if stayed <= 50:
        failed += 1
    if sales_count < 3:
        failed += 1

    if failed == 0:
        return "green"
    if failed == 1:
        return "yellow"
    return "red"


def get_event_day_dates(
    webinars_dict: dict,
    meeting_id: str,
) -> tuple[str | None, str | None]:
    """Return (day1_date, day2_date) ISO strings for a meeting_id."""
    sessions = [w for w in webinars_dict.values() if w["meeting_id"] == meeting_id]
    sessions.sort(key=lambda w: w["date"])
    d1 = sessions[0]["date"] if sessions else None
    d2 = sessions[1]["date"] if len(sessions) > 1 else None
    return d1, d2


def get_event_cohorts(
    webinars_dict: dict,
    meeting_id: str,
) -> dict:
    """Slice the webinars dict to one event with Day 1/Day 2 email sets.

    Emails are lowercased to make comparison with purchases.norm_email safe.
    """
    sessions = [w for w in webinars_dict.values() if w["meeting_id"] == meeting_id]
    sessions.sort(key=lambda w: w["date"])
    day1 = sessions[0] if sessions else None
    day2 = sessions[1] if len(sessions) > 1 else None

    def _emails(w: dict | None) -> set[str]:
        if not w:
            return set()
        return set(
            w["participants"]["Email"].dropna().astype(str).str.strip().str.lower()
        )

    d1_emails = _emails(day1)
    d2_emails = _emails(day2)
    return {
        "day1": day1,
        "day2": day2,
        "day1_emails": d1_emails,
        "day2_emails": d2_emails,
        "both_days": d1_emails & d2_emails,
        "day1_only": d1_emails - d2_emails,
        "day2_only": d2_emails - d1_emails,
    }


# Month abbreviation lookup for matching objections.webinar_date like "Mar 9-10 2026".
_MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def match_objections_for_event(
    objections_df: pd.DataFrame,
    day1_date: str | None,
    day2_date: str | None,
) -> pd.DataFrame:
    """Return objections whose human-written webinar_date matches this event.

    objections.csv uses strings like "Mar 9-10 2026", "Mar 17 2026".
    Match by constructing canonical forms from the event's ISO dates.
    """
    if objections_df.empty or not day1_date:
        return objections_df.iloc[0:0]

    d1 = pd.Timestamp(day1_date)
    month = _MONTH_ABBR[d1.month]
    year = d1.year
    candidates = {
        f"{month} {d1.day} {year}",
    }
    if day2_date:
        d2 = pd.Timestamp(day2_date)
        if d2.month == d1.month and d2.year == d1.year:
            candidates.add(f"{month} {d1.day}-{d2.day} {year}")
        candidates.add(f"{_MONTH_ABBR[d2.month]} {d2.day} {year}")

    raw = objections_df["webinar_date"].fillna("").astype(str).str.strip()
    return objections_df[raw.isin(candidates)]
