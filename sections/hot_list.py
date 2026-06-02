import pandas as pd
import streamlit as st

from utils.data_loader import load_all
from utils.metrics import calculate_hot_list
from utils.styles import COLORS, alert, metric_card, section_header


def render(data: dict):
    # The Hot List must reason over the FULL dataset, never the sidebar-filtered
    # slice that app.py passes in. Buyer exclusion has to see every purchase (a
    # buyer outside the selected range must still be excluded), and the candidate
    # pool must not shrink with the date filter. Recency is already a scoring
    # signal, so we deliberately re-load the unfiltered (cached) data here.
    full = load_all()
    leads = full["leads"]
    purchases = full["purchases"]
    webinars = full["webinars"]
    ebook = full.get("ebook", pd.DataFrame())
    objections = full["objections"]

    st.markdown(section_header("Hot List"), unsafe_allow_html=True)
    st.caption(
        "Warm leads who have **not** purchased, ranked by buying signals — stayed to "
        "the offer pitch, high stated intent, a logged objection, recent attendance. "
        "Call top-down. Covers all data, not just the sidebar date range."
    )

    hot = calculate_hot_list(leads, purchases, webinars, ebook, objections)

    st.markdown(metric_card("Hot Leads", f"{len(hot)}"), unsafe_allow_html=True)

    if hot.empty:
        st.markdown(alert("No hot leads right now.", "info"), unsafe_allow_html=True)
        return

    def _color_score(v):
        if v >= 5:
            return f"color: {COLORS['success']}; font-weight: 700;"
        if v >= 3:
            return f"color: {COLORS['accent']}; font-weight: 600;"
        return f"color: {COLORS['secondary']}; font-weight: 600;"

    display = hot.rename(columns={
        "name": "Name",
        "phone": "Phone",
        "score": "Score",
        "reasons": "Why",
        "webinar_date": "Last webinar",
        "objection": "Objection",
        "intent": "Intent",
    })

    styled = display.style.map(_color_score, subset=["Score"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
