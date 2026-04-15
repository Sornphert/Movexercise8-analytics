from __future__ import annotations

from google import genai
import streamlit as st

MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are an analytics advisor for MOVEXERCISE8, an online children's exercise course "
    "by Daphnie Wong (Tree Solutions) in Malaysia. Currency is MYR (RM). "
    "The business model: Meta ads drive leads to free 2-day Zoom webinars, "
    "then a course offer is made ~120 minutes into Day 1. "
    "Be concise, specific with numbers, and actionable. Use bullet points."
)


def _get_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def generate_insights(api_key: str, section: str, context: str) -> str:
    """Generate AI insights for a dashboard section."""
    client = _get_client(api_key)
    prompt = (
        f"Analyze this {section} data and provide 3-5 actionable insights. "
        f"Focus on what's working, what needs attention, and concrete next steps.\n\n"
        f"Data:\n{context}"
    )
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )
    return response.text


def chat_response(api_key: str, message: str, data_context: str, history: list) -> str:
    """Send a chat message with full dashboard context."""
    client = _get_client(api_key)

    system_msg = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Here is the current dashboard data:\n{data_context}\n\n"
        f"Answer questions about this data. Be specific and actionable. "
        f"If asked about something not in the data, say so."
    )

    # Build contents: system context + history + new message
    contents = [
        genai.types.Content(role="user", parts=[genai.types.Part(text=system_msg)]),
        genai.types.Content(role="model", parts=[genai.types.Part(text="Understood. I have the full dashboard data loaded. Ask me anything about your MOVEXERCISE8 analytics.")]),
    ]
    for msg in history:
        contents.append(
            genai.types.Content(role=msg["role"], parts=[genai.types.Part(text=msg["content"])])
        )
    contents.append(
        genai.types.Content(role="user", parts=[genai.types.Part(text=message)])
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
    )
    return response.text


def build_data_summary(data: dict) -> str:
    """Build a comprehensive text summary of all dashboard data for the chatbot."""
    leads = data["leads"]
    purchases = data["purchases"]
    meta = data["meta"]
    objections = data["objections"]
    webinars = data["webinars"]
    config = data["config"]

    # Funnel
    total_leads = len(leads)
    total_buyers = len(purchases)
    conv_rate = round(total_buyers / total_leads * 100, 2) if total_leads else 0
    payment_complete = int(purchases["payment_complete"].sum())

    # Revenue
    total_revenue = float(purchases["amount"].sum())
    collected = float(purchases[purchases["payment_complete"]]["amount"].sum())
    outstanding = total_revenue - collected

    # Ads
    total_spend = float(meta["amount_spent"].sum())
    total_results = int(meta["results"].sum())
    roas = round(total_revenue / total_spend, 2) if total_spend else 0

    # Webinars
    webinar_lines = []
    for key, w in sorted(webinars.items()):
        webinar_lines.append(
            f"  {w['date']}: {w['unique_attendees']} attendees, "
            f"avg {w['avg_duration']}min, {w['stayed_120plus_pct']}% stayed 120+min"
        )

    # Objections
    obj_cats = objections["category"].value_counts().to_dict()
    obj_summary = ", ".join(f"{k}: {v}" for k, v in obj_cats.items())

    # Purchases by status
    status_counts = purchases["status"].value_counts().to_dict()
    status_summary = ", ".join(f"{k}: {v}" for k, v in status_counts.items())

    # Payment methods
    method_counts = purchases["payment_method"].value_counts().to_dict()
    method_summary = ", ".join(f"{k}: {v}" for k, v in method_counts.items())

    return f"""PROGRAM: {config['program_name']} by {config['teacher_name']}
Course fee: RM {config['course_fee_full']:,} | Format: {config['webinar_format']} webinar

FUNNEL OVERVIEW:
- Total leads: {total_leads:,}
- Total buyers: {total_buyers} ({conv_rate}% conversion)
- Payment complete: {payment_complete}/{total_buyers}
- Total revenue: RM {total_revenue:,.0f}
- Collected: RM {collected:,.0f} | Outstanding: RM {outstanding:,.0f}
- Buyer status breakdown: {status_summary}
- Payment methods: {method_summary}

AD SPEND:
- Total spend: RM {total_spend:,.0f}
- Leads from ads: {total_results:,}
- ROAS: {roas}x
- CPL: RM {round(total_spend / total_results, 2) if total_results else 0}

WEBINAR SESSIONS:
{chr(10).join(webinar_lines)}

OBJECTIONS ({len(objections)} failed leads):
{obj_summary}

LEAD SOURCES (UTM campaigns):
{leads['utm_campaign'].value_counts().head(5).to_string() if 'utm_campaign' in leads.columns else 'N/A'}
"""


def render_ai_insights(section: str, context: str) -> None:
    """Render AI insights at the bottom of a section tab."""
    st.divider()
    st.subheader("AI Suggestions")

    api_key = st.session_state.get("gemini_api_key", "")
    if not api_key:
        st.caption("Gemini API key not configured — add it to .streamlit/secrets.toml")
        return

    cache_key = f"ai_insights_{section}"

    # Show cached insights if available
    if cache_key in st.session_state:
        st.markdown(st.session_state[cache_key])
        button_label = "Regenerate"
    else:
        button_label = "Generate Suggestions"

    if st.button(button_label, key=f"gen_{section}"):
        with st.spinner("Analyzing with Gemini..."):
            try:
                result = generate_insights(api_key, section, context)
                st.session_state[cache_key] = result
                st.rerun()
            except Exception as e:
                st.error(f"Gemini API error: {e}")
