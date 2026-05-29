import html

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

/* ── info icon + hover tooltip on metric card label ── */
.mc .l { display: flex; align-items: center; gap: 0.4rem; }
.mc-i {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #E8F0EB;
    color: #2D6A4F;
    font-family: 'Fraunces', serif;
    font-size: 0.65rem;
    font-style: italic;
    font-weight: 700;
    cursor: help;
    position: relative;
    text-transform: none;
    letter-spacing: 0;
}
.mc-i:hover { background: #2D6A4F; color: #fff; }
.mc-i:hover::after {
    content: attr(data-tip);
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%);
    background: #1B4332;
    color: #fff;
    padding: 0.5rem 0.7rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 400;
    line-height: 1.4;
    letter-spacing: 0;
    text-transform: none;
    white-space: normal;
    width: max-content;
    max-width: 240px;
    z-index: 10;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    pointer-events: none;
}
.mc-i:hover::before {
    content: "";
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 5px solid transparent;
    border-top-color: #1B4332;
    z-index: 10;
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

/* ── decision panels — Kill / Scale / Test ── */
.dp {
    background: #fff;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    border-left: 4px solid #6C757D;
    height: 100%;
}
.dp h4 {
    font-family: 'Fraunces', serif;
    font-size: 1rem;
    margin: 0 0 0.6rem;
    color: #1B4332;
}
.dp ul {
    margin: 0;
    padding-left: 1.1rem;
    font-size: 0.85rem;
    line-height: 1.6;
    color: #1B4332;
}
.dp .foot {
    margin: 0.7rem 0 0;
    font-size: 0.78rem;
    color: #6C757D;
    font-weight: 600;
}
.dp-r { border-left-color: #E76F51; }
.dp-g { border-left-color: #40916C; }
.dp-y { border-left-color: #D4A843; }

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


def metric_card(label: str, value: str, sub: str = "", variant: str = "", info: str = "") -> str:
    cls = f"mc {_VARIANT_CLASS.get(variant, '')}"
    sub_html = f'<p class="s">{sub}</p>' if sub else ""
    info_html = (
        f'<span class="mc-i" data-tip="{html.escape(info, quote=True)}">i</span>'
        if info else ""
    )
    return (
        f'<div class="{cls}">'
        f'<p class="l">{label}{info_html}</p>'
        f'<p class="v">{value}</p>{sub_html}'
        f'</div>'
    )


def inject_css():
    st.markdown(f"<style>{MAIN_CSS}</style>", unsafe_allow_html=True)


def section_header(title: str) -> str:
    return f'<div class="sh">{title}</div>'


_ALERT_CLASS = {"info": "ad-b", "success": "ad-g", "warning": "ad-y", "danger": "ad-r"}


def alert(message: str, variant: str = "info") -> str:
    cls = f"ad {_ALERT_CLASS.get(variant, 'ad-b')}"
    return f'<div class="{cls}">{message}</div>'


def decision_panel(title: str, items: list, footer: str, variant: str = "r") -> str:
    """variant: 'r' (kill/red), 'g' (scale/green), 'y' (test/yellow)."""
    cls = f"dp dp-{variant}"
    if not items:
        return f'<div class="{cls}"><h4>{title}</h4><p class="foot">{footer}</p></div>'
    bullets = "".join(f"<li>{it}</li>" for it in items)
    return (f'<div class="{cls}"><h4>{title}</h4>'
            f'<ul>{bullets}</ul><p class="foot">{footer}</p></div>')
