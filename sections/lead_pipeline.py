import pandas as pd
import streamlit as st

from utils.charts import bar_chart, funnel_chart, pie_chart
from utils.metrics import (
    calculate_funnel_stages,
    calculate_lead_to_sale_times,
)
from utils.ai import render_ai_insights
from utils.styles import metric_card, section_header


def _health_variant(pct: float) -> str:
    if pct >= 50:
        return ""
    return "warning" if pct >= 20 else "danger"


def render(data: dict):
    leads = data["leads"]
    purchases = data["purchases"]
    webinars = data["webinars"]
    objections = data["objections"]

    stages = calculate_funnel_stages(leads, purchases, webinars, objections)

    # ── Funnel chart ──────────────────────────────────────────────
    st.markdown(section_header("Lead Pipeline"), unsafe_allow_html=True)

    stage_names = [s[0] for s in stages]
    stage_values = [s[1] for s in stages]
    st.plotly_chart(
        funnel_chart(stage_names, stage_values, title="Full Funnel"),
        use_container_width=True,
    )

    # ── Stage-by-stage conversion rates ───────────────────────────
    st.markdown(section_header("Stage Conversion Rates"), unsafe_allow_html=True)

    cols = st.columns(len(stages) - 1)
    for i, col in enumerate(cols):
        prev_val = stages[i][1]
        curr_val = stages[i + 1][1]
        rate = round(curr_val / prev_val * 100, 1) if prev_val else 0.0
        label = f"{stages[i][0]} → {stages[i + 1][0]}"
        with col:
            st.markdown(
                metric_card(label, f"{rate}%", f"{curr_val:,} / {prev_val:,}",
                            variant=_health_variant(rate)),
                unsafe_allow_html=True,
            )

    # ── Period comparison ─────────────────────────────────────────
    st.markdown(section_header("This Month vs Last Month vs All-Time"), unsafe_allow_html=True)

    today = pd.Timestamp.today().normalize()
    month_start = today.replace(day=1)
    last_month_start = (month_start - pd.Timedelta(days=1)).replace(day=1)

    def _period_stages(ld, pu):
        total = len(ld)
        buyers = len(pu)
        paid = int(pu["payment_complete"].sum()) if len(pu) else 0
        conv = round(buyers / total * 100, 1) if total else 0.0
        pay_rate = round(paid / buyers * 100, 1) if buyers else 0.0
        return total, buyers, paid, conv, pay_rate

    leads_this = leads[leads["date"] >= month_start]
    purch_this = purchases[purchases["date"] >= month_start]
    leads_last = leads[(leads["date"] >= last_month_start) & (leads["date"] < month_start)]
    purch_last = purchases[(purchases["date"] >= last_month_start) & (purchases["date"] < month_start)]

    this_m = _period_stages(leads_this, purch_this)
    last_m = _period_stages(leads_last, purch_last)
    all_t = _period_stages(leads, purchases)

    p1, p2, p3 = st.columns(3)
    for col, label, vals in [(p1, "This Month", this_m), (p2, "Last Month", last_m), (p3, "All-Time", all_t)]:
        with col:
            st.markdown(f"**{label}**")
            st.markdown(
                metric_card("Leads", f"{vals[0]:,}"),
                unsafe_allow_html=True,
            )
            st.markdown(
                metric_card("Buyers", f"{vals[1]:,}", f"Conversion: {vals[3]}%",
                            variant=_health_variant(vals[3])),
                unsafe_allow_html=True,
            )
            st.markdown(
                metric_card("Paid", f"{vals[2]:,}", f"Payment rate: {vals[4]}%"),
                unsafe_allow_html=True,
            )

    # ── Lead source breakdown ─────────────────────────────────────
    st.markdown(section_header("Lead Sources"), unsafe_allow_html=True)

    src = leads["utm_campaign"].fillna("(direct / organic)").value_counts().reset_index()
    src.columns = ["source", "count"]
    top5 = src.head(5)
    other_count = src["count"].iloc[5:].sum()
    if other_count > 0:
        top5 = pd.concat(
            [top5, pd.DataFrame([{"source": "Other", "count": other_count}])],
            ignore_index=True,
        )
    st.plotly_chart(
        pie_chart(top5, "count", "source", title="Top Lead Sources"),
        use_container_width=True,
    )

    # ── Lead-to-sale time histogram ───────────────────────────────
    st.markdown(section_header("Time from Lead to Sale"), unsafe_allow_html=True)

    day_diffs = calculate_lead_to_sale_times(leads, purchases)
    if day_diffs:
        def _bucket(d: int) -> str:
            if d <= 7:
                return "0–7 days"
            if d <= 14:
                return "8–14 days"
            if d <= 30:
                return "15–30 days"
            return "30+ days"

        bucket_order = ["0–7 days", "8–14 days", "15–30 days", "30+ days"]
        hist = pd.DataFrame({"days": day_diffs})
        hist["bucket"] = hist["days"].apply(_bucket)
        counts = (
            hist["bucket"]
            .value_counts()
            .reindex(bucket_order, fill_value=0)
            .reset_index()
        )
        counts.columns = ["bucket", "count"]
        st.plotly_chart(
            bar_chart(counts, "bucket", "count", title="Days to Convert", text_col="count"),
            use_container_width=True,
        )
        st.caption(f"Based on {len(day_diffs)} matched lead → purchase pairs. "
                   f"Median: {sorted(day_diffs)[len(day_diffs)//2]} days.")
    else:
        st.info("No matched lead-to-sale data available.")

    # ── AI Insights ──────────────────────────────────────────────
    stage_text = " -> ".join(f"{s[0]}: {s[1]:,}" for s in stages)
    conv_rates = []
    for i in range(len(stages) - 1):
        prev_val = stages[i][1]
        curr_val = stages[i + 1][1]
        rate = round(curr_val / prev_val * 100, 1) if prev_val else 0.0
        conv_rates.append(f"{stages[i][0]}->{stages[i+1][0]}: {rate}%")
    median_days = sorted(day_diffs)[len(day_diffs) // 2] if day_diffs else "N/A"
    context = (
        f"Funnel: {stage_text}\n"
        f"Stage conversion rates: {', '.join(conv_rates)}\n"
        f"This month leads: {this_m[0]:,}, buyers: {this_m[1]}, conv: {this_m[3]}%\n"
        f"Last month leads: {last_m[0]:,}, buyers: {last_m[1]}, conv: {last_m[3]}%\n"
        f"Lead sources: {src.head(5).to_string(index=False)}\n"
        f"Lead-to-sale median: {median_days} days ({len(day_diffs)} matched pairs)"
    )
    render_ai_insights("lead_pipeline", context)
