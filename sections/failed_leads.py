import streamlit as st

from utils.charts import bar_chart, horizontal_bar_chart, pie_chart
from utils.metrics import (
    calculate_child_profile,
    calculate_objection_breakdown,
    calculate_objection_by_webinar,
    calculate_objection_summary,
)
from utils.ai import render_ai_insights
from utils.styles import COLORS, alert, metric_card, section_header

CATEGORY_COLORS = {
    "Financial Constraint": "#E76F51",
    "Skepticism": "#D4A843",
    "Spouse Buy-in": "#40916C",
    "Prefers Physical": "#3B82F6",
    "Not Ready / Timing": "#E9C46A",
    "Still Considering": "#F97316",
    "Went Silent": "#95A5A6",
    "Other": "#6B7280",
}


def render(data: dict):
    objections = data["objections"]

    if objections.empty:
        st.warning("No failed leads data available. Upload analyzed WhatsApp conversations to data/objections.csv")
        return

    summary = calculate_objection_summary(objections)

    # ── Section 1: Failed Leads Overview ──────────────────────────
    st.markdown(section_header("Failed Leads Overview"), unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
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
            metric_card("Webinar Batches", str(summary["webinar_batches"])),
            unsafe_allow_html=True,
        )

    # ── Section 2: Objection Breakdown ────────────────────────────
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
            pie_chart(
                breakdown, "count", "category",
                title="By Proportion", color_map=CATEGORY_COLORS,
            ),
            use_container_width=True,
        )

    # ── Section 3: Objections by Webinar ──────────────────────────
    st.markdown(section_header("Objections by Webinar"), unsafe_allow_html=True)

    by_webinar = calculate_objection_by_webinar(objections)
    if len(by_webinar):
        st.plotly_chart(
            bar_chart(
                by_webinar, x="webinar_date", y="count",
                title="Objection Categories per Webinar",
                color_col="category", barmode="stack",
                color_map=CATEGORY_COLORS,
            ),
            use_container_width=True,
        )

        fin = objections[objections["category"] == "Financial Constraint"]
        if len(fin) and objections["webinar_date"].notna().any():
            by_web_total = objections.groupby("webinar_date").size()
            by_web_fin = fin.groupby("webinar_date").size()
            fin_pct = (by_web_fin / by_web_total * 100).dropna()
            if len(fin_pct):
                worst = fin_pct.idxmax()
                worst_pct = round(fin_pct.max(), 0)
                if worst_pct > 60:
                    st.markdown(
                        alert(
                            f"Webinar <strong>{worst}</strong> had {worst_pct:.0f}% financial "
                            f"objections — the audience may have been less qualified.",
                            "warning",
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    overall_pct = round(len(fin) / len(objections) * 100, 0)
                    st.markdown(
                        alert(
                            f"Financial objections make up {overall_pct:.0f}% of all objections across webinars.",
                            "info",
                        ),
                        unsafe_allow_html=True,
                    )
    else:
        st.info("No webinar date data available.")

    # ── Section 4: Child Profile ──────────────────────────────────
    st.markdown(section_header("Child Profile"), unsafe_allow_html=True)

    profile = calculate_child_profile(objections)

    left2, right2 = st.columns(2)
    with left2:
        age_df = profile["age_distribution"]
        if len(age_df):
            colors = [
                "#95A5A6" if g == "Unknown" else COLORS["primary"]
                for g in age_df["age_group"]
            ]
            import plotly.graph_objects as go
            fig = go.Figure(go.Bar(
                x=age_df["age_group"], y=age_df["count"],
                marker_color=colors, text=age_df["count"],
                textposition="outside",
            ))
            fig.update_layout(title_text="Child Age Distribution", xaxis_type="category")
            from utils.charts import apply_standard_layout
            st.plotly_chart(
                apply_standard_layout(fig),
                use_container_width=True,
            )
        else:
            st.info("No age data available.")

    with right2:
        issues_df = profile["child_issues"]
        if len(issues_df):
            st.plotly_chart(
                horizontal_bar_chart(
                    issues_df, x="count", y="issue",
                    title="Top Child Issues", text_col="count",
                ),
                use_container_width=True,
            )
        else:
            st.info("No child issue data available.")

    sit_df = profile["parent_situations"]
    if len(sit_df) >= 3:
        st.plotly_chart(
            horizontal_bar_chart(
                sit_df, x="count", y="situation",
                title="Parent Situations", text_col="count",
            ),
            use_container_width=True,
        )
    else:
        st.info("Not enough parent situation data captured yet.")

    # ── Section 5: All Failed Leads ───────────────────────────────
    st.markdown(section_header("All Failed Leads"), unsafe_allow_html=True)

    display_cols = ["name", "phone", "webinar_date", "category",
                    "primary_objection", "child_issue", "child_age", "notes"]
    show_df = objections[[c for c in display_cols if c in objections.columns]].copy()
    st.dataframe(
        show_df,
        use_container_width=True,
        column_config={
            "name": "Name",
            "phone": "Phone",
            "webinar_date": "Webinar",
            "category": "Category",
            "primary_objection": "Objection",
            "child_issue": "Child Issue",
            "child_age": "Child Age",
            "notes": "Notes",
        },
        hide_index=True,
    )

    # ── AI Insights ───────────────────────────────────────────────
    breakdown_text = "\n".join(
        f"  {row['category']}: {row['count']} ({row['pct']}%)"
        for _, row in breakdown.iterrows()
    )
    age_text = profile["age_distribution"].to_string(index=False) if len(profile["age_distribution"]) else "N/A"
    issues_text = profile["child_issues"].to_string(index=False) if len(profile["child_issues"]) else "N/A"
    sit_text = profile["parent_situations"].to_string(index=False) if len(profile["parent_situations"]) else "N/A"
    context = (
        f"Total failed leads: {summary['total']}\n"
        f"Top objection: {summary['top_category']} ({summary['top_category_pct']}%)\n"
        f"Webinar batches: {summary['webinar_batches']}\n"
        f"Objection breakdown:\n{breakdown_text}\n"
        f"Child age distribution:\n{age_text}\n"
        f"Top child issues:\n{issues_text}\n"
        f"Parent situations:\n{sit_text}"
    )
    render_ai_insights("failed_leads", context)
