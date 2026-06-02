import streamlit as st

from utils.data_loader import load_all
from utils.metrics import calculate_payments_due
from utils.styles import metric_card, section_header


def render(data: dict):
    # This is a monthly collection worklist, not a date-scoped report. A buyer who
    # signed up months ago still owes this month, so we must reason over the FULL
    # purchase set — never the sidebar-filtered slice app.py passes in. We re-load
    # the unfiltered (cached) data, same as the Hot List tab.
    full = load_all()
    purchases = full["purchases"]
    course_fee = full["config"].get("course_fee_full", 2688)
    due = calculate_payments_due(purchases, course_fee_full=course_fee)

    st.markdown(section_header("Payments Due"), unsafe_allow_html=True)
    st.caption(
        "Installment buyers scheduled to pay this calendar month, ranked by total still "
        "owed — chase the biggest balances first. This reflects the payment schedule "
        "inferred from signup data: it shows who is *due* per plan, not confirmed-unpaid "
        "(a buyer may have already paid this month or paid early). Covers all data, not "
        "just the sidebar date range."
    )

    if due.empty:
        st.info("No installment payments scheduled this month.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(metric_card("Buyers Due", f"{len(due)}"), unsafe_allow_html=True)
    with c2:
        st.markdown(
            metric_card("Expected This Month", f"RM {due['monthly_amount'].sum():,.0f}"),
            unsafe_allow_html=True,
        )

    display = due.rename(columns={
        "name": "Name",
        "phone": "Phone",
        "monthly_amount": "This Month",
        "months_remaining": "Months Left",
        "months_label": "Progress",
        "total_outstanding": "Total Outstanding",
        "signup_date": "Signed Up",
    }).copy()
    display["Signed Up"] = display["Signed Up"].dt.strftime("%d %b %Y")

    styled = (
        display.style
        .set_properties(subset=["Total Outstanding"], **{"font-weight": "700"})
        .format({
            "This Month": "RM {:,.0f}",
            "Total Outstanding": "RM {:,.0f}",
        })
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
