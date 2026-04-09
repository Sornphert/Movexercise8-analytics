import streamlit as st

from utils.charts import bar_chart, heatmap_chart, line_chart
from utils.metrics import (
    build_cohort_heatmap,
    build_monthly_cohorts,
    build_webinar_cohorts,
    calculate_cohort_summary,
)
from utils.ai import render_ai_insights
from utils.styles import alert, metric_card, section_header


def render(data: dict):
    leads = data["leads"]
    purchases = data["purchases"]
    webinars = data["webinars"]
    objections = data["objections"]

    monthly = build_monthly_cohorts(leads, purchases)
    webinar = build_webinar_cohorts(leads, purchases, webinars, objections)
    summary = calculate_cohort_summary(monthly, webinar)

    # -- Hero cards --------------------------------------------------------
    st.markdown(section_header("Cohort Overview"), unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            metric_card("Monthly Cohorts", str(summary["total_months"])),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card("Webinar Batches", str(summary["total_webinars"])),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            metric_card(
                "Best Month",
                summary["best_month"],
                f"{summary['best_month_rate']}% conversion",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            metric_card(
                "Avg Webinar Conv.",
                f"{summary['avg_webinar_conv']}%",
                f"Best: {summary['best_webinar_date']} ({summary['best_webinar_rate']}%)",
            ),
            unsafe_allow_html=True,
        )

    # -- Monthly cohorts ---------------------------------------------------
    st.markdown(section_header("Monthly Cohorts"), unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            bar_chart(
                monthly, x="month", y="leads",
                title="Leads per Month", text_col="leads",
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            bar_chart(
                monthly, x="month", y="conversion_rate",
                title="Conversion Rate by Month (%)",
                text_col="conversion_rate", color="#D4A843",
            ),
            use_container_width=True,
        )

    st.dataframe(
        monthly.rename(columns={
            "month": "Month",
            "leads": "Leads",
            "buyers": "Buyers",
            "paid": "Paid",
            "conversion_rate": "Conv %",
            "revenue": "Revenue (RM)",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Revenue (RM)": st.column_config.NumberColumn(format="%.0f"),
        },
    )

    # -- Webinar cohort comparison -----------------------------------------
    st.markdown(section_header("Webinar Cohort Comparison"), unsafe_allow_html=True)

    left2, right2 = st.columns(2)
    with left2:
        st.plotly_chart(
            bar_chart(
                webinar, x="webinar_date", y="attendees",
                title="Attendees per Webinar", text_col="attendees",
            ),
            use_container_width=True,
        )
    with right2:
        st.plotly_chart(
            bar_chart(
                webinar, x="webinar_date", y="conversion_rate",
                title="Conversion Rate by Webinar (%)",
                text_col="conversion_rate", color="#D4A843",
            ),
            use_container_width=True,
        )

    st.dataframe(
        webinar[["webinar_date", "attendees", "day2_attendees", "avg_duration",
                 "at_offer", "buyers", "objections", "revenue", "conversion_rate",
                 "offer_conversion_rate", "retention"]].rename(columns={
            "webinar_date": "Date",
            "attendees": "Day 1",
            "day2_attendees": "Day 2",
            "avg_duration": "Avg Min",
            "at_offer": "At Offer",
            "buyers": "Buyers",
            "objections": "Objections",
            "revenue": "Revenue (RM)",
            "conversion_rate": "Conv %",
            "offer_conversion_rate": "Offer Conv %",
            "retention": "Retention %",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Revenue (RM)": st.column_config.NumberColumn(format="%.0f"),
        },
    )

    # -- Conversion heatmap ------------------------------------------------
    st.markdown(section_header("Funnel Heatmap by Webinar"), unsafe_allow_html=True)

    if len(webinar):
        heatmap_df = build_cohort_heatmap(webinar)
        stage_cols = ["Attended", "Stayed 120+ min", "At Offer", "Bought", "Paid"]
        st.plotly_chart(
            heatmap_chart(heatmap_df, stage_cols, "webinar", title="% of Attendees at Each Stage"),
            use_container_width=True,
        )
    else:
        st.info("No webinar data available.")

    # -- Engagement trend --------------------------------------------------
    st.markdown(section_header("Engagement Trend"), unsafe_allow_html=True)

    if len(webinar) >= 2:
        st.plotly_chart(
            line_chart(
                webinar, x="webinar_date", y="avg_duration",
                title="Average Duration Across Webinars",
            ),
            use_container_width=True,
        )

        # Alert if declining
        if len(webinar) >= 4:
            recent_avg = webinar["avg_duration"].iloc[-2:].mean()
            earlier_avg = webinar["avg_duration"].iloc[:-2].mean()
            if recent_avg < earlier_avg * 0.9:
                st.markdown(
                    alert(
                        f"Engagement is declining: recent webinars average "
                        f"<strong>{recent_avg:.0f} min</strong> vs earlier "
                        f"<strong>{earlier_avg:.0f} min</strong>.",
                        "warning",
                    ),
                    unsafe_allow_html=True,
                )
    else:
        st.info("Need at least 2 webinars to show trend.")

    # ── AI Insights ──────────────────────────────────────────────
    monthly_text = monthly[["month", "leads", "buyers", "conversion_rate", "revenue"]].to_string(index=False)
    webinar_text = webinar[["webinar_date", "attendees", "buyers", "conversion_rate", "offer_conversion_rate", "retention"]].to_string(index=False)
    context = (
        f"Best month: {summary['best_month']} ({summary['best_month_rate']}% conversion)\n"
        f"Worst month: {summary['worst_month']} ({summary['worst_month_rate']}% conversion)\n"
        f"Avg webinar conversion: {summary['avg_webinar_conv']}%\n"
        f"Monthly cohorts:\n{monthly_text}\n\n"
        f"Webinar cohorts:\n{webinar_text}"
    )
    render_ai_insights("cohort_analysis", context)
