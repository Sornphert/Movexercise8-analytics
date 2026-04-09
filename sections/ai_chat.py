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

    # Build data context once per session
    if "ai_data_context" not in st.session_state:
        st.session_state["ai_data_context"] = build_data_summary(data)

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
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = chat_response(
                        api_key=api_key,
                        message=prompt,
                        data_context=st.session_state["ai_data_context"],
                        history=st.session_state["ai_chat_history"],
                    )
                    st.markdown(result)
                except Exception as e:
                    result = f"Error: {e}"
                    st.error(result)

        # Save to history
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
