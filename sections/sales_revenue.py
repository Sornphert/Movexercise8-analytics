import pandas as pd
import streamlit as st

from utils.charts import bar_chart, pie_chart
from utils.metrics import (
    calculate_revenue_metrics,
    get_monthly_revenue,
    get_outstanding_payments,
    get_payment_completion_by_status,
    get_revenue_by_payment_method,
    get_revenue_by_status,
)
from utils.ai import render_ai_insights
from utils.styles import metric_card, section_header


def render(data: dict):
    purchases = data["purchases"]
    course_fee_full = data["config"].get("course_fee_full", 2688)
    today = pd.Timestamp.today().normalize()

    rev = calculate_revenue_metrics(purchases, course_fee_full, today)

    # ── Hero cards ────────────────────────────────────────────────
    st.markdown(section_header("Sales & Revenue"), unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(
            metric_card("Total Revenue", f"RM {rev['total_revenue']:,.0f}",
                        f"{rev['total_transactions']} transactions"),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card("Collected", f"RM {rev['collected_revenue']:,.0f}"),
            unsafe_allow_html=True,
        )
    with c3:
        variant = "danger" if rev["outstanding_revenue"] > 10_000 else ""
        st.markdown(
            metric_card("Outstanding", f"RM {rev['outstanding_revenue']:,.0f}", variant=variant),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            metric_card("This Month", f"RM {rev['this_month_revenue']:,.0f}",
                        rev["this_month_label"]),
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            metric_card("Last Month", f"RM {rev['last_month_revenue']:,.0f}",
                        rev["last_month_label"]),
            unsafe_allow_html=True,
        )

    # ── Revenue by status / method charts ─────────────────────────
    st.markdown(section_header("Revenue Breakdown"), unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        by_status = get_revenue_by_status(purchases, course_fee_full, today)
        st.plotly_chart(
            pie_chart(by_status, "revenue", "status", title="By Status"),
            use_container_width=True,
        )
    with right:
        by_method = get_revenue_by_payment_method(purchases, course_fee_full, today)
        st.plotly_chart(
            pie_chart(by_method, "revenue", "payment_method", title="By Payment Method"),
            use_container_width=True,
        )

    # ── Outstanding payments table ────────────────────────────────
    st.markdown(section_header("Outstanding Payments"), unsafe_allow_html=True)

    outstanding = get_outstanding_payments(purchases, course_fee_full, today)
    if len(outstanding):
        st.dataframe(
            outstanding,
            use_container_width=True,
            column_config={
                "name": "Name",
                "phone": "Phone",
                "amount": st.column_config.NumberColumn("Amount (RM)", format="%.0f"),
                "status": "Status",
                "date": st.column_config.DateColumn("Date"),
            },
            hide_index=True,
        )
    else:
        st.success("All payments complete!")

    # ── Payment completion by status ──────────────────────────────
    st.markdown(section_header("Payment Completion by Status"), unsafe_allow_html=True)

    for row in get_payment_completion_by_status(purchases):
        st.text(f"{row['status']}: {row['complete']}/{row['total']} completed ({row['pct']}%)")
        st.progress(row["pct"] / 100)

    # ── Monthly revenue chart ─────────────────────────────────────
    st.markdown(section_header("Monthly Revenue"), unsafe_allow_html=True)

    monthly = get_monthly_revenue(purchases)
    monthly["label"] = monthly["revenue"].apply(lambda v: f"RM {v:,.0f}")
    st.plotly_chart(
        bar_chart(monthly, "month", "revenue", text_col="label"),
        use_container_width=True,
    )

    # ── AI Insights ──────────────────────────────────────────────
    completion_lines = "\n".join(
        f"  {r['status']}: {r['complete']}/{r['total']} ({r['pct']}%)"
        for r in get_payment_completion_by_status(purchases)
    )
    context = (
        f"Revenue: RM {rev['total_revenue']:,.0f} total, "
        f"RM {rev['collected_revenue']:,.0f} collected, "
        f"RM {rev['outstanding_revenue']:,.0f} outstanding\n"
        f"This month ({rev['this_month_label']}): RM {rev['this_month_revenue']:,.0f}; "
        f"last month ({rev['last_month_label']}): RM {rev['last_month_revenue']:,.0f}\n"
        f"Transactions: {rev['total_transactions']}\n"
        f"Revenue by status: {rev['revenue_by_status']}\n"
        f"Revenue by method: {rev['revenue_by_method']}\n"
        f"Payment completion by status:\n{completion_lines}\n"
        f"Outstanding payments: {len(outstanding)} buyers"
    )
    render_ai_insights("sales_revenue", context)
