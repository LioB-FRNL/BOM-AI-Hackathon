from __future__ import annotations

import streamlit as st

from pentabody_chatbot.config import load_settings
from pentabody_chatbot.orchestrator import ChatService


st.set_page_config(
    page_title="Trusted Cancer information",
    page_icon=":speech_balloon:",
    layout="centered",
)
st.title("Trusted Cancer information")
st.caption("Structured question narrowing + trusted source routing")

settings = load_settings()
chat_service = ChatService(settings)

if "history" not in st.session_state:
    st.session_state.history = []
if "last_extracted" not in st.session_state:
    st.session_state.last_extracted = None
if "last_matched_cancer_type" not in st.session_state:
    st.session_state.last_matched_cancer_type = None

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if not settings.openai_api_key:
    st.warning("OPENAI_API_KEY missing. Add it to .env to enable real extraction.")

user_input = st.chat_input("Ask a cancer information question...")
if user_input:
    st.session_state.history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    turn = chat_service.next_assistant_turn(
        st.session_state.history,
        previous_extracted=st.session_state.last_extracted,
        previous_matched_cancer_type=st.session_state.last_matched_cancer_type,
    )
    st.session_state.history.append({"role": "assistant", "content": turn.message})
    st.session_state.last_extracted = turn.extracted
    st.session_state.last_matched_cancer_type = turn.matched_cancer_type

    with st.chat_message("assistant"):
        st.markdown(turn.message)

if st.button("Reset conversation"):
    st.session_state.history = []
    st.session_state.last_extracted = None
    st.session_state.last_matched_cancer_type = None
    st.rerun()
