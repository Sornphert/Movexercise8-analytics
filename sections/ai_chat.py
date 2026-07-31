from __future__ import annotations

import streamlit as st

from utils.ai import build_data_summary, chat_response
from utils.styles import section_header


def render(data: dict) -> None:
    st.markdown(section_header("AI Analytics Assistant"), unsafe_allow_html=True)

    api_key = st.session_state.get("gemini_api_key", "")
    if not api_key:
        st.info(
            "Enter your Gemini API key in the sidebar to start chatting. "
            "Get a free key at [aistudio.google.com](https://aistudio.google.com)."
        )
        return

    # Rebuild the data context each render so the assistant always reflects the
    # CURRENT sidebar date filter (caching it once per session made it answer from
    # whatever filter was active on first open).
    data_context = build_data_summary(data)

    # Initialize chat history
    if "ai_chat_history" not in st.session_state:
        st.session_state["ai_chat_history"] = []

    # Display chat history
    for msg in st.session_state["ai_chat_history"]:
        role = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(role):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask anything about your dashboard data..."):
        # Show user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        result = None
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = chat_response(
                        api_key=api_key,
                        message=prompt,
                        data_context=data_context,
                        history=st.session_state["ai_chat_history"],
                    )
                    st.markdown(result)
                except Exception as e:
                    st.error(f"Error: {e}")

        # Save to history only on success — a failed attempt shouldn't pollute the
        # transcript or get re-sent as context (and would leave a dangling user turn).
        if result is not None:
            st.session_state["ai_chat_history"].append(
                {"role": "user", "content": prompt}
            )
            st.session_state["ai_chat_history"].append(
                {"role": "model", "content": result}
            )

    # Clear chat button
    if st.session_state["ai_chat_history"]:
        if st.button("Clear Chat"):
            st.session_state["ai_chat_history"] = []
            st.rerun()
