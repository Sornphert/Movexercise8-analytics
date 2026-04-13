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
data = load_all()
config = data["config"]

# ── Header ────────────────────────────────────────────────────────
st.markdown(
    f'<div class="hdr"><h1>{config["program_name"]} Analytics</h1>'
    f'<p>by {config["teacher_name"]}</p></div>',
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("Data loaded")
    st.caption(f"**{len(data['leads']):,}** leads")
    st.caption(f"**{len(data['purchases'])}** purchases")
    st.caption(f"**{len(data['webinars'])}** webinar sessions")
    st.caption(f"**{len(data['meta'])}** ad rows")
    st.caption(f"**{len(data['objections'])}** objections")

    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

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
