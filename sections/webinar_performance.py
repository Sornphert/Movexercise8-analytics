from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.ai import render_ai_insights
from utils.charts import apply_standard_layout
from utils.data_loader import load_participant_detail
from utils.metrics import (
    calculate_dropoff_curve,
    calculate_engagement_windows,
    calculate_exit_histogram,
    calculate_offer_conversion,
    calculate_webinar_health,
    calculate_webinar_summary,
    get_event_cohorts,
    get_event_day_dates,
    match_objections_for_event,
)
from utils.styles import COLORS, alert, metric_card, section_header

OFFER_MINUTE = 120
MIN_DAY1_ATTENDEES = 50  # Exclude small sessions (likely Daphnie's personal meetings)
_HEALTH = {
    "green":  ("🟢 Healthy",    "#40916C"),
    "yellow": ("🟡 Watch list", "#D4A843"),
    "red":    ("🔴 Needs work", "#E76F51"),
}


def render(data: dict):
    webinars = data["webinars"]
    purchases = data["purchases"]
    objections = data["objections"]

    if not webinars:
        st.info("No webinar data loaded.")
        return

    events = calculate_webinar_summary(webinars, min_attendees=MIN_DAY1_ATTENDEES)
    if not events:
        st.info(f"No webinars with at least {MIN_DAY1_ATTENDEES} Day 1 attendees.")
        return
    events_desc = list(reversed(events))
    all_mids = [e["meeting_id"] for e in events_desc]

    if (
        "selected_webinar" not in st.session_state
        or st.session_state["selected_webinar"] not in all_mids
    ):
        st.session_state["selected_webinar"] = events_desc[0]["meeting_id"]

    latest_event = events_desc[0]
    _render_snapshot(latest_event, webinars, purchases, objections)

    _render_all_table(events_desc, webinars, purchases)

    selected_mid = st.session_state["selected_webinar"]
    selected_event = next(
        (e for e in events_desc if e["meeting_id"] == selected_mid),
        latest_event,
    )
    day1_date, day2_date = get_event_day_dates(webinars, selected_mid)

    d1_df, _ = load_participant_detail(day1_date, selected_mid) if day1_date else (pd.DataFrame(), None)
    d2_df, _ = load_participant_detail(day2_date, selected_mid) if day2_date else (pd.DataFrame(), None)

    _render_dropoff(selected_event, d1_df, d2_df, day1_date, day2_date)
    _render_exit_histogram(selected_event, d1_df)
    _render_engagement_windows(selected_event, webinars, d1_df)
    _render_day_breakdown(webinars, selected_mid, purchases)
    _render_offer_conversion(selected_event, events, purchases, webinars)

    _render_ai(events, latest_event, purchases, webinars)


# ─────────────────────────────────────────────────────────────────────
# Section 1 — Latest webinar snapshot
# ─────────────────────────────────────────────────────────────────────

def _render_snapshot(event: dict, webinars: dict, purchases: pd.DataFrame, objections: pd.DataFrame):
    mid = event["meeting_id"]
    cohorts = get_event_cohorts(webinars, mid)
    day1, day2 = cohorts["day1"], cohorts["day2"]
    d1_date, d2_date = get_event_day_dates(webinars, mid)

    event_sales = _sales_for_event(purchases, d1_date, d2_date)
    sales_count = len(event_sales)
    revenue = float(event_sales["amount"].fillna(0).sum()) if sales_count else 0.0

    health = calculate_webinar_health(event, sales_count)
    pill_label, pill_color = _HEALTH[health]

    date_label = _format_date_range(d1_date, d2_date)
    st.markdown(
        f'<div class="hdr" style="background:linear-gradient(135deg,#1B4332,{pill_color});">'
        f'<h1>Latest Webinar — {date_label}</h1>'
        f'<p>{pill_label}</p></div>',
        unsafe_allow_html=True,
    )

    # Group A — Attendance (6 cards)
    day1_att = day1["unique_attendees"] if day1 else 0
    day2_att = day2["unique_attendees"] if day2 else 0
    both = len(cohorts["both_days"])
    d1_only = len(cohorts["day1_only"])
    d2_only = len(cohorts["day2_only"])
    total = len(cohorts["day1_emails"] | cohorts["day2_emails"])

    st.markdown(section_header("Attendance"), unsafe_allow_html=True)
    cols = st.columns(6)
    specs = [
        ("Day 1 Unique", day1_att),
        ("Day 2 Unique", day2_att),
        ("Both Days", both),
        ("Day 1 Only", d1_only),
        ("Day 2 Only", d2_only),
        ("Total Unique", total),
    ]
    for col, (label, val) in zip(cols, specs):
        with col:
            st.markdown(metric_card(label, str(val)), unsafe_allow_html=True)

    # Group B — Engagement
    st.markdown(section_header("Engagement"), unsafe_allow_html=True)
    cols = st.columns(5)
    d1_avg = day1["avg_duration"] if day1 else 0
    d2_avg = day2["avg_duration"] if day2 else 0
    d1_stayed = day1["stayed_120plus_pct"] if day1 else 0
    d2_stayed = day2["stayed_120plus_pct"] if day2 else 0
    retention = round(both / day1_att * 100, 1) if day1_att else 0.0

    eng = [
        ("Avg Watch — Day 1", f"{d1_avg:.0f} min"),
        ("Avg Watch — Day 2", f"{d2_avg:.0f} min" if day2 else "—"),
        ("Stayed 120+ — Day 1", f"{d1_stayed:.1f}%"),
        ("Stayed 120+ — Day 2", f"{d2_stayed:.1f}%" if day2 else "—"),
        ("Day 1 → Day 2 Retention", f"{retention:.1f}%" if day2 else "—"),
    ]
    for col, (label, val) in zip(cols, eng):
        with col:
            st.markdown(metric_card(label, val), unsafe_allow_html=True)

    # Group C — Conversion
    st.markdown(section_header("Conversion"), unsafe_allow_html=True)
    cols = st.columns(4)
    conv_rate = round(sales_count / day1_att * 100, 1) if day1_att else 0.0
    at_offer = int(event.get("at_offer", 0))
    offer_conv = round(sales_count / at_offer * 100, 1) if at_offer else 0.0

    conv = [
        ("Sales From This Webinar", str(sales_count)),
        ("Revenue", f"RM {revenue:,.0f}"),
        ("Conversion Rate", f"{conv_rate:.1f}%", "sales / Day 1 attendees"),
        ("Offer-time Conversion", f"{offer_conv:.1f}%", f"sales / {at_offer} present at 120m"),
    ]
    for col, spec in zip(cols, conv):
        label, val = spec[0], spec[1]
        sub = spec[2] if len(spec) > 2 else ""
        with col:
            st.markdown(metric_card(label, val, sub=sub), unsafe_allow_html=True)

    # Group D — Failed leads
    st.markdown(section_header("Failed Leads"), unsafe_allow_html=True)
    cols = st.columns(2)
    ev_obj = match_objections_for_event(objections, d1_date, d2_date)
    bonus_count = len(ev_obj) + sales_count
    if len(ev_obj):
        top_cat = ev_obj["category"].value_counts().idxmax()
    else:
        top_cat = "—"
    with cols[0]:
        st.markdown(metric_card("BONUS Messages", str(bonus_count),
                                sub="objections + buyers"), unsafe_allow_html=True)
    with cols[1]:
        st.markdown(metric_card("Top Objection", top_cat), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# Section 2 — All webinars table + selector
# ─────────────────────────────────────────────────────────────────────

def _render_all_table(events_desc: list[dict], webinars: dict, purchases: pd.DataFrame):
    st.markdown(section_header("All Webinars"), unsafe_allow_html=True)

    # Selector — store meeting_id, display Day 1 date
    option_labels = {e["meeting_id"]: _format_event_label(e, webinars) for e in events_desc}
    selected_default = st.session_state["selected_webinar"]

    st.selectbox(
        "Select a webinar to view details",
        options=list(option_labels.keys()),
        format_func=lambda mid: option_labels[mid],
        index=list(option_labels.keys()).index(selected_default),
        key="selected_webinar",
    )

    # Build table
    rows = []
    for e in events_desc:
        d1, d2 = get_event_day_dates(webinars, e["meeting_id"])
        sales_df = _sales_for_event(purchases, d1, d2)
        sales = len(sales_df)
        revenue = float(sales_df["amount"].fillna(0).sum()) if sales else 0.0
        conv = round(sales / e["day1_attendees"] * 100, 1) if e["day1_attendees"] else 0.0
        rows.append({
            "Date": _format_event_label(e, webinars),
            "Day 1": e["day1_attendees"],
            "Day 2": e["day2_attendees"],
            "Unique": e["day1_attendees"] + e["day2_attendees"],
            "Avg Dur": e["avg_duration"],
            "% 120+": e["stayed_120plus_pct"],
            "% Left <30m": e["left_30min_pct"],
            "D2 Ret %": e["retention"],
            "Sales": sales,
            "Revenue": revenue,
            "Conv %": conv,
        })
    df = pd.DataFrame(rows)

    def _color_sales(v):
        if v <= 1:
            return f"color: {COLORS['danger']}; font-weight: 600;"
        if v <= 3:
            return f"color: {COLORS['warning']}; font-weight: 600;"
        return f"color: {COLORS['success']}; font-weight: 600;"

    def _color_stayed(v):
        if v < 40:
            return f"color: {COLORS['danger']}; font-weight: 600;"
        if v < 50:
            return f"color: {COLORS['warning']}; font-weight: 600;"
        return f"color: {COLORS['success']}; font-weight: 600;"

    styled = (
        df.style
        .map(_color_sales, subset=["Sales"])
        .map(_color_stayed, subset=["% 120+"])
        .format({
            "Avg Dur": "{:.0f}",
            "% 120+": "{:.1f}%",
            "% Left <30m": "{:.1f}%",
            "D2 Ret %": "{:.1f}%",
            "Revenue": "RM {:,.0f}",
            "Conv %": "{:.1f}%",
        })
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────
# Section 3 — Drop-off curves
# ─────────────────────────────────────────────────────────────────────

def _render_dropoff(event: dict, d1_df: pd.DataFrame, d2_df: pd.DataFrame,
                    d1_date: str | None, d2_date: str | None):
    st.markdown(section_header("Drop-off Curves"), unsafe_allow_html=True)

    has_d2 = d2_date is not None
    cols = st.columns(2) if has_d2 else [st.container()]

    with cols[0]:
        st.caption(f"Day 1 — {d1_date}")
        if d1_df.empty:
            st.warning("Raw participant data not available for Day 1.")
        else:
            st.plotly_chart(_dropoff_figure(d1_df, "Day 1"), use_container_width=True)

    if has_d2:
        with cols[1]:
            st.caption(f"Day 2 — {d2_date}")
            if d2_df.empty:
                st.warning("Raw participant data not available for Day 2.")
            else:
                st.plotly_chart(_dropoff_figure(d2_df, "Day 2"), use_container_width=True)


def _dropoff_figure(participants: pd.DataFrame, title_suffix: str) -> go.Figure:
    curve = calculate_dropoff_curve(participants, interval=5)
    if curve.empty:
        return apply_standard_layout(go.Figure())

    peak = int(curve["attendees"].max())
    # attendees at minute nearest to offer
    at_offer_row = curve.iloc[(curve["minute"] - OFFER_MINUTE).abs().argmin()]
    at_offer = int(at_offer_row["attendees"])

    fig = go.Figure()
    # Shaded area from curve down to at_offer level (visualizes who left before offer)
    fig.add_trace(go.Scatter(
        x=curve["minute"], y=[at_offer] * len(curve),
        mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=curve["minute"], y=curve["attendees"],
        mode="lines", line=dict(color=COLORS["secondary"], width=2.5),
        fill="tonexty", fillcolor="rgba(231,111,81,0.15)",
        name="Attendees", hovertemplate="min %{x}: %{y} present<extra></extra>",
    ))
    fig.add_vline(
        x=OFFER_MINUTE, line_dash="dash", line_color=COLORS["danger"],
        annotation_text="OFFER", annotation_position="top",
    )
    fig.add_annotation(
        x=curve["minute"].iloc[0], y=peak,
        text=f"Peak: {peak}", showarrow=False, xanchor="left", yanchor="bottom",
        font=dict(size=11, color=COLORS["primary"]),
    )
    fig.add_annotation(
        x=OFFER_MINUTE, y=at_offer,
        text=f"At offer: {at_offer}", showarrow=True, arrowhead=2,
        ax=30, ay=-30, font=dict(size=11, color=COLORS["danger"]),
    )
    fig.update_layout(
        title_text=f"{title_suffix} — Attendees over time",
        xaxis_title="Minutes from start",
        yaxis_title="Unique attendees present",
    )
    return apply_standard_layout(fig, height=380)


# ─────────────────────────────────────────────────────────────────────
# Section 4 — Exit histogram
# ─────────────────────────────────────────────────────────────────────

def _render_exit_histogram(event: dict, d1_df: pd.DataFrame):
    st.markdown(section_header("When Do They Leave?"), unsafe_allow_html=True)
    if d1_df.empty:
        st.warning("Raw participant data not available for this webinar.")
        return

    hist = calculate_exit_histogram(d1_df, bucket_minutes=5)
    if hist.empty:
        st.info("No exit data to show.")
        return

    top3_starts = set(hist.nlargest(3, "exits")["bucket_start"].tolist())
    colors = [
        COLORS["danger"] if s in top3_starts else COLORS["secondary"]
        for s in hist["bucket_start"]
    ]

    fig = go.Figure(go.Bar(
        x=hist["minute_bucket"],
        y=hist["exits"],
        marker_color=colors,
        hovertemplate="min %{x}: %{y} exits<extra></extra>",
    ))
    # OFFER annotation at x bucket containing 120
    offer_bucket = f"{(OFFER_MINUTE // 5) * 5}-{(OFFER_MINUTE // 5) * 5 + 5}"
    if offer_bucket in hist["minute_bucket"].values:
        fig.add_annotation(
            x=offer_bucket, y=hist["exits"].max(),
            text="OFFER", showarrow=True, arrowhead=2,
            ax=0, ay=-30, font=dict(size=11, color=COLORS["danger"]),
        )
    fig.update_layout(
        title_text="Exits per 5-minute bucket (Day 1)",
        xaxis_title="Minute bucket",
        yaxis_title="People who left",
    )
    st.plotly_chart(apply_standard_layout(fig, height=360), use_container_width=True)

    top = hist.nlargest(1, "exits").iloc[0]
    st.markdown(
        alert(
            f"<strong>Biggest exit moment:</strong> {top['exits']} people left between "
            f"minute {top['bucket_start']} and {top['bucket_start'] + 5}. "
            f"Check the recording at this timestamp.",
            variant="warning",
        ),
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# Section 5 — Engagement windows
# ─────────────────────────────────────────────────────────────────────

def _render_engagement_windows(event: dict, webinars: dict, d1_df: pd.DataFrame):
    st.markdown(section_header("Engagement Windows"), unsafe_allow_html=True)
    if d1_df.empty:
        st.warning("Raw participant data not available for this webinar.")
        return

    mid = event["meeting_id"]
    # find Day 1 entry for meeting duration
    day1_entries = sorted(
        [w for w in webinars.values() if w["meeting_id"] == mid],
        key=lambda w: w["date"],
    )
    meeting_dur = day1_entries[0]["meeting_duration"] if day1_entries else 180
    windows = calculate_engagement_windows(d1_df, meeting_dur)

    def _color(pct: float) -> str:
        if pct >= 80:
            return COLORS["success"]
        if pct >= 60:
            return COLORS["warning"]
        return COLORS["danger"]

    labels = [w["window"] for w in windows]
    values = [w["retention_pct"] for w in windows]
    text = [
        f"{w['retention_pct']}% ({w['end_count']}/{w['start_count']} stayed)"
        for w in windows
    ]
    colors = [_color(p) for p in values]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors, text=text, textposition="outside",
    ))
    fig.update_layout(
        title_text="Retention by phase (Day 1)",
        xaxis_title="Retention %", xaxis_range=[0, 115],
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(apply_standard_layout(fig, height=320), use_container_width=True)

    worst = min(windows, key=lambda w: w["retention_pct"])
    insight_map = {
        "First impression (0-30min)":
            "People are leaving in the first 30 minutes — check the opening hook.",
        "Content hook (30-90min)":
            "The middle section (30-90min) is losing people — content may need tightening.",
        "Offer approach (90-120min)":
            "People are leaving just before the offer — they may sense the pitch coming.",
        "Decision window (120-end)":
            "People hear the offer but leave without buying — the offer itself may need work.",
    }
    variant = "danger" if worst["retention_pct"] < 60 else (
        "warning" if worst["retention_pct"] < 80 else "info"
    )
    st.markdown(
        alert(f"<strong>{worst['window']}:</strong> {insight_map[worst['window']]}",
              variant=variant),
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# Section 6 — Day 1 vs Day 2 breakdown
# ─────────────────────────────────────────────────────────────────────

def _render_day_breakdown(webinars: dict, mid: str, purchases: pd.DataFrame):
    st.markdown(section_header("Day 1 vs Day 2 Breakdown"), unsafe_allow_html=True)

    cohorts = get_event_cohorts(webinars, mid)
    if cohorts["day2"] is None:
        st.info("This was a single-day event.")
        return

    d1_only = cohorts["day1_only"]
    both = cohorts["both_days"]
    d2_only = cohorts["day2_only"]

    d1_date, d2_date = get_event_day_dates(webinars, mid)
    event_sales = _sales_for_event(purchases, d1_date, d2_date)
    buyer_emails = set(
        event_sales["norm_email"].dropna().astype(str).str.lower()
    )

    def _stats(emails: set[str]) -> tuple[int, int, float]:
        n = len(emails)
        buyers = len(emails & buyer_emails)
        pct = round(buyers / n * 100, 1) if n else 0.0
        return n, buyers, pct

    d1_n, d1_b, d1_p = _stats(d1_only)
    both_n, both_b, both_p = _stats(both)
    d2_n, d2_b, d2_p = _stats(d2_only)

    cols = st.columns(3)
    for col, title, (n, b, p) in zip(
        cols,
        ["Day 1 Only", "Both Days", "Day 2 Only"],
        [(d1_n, d1_b, d1_p), (both_n, both_b, both_p), (d2_n, d2_b, d2_p)],
    ):
        with col:
            st.markdown(
                metric_card(title, f"{n} attendees",
                            sub=f"{b} bought ({p:.1f}% conversion)"),
                unsafe_allow_html=True,
            )

    if d1_p > 0:
        ratio = both_p / d1_p
        ratio_text = f"{ratio:.1f}x more likely to buy"
    elif both_p > 0:
        ratio_text = "infinitely more likely to buy (Day 1 only = 0% conv)"
    else:
        ratio_text = "no sales in either group"
    st.markdown(
        alert(
            f"People who attended both days converted at <strong>{both_p:.1f}%</strong> "
            f"vs <strong>{d1_p:.1f}%</strong> for Day 1 only — {ratio_text}.",
            variant="info",
        ),
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# Section 7 — Offer moment conversion
# ─────────────────────────────────────────────────────────────────────

def _render_offer_conversion(event: dict, all_events: list[dict],
                             purchases: pd.DataFrame, webinars: dict):
    st.markdown(section_header("Offer Moment Conversion"), unsafe_allow_html=True)

    m = calculate_offer_conversion(event, purchases, all_events, webinars)
    variant = "success" if m["above_avg"] else "danger"
    direction = "above" if m["above_avg"] else "below"

    st.markdown(
        alert(
            f"Of <strong>{m['people_at_offer']}</strong> people present when the offer was made, "
            f"<strong>{m['sales']}</strong> bought "
            f"(<strong>{m['offer_conversion_pct']:.1f}%</strong>). "
            f"This is {direction} the all-time average of "
            f"<strong>{m['all_time_avg_pct']:.1f}%</strong>.",
            variant=variant,
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        "_If the offer conversion is low but attendance is high, the offer needs work. "
        "If attendance at offer time is low, the problem is earlier — people are leaving "
        "before hearing the pitch._"
    )


# ─────────────────────────────────────────────────────────────────────
# AI insights
# ─────────────────────────────────────────────────────────────────────

def _render_ai(events: list[dict], latest: dict,
               purchases: pd.DataFrame, webinars: dict):
    lines = []
    for e in events:
        d1, d2 = get_event_day_dates(webinars, e["meeting_id"])
        sales = len(_sales_for_event(purchases, d1, d2))
        lines.append(
            f"  {e['label']}: D1 {e['day1_attendees']}, D2 {e['day2_attendees']}, "
            f"avg {e['avg_duration']:.0f}m, 120+ {e['stayed_120plus_pct']:.1f}%, "
            f"retention {e['retention']:.1f}%, at_offer {e['at_offer']}, "
            f"sales {sales}"
        )
    context = (
        f"Latest webinar: {latest['label']} — health "
        f"{calculate_webinar_health(latest, len(_sales_for_event(purchases, *get_event_day_dates(webinars, latest['meeting_id']))))}\n"
        f"All events:\n" + "\n".join(lines)
    )
    render_ai_insights("webinar_performance", context)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _sales_for_event(purchases: pd.DataFrame, d1: str | None, d2: str | None) -> pd.DataFrame:
    if purchases.empty or "inferred_webinar" not in purchases.columns:
        return purchases.iloc[0:0]
    dates = [d for d in [d1, d2] if d]
    return purchases[purchases["inferred_webinar"].isin(dates)]


def _format_date_range(d1: str | None, d2: str | None) -> str:
    if not d1:
        return "—"
    d1_ts = pd.Timestamp(d1)
    if d2:
        d2_ts = pd.Timestamp(d2)
        if d1_ts.month == d2_ts.month and d1_ts.year == d2_ts.year:
            return f"{d1_ts.strftime('%B')} {d1_ts.day}-{d2_ts.day}, {d1_ts.year}"
        return f"{d1_ts.strftime('%b %d')} – {d2_ts.strftime('%b %d, %Y')}"
    return d1_ts.strftime("%B %d, %Y")


def _format_event_label(event: dict, webinars: dict) -> str:
    d1, d2 = get_event_day_dates(webinars, event["meeting_id"])
    return _format_date_range(d1, d2)
