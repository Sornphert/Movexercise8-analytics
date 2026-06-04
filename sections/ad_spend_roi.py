from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.ai import render_ai_insights
from utils.charts import apply_standard_layout, pie_chart
from utils.data_loader import (
    build_creative_thumbnail_map, creative_placeholder_data_uri,
)
from utils.metrics import (
    calculate_ad_spend_snapshot, calculate_break_even_analysis,
    calculate_campaign_performance, calculate_creative_fatigue,
    calculate_creative_type_performance, calculate_daily_spend_trend,
    calculate_kill_impact, get_top_ads_with_buyers,
    identify_kill_ads, identify_scale_ads, identify_test_ads,
)
from utils.styles import COLORS, alert, decision_panel, metric_card, section_header

_ROAS_VARIANT = {"green": "", "yellow": "warning", "red": "danger"}
_HEALTH_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
_FATIGUE_BADGE = {"fatiguing": "🔴 Fatiguing", "saturated": "🟠 Saturated",
                  "fresh": "🟢 Fresh", "improving": "🔵 Improving"}


def _N(label, fmt=None):
    return st.column_config.NumberColumn(label, format=fmt) if fmt else st.column_config.NumberColumn(label)
def _T(label, **kw): return st.column_config.TextColumn(label, **kw)


_CT_CONFIG = {"type": _T("Type"), "ads": _N("Ads"), "spend": _N("Spend", "RM %.0f"),
              "leads": _N("Leads"), "buyers": _N("Buyers"), "revenue": _N("Revenue", "RM %.0f"),
              "cpl": _N("CPL", "RM %.2f"), "cpa": _N("CPA", "RM %.2f"),
              "roas": _N("ROAS", "%.2fx"), "ctr": _N("CTR %", "%.2f")}

_CAMP_CONFIG = {"campaign_name": _T("Campaign", help="Hover row to see full name", width="large"),
                "active_ads": _N("Ads"), "spend": _N("Spend", "RM %.0f"), "leads": _N("Leads"),
                "buyers": _N("Buyers"), "revenue": _N("Revenue", "RM %.0f"),
                "cpl": _N("CPL", "RM %.2f"), "cpa": _N("CPA", "RM %.2f"),
                "roas": _N("ROAS", "%.2fx"), "health": _T("Health")}

_FATIGUE_CONFIG = {"short_name": _T("Ad"), "status": _T("Status"),
                   "recent_cpl": _N("Recent CPL", "RM %.2f"),
                   "previous_cpl": _N("Prev CPL", "RM %.2f"),
                   "change_pct": _N("Change %", "%+.1f%%"), "frequency": _N("Freq", "%.2fx")}

_TOP_CONFIG = {"short_name": _T("Ad", width="medium"),
               "spend": _N("Spend", "RM %.0f"), "leads": _N("Leads"), "buyers": _N("Buyers"),
               "revenue": _N("Revenue", "RM %.0f"), "cpl": _N("CPL", "RM %.2f"),
               "cpa": _N("CPA", "RM %.2f"), "roas": _N("ROAS", "%.2fx"),
               "clicks": _N("Clicks"), "ctr": _N("CTR %", "%.2f"),
               "frequency": _N("Freq", "%.2fx"),
               "frequency_status": _T("Status", width="small"),
               "days_running": _N("Days"),
               "quality_ranking": _T("Quality")}


def render(data: dict) -> None:
    meta, purchases, leads = data["meta"], data["purchases"], data["leads"]
    attribution = data.get("ad_attribution", pd.DataFrame())
    creatives = data.get("ad_creatives", pd.DataFrame())
    config = data["config"]
    if meta.empty:
        st.warning("No ad data available. Run scripts/fetch_meta_ads.py to pull from Meta API.")
        return
    snap = calculate_ad_spend_snapshot(meta, purchases, attribution)
    _render_spend_snapshot(snap)
    _render_spend_trend(meta, purchases, attribution, snap)
    _render_decision_panels(meta, attribution, purchases)
    _render_creative_type(meta, attribution)
    _render_campaign_performance(meta, attribution)
    _render_creative_fatigue(meta, attribution)
    _render_top_ads_table(meta, attribution, creatives)
    _render_quality_rankings(meta)
    _render_break_even_analysis(meta, purchases, attribution, leads, config)
    _render_ai(snap, meta, attribution)


def _format_delta(change_pct, previous_value, time_label: str = "prev 7d") -> str:
    if change_pct is None:
        if not previous_value:
            return f"new this week (no prior {time_label})"
        return ""
    arrow = "↑" if change_pct > 0 else ("↓" if change_pct < 0 else "→")
    if change_pct == 0:
        return f"→ flat vs {time_label}"
    return f"{arrow} {abs(change_pct):.0f}% vs {time_label}"


def _join_sub(prefix: str, delta: str) -> str:
    return f"{prefix} · {delta}" if delta else prefix


def _render_spend_snapshot(s: dict) -> None:
    st.markdown(section_header("Spend Snapshot"), unsafe_allow_html=True)
    buyer_change = s["buyers"]["change_pct"]
    buyer_v = "danger" if s["buyers"]["value"] == 0 or (
        buyer_change is not None and buyer_change < 0) else ""
    cards = [
        ("Total Spend (7d)", f"RM {s['spend']['value']:,.0f}",
         _format_delta(s["spend"]["change_pct"], s["spend"]["previous"]), ""),
        ("Leads (7d)", f"{s['leads']['value']:,}",
         _join_sub(f"CPL: RM {s['leads']['cpl']:.2f}",
                   _format_delta(s["leads"]["change_pct"], s["leads"]["previous"])), ""),
        ("Buyers (7d)", f"{s['buyers']['value']:,}",
         _join_sub(f"CPA: RM {s['buyers']['cpa']:.2f}",
                   _format_delta(s["buyers"]["change_pct"], s["buyers"]["previous"])), buyer_v),
        ("Revenue (7d)", f"RM {s['revenue']['value']:,.0f}",
         _format_delta(s["revenue"]["change_pct"], s["revenue"]["previous"]), ""),
        ("ROAS (7d)", f"{s['roas']['value']:.2f}x", f"prev: {s['roas']['previous']:.2f}x",
         _ROAS_VARIANT[s["roas"]["health"]]),
    ]
    for col, (l, v, sub, var) in zip(st.columns(5), cards):
        with col: st.markdown(metric_card(l, v, sub, variant=var), unsafe_allow_html=True)


def _render_spend_trend(meta, purchases, attribution, s) -> None:
    st.markdown(section_header("Spend Trend Over Time"), unsafe_allow_html=True)
    trend = calculate_daily_spend_trend(meta, purchases, attribution)
    if trend.empty:
        st.info("No daily trend data yet."); return
    fig = go.Figure()
    fig.add_trace(go.Bar(x=trend["date"], y=trend["spend"], name="Spend (RM)",
                         marker_color=COLORS["secondary"], opacity=0.85))
    fig.add_trace(go.Scatter(x=trend["date"], y=trend["leads"], name="Leads", mode="lines",
                             line=dict(color=COLORS["accent"], width=2.5), yaxis="y2"))
    fig.add_trace(go.Scatter(x=trend["date"], y=trend["buyers"], name="Buyers", mode="lines",
                             line=dict(color=COLORS["danger"], width=2, dash="dash"), yaxis="y2"))
    fig.update_layout(title_text="",
                      yaxis=dict(title="Spend (RM)"),
                      yaxis2=dict(title="Leads / Buyers", overlaying="y", side="right"),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(apply_standard_layout(fig, height=380), use_container_width=True)

    prev_cpl = s["leads"]["previous_cpl"]
    cpl_change = 0.0 if prev_cpl == 0 else (s["leads"]["cpl"] - prev_cpl) / prev_cpl * 100
    if cpl_change > 15:
        msg, var = (f"CPL trending up ({cpl_change:+.0f}% vs prev 7d) — investigate creative fatigue.",
                    "warning")
    elif s["roas"]["value"] > 3 and s["roas"]["value"] >= s["roas"]["previous"]:
        msg, var = (f"Strong week — ROAS {s['roas']['value']:.2f}x. Consider scaling winners.", "success")
    else:
        msg, var = (f"Last 7 days: RM {s['spend']['value']:,.0f} spent, "
                    f"{s['leads']['value']} leads, {s['buyers']['value']} buyers.", "info")
    st.markdown(alert(msg, var), unsafe_allow_html=True)


def _render_decision_panels(meta, attribution, purchases) -> None:
    st.markdown(section_header("What to Do This Week"), unsafe_allow_html=True)
    kill_full = identify_kill_ads(meta, attribution)
    kill = kill_full.head(5)
    scale = identify_scale_ads(meta, attribution).head(5)
    test = identify_test_ads(meta, attribution).head(5)
    kill_items = [f"<b>{r.short_name}</b> — RM {r.spend:,.0f} spent, {int(r.buyers)} buyers, "
                  f"RM {r.wasted_spend:,.0f} wasted ({int(r.days_running)}d)" for r in kill.itertuples()]
    scale_items = [f"<b>{r.short_name}</b> — RM {r.spend:,.0f}, {int(r.buyers)} buyers, "
                   f"{r.roas:.1f}x ROAS (3x → ~RM {r.projected_3x_revenue:,.0f})"
                   for r in scale.itertuples()]
    test_items = [f"<b>{r.short_name}</b> — {int(r.days_running)}d, RM {r.spend:,.0f} spent, "
                  f"{r.ctr:.1f}% CTR" for r in test.itertuples()]
    panels = [
        ("🔴 Stop Spending", kill_items,
         f"Pause these to save ~RM {kill['wasted_spend'].sum():,.0f}/wk" if kill_items
         else "✅ No problem ads detected", "r"),
        ("🟢 Scale Winners", scale_items,
         "Triple budget on these to capture more performance" if scale_items
         else "ℹ️ No hidden gems found yet", "g"),
        ("🟡 Give These More Budget", test_items,
         "Allocate small budget to validate" if test_items
         else "ℹ️ No early-stage ads to evaluate", "y"),
    ]
    for col, (title, items, foot, v) in zip(st.columns(3), panels):
        with col: st.markdown(decision_panel(title, items, foot, v), unsafe_allow_html=True)

    if not kill_full.empty:
        impact = calculate_kill_impact(meta, attribution, kill_full, purchases)
        if impact["weekly_savings"] > 0:
            base = (
                f"💡 If you pause these {len(kill_full)} ad(s): "
                f"weekly spend drops from RM {impact['current_spend']:,.0f} to "
                f"RM {impact['projected_spend']:,.0f} "
                f"(save RM {impact['weekly_savings']:,.0f}/week)"
            )
            if impact["roas_lift"] > 0.01:
                base += (f", and ROAS could lift from {impact['current_roas']:.2f}x "
                         f"to {impact['projected_roas']:.2f}x")
            st.markdown(alert(base + ".", "info"), unsafe_allow_html=True)


def _render_creative_type(meta, attribution) -> None:
    st.markdown(section_header("Creative Type Comparison"), unsafe_allow_html=True)
    summary, others = calculate_creative_type_performance(meta, attribution)
    if summary.empty:
        st.info("No creative type data."); return
    fig = go.Figure([
        go.Bar(x=summary["type"], y=summary["spend"], name="Spend (RM)",
               marker_color=COLORS["secondary"]),
        go.Bar(x=summary["type"], y=summary["revenue"], name="Revenue (RM)",
               marker_color=COLORS["accent"]),
    ])
    fig.update_layout(title_text="", barmode="group", yaxis=dict(title="RM"))
    st.plotly_chart(apply_standard_layout(fig, height=320), use_container_width=True)
    st.dataframe(summary, use_container_width=True, hide_index=True, column_config=_CT_CONFIG)
    if others:
        with st.expander(f"What's in 'Other'? ({len(others)} ads)"):
            for ad in others: st.write(f"• {ad}")


def _render_campaign_performance(meta, attribution) -> None:
    st.markdown(section_header("Campaign Performance"), unsafe_allow_html=True)
    df = calculate_campaign_performance(meta, attribution)
    if df.empty:
        st.info("No campaign data."); return
    display = df.copy(); display["health"] = display["health"].map(_HEALTH_EMOJI)
    st.dataframe(display, use_container_width=True, hide_index=True, column_config=_CAMP_CONFIG)
    red = df[df["health"] == "red"]
    if not red.empty:
        st.markdown(alert(f"Underperforming campaigns: <b>{', '.join(red['campaign_name'].tolist())}</b>. "
                          f"Review or pause.", "danger"), unsafe_allow_html=True)
    elif (df["health"] == "green").all():
        st.markdown(alert("All campaigns performing healthy.", "success"), unsafe_allow_html=True)


def _render_creative_fatigue(meta, attribution) -> None:
    st.markdown(section_header("Creative Fatigue"), unsafe_allow_html=True)
    st.caption("Ads where audience may be saturated. Refresh creatives or pause.")
    df = calculate_creative_fatigue(meta, attribution)
    if df.empty:
        st.markdown(alert("✅ All ads performing within healthy frequency range "
                          "(or insufficient history yet).", "success"), unsafe_allow_html=True)
        return
    show_all = st.checkbox("Show all", value=False, key="fatigue_show_all")
    view = df if show_all else df[df["status"].isin(["fatiguing", "saturated"])]
    if view.empty:
        st.markdown(alert("✅ No fatiguing or saturated ads.", "success"), unsafe_allow_html=True)
        return
    display = view.copy(); display["status"] = display["status"].map(_FATIGUE_BADGE)
    st.dataframe(display.drop(columns=["ad_name"]), use_container_width=True,
                 hide_index=True, column_config=_FATIGUE_CONFIG)


def _render_top_ads_table(meta, attribution, creatives_df=None) -> None:
    st.markdown(section_header("Top Performing Ads"), unsafe_allow_html=True)
    df = get_top_ads_with_buyers(meta, attribution, top_n=20)
    if df.empty:
        st.info("No ads to display."); return
    high_freq = df[df["frequency"] >= 10]
    if not high_freq.empty:
        names = high_freq["short_name"].tolist()
        sample = ", ".join(names[:3]) + ("..." if len(names) > 3 else "")
        st.markdown(alert(
            f"🔴 {len(names)} ad(s) have frequency ≥ 10 — audience seeing these "
            f"too many times: {sample}. Refresh creative or pause to avoid ad fatigue.",
            "danger"), unsafe_allow_html=True)
    thumb_map = build_creative_thumbnail_map(creatives_df)
    placeholder = creative_placeholder_data_uri()
    display = df.drop(columns=["ad_name"]).copy()
    display.insert(0, "Preview", df["ad_name"].map(thumb_map).fillna(placeholder))
    st.dataframe(display, row_height=90,
                 column_config={"Preview": st.column_config.ImageColumn("Preview", width="medium"), **_TOP_CONFIG})


def _render_quality_rankings(meta) -> None:
    st.markdown(section_header("Ad Quality Rankings"), unsafe_allow_html=True)
    active = meta[meta["amount_spent"] > 0]
    rankings = [("quality_ranking", "Quality Ranking"),
                ("engagement_ranking", "Engagement Ranking"),
                ("conversion_ranking", "Conversion Ranking")]
    distributions = {}
    for col, _ in rankings:
        f = active[~active[col].isin(["-", "", None]) & active[col].notna()]
        counts = f[col].value_counts().reset_index()
        counts.columns = ["ranking", "count"]
        distributions[col] = counts

    for (col, title), slot in zip(rankings, st.columns(3)):
        with slot:
            counts = distributions[col]
            if col == "conversion_ranking" and len(counts) <= 1:
                st.markdown(f"**{title}**")
                st.info(
                    "📊 Insufficient data for ranking analysis. Meta needs ~50 "
                    "conversions per ad to grade conversion performance reliably. "
                    "As more sales accumulate, this metric becomes diagnostic."
                )
            elif counts.empty:
                st.caption(f"{title}: no data")
            else:
                st.plotly_chart(pie_chart(counts, "count", "ranking", title),
                                use_container_width=True)

    qd = distributions.get("quality_ranking")
    if qd is not None and not qd.empty:
        below = qd[qd["ranking"].str.contains("below", case=False, na=False)]["count"].sum()
        total = qd["count"].sum()
        if total and below / total > 0.20:
            below_ads = active[active["quality_ranking"].str.contains("below", case=False, na=False)]
            sample = ", ".join(below_ads["ad_name"].drop_duplicates().head(5).tolist()) or "see table above"
            st.markdown(alert(
                f"<b>{below/total*100:.0f}%</b> of your ads are in Meta's bottom 35% quality bracket. "
                f"These ads cost more and reach less. Action: refresh creative or rewrite copy. "
                f"Sample: {sample}.", "danger"), unsafe_allow_html=True)


def _render_break_even_analysis(meta, purchases, attribution, leads, config) -> None:
    st.markdown(section_header("ROI Analysis"), unsafe_allow_html=True)
    course_fee = config.get("course_fee_full", 0)
    be = calculate_break_even_analysis(meta, purchases, attribution, leads, course_fee)
    cards = [
        ("Break-even Sales Needed", str(be["break_even_sales_needed"]),
         f"At RM {course_fee:,} per course", ""),
        ("Actual Sales", str(be["actual_sales"]),
         f"Surplus: {be['surplus']} sales above break-even", _ROAS_VARIANT[be["health"]]),
        ("UTM-Tracked Leads", f"{be['utm_tracked_leads']:,}",
         f"{be['utm_coverage_pct']}% of all leads · {be['attributed_buyers']} converted", ""),
    ]
    for col, (l, v, sub, var) in zip(st.columns(3), cards):
        with col: st.markdown(metric_card(l, v, sub, variant=var), unsafe_allow_html=True)
    st.markdown(alert(
        "This is a rough break-even calculation using sale price, not collected revenue. "
        "It does NOT account for: instalment payments not yet collected, refunds, payment "
        "processor fees, or team/operational costs. For accurate margin, see the Sales & "
        "Revenue tab.", "info"), unsafe_allow_html=True)
    if be["health"] == "green":
        st.markdown(alert(f"ROAS healthy — {be['surplus']} sales above break-even on "
                          f"RM {be['total_spend']:,.0f} ad spend.", "success"), unsafe_allow_html=True)
    elif be["health"] == "red":
        st.markdown(alert("Spending more than recouping. Investigate the KILL panel and "
                          "creative fatigue tracker above.", "danger"), unsafe_allow_html=True)


def _render_ai(snap, meta, attribution) -> None:
    kill = identify_kill_ads(meta, attribution).head(3)
    scale = identify_scale_ads(meta, attribution).head(3)
    kill_str = "; ".join(f"{r.short_name} (RM{r.wasted_spend:,.0f} wasted)"
                         for r in kill.itertuples()) or "none"
    scale_str = "; ".join(f"{r.short_name} ({r.roas:.1f}x ROAS)"
                          for r in scale.itertuples()) or "none"
    spend_change = snap["spend"]["change_pct"]
    spend_str = "n/a" if spend_change is None else f"{spend_change:+.0f}%"
    context = (f"Last 7d: RM {snap['spend']['value']:,.0f} spent "
               f"({spend_str} vs prev), "
               f"{snap['leads']['value']} leads (CPL RM {snap['leads']['cpl']:.2f}), "
               f"{snap['buyers']['value']} buyers (CPA RM {snap['buyers']['cpa']:.2f}), "
               f"ROAS {snap['roas']['value']:.2f}x ({snap['roas']['health']}).\n"
               f"KILL candidates: {kill_str}\nSCALE candidates: {scale_str}")
    render_ai_insights("ad_spend", context)
