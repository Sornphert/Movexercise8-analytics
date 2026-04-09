import streamlit as st

MAIN_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap');

.stApp { font-family: 'DM Sans', sans-serif; }

/* ── header banner ── */
.hdr {
    background: linear-gradient(135deg, #1B4332, #2D6A4F, #40916C);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    color: #fff;
    margin-bottom: 1.5rem;
}
.hdr h1 {
    font-family: 'Fraunces', serif;
    font-size: 2rem;
    margin: 0;
    font-weight: 700;
}
.hdr p { margin: 0.3rem 0 0; opacity: 0.85; font-size: 0.95rem; }

/* ── metric card ── */
.mc {
    background: #fff;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    border-left: 3px solid #2D6A4F;
}
.mc-d { border-left-color: #E76F51; }
.mc-d .v { color: #E76F51 !important; }
.mc-w { border-left-color: #D4A843; }
.mc-w .v { color: #D4A843 !important; }

.mc .l {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6C757D;
    font-weight: 600;
    margin: 0;
}
.mc .v {
    font-size: 1.8rem;
    font-weight: 700;
    color: #1B4332;
    margin: 0.15rem 0;
    line-height: 1.2;
}
.mc .s {
    font-size: 0.78rem;
    color: #6C757D;
    margin: 0;
}

/* ── section header ── */
.sh {
    font-family: 'Fraunces', serif;
    font-size: 1.35rem;
    color: #1B4332;
    border-bottom: 2px solid #E8F0EB;
    padding-bottom: 0.5rem;
    margin: 1.5rem 0 1rem;
    font-weight: 600;
}

/* ── alert boxes ── */
.ad {
    padding: 0.8rem 1.2rem;
    border-radius: 8px;
    font-size: 0.88rem;
    margin-bottom: 1rem;
    line-height: 1.5;
}
.ad-b { background: #E8F4FD; color: #1B4332; border-left: 3px solid #2D6A4F; }
.ad-g { background: #E8F0EB; color: #1B4332; border-left: 3px solid #40916C; }
.ad-y { background: #FFF8E7; color: #5A4B1A; border-left: 3px solid #D4A843; }
.ad-r { background: #FDECEB; color: #7A2921; border-left: 3px solid #E76F51; }

/* ── hide Streamlit chrome ── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
"""

COLORS = {
    "primary": "#1B4332",
    "secondary": "#2D6A4F",
    "accent": "#D4A843",
    "success": "#40916C",
    "warning": "#D4A843",
    "danger": "#E76F51",
    "chart_palette": ["#1B4332", "#2D6A4F", "#40916C", "#D4A843", "#E9C46A", "#E76F51"],
}

_VARIANT_CLASS = {"danger": "mc-d", "warning": "mc-w"}


def metric_card(label: str, value: str, sub: str = "", variant: str = "") -> str:
    cls = f"mc {_VARIANT_CLASS.get(variant, '')}"
    sub_html = f'<p class="s">{sub}</p>' if sub else ""
    return f'<div class="{cls}"><p class="l">{label}</p><p class="v">{value}</p>{sub_html}</div>'


def inject_css():
    st.markdown(f"<style>{MAIN_CSS}</style>", unsafe_allow_html=True)


def section_header(title: str) -> str:
    return f'<div class="sh">{title}</div>'


_ALERT_CLASS = {"info": "ad-b", "success": "ad-g", "warning": "ad-y", "danger": "ad-r"}


def alert(message: str, variant: str = "info") -> str:
    cls = f"ad {_ALERT_CLASS.get(variant, 'ad-b')}"
    return f'<div class="{cls}">{message}</div>'
