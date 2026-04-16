import pandas as pd
import streamlit as st

from utils.charts import bar_chart
from utils.metrics import (
    calculate_funnel_metrics,
    calculate_period_comparison,
    calculate_revenue_metrics,
    calculate_webinar_summary,
    get_event_day_dates,
)
from utils.ai import render_ai_insights
from utils.data_loader import get_webinar_sales_summary
from utils.styles import alert, metric_card, section_header


def render(data: dict):
    leads = data["leads"]
    purchases = data["purchases"]
    webinars = data["webinars"]

    funnel = calculate_funnel_metrics(leads, purchases)
    revenue = calculate_revenue_metrics(purchases)
    events = calculate_webinar_summary(webinars)
    webinar_sales = get_webinar_sales_summary(purchases, webinars)

    # ── Hero metrics ──────────────────────────────────────────────
    st.markdown(section_header("Overview"), unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(metric_card("Total Leads", f"{funnel['total_leads']:,}"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Total Buyers", f"{funnel['total_buyers']}"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Conversion Rate", f"{funnel['conversion_rate']}%"), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Total Revenue", f"RM {revenue['total_revenue']:,.0f}"), unsafe_allow_html=True)
    with c5:
        st.markdown(
            metric_card(
                "Payment Complete",
                f"{funnel['payment_complete_count']}/{funnel['total_buyers']}",
                f"{funnel['payment_completion_rate']}%",
            ),
            unsafe_allow_html=True,
        )

    # ── Latest webinar snapshot ───────────────────────────────────
    st.markdown(section_header("Latest Webinar"), unsafe_allow_html=True)

    if events:
        latest = events[-1]  # sorted by date ascending
        day1_date, day2_date = get_event_day_dates(webinars, latest["meeting_id"])

        day1_sales = webinar_sales.get(
            day1_date, {"sales_count": 0, "total_revenue": 0.0}
        ) if day1_date else {"sales_count": 0, "total_revenue": 0.0}
        day2_sales = webinar_sales.get(
            day2_date, {"sales_count": 0, "total_revenue": 0.0}
        ) if day2_date else {"sales_count": 0, "total_revenue": 0.0}

        w1, w2, w3, w4, w5 = st.columns(5)
        with w1:
            st.markdown(metric_card("Date", latest["label"]), unsafe_allow_html=True)
        with w2:
            st.markdown(metric_card("Day 1 Attendees", str(latest["day1_attendees"])), unsafe_allow_html=True)
        with w3:
            st.markdown(metric_card("Day 2 Attendees", str(latest["day2_attendees"])), unsafe_allow_html=True)
        with w4:
            st.markdown(
                metric_card(
                    "Sales from Day 1",
                    str(day1_sales["sales_count"]),
                    f"RM {day1_sales['total_revenue']:,.0f}",
                ),
                unsafe_allow_html=True,
            )
        with w5:
            st.markdown(
                metric_card(
                    "Sales from Day 2",
                    str(day2_sales["sales_count"]),
                    f"RM {day2_sales['total_revenue']:,.0f}",
                ),
                unsafe_allow_html=True,
            )
    else:
        st.info("No webinar data available.")

    # ── What changed this week ────────────────────────────────────
    st.markdown(section_header("What Changed This Week"), unsafe_allow_html=True)

    leads_delta = calculate_period_comparison(leads, "date")
    buyers_delta = calculate_period_comparison(purchases, "date")
    # Revenue comparison: sum amounts instead of counting rows
    rev_current = purchases[
        purchases["date"] >= (purchases["date"].max() - pd.Timedelta(days=7))
    ]["amount"].sum()
    rev_previous = purchases[
        (purchases["date"] >= (purchases["date"].max() - pd.Timedelta(days=14)))
        & (purchases["date"] < (purchases["date"].max() - pd.Timedelta(days=7)))
    ]["amount"].sum()
    rev_change = round((rev_current - rev_previous) / rev_previous * 100, 1) if rev_previous else 0.0
    rev_dir = "up" if rev_change > 0 else ("down" if rev_change < 0 else "flat")

    def _arrow(direction: str) -> str:
        if direction == "up":
            return '<span style="color:#40916C">&#9650;</span>'
        if direction == "down":
            return '<span style="color:#E76F51">&#9660;</span>'
        return '<span style="color:#6C757D">&#9644;</span>'

    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown(
            metric_card(
                "Leads This Week",
                str(leads_delta["current_count"]),
                f"{_arrow(leads_delta['change_direction'])} {leads_delta['change_pct']:+.1f}% vs prior week ({leads_delta['previous_count']})",
            ),
            unsafe_allow_html=True,
        )
    with d2:
        st.markdown(
            metric_card(
                "Buyers This Week",
                str(buyers_delta["current_count"]),
                f"{_arrow(buyers_delta['change_direction'])} {buyers_delta['change_pct']:+.1f}% vs prior week ({buyers_delta['previous_count']})",
            ),
            unsafe_allow_html=True,
        )
    with d3:
        st.markdown(
            metric_card(
                "Revenue This Week",
                f"RM {rev_current:,.0f}",
                f"{_arrow(rev_dir)} {rev_change:+.1f}% vs prior week (RM {rev_previous:,.0f})",
            ),
            unsafe_allow_html=True,
        )

    # ── Quick alerts ──────────────────────────────────────────────
    alerts_html = ""

    if revenue["outstanding_revenue"] > 10_000:
        alerts_html += alert(
            f"Outstanding revenue: <strong>RM {revenue['outstanding_revenue']:,.0f}</strong> "
            f"across unpaid transactions.",
            "warning",
        )

    if events and len(events) >= 2:
        avg_att = sum(e["day1_attendees"] for e in events) / len(events)
        latest_att = events[-1]["day1_attendees"]
        if latest_att < avg_att * 0.8:
            alerts_html += alert(
                f"Latest webinar attendance ({latest_att}) is "
                f"<strong>{((avg_att - latest_att) / avg_att * 100):.0f}% below</strong> "
                f"the average ({avg_att:.0f}).",
                "danger",
            )

    if alerts_html:
        st.markdown(alerts_html, unsafe_allow_html=True)

    # ── Lead trend chart ──────────────────────────────────────────
    st.markdown(section_header("Daily Lead Registrations"), unsafe_allow_html=True)

    daily = leads.groupby(leads["date"].dt.date).size().reset_index(name="count")
    daily.columns = ["date", "count"]
    st.plotly_chart(bar_chart(daily, "date", "count"), use_container_width=True)

    # ── AI Insights ──────────────────────────────────────────────
    latest_label = events[-1]["label"] if events else "N/A"
    latest_att = events[-1]["day1_attendees"] if events else 0
    latest_dur = events[-1]["avg_duration"] if events else 0
    context = (
        f"Funnel: {funnel['total_leads']:,} leads -> {funnel['total_buyers']} buyers "
        f"({funnel['conversion_rate']}% conversion)\n"
        f"Payment completion: {funnel['payment_complete_count']}/{funnel['total_buyers']} "
        f"({funnel['payment_completion_rate']}%)\n"
        f"Revenue: RM {revenue['total_revenue']:,.0f} total, "
        f"RM {revenue['collected_revenue']:,.0f} collected, "
        f"RM {revenue['outstanding_revenue']:,.0f} outstanding\n"
        f"Avg per buyer: RM {revenue['avg_per_buyer']:,.0f}\n"
        f"Latest webinar ({latest_label}): {latest_att} attendees, avg {latest_dur:.0f} min\n"
        f"Leads this week: {leads_delta['current_count']} ({leads_delta['change_pct']:+.1f}% vs prior)\n"
        f"Buyers this week: {buyers_delta['current_count']} ({buyers_delta['change_pct']:+.1f}% vs prior)"
    )
    render_ai_insights("overview", context)
