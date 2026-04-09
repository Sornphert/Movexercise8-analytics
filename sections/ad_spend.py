from __future__ import annotations

import streamlit as st

from utils.charts import bar_chart, horizontal_bar_chart, pie_chart
from utils.metrics import (
    calculate_ad_overview,
    calculate_ad_performance,
    calculate_ad_quality,
    calculate_ad_roi,
    calculate_creative_comparison,
    get_top_ads,
)
from utils.ai import render_ai_insights
from utils.styles import alert, metric_card, section_header


def render(data: dict) -> None:
    meta = data["meta"]
    leads = data["leads"]
    purchases = data["purchases"]
    config = data["config"]

    overview = calculate_ad_overview(meta)
    roi = calculate_ad_roi(meta, leads, purchases, config)

    # ── Hero cards ────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            metric_card("Total Ad Spend", f"RM {overview['total_spend']:,.0f}",
                        f"{overview['total_reach']:,} people reached"),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card("Leads Generated", f"{overview['total_results']:,}",
                        f"CPL: RM {overview['cpl']:.2f}"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            metric_card("Click-through Rate", f"{overview['ctr']}%",
                        f"{overview['total_clicks']:,} clicks · CPC: RM {overview['cpc']:.2f}"),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            metric_card("ROAS", f"{roi['roas']}x",
                        f"RM {roi['total_revenue']:,.0f} revenue / RM {roi['total_spend']:,.0f} spend"),
            unsafe_allow_html=True,
        )

    # ── Creative Type Comparison ─────────────────────────────────
    st.markdown(section_header("Creative Type Comparison"), unsafe_allow_html=True)
    creative = calculate_creative_comparison(meta)

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            pie_chart(creative, "spend", "creative_type", "Spend by Creative Type"),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            bar_chart(creative, "creative_type", "cpl", "Cost per Lead by Type",
                      color="#D4A843", text_col="cpl"),
            use_container_width=True,
        )

    # Summary table
    display_creative = creative.copy()
    display_creative.columns = ["Type", "Ads", "Spend (RM)", "Results", "Clicks", "Impressions", "CPL (RM)", "CTR (%)"]
    display_creative["Spend (RM)"] = display_creative["Spend (RM)"].map("{:,.0f}".format)
    display_creative["Results"] = display_creative["Results"].astype(int)
    display_creative["Clicks"] = display_creative["Clicks"].astype(int)
    display_creative["Impressions"] = display_creative["Impressions"].astype(int)
    st.dataframe(display_creative, use_container_width=True, hide_index=True)

    # ── Top Performing Ads ───────────────────────────────────────
    st.markdown(section_header("Top Performing Ads"), unsafe_allow_html=True)
    ad_perf = calculate_ad_performance(meta)

    top_by_results = get_top_ads(meta, n=8, by="results")
    # Shorten ad names for display
    top_by_results["short_name"] = top_by_results["ad_name"].str.extract(r"((?:Video|Image).*$)")
    top_by_results["short_name"] = top_by_results["short_name"].fillna(top_by_results["ad_name"].str[-20:])

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            horizontal_bar_chart(
                top_by_results, x="results", y="short_name",
                title="Top Ads by Leads Generated",
            ),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            horizontal_bar_chart(
                top_by_results.sort_values("cpl"), x="cpl", y="short_name",
                title="Cost per Lead (lower = better)", color="#D4A843",
            ),
            use_container_width=True,
        )

    # Full ad performance table
    display_ads = ad_perf[ad_perf["results"] > 0][
        ["ad_name", "amount_spent", "results", "cpl", "link_clicks", "cpc", "ctr",
         "impressions", "creative_type", "quality_ranking"]
    ].copy()
    display_ads.columns = [
        "Ad Name", "Spend (RM)", "Leads", "CPL (RM)", "Clicks", "CPC (RM)", "CTR (%)",
        "Impressions", "Type", "Quality",
    ]
    st.dataframe(display_ads, use_container_width=True, hide_index=True)

    # ── Quality Rankings ─────────────────────────────────────────
    st.markdown(section_header("Ad Quality Rankings"), unsafe_allow_html=True)
    quality = calculate_ad_quality(meta)

    q1, q2, q3 = st.columns(3)
    with q1:
        st.plotly_chart(
            pie_chart(quality["quality_ranking"], "count", "ranking", "Quality Ranking"),
            use_container_width=True,
        )
    with q2:
        st.plotly_chart(
            pie_chart(quality["engagement_ranking"], "count", "ranking", "Engagement Ranking"),
            use_container_width=True,
        )
    with q3:
        st.plotly_chart(
            pie_chart(quality["conversion_ranking"], "count", "ranking", "Conversion Ranking"),
            use_container_width=True,
        )

    # ── ROI Analysis ─────────────────────────────────────────────
    st.markdown(section_header("ROI Analysis"), unsafe_allow_html=True)

    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown(
            metric_card("Break-even Sales Needed", str(roi["breakeven_sales"]),
                        f"At RM {config.get('course_fee_full', 0):,} per course"),
            unsafe_allow_html=True,
        )
    with r2:
        st.markdown(
            metric_card("Actual Sales", str(roi["actual_sales"]),
                        f"Surplus: {roi['actual_sales'] - roi['breakeven_sales']} sales above break-even",
                        variant="warning" if roi["actual_sales"] <= roi["breakeven_sales"] else ""),
            unsafe_allow_html=True,
        )
    with r3:
        st.markdown(
            metric_card("UTM-Tracked Leads", f"{roi['attributed_leads']}",
                        f"{roi['utm_tracking_pct']}% of all leads · {roi['attributed_buyers']} converted"),
            unsafe_allow_html=True,
        )

    # ROI insight
    if roi["roas"] >= 5:
        msg = (f"Strong ROAS of <b>{roi['roas']}x</b> — every RM 1 spent on ads returned "
               f"RM {roi['roas']:.0f} in revenue. Total revenue (RM {roi['total_revenue']:,.0f}) "
               f"far exceeds ad spend (RM {roi['total_spend']:,.0f}).")
        st.markdown(alert(msg, "success"), unsafe_allow_html=True)
    elif roi["roas"] >= 2:
        msg = (f"Healthy ROAS of <b>{roi['roas']}x</b>. Revenue covers ad spend with room to spare.")
        st.markdown(alert(msg, "info"), unsafe_allow_html=True)
    else:
        msg = (f"ROAS of <b>{roi['roas']}x</b> is thin. Consider optimizing ad targeting or creative.")
        st.markdown(alert(msg, "warning"), unsafe_allow_html=True)

    if roi["utm_tracking_pct"] < 20:
        st.markdown(
            alert(
                f"Only <b>{roi['utm_tracking_pct']}%</b> of leads have UTM tracking. "
                f"Most leads cannot be traced back to a specific ad. Consider improving UTM tagging "
                f"on landing pages to get better attribution data.",
                "warning",
            ),
            unsafe_allow_html=True,
        )

    # ── AI Insights ──────────────────────────────────────────────
    creative_text = creative[["creative_type", "ads", "spend", "results", "cpl", "ctr"]].to_string(index=False)
    context = (
        f"Total ad spend: RM {overview['total_spend']:,.0f}\n"
        f"Leads generated: {overview['total_results']:,}, CPL: RM {overview['cpl']:.2f}\n"
        f"CTR: {overview['ctr']}%, CPC: RM {overview['cpc']:.2f}\n"
        f"ROAS: {roi['roas']}x (RM {roi['total_revenue']:,.0f} revenue / RM {roi['total_spend']:,.0f} spend)\n"
        f"UTM tracking: {roi['utm_tracking_pct']}% of leads\n"
        f"Break-even: {roi['breakeven_sales']} sales needed, actual: {roi['actual_sales']}\n"
        f"Creative comparison:\n{creative_text}"
    )
    render_ai_insights("ad_spend", context)
