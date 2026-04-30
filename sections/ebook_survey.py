import pandas as pd
import streamlit as st

from utils.ai import render_ai_insights
from utils.charts import bar_chart, horizontal_bar_chart, pie_chart
from utils.metrics import (
    calculate_ebook_audience,
    calculate_ebook_intent_conversion,
    calculate_ebook_objections,
    calculate_ebook_overview,
)
from utils.styles import metric_card, section_header


SMALL_N_THRESHOLD = 10


def render(data: dict):
    survey = data.get("ebook", pd.DataFrame())

    if survey is None or survey.empty:
        st.warning(
            "No e-book survey data available. Confirm the sheet is shared with "
            "the service account and the [sheets] entries in secrets.toml are correct."
        )
        return

    purchases = data["purchases"]
    overview = calculate_ebook_overview(survey, purchases)

    # ── Section 1: Overview ────────────────────────────────────────
    st.markdown(section_header("E-book Survey Overview"), unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            metric_card("Total Responses", f"{overview['total_responses']:,}"),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card(
                "Conversion Rate",
                f"{overview['conversion_rate']}%",
                f"{overview['converted_count']} of {overview['total_responses']} bought",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            metric_card(
                "Top Objection",
                overview["top_objection"],
                f"{overview['top_objection_count']} responses",
                variant="danger",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            metric_card(
                "Answer Rate",
                f"{overview['answer_rate']}%",
                "Filled the 'what stops you' field",
            ),
            unsafe_allow_html=True,
        )

    # ── Section 2: Why People Don't Join ───────────────────────────
    st.markdown(section_header("Why People Don't Join"), unsafe_allow_html=True)

    obj_df = calculate_ebook_objections(survey, purchases)
    if obj_df.empty:
        st.info("No objection data yet.")
    else:
        left, right = st.columns([1, 1])
        with left:
            st.plotly_chart(
                horizontal_bar_chart(
                    obj_df, x="count", y="objection",
                    title="Stated objections (canonical buckets)",
                    text_col="count",
                    color="#E76F51",
                ),
                use_container_width=True,
            )
        with right:
            st.dataframe(
                obj_df.rename(columns={
                    "objection": "Objection",
                    "count": "Responses",
                    "converted": "Bought",
                    "conv_rate": "Conv %",
                }),
                use_container_width=True,
                hide_index=True,
            )
        st.caption(
            f"Free-text answers are bucketed by keyword (e.g. 'cost', 'finance', 'afford' → "
            f"'Budget / Financial'). Sample sizes are small; conversion rates with n<{SMALL_N_THRESHOLD} "
            "are directional only."
        )

    # ── Section 3: Intent vs Reality ───────────────────────────────
    st.markdown(section_header("Intent vs Reality"), unsafe_allow_html=True)

    intent_df = calculate_ebook_intent_conversion(survey, purchases)
    if intent_df.empty:
        st.info("No intent data yet.")
    else:
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                pie_chart(intent_df, values_col="count", names_col="intent",
                          title="What respondents said about joining"),
                use_container_width=True,
            )
        with right:
            st.dataframe(
                intent_df.rename(columns={
                    "intent": "Stated intent",
                    "count": "Responses",
                    "converted": "Bought",
                    "conv_rate": "Conv %",
                }),
                use_container_width=True,
                hide_index=True,
            )
        st.caption(
            "Cross-tab of stated intent at survey time vs whether they later appear in `purchases`. "
            "Useful for sanity-checking which intent levels actually predict purchase."
        )

    # ── Section 4: Audience Profile ────────────────────────────────
    st.markdown(section_header("Audience Profile"), unsafe_allow_html=True)
    aud = calculate_ebook_audience(survey)

    a, b, c = st.columns(3)
    with a:
        st.plotly_chart(
            pie_chart(
                aud["role_breakdown"], values_col="count", names_col="label",
                title="Who is filling out the survey",
            ),
            use_container_width=True,
        )
    with b:
        st.plotly_chart(
            bar_chart(
                aud["age_breakdown"], x="label", y="count",
                title="Child age", text_col="count",
                category_x=True,
            ),
            use_container_width=True,
        )
    with c:
        st.plotly_chart(
            horizontal_bar_chart(
                aud["followup_breakdown"], x="count", y="label",
                title="Preferred next step",
                text_col="count",
                color="#40916C",
            ),
            use_container_width=True,
        )

    # ── Section 5: All Survey Responses ────────────────────────────
    st.markdown(section_header("All Survey Responses"), unsafe_allow_html=True)

    purchase_phones = (
        set(purchases["norm_phone"].dropna()) if not purchases.empty else set()
    )
    table_df = survey.copy()
    table_df["Converted?"] = table_df["norm_phone"].isin(purchase_phones).map({True: "✓", False: ""})
    display_cols = [
        "date", "name", "child_age", "age_bucket", "role",
        "intent", "objection", "preferred_followup",
        "reason_join", "challenge", "comments", "Converted?",
    ]
    display_cols = [c for c in display_cols if c in table_df.columns]
    st.dataframe(
        table_df[display_cols].rename(columns={
            "date": "Date",
            "name": "Name",
            "child_age": "Child age (raw)",
            "age_bucket": "Age bucket",
            "role": "Role",
            "intent": "Intent",
            "objection": "Stated objection",
            "preferred_followup": "Preferred follow-up",
            "reason_join": "Reason for joining webinar",
            "challenge": "Biggest challenge",
            "comments": "Comments",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # ── AI Insights ────────────────────────────────────────────────
    top_obj_lines = "\n".join(
        f"  {r['objection']}: {r['count']} responses, {r['conv_rate']}% conv"
        for _, r in obj_df.head(5).iterrows()
    )
    top_intent_lines = "\n".join(
        f"  {r['intent']}: {r['count']} responses, {r['conv_rate']}% conv"
        for _, r in intent_df.head(5).iterrows()
    )
    role_top = aud["role_breakdown"].head(3).to_string(index=False)
    context = (
        f"Total survey responses: {overview['total_responses']}\n"
        f"Overall survey-to-purchase conversion: {overview['conversion_rate']}% "
        f"({overview['converted_count']}/{overview['total_responses']})\n"
        f"Answer rate on 'what stops you': {overview['answer_rate']}%\n"
        f"Top objection: {overview['top_objection']} ({overview['top_objection_count']} responses)\n\n"
        f"Top objections (canonical):\n{top_obj_lines}\n\n"
        f"Stated intent breakdown:\n{top_intent_lines}\n\n"
        f"Top roles:\n{role_top}"
    )
    render_ai_insights("ebook_survey", context)
