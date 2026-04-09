import streamlit as st

st.set_page_config(
    page_title="MOVEXERCISE8 Analytics",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sections import lead_pipeline, overview, sales_revenue, webinar_performance
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

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["Overview", "Sales & Revenue", "Lead Pipeline", "Webinar Performance"]
)

with tab1:
    overview.render(data)
with tab2:
    sales_revenue.render(data)
with tab3:
    lead_pipeline.render(data)
with tab4:
    webinar_performance.render(data)
