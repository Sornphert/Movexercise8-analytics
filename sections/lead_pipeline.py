import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.ai import render_ai_insights
from utils.charts import apply_standard_layout, bar_chart, funnel_chart
from utils.metrics import (
    calculate_funnel_health,
    calculate_lead_source_quality,
    calculate_show_up_diagnostics,
    calculate_time_to_convert_buckets,
)
from utils.styles import COLORS, alert, metric_card, section_header

_HEALTH_VARIANT = {"green": "", "yellow": "warning", "red": "danger"}


def render(data: dict):
    leads = data["leads"]
    purchases = data["purchases"]
    webinars = data["webinars"]
    objections = data["objections"]

    if leads.empty:
        st.warning("No lead data in the selected date range.")
        return

    health = _render_funnel_health(leads, purchases, webinars, objections)
    show_up = _render_show_up_diagnosis(leads, webinars)
    source_table = _render_lead_source_quality(leads, purchases)
    convert = _render_time_to_convert(leads, purchases)
    _render_ai(health, show_up, source_table, convert)


def _render_funnel_health(leads, purchases, webinars, objections):
    health = calculate_funnel_health(leads, purchases, webinars, objections)

    st.markdown(section_header("Funnel"), unsafe_allow_html=True)
    stage_names = [s["name"] for s in health["stages"]]
    stage_values = [s["count"] for s in health["stages"]]
    st.plotly_chart(
        funnel_chart(stage_names, stage_values, title="Full Funnel"),
        use_container_width=True,
    )

    cols = st.columns(len(health["transitions"]))
    for col, t in zip(cols, health["transitions"]):
        with col:
            st.markdown(
                metric_card(
                    t["label"],
                    f"{t['rate']}%",
                    f"{t['numer']:,} / {t['denom']:,}",
                    variant=_HEALTH_VARIANT[t["health"]],
                ),
                unsafe_allow_html=True,
            )

    weakest = health["weakest_stage"]
    if weakest is not None:
        st.markdown(
            alert(
                f"⚠️ The biggest leak is at <b>{weakest['label']}</b>: only "
                f"{weakest['rate']}% convert. Target benchmark is "
                f"{weakest['benchmark']}% — a gap of {weakest['gap_pp']} pp.",
                variant="warning",
            ),
            unsafe_allow_html=True,
        )

    return health


def _render_show_up_diagnosis(leads, webinars):
    st.markdown(section_header("Show-up Diagnosis"), unsafe_allow_html=True)
    if not webinars:
        st.info("No webinar data available.")
        return None

    diag = calculate_show_up_diagnostics(leads, webinars)
    per = diag["per_webinar"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            metric_card("Average Show-up", f"{diag['avg_show_up']}%",
                        "Registration-weighted across all webinars"),
            unsafe_allow_html=True,
        )
    with c2:
        if diag["best"]:
            st.markdown(
                metric_card("Best Webinar",
                            f"{round(diag['best']['rate'], 1)}%",
                            diag["best"]["date"]),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(metric_card("Best Webinar", "—"), unsafe_allow_html=True)
    with c3:
        if diag["worst"]:
            st.markdown(
                metric_card("Worst Webinar",
                            f"{round(diag['worst']['rate'], 1)}%",
                            diag["worst"]["date"], variant="danger"),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(metric_card("Worst Webinar", "—"), unsafe_allow_html=True)

    if per.empty:
        st.info("No webinars with registered leads in this range.")
        return diag

    display = per.rename(columns={
        "date": "Date",
        "registered": "Registered",
        "attended": "Attended",
        "show_up_rate": "Show-up %",
        "avg_days_before": "Avg Days Before",
    })
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Show-up %": st.column_config.ProgressColumn(
                "Show-up %", min_value=0, max_value=100, format="%.1f%%"
            ),
            "Avg Days Before": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    plot_df = per[(per["registered"] > 0)].copy()
    if len(plot_df) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=plot_df["avg_days_before"], y=plot_df["show_up_rate"],
            mode="markers+text",
            text=plot_df["date"], textposition="top center",
            marker=dict(size=10, color=COLORS["secondary"]),
            name="Webinars",
            hovertemplate="%{text}<br>Avg days before: %{x:.1f}<br>Show-up: %{y:.1f}%<extra></extra>",
        ))
        if len(plot_df) >= 3:
            x = plot_df["avg_days_before"].to_numpy()
            y = plot_df["show_up_rate"].to_numpy()
            try:
                slope, intercept = np.polyfit(x, y, 1)
                xs = np.linspace(x.min(), x.max(), 50)
                fig.add_trace(go.Scatter(
                    x=xs, y=slope * xs + intercept,
                    mode="lines", line=dict(color=COLORS["accent"], dash="dash"),
                    name="Trend", hoverinfo="skip",
                ))
            except (np.linalg.LinAlgError, ValueError):
                pass
        fig.update_layout(
            title_text="Show-up Rate vs Registration Lead Time",
            xaxis_title="Avg days between registration and webinar",
            yaxis_title="Show-up rate (%)",
            showlegend=False,
        )
        st.plotly_chart(apply_standard_layout(fig, height=380), use_container_width=True)

    return diag


def _render_lead_source_quality(leads, purchases):
    st.markdown(section_header("Lead Source Quality"), unsafe_allow_html=True)
    table = calculate_lead_source_quality(leads, purchases)
    if table.empty:
        st.info("No lead source data available.")
        return table

    total_leads = int(table["leads"].sum())
    no_utm_row = table[table["campaign_full"] == "No UTM"]
    no_utm_pct = (
        round(int(no_utm_row["leads"].iloc[0]) / total_leads * 100, 1)
        if not no_utm_row.empty and total_leads > 0 else 0.0
    )

    display = table.rename(columns={
        "campaign_short": "Campaign",
        "leads": "Leads",
        "buyers": "Buyers",
        "conv_rate": "Conv %",
        "avg_days_to_purchase": "Avg Days to Purchase",
    })[["Campaign", "Leads", "Buyers", "Conv %", "Avg Days to Purchase", "campaign_full"]]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Campaign": st.column_config.TextColumn(
                "Campaign", help="Hover row for full UTM campaign name"
            ),
            "campaign_full": st.column_config.TextColumn("Full UTM"),
            "Conv %": st.column_config.NumberColumn(format="%.2f%%"),
            "Avg Days to Purchase": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    if no_utm_pct > 50:
        st.markdown(
            alert(
                f"⚠️ {no_utm_pct}% of leads have no UTM tracking. "
                "Improving UTM coverage would unlock better source analysis.",
                variant="warning",
            ),
            unsafe_allow_html=True,
        )
    return table


def _render_time_to_convert(leads, purchases):
    st.markdown(section_header("Time to Convert"), unsafe_allow_html=True)
    convert = calculate_time_to_convert_buckets(leads, purchases)
    buckets = convert["buckets"]
    if int(buckets["count"].sum()) == 0:
        st.info("No matched lead-to-sale data available.")
        return convert

    st.plotly_chart(
        bar_chart(buckets, "bucket", "count", title="Days to Convert",
                  text_col="count", category_x=True),
        use_container_width=True,
    )
    median = convert["median_days"]
    if median is not None:
        st.caption(
            f"Median time to purchase: {median} days. Most buyers "
            f"({convert['within_7_pct']}%) decide within 7 days — focus follow-up "
            "energy in this window."
        )
    return convert


def _render_ai(health, show_up, source_table, convert):
    stage_text = " -> ".join(f"{s['name']}: {s['count']:,}" for s in health["stages"])
    transition_text = ", ".join(
        f"{t['label']}: {t['rate']}%" for t in health["transitions"]
    )
    weakest = health["weakest_stage"]
    weakest_text = (
        f"{weakest['label']} at {weakest['rate']}% (target {weakest['benchmark']}%)"
        if weakest else "n/a"
    )
    show_up_text = (
        f"avg {show_up['avg_show_up']}%, best {show_up['best']['date']} "
        f"({round(show_up['best']['rate'], 1)}%), worst {show_up['worst']['date']} "
        f"({round(show_up['worst']['rate'], 1)}%)"
        if show_up and show_up["best"] and show_up["worst"]
        else "n/a"
    )
    median = convert["median_days"] if convert else None
    top_sources = (
        source_table.head(5)[["campaign_short", "leads", "buyers", "conv_rate"]].to_string(index=False)
        if source_table is not None and not source_table.empty else "n/a"
    )

    context = (
        f"Funnel: {stage_text}\n"
        f"Transitions: {transition_text}\n"
        f"Weakest stage: {weakest_text}\n"
        f"Show-up: {show_up_text}\n"
        f"Median lead-to-purchase: {median if median is not None else 'n/a'} days\n"
        f"Top lead sources:\n{top_sources}"
    )
    render_ai_insights("lead_pipeline", context)
