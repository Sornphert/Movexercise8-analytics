import pandas as pd
import streamlit as st

from utils.charts import bar_chart, pie_chart
from utils.metrics import (
    calculate_revenue_metrics,
    get_monthly_revenue,
    get_outstanding_payments,
    get_payment_completion_by_status,
    get_top_customers,
)
from utils.styles import metric_card, section_header


def render(data: dict):
    purchases = data["purchases"]
    rev = calculate_revenue_metrics(purchases)

    # ── Hero cards ────────────────────────────────────────────────
    st.markdown(section_header("Sales & Revenue"), unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
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
            metric_card("Avg per Buyer", f"RM {rev['avg_per_buyer']:,.0f}"),
            unsafe_allow_html=True,
        )

    # ── Revenue by status / method charts ─────────────────────────
    st.markdown(section_header("Revenue Breakdown"), unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        by_status = pd.DataFrame(
            list(rev["revenue_by_status"].items()), columns=["status", "amount"]
        )
        st.plotly_chart(
            bar_chart(by_status, "status", "amount", title="By Status", text_col="amount"),
            use_container_width=True,
        )
    with right:
        by_method = pd.DataFrame(
            list(rev["revenue_by_method"].items()), columns=["method", "amount"]
        )
        st.plotly_chart(
            pie_chart(by_method, "amount", "method", title="By Payment Method"),
            use_container_width=True,
        )

    # ── Outstanding payments table ────────────────────────────────
    st.markdown(section_header("Outstanding Payments"), unsafe_allow_html=True)

    outstanding = get_outstanding_payments(purchases)
    if len(outstanding):
        st.dataframe(
            outstanding,
            use_container_width=True,
            column_config={
                "name": "Name",
                "amount": st.column_config.NumberColumn("Amount (RM)", format="%.0f"),
                "status": "Status",
                "date": st.column_config.DateColumn("Date"),
                "days_overdue": "Days Overdue",
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

    # ── Top 10 customers ──────────────────────────────────────────
    st.markdown(section_header("Top 10 Highest-Paying Customers"), unsafe_allow_html=True)

    st.dataframe(
        get_top_customers(purchases),
        use_container_width=True,
        column_config={
            "name": "Name",
            "amount": st.column_config.NumberColumn("Amount (RM)", format="%.0f"),
            "status": "Status",
            "payment_method": "Payment Method",
        },
        hide_index=True,
    )

    # ── Monthly revenue chart ─────────────────────────────────────
    st.markdown(section_header("Monthly Revenue"), unsafe_allow_html=True)

    monthly = get_monthly_revenue(purchases)
    monthly["label"] = monthly["revenue"].apply(lambda v: f"RM {v:,.0f}")
    st.plotly_chart(
        bar_chart(monthly, "month", "revenue", text_col="label"),
        use_container_width=True,
    )
