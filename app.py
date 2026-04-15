import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Movexercise8 Analytics",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sections import ad_spend, ai_chat, cohort_analysis, failed_leads, lead_pipeline, overview, sales_revenue, webinar_performance
from utils.data_loader import load_all
from utils.styles import inject_css

inject_css()
_raw = load_all()
data = {k: v.copy() if hasattr(v, 'copy') else v for k, v in _raw.items()}
data["webinars"] = dict(data["webinars"])
config = data["config"]

min_date = data["leads"]["date"].min().date()
max_date = data["leads"]["date"].max().date()

# ── Header ────────────────────────────────────────────────────────
st.markdown(
    f'<div class="hdr"><h1>{config["program_name"]} Analytics</h1>'
    f'<p>by {config["teacher_name"]}</p></div>',
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

    if st.button("Fetch new Zoom data"):
        with st.spinner("Fetching from Zoom API..."):
            script = Path(__file__).parent / "scripts" / "fetch_zoom_data.py"
            result = subprocess.run(
                [sys.executable, str(script), "--days", "14"],
                capture_output=True, text=True,
            )
        if result.returncode == 0:
            created = sum(1 for ln in result.stdout.splitlines() if "-> created" in ln)
            skipped = sum(1 for ln in result.stdout.splitlines() if "-> skipped" in ln)
            if created:
                st.success(f"{created} new session(s) added, {skipped} already had.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.info(f"No new sessions. {skipped} already up to date.")
        else:
            st.error(f"Fetch failed: {result.stderr or result.stdout}")

    st.divider()
    st.header("Date Filter")
    date_range = st.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if len(date_range) == 2:
        start = pd.Timestamp(date_range[0])
        end = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
        data["leads"] = data["leads"][(data["leads"]["date"] >= start) & (data["leads"]["date"] < end)]
        data["purchases"] = data["purchases"][(data["purchases"]["date"] >= start) & (data["purchases"]["date"] < end)]
        obj = data["objections"]
        obj_dates = pd.to_datetime(obj["webinar_date"], errors="coerce")
        data["objections"] = obj[(obj_dates >= start) & (obj_dates < end)]
        data["webinars"] = {
            k: v for k, v in data["webinars"].items()
            if start <= pd.Timestamp(v["date"]) < end
        }

    st.divider()
    st.header("Data loaded")
    st.caption(f"**{len(data['leads']):,}** leads")
    st.caption(f"**{len(data['purchases'])}** purchases")
    st.caption(f"**{len(data['webinars'])}** webinar sessions")
    st.caption(f"**{len(data['meta'])}** ad rows")
    st.caption(f"**{len(data['objections'])}** objections")

    # Auto-load API key from secrets, allow sidebar override
    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = st.secrets.get("GEMINI_API_KEY", "")

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    ["Overview", "Sales & Revenue", "Lead Pipeline", "Webinar Performance",
     "Failed Leads", "Cohort Analysis", "Ad Spend & ROI", "AI Assistant"]
)

with tab1:
    overview.render(data)
with tab2:
    sales_revenue.render(data)
with tab3:
    lead_pipeline.render(data)
with tab4:
    webinar_performance.render(data)
with tab5:
    failed_leads.render(data)
with tab6:
    cohort_analysis.render(data)
with tab7:
    ad_spend.render(data)
with tab8:
    ai_chat.render(data)
