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
    calculate_webinar_health,
    calculate_webinar_summary,
    get_event_cohorts,
    get_event_day_dates,
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
    _render_snapshot(latest_event, webinars, purchases)

    _render_all_table(events_desc, webinars, purchases)

    selected_mid = st.session_state["selected_webinar"]
    selected_event = next(
        (e for e in events_desc if e["meeting_id"] == selected_mid),
        latest_event,
    )
    day1_date, day2_date = get_event_day_dates(webinars, selected_mid)

    d1_df, _ = load_participant_detail(day1_date, selected_mid) if day1_date else (pd.DataFrame(), None)
    d2_df, _ = load_participant_detail(day2_date, selected_mid) if day2_date else (pd.DataFrame(), None)

    _render_dropoff(selected_event, d1_df, d2_df, day1_date, day2_date, webinars)
    _render_exit_histogram(selected_event, d1_df, webinars, day1_date)
    _render_engagement_windows(selected_event, webinars, d1_df, d2_df)

    _render_ai(events, latest_event, purchases, webinars)


# ─────────────────────────────────────────────────────────────────────
# Section 1 — Latest webinar snapshot
# ─────────────────────────────────────────────────────────────────────

def _render_snapshot(event: dict, webinars: dict, purchases: pd.DataFrame):
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

    # Group A — Attendance (join-only, after zero-duration filter)
    day1_att = day1["unique_attendees"] if day1 else 0
    day2_att = day2["unique_attendees"] if day2 else 0
    d1_peak = int(day1.get("peak_attendance", 0)) if day1 else 0
    d2_peak = int(day2.get("peak_attendance", 0)) if day2 else 0
    both = len(cohorts["both_days"])
    d1_only = len(cohorts["day1_only"])
    d2_only = len(cohorts["day2_only"])
    total = len(cohorts["day1_emails"] | cohorts["day2_emails"])

    st.markdown(section_header("Attendance"), unsafe_allow_html=True)
    cols = st.columns(6)
    specs = [
        ("Day 1 Joined", day1_att),
        ("Day 2 Joined", day2_att),
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

    # Per-day sales attribution
    sales_d1 = len(event_sales[event_sales["inferred_webinar"] == d1_date]) if d1_date else 0
    sales_d2 = len(event_sales[event_sales["inferred_webinar"] == d2_date]) if d2_date else 0

    day2_att = day2["unique_attendees"] if day2 else 0
    d1_at_offer = int(day1.get("present_at_offer", 0)) if day1 else 0
    d2_at_offer = int(day2.get("present_at_offer", 0)) if day2 else 0

    d1_conv = round(sales_d1 / day1_att * 100, 1) if day1_att else 0.0
    d1_offer_conv = round(sales_d1 / d1_at_offer * 100, 1) if d1_at_offer else None
    d2_conv = round(sales_d2 / day2_att * 100, 1) if day2_att else 0.0
    d2_offer_conv = round(sales_d2 / d2_at_offer * 100, 1) if d2_at_offer else None

    avg_conv = round(sales_count / total * 100, 1) if total else 0.0

    row1 = st.columns(3)
    with row1[0]:
        st.markdown(metric_card("Sales From This Webinar", str(sales_count)), unsafe_allow_html=True)
    with row1[1]:
        st.markdown(metric_card("Revenue", f"RM {revenue:,.0f}"), unsafe_allow_html=True)
    with row1[2]:
        st.markdown(
            metric_card(
                "Average Conversion Rate",
                f"{avg_conv:.1f}%",
                sub=f"{sales_count} / {total} total unique",
            ),
            unsafe_allow_html=True,
        )

    row2 = st.columns(4)
    d1_offer_val = f"{d1_offer_conv:.1f}%" if d1_offer_conv is not None else "—"
    d1_offer_sub = f"{sales_d1} / {d1_at_offer} present at 120m" if d1_at_offer else "no timing data"
    d2_offer_val = (f"{d2_offer_conv:.1f}%" if d2_offer_conv is not None else "—") if day2 else "—"
    d2_offer_sub = (f"{sales_d2} / {d2_at_offer} present at 120m" if d2_at_offer else "no timing data") if day2 else ""
    cards = [
        ("Day 1 Conversion", f"{d1_conv:.1f}%", f"{sales_d1} / {day1_att} Day 1 attendees"),
        ("Day 1 Offer-time Conv", d1_offer_val, d1_offer_sub),
        ("Day 2 Conversion",
         f"{d2_conv:.1f}%" if day2 else "—",
         f"{sales_d2} / {day2_att} Day 2 attendees" if day2 else ""),
        ("Day 2 Offer-time Conv", d2_offer_val, d2_offer_sub),
    ]
    for col, (label, val, sub) in zip(row2, cards):
        with col:
            st.markdown(metric_card(label, val, sub=sub), unsafe_allow_html=True)


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
        unique = e["total_unique"]
        avg_conv = round(sales / unique * 100, 1) if unique else 0.0
        rows.append({
            "Date": _format_event_label(e, webinars),
            "Day": _format_day_names(d1, d2),
            "Day 1 Peak": e.get("day1_peak", 0),
            "Day 2 Peak": e.get("day2_peak", 0),
            "Total Unique": unique,
            "Sales": sales,
            "Revenue": revenue,
            "Avg Conv Rate": avg_conv,
        })
    df = pd.DataFrame(rows)

    def _color_sales(v):
        if v <= 1:
            return f"color: {COLORS['danger']}; font-weight: 600;"
        if v <= 3:
            return f"color: {COLORS['warning']}; font-weight: 600;"
        return f"color: {COLORS['success']}; font-weight: 600;"

    styled = (
        df.style
        .map(_color_sales, subset=["Sales"])
        .format({
            "Revenue": "RM {:,.0f}",
            "Avg Conv Rate": "{:.1f}%",
        })
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────
# Section 3 — Drop-off curves
# ─────────────────────────────────────────────────────────────────────

def _render_dropoff(event: dict, d1_df: pd.DataFrame, d2_df: pd.DataFrame,
                    d1_date: str | None, d2_date: str | None,
                    webinars: dict | None = None):
    st.markdown(section_header("Drop-off Curves"), unsafe_allow_html=True)

    has_d2 = d2_date is not None
    cols = st.columns(2) if has_d2 else [st.container()]

    mid = event["meeting_id"]
    d1_entry = webinars.get(f"{d1_date}_{mid}") if (webinars and d1_date) else None
    d2_entry = webinars.get(f"{d2_date}_{mid}") if (webinars and d2_date) else None
    d1_offer_min = d1_entry.get("offer_minute", OFFER_MINUTE) if d1_entry else OFFER_MINUTE
    d2_offer_min = d2_entry.get("offer_minute", OFFER_MINUTE) if d2_entry else OFFER_MINUTE

    with cols[0]:
        st.caption(f"Day 1 — {d1_date}")
        if d1_df.empty:
            st.warning("Raw participant data not available for Day 1.")
        else:
            st.plotly_chart(_dropoff_figure(d1_df, "Day 1", d1_offer_min),
                            use_container_width=True, key="dropoff_day1")

    if has_d2:
        with cols[1]:
            st.caption(f"Day 2 — {d2_date}")
            if d2_df.empty:
                st.warning("Raw participant data not available for Day 2.")
            else:
                st.plotly_chart(_dropoff_figure(d2_df, "Day 2", d2_offer_min),
                                use_container_width=True, key="dropoff_day2")


def _mins_to_clock(m: float, eight_pm: float) -> str:
    """Convert minute-from-zoom-start to clock time label, with 8pm as the anchor."""
    total = (m - eight_pm) + 20 * 60  # 20:00 + offset
    hh = int(total // 60) % 24
    mm = int(round(total % 60))
    if mm == 60:
        hh = (hh + 1) % 24
        mm = 0
    period = "PM" if hh >= 12 else "AM"
    h12 = ((hh - 1) % 12) + 1
    return f"{h12}:{mm:02d} {period}"


def _dropoff_figure(participants: pd.DataFrame, title_suffix: str,
                    offer_minute: float = OFFER_MINUTE) -> go.Figure:
    eight_pm = offer_minute - 120
    curve = calculate_dropoff_curve(participants, interval=5, align_to=eight_pm)
    if curve.empty:
        return apply_standard_layout(go.Figure())

    peak = int(curve["attendees"].max())
    at_offer_row = curve.iloc[(curve["minute"] - offer_minute).abs().argmin()]
    at_offer = int(at_offer_row["attendees"])
    # Rebase x-axis so 8:00 PM = 0
    x_rebased = [m - eight_pm for m in curve["minute"]]
    offer_x = offer_minute - eight_pm  # always 120
    clock_labels = [_mins_to_clock(m, eight_pm) for m in curve["minute"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_rebased, y=[at_offer] * len(curve),
        mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x_rebased, y=curve["attendees"],
        mode="lines", line=dict(color=COLORS["secondary"], width=2.5),
        fill="tonexty", fillcolor="rgba(231,111,81,0.15)",
        name="Attendees", customdata=clock_labels,
        hovertemplate="%{customdata}: %{y} present<extra></extra>",
    ))
    # Half-hour dotted gridlines (skip 10pm — already has OFFER line)
    for offset in [-30, 30, 60, 90, 150]:
        fig.add_vline(x=offset, line_dash="dot",
                      line_color="rgba(0,0,0,0.18)", line_width=1)
    fig.add_vline(
        x=offer_x, line_dash="dash", line_color=COLORS["danger"],
        annotation_text="OFFER", annotation_position="top",
    )
    fig.add_annotation(
        x=-30, y=peak,
        text=f"Peak: {peak}", showarrow=False, xanchor="left", yanchor="bottom",
        font=dict(size=11, color=COLORS["primary"]),
    )
    fig.add_annotation(
        x=offer_x, y=at_offer,
        text=f"At offer: {at_offer}", showarrow=True, arrowhead=2,
        ax=30, ay=-30, font=dict(size=11, color=COLORS["danger"]),
    )
    tick_vals = [-30, 0, 30, 60, 90, 120, 150, 180]
    tick_text = ["7:30 PM", "8:00 PM", "8:30", "9:00 PM", "9:30", "10:00 PM", "10:30", "11:00 PM"]
    fig.update_layout(
        title_text=f"{title_suffix} — Attendees over time",
        xaxis_title="Time",
        yaxis_title="Unique attendees present",
        hovermode="x",
        xaxis=dict(
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            range=[-30, 180],
        ),
    )
    return apply_standard_layout(fig, height=380)


# ─────────────────────────────────────────────────────────────────────
# Section 4 — Exit histogram
# ─────────────────────────────────────────────────────────────────────

def _render_exit_histogram(event: dict, d1_df: pd.DataFrame,
                           webinars: dict | None = None,
                           d1_date: str | None = None):
    st.markdown(section_header("When Do They Leave?"), unsafe_allow_html=True)
    if d1_df.empty:
        st.warning("Raw participant data not available for this webinar.")
        return

    mid = event["meeting_id"]
    d1_entry = webinars.get(f"{d1_date}_{mid}") if (webinars and d1_date) else None
    offer_minute = d1_entry.get("offer_minute", OFFER_MINUTE) if d1_entry else OFFER_MINUTE
    eight_pm = offer_minute - 120

    hist = calculate_exit_histogram(d1_df, bucket_minutes=5, align_to=eight_pm)
    if hist.empty:
        st.info("No exit data to show.")
        return

    top3_starts = set(hist.nlargest(3, "exits")["bucket_start"].tolist())
    colors = [
        COLORS["danger"] if s in top3_starts else COLORS["secondary"]
        for s in hist["bucket_start"]
    ]

    x_rebased = [s - eight_pm for s in hist["bucket_start"]]
    clock_labels = [_mins_to_clock(s, eight_pm) for s in hist["bucket_start"]]

    fig = go.Figure(go.Bar(
        x=x_rebased,
        y=hist["exits"],
        marker_color=colors,
        width=4.5,
        customdata=clock_labels,
        hovertemplate="%{customdata}: %{y} exits<extra></extra>",
    ))
    # Half-hour dotted gridlines
    for offset in [-30, 30, 60, 90, 150]:
        fig.add_vline(x=offset, line_dash="dot",
                      line_color="rgba(0,0,0,0.18)", line_width=1)
    fig.add_vline(
        x=120, line_dash="dash", line_color=COLORS["danger"],
        annotation_text="OFFER", annotation_position="top",
    )

    tick_vals = [-30, 0, 30, 60, 90, 120, 150, 180]
    tick_text = ["7:30 PM", "8:00 PM", "8:30", "9:00 PM", "9:30", "10:00 PM", "10:30", "11:00 PM"]
    fig.update_layout(
        title_text="Exits per 5-minute bucket (Day 1)",
        xaxis_title="Time",
        yaxis_title="People who left",
        hovermode="x",
        xaxis=dict(
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            range=[-30, 180],
        ),
    )
    st.plotly_chart(apply_standard_layout(fig, height=360), use_container_width=True)

    top = hist.nlargest(1, "exits").iloc[0]
    top_start_clock = _mins_to_clock(top["bucket_start"], eight_pm)
    top_end_clock = _mins_to_clock(top["bucket_start"] + 5, eight_pm)
    st.markdown(
        alert(
            f"<strong>Biggest exit moment:</strong> {top['exits']} people left between "
            f"{top_start_clock} and {top_end_clock}. "
            f"Check the recording at this timestamp.",
            variant="warning",
        ),
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# Section 5 — Engagement windows
# ─────────────────────────────────────────────────────────────────────

def _render_engagement_windows(event: dict, webinars: dict,
                               d1_df: pd.DataFrame, d2_df: pd.DataFrame):
    st.markdown(section_header("Engagement Windows"), unsafe_allow_html=True)

    mid = event["meeting_id"]
    day_entries = sorted(
        [w for w in webinars.values() if w["meeting_id"] == mid],
        key=lambda w: w["date"],
    )
    d1_dur = day_entries[0]["meeting_duration"] if day_entries else 180
    d2_dur = day_entries[1]["meeting_duration"] if len(day_entries) > 1 else d1_dur

    def _color(pct: float) -> str:
        if pct >= 80:
            return COLORS["success"]
        if pct >= 60:
            return COLORS["warning"]
        return COLORS["danger"]

    def _windows_fig(df: pd.DataFrame, dur: int, title: str) -> go.Figure:
        windows = calculate_engagement_windows(df, dur)
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
            title_text=title,
            xaxis_title="Retention %", xaxis_range=[0, 115],
            yaxis=dict(autorange="reversed"),
        )
        return apply_standard_layout(fig, height=320), windows

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

    def _insight(windows: list[dict]) -> tuple[str, str]:
        worst = min(windows, key=lambda w: w["retention_pct"])
        variant = "danger" if worst["retention_pct"] < 60 else (
            "warning" if worst["retention_pct"] < 80 else "info"
        )
        msg = f"<strong>{worst['window']}:</strong> {insight_map[worst['window']]}"
        return msg, variant

    has_d2 = not d2_df.empty
    cols = st.columns(2) if has_d2 else [st.container()]

    with cols[0]:
        if d1_df.empty:
            st.warning("Raw participant data not available for Day 1.")
        else:
            fig, windows = _windows_fig(d1_df, d1_dur, "Retention by phase (Day 1)")
            st.plotly_chart(fig, use_container_width=True, key="eng_day1")
            msg, variant = _insight(windows)
            st.markdown(alert(msg, variant=variant), unsafe_allow_html=True)

    if has_d2:
        with cols[1]:
            fig, windows = _windows_fig(d2_df, d2_dur, "Retention by phase (Day 2)")
            st.plotly_chart(fig, use_container_width=True, key="eng_day2")
            msg, variant = _insight(windows)
            st.markdown(alert(msg, variant=variant), unsafe_allow_html=True)




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
    d1_day = d1_ts.strftime("%A")  # e.g. "Sunday"
    if d2:
        d2_ts = pd.Timestamp(d2)
        d2_day = d2_ts.strftime("%A")
        if d1_ts.month == d2_ts.month and d1_ts.year == d2_ts.year:
            return f"{d1_ts.strftime('%B')} {d1_ts.day}-{d2_ts.day}, {d1_ts.year} ({d1_day}-{d2_day})"
        return f"{d1_ts.strftime('%b %d')} – {d2_ts.strftime('%b %d, %Y')} ({d1_day}-{d2_day})"
    return f"{d1_ts.strftime('%B %d, %Y')} ({d1_day})"


def _format_day_names(d1: str | None, d2: str | None) -> str:
    if not d1:
        return "—"
    d1_day = pd.Timestamp(d1).strftime("%A")
    if d2:
        d2_day = pd.Timestamp(d2).strftime("%A")
        return f"{d1_day}-{d2_day}"
    return d1_day


def _format_event_label(event: dict, webinars: dict) -> str:
    d1, d2 = get_event_day_dates(webinars, event["meeting_id"])
    return _format_date_range(d1, d2)
