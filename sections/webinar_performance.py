from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import apply_standard_layout, bar_chart, line_chart
from utils.data_loader import load_participant_detail
from utils.metrics import (
    calculate_dropoff_curve,
    calculate_engagement_trend,
    calculate_webinar_summary,
    find_best_worst_webinars,
)
from utils.styles import alert, metric_card, section_header


def render(data: dict):
    webinars = data["webinars"]
    config = data["config"]
    offer_min = config.get("offer_timing_minutes", 120)

    events = calculate_webinar_summary(webinars)
    if not events:
        st.info("No webinar data available.")
        return

    # ── 1. Per-webinar table ─────────────────────────────────────
    st.markdown(section_header("Webinar Performance"), unsafe_allow_html=True)

    table = pd.DataFrame(events)
    table = table.rename(columns={
        "label": "Date",
        "day1_attendees": "Day 1",
        "day2_attendees": "Day 2",
        "avg_duration": "Avg Duration (min)",
        "stayed_120plus_pct": "% 120+ min",
        "left_30min_pct": "% Left <30 min",
        "retention": "Day 2 Retention %",
        "waiting_bounced": "Waiting Bounces",
    })
    st.dataframe(
        table[["Date", "Day 1", "Day 2", "Avg Duration (min)",
               "% 120+ min", "% Left <30 min", "Day 2 Retention %",
               "Waiting Bounces"]],
        use_container_width=True,
        hide_index=True,
    )

    # ── 2. Best / worst callout cards ────────────────────────────
    st.markdown(section_header("Best & Worst Webinars"), unsafe_allow_html=True)

    best, worst = find_best_worst_webinars(events)
    b_col, w_col = st.columns(2)
    if best:
        with b_col:
            st.markdown(
                metric_card(
                    "Best Webinar",
                    best["label"],
                    f"Avg {best['avg_duration']:.0f} min | "
                    f"{best['day1_attendees']} attendees | "
                    f"{best['stayed_120plus_pct']:.1f}% stayed 120+ min",
                ),
                unsafe_allow_html=True,
            )
    if worst:
        with w_col:
            st.markdown(
                metric_card(
                    "Worst Webinar",
                    worst["label"],
                    f"Avg {worst['avg_duration']:.0f} min | "
                    f"{worst['day1_attendees']} attendees | "
                    f"{worst['stayed_120plus_pct']:.1f}% stayed 120+ min",
                    variant="danger",
                ),
                unsafe_allow_html=True,
            )

    # ── 3. Compare two webinars ──────────────────────────────────
    st.markdown(section_header("Compare Two Webinars"), unsafe_allow_html=True)

    labels = [e["label"] for e in events]
    c1, c2 = st.columns(2)
    with c1:
        pick_a = st.selectbox("Webinar A", labels, index=len(labels) - 1, key="cmp_a")
    with c2:
        pick_b = st.selectbox("Webinar B", labels, index=max(0, len(labels) - 2), key="cmp_b")

    ev_a = next(e for e in events if e["label"] == pick_a)
    ev_b = next(e for e in events if e["label"] == pick_b)

    compare_keys = [
        ("day1_attendees", "Day 1 Attendees", True),
        ("day2_attendees", "Day 2 Attendees", True),
        ("avg_duration", "Avg Duration (min)", True),
        ("stayed_120plus_pct", "% Stayed 120+ min", True),
        ("left_30min_pct", "% Left <30 min", False),  # lower is better
        ("retention", "Day 2 Retention %", True),
        ("waiting_bounced", "Waiting Bounces", False),
        ("at_offer", "At Offer Time", True),
    ]

    col_a, col_b = st.columns(2)
    for key, label, higher_better in compare_keys:
        val_a = ev_a[key]
        val_b = ev_b[key]
        a_wins = (val_a > val_b) if higher_better else (val_a < val_b)
        b_wins = (val_b > val_a) if higher_better else (val_b < val_a)
        with col_a:
            variant = "" if a_wins else ("danger" if b_wins else "")
            fmt = f"{val_a:.1f}" if isinstance(val_a, float) else str(val_a)
            st.markdown(metric_card(label, fmt, variant=variant), unsafe_allow_html=True)
        with col_b:
            variant = "" if b_wins else ("danger" if a_wins else "")
            fmt = f"{val_b:.1f}" if isinstance(val_b, float) else str(val_b)
            st.markdown(metric_card(label, fmt, variant=variant), unsafe_allow_html=True)

    # ── 4. People at offer time chart ────────────────────────────
    st.markdown(section_header("People at Offer Time"), unsafe_allow_html=True)

    offer_df = pd.DataFrame(events)[["label", "at_offer"]].rename(
        columns={"label": "date", "at_offer": "count"}
    )
    avg_at_offer = offer_df["count"].mean()

    fig_offer = bar_chart(offer_df, "date", "count", title="Attendees Present at Offer")
    fig_offer.add_hline(
        y=avg_at_offer,
        line_dash="dash",
        line_color="#E76F51",
        annotation_text=f"Avg: {avg_at_offer:.0f}",
        annotation_position="top right",
    )
    st.plotly_chart(fig_offer, use_container_width=True)

    # ── 5. Day 1 → Day 2 retention trend ────────────────────────
    has_day2 = [e for e in events if e["day2_attendees"] > 0]
    if has_day2:
        st.markdown(section_header("Day 1 → Day 2 Retention Trend"), unsafe_allow_html=True)

        ret_df = pd.DataFrame(has_day2)[["label", "retention"]].rename(
            columns={"label": "date", "retention": "retention_pct"}
        )
        st.plotly_chart(
            line_chart(ret_df, "date", "retention_pct",
                       title="Retention: % of Day 1 Attendees Returning for Day 2"),
            use_container_width=True,
        )

    # ── 6. Engagement decline alert ──────────────────────────────
    st.markdown(section_header("Engagement Trend"), unsafe_allow_html=True)

    trend = calculate_engagement_trend(events)
    if trend is None:
        st.info("Need at least 6 webinars to calculate engagement trend.")
    elif trend["declining"]:
        st.markdown(
            alert(
                f"Engagement declining: avg duration dropped from "
                f"<strong>{trend['previous_avg']:.0f} min</strong> to "
                f"<strong>{trend['recent_avg']:.0f} min</strong> "
                f"(<strong>{trend['change_pct']:+.1f}%</strong>) — "
                f"last 3 webinars vs previous 3.",
                "danger",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            alert(
                f"Engagement stable/improving: avg duration went from "
                f"<strong>{trend['previous_avg']:.0f} min</strong> to "
                f"<strong>{trend['recent_avg']:.0f} min</strong> "
                f"(<strong>{trend['change_pct']:+.1f}%</strong>) — "
                f"last 3 webinars vs previous 3.",
                "success",
            ),
            unsafe_allow_html=True,
        )

    # ── 7. Drop-off curve (most recent webinar, Day 1) ──────────
    st.markdown(section_header("Drop-off Curve — Latest Webinar"), unsafe_allow_html=True)

    latest = events[-1]
    # Find the Day 1 session key for the latest event
    day1_key = None
    for k, w in webinars.items():
        if w["meeting_id"] == latest["meeting_id"] and w["date"] == latest["label"]:
            day1_key = k
            break

    if day1_key:
        w = webinars[day1_key]
        participants, start_time = load_participant_detail(w["date"], w["meeting_id"])

        if not participants.empty:
            curve = calculate_dropoff_curve(participants)
            fig_curve = go.Figure()
            fig_curve.add_trace(go.Scatter(
                x=curve["minute"],
                y=curve["attendees"],
                mode="lines+markers",
                line=dict(color="#2D6A4F", width=2.5),
                marker=dict(size=5),
                name="Attendees",
            ))
            fig_curve.add_vline(
                x=offer_min,
                line_dash="dash",
                line_color="#E76F51",
                annotation_text=f"Offer ({offer_min} min)",
                annotation_position="top right",
            )
            fig_curve.update_layout(
                title_text=f"Attendee Drop-off — {latest['label']}",
                xaxis_title="Minutes from Start",
                yaxis_title="Unique Attendees",
            )
            apply_standard_layout(fig_curve, height=400)
            st.plotly_chart(fig_curve, use_container_width=True)

            at_start = curve.iloc[0]["attendees"] if len(curve) > 0 else 0
            at_offer_row = curve[curve["minute"] <= offer_min].iloc[-1] if len(curve) > 0 else None
            if at_offer_row is not None and at_start > 0:
                pct_remaining = round(at_offer_row["attendees"] / at_start * 100, 1)
                st.caption(
                    f"{at_offer_row['attendees']:.0f} of {at_start:.0f} attendees "
                    f"({pct_remaining}%) still present at offer time ({offer_min} min)."
                )
        else:
            st.info("No participant data available for the latest webinar.")
    else:
        st.info("Could not locate participant data for the latest webinar.")
