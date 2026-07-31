import pandas as pd
import streamlit as st

from utils.data_loader import load_all, load_email_aliases
from utils.metrics import calculate_payments_due, reconcile_payments_with_stripe
from utils.styles import COLORS, metric_card, section_header

_DISPLAY_RENAMES = {
    "name": "Name",
    "phone": "Phone",
    "monthly_amount": "This Month",
    "months_remaining": "Months Left",
    "months_label": "Progress",
    "total_outstanding": "Total Outstanding",
    "signup_date": "Signed Up",
}
_REQUIRED_STRIPE_COLS = ["Customer Email", "Status", "Amount", "Description"]


def _base_display(due: pd.DataFrame) -> pd.DataFrame:
    """Schedule columns, renamed and formatted, with internal cols dropped."""
    display = due.drop(
        columns=["norm_email", "norm_name", "stripe_status", "stripe_amount",
                 "stripe_email", "match_method"],
        errors="ignore",
    ).rename(columns=_DISPLAY_RENAMES).copy()
    display["Signed Up"] = display["Signed Up"].dt.strftime("%d %b %Y")
    # 0 months left = the buyer is in their final scheduled month (payment due now).
    display["Months Left"] = display["Months Left"].map(
        lambda n: "Final month" if n == 0 else str(int(n))
    )
    return display


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

    uploaded = st.file_uploader(
        "Upload Stripe export (CSV) to reconcile against actual charges",
        type=["csv"],
    )
    st.caption(
        "Matching tries email, then a staff-maintained alias table, then an exact "
        "name-in-email fallback. To permanently fix a buyer whose Stripe email differs "
        "from their purchase-sheet email, add a row to `data/email_aliases.csv` "
        "(`stripe_email,buyer_email`)."
    )

    if uploaded is None:
        _render_schedule_only(due)
        return

    stripe_df = pd.read_csv(uploaded)
    missing = [c for c in _REQUIRED_STRIPE_COLS if c not in stripe_df.columns]
    if missing:
        st.warning(
            "Stripe CSV is missing required column(s): "
            + ", ".join(f"'{c}'" for c in missing)
            + ". Showing the schedule-only view instead."
        )
        _render_schedule_only(due)
        return

    aliases = load_email_aliases()
    reconciled, unmatched = reconcile_payments_with_stripe(due, stripe_df, aliases)
    _render_reconciled(reconciled, unmatched)


def _render_schedule_only(due: pd.DataFrame):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(metric_card("Buyers Due", f"{len(due)}"), unsafe_allow_html=True)
    with c2:
        st.markdown(
            metric_card("Expected This Month", f"RM {due['monthly_amount'].sum():,.0f}"),
            unsafe_allow_html=True,
        )

    display = _base_display(due)
    styled = (
        display.style
        .set_properties(subset=["Total Outstanding"], **{"font-weight": "700"})
        .format({"This Month": "RM {:,.0f}", "Total Outstanding": "RM {:,.0f}"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


def _render_reconciled(reconciled: pd.DataFrame, unmatched: pd.DataFrame):
    status = reconciled["stripe_status"]
    paid_n = int((status == "Paid").sum())
    failed_n = int((status == "Failed").sum())
    norecord_n = int((status == "No record").sum())
    uncollected = reconciled.loc[status != "Paid", "monthly_amount"].sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Paid", f"{paid_n}"), unsafe_allow_html=True)
    with c2:
        st.markdown(
            metric_card("Failed (recoverable)", f"{failed_n}", variant="danger"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(metric_card("No Record", f"{norecord_n}"), unsafe_allow_html=True)
    with c4:
        st.markdown(
            metric_card("Still Uncollected", f"RM {uncollected:,.0f}"),
            unsafe_allow_html=True,
        )

    display = _base_display(reconciled)
    display["Status"] = reconciled["stripe_status"].values
    display["Matched by"] = reconciled["match_method"].values
    display["Stripe Email"] = reconciled["stripe_email"].values

    def _color_status(v):
        if v == "Paid":
            return f"color: {COLORS['success']}; font-weight: 700;"
        if v == "Failed":
            return f"color: {COLORS['danger']}; font-weight: 700;"
        return f"color: {COLORS['secondary']}; font-weight: 400;"

    styled = (
        display.style
        .map(_color_status, subset=["Status"])
        .set_properties(subset=["Total Outstanding"], **{"font-weight": "700"})
        .format({"This Month": "RM {:,.0f}", "Total Outstanding": "RM {:,.0f}"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    if not unmatched.empty:
        st.markdown(
            section_header("Stripe charges that didn't match a due buyer — check emails manually"),
            unsafe_allow_html=True,
        )
        st.caption(
            "These are Stripe Paid/Failed installment charges whose email matched no buyer "
            "in the due list — likely an email mismatch, or a buyer not currently due. "
            "Resolve by hand."
        )
        unmatched_display = unmatched.rename(columns={
            "stripe_email": "Stripe Email",
            "amount": "Amount",
            "status": "Status",
            "description": "Description",
        })
        st.dataframe(unmatched_display, use_container_width=True, hide_index=True)
