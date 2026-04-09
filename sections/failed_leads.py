import streamlit as st

from utils.charts import bar_chart, pie_chart
from utils.metrics import (
    calculate_child_profile,
    calculate_objection_breakdown,
    calculate_objection_by_webinar,
    calculate_objection_summary,
    classify_recoverability,
)
from utils.ai import render_ai_insights
from utils.styles import alert, metric_card, section_header


def render(data: dict):
    objections = data["objections"]
    summary = calculate_objection_summary(objections)

    # -- Hero cards --------------------------------------------------------
    st.markdown(section_header("Failed Leads Overview"), unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            metric_card("Total Failed Leads", str(summary["total"])),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card(
                "Top Objection",
                summary["top_category"],
                f"{summary['top_category_pct']}% of all objections",
                variant="danger",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            metric_card(
                "Recoverable Leads",
                str(summary["recoverable_count"]),
                f"{summary['recoverable_pct']}% of failed leads",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            metric_card("Webinar Batches", str(summary["webinar_batches"])),
            unsafe_allow_html=True,
        )

    # -- Objection breakdown -----------------------------------------------
    st.markdown(section_header("Objection Breakdown"), unsafe_allow_html=True)

    breakdown = calculate_objection_breakdown(objections)
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            bar_chart(
                breakdown, x="count", y="category",
                title="By Count", text_col="count", orientation="h",
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            pie_chart(breakdown, "count", "category", title="By Proportion"),
            use_container_width=True,
        )

    # -- Objections by webinar ---------------------------------------------
    st.markdown(section_header("Objections by Webinar"), unsafe_allow_html=True)

    by_webinar = calculate_objection_by_webinar(objections)
    if len(by_webinar):
        st.plotly_chart(
            bar_chart(
                by_webinar, x="webinar_date", y="count",
                title="Objection Categories per Webinar",
                color_col="category",
            ),
            use_container_width=True,
        )
    else:
        st.info("No webinar date data available.")

    # -- Audience profile --------------------------------------------------
    st.markdown(section_header("Audience Profile"), unsafe_allow_html=True)

    profile = calculate_child_profile(objections)
    left2, right2 = st.columns(2)
    with left2:
        age_df = profile["age_distribution"]
        if len(age_df):
            st.plotly_chart(
                bar_chart(
                    age_df, x="age_group", y="count",
                    title="Child Age Distribution", text_col="count",
                ),
                use_container_width=True,
            )
        else:
            st.info("No age data available.")
    with right2:
        issues_df = profile["top_issues"]
        if len(issues_df):
            st.plotly_chart(
                bar_chart(
                    issues_df, x="count", y="issue",
                    title="Top Child Issues", text_col="count", orientation="h",
                ),
                use_container_width=True,
            )
        else:
            st.info("No child issue data available.")

    # -- Recoverable leads -------------------------------------------------
    st.markdown(section_header("Recoverable Leads"), unsafe_allow_html=True)

    classified = classify_recoverability(objections)
    recoverable = classified[classified["recoverable"] != "Unlikely"]

    if len(recoverable):
        rec_count = int((recoverable["recoverable"] == "Recoverable").sum())
        pos_count = int((recoverable["recoverable"] == "Possibly Recoverable").sum())
        st.markdown(
            alert(
                f"<strong>{rec_count}</strong> leads are likely recoverable, "
                f"<strong>{pos_count}</strong> are possibly recoverable with the right offer.",
                "success",
            ),
            unsafe_allow_html=True,
        )
        st.dataframe(
            recoverable[["name", "phone", "webinar_date", "category",
                          "primary_objection", "recoverable", "notes"]],
            use_container_width=True,
            column_config={
                "name": "Name",
                "phone": "Phone",
                "webinar_date": "Webinar",
                "category": "Category",
                "primary_objection": "Objection",
                "recoverable": "Status",
                "notes": "Notes",
            },
            hide_index=True,
        )
    else:
        st.info("No recoverable leads identified.")

    # ── AI Insights ──────────────────────────────────────────────
    breakdown_text = "\n".join(
        f"  {row['category']}: {row['count']} ({row['pct']}%)"
        for _, row in breakdown.iterrows()
    )
    profile = calculate_child_profile(objections)
    age_text = profile["age_distribution"].to_string(index=False) if len(profile["age_distribution"]) else "N/A"
    context = (
        f"Total failed leads: {summary['total']}\n"
        f"Top objection: {summary['top_category']} ({summary['top_category_pct']}%)\n"
        f"Recoverable: {summary['recoverable_count']} ({summary['recoverable_pct']}%)\n"
        f"Webinar batches: {summary['webinar_batches']}\n"
        f"Objection breakdown:\n{breakdown_text}\n"
        f"Child age distribution:\n{age_text}\n"
        f"Top child issues: {profile['top_issues'].to_string(index=False) if len(profile['top_issues']) else 'N/A'}"
    )
    render_ai_insights("failed_leads", context)
