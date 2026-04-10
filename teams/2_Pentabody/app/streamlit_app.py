from __future__ import annotations

import json
from typing import Any

import streamlit as st

from pentabody_chatbot.config import load_settings
from pentabody_chatbot.orchestrator import ChatService


st.set_page_config(
    page_title="Pentabody Chatbot",
    page_icon=":speech_balloon:",
    layout="centered",
)
st.title("Pentabody Chatbot (Barebones)")
st.caption("Structured question narrowing + trusted source routing")

settings = load_settings()
chat_service = ChatService(settings)

if "history" not in st.session_state:
    st.session_state.history = []
if "final_payload" not in st.session_state:
    st.session_state.final_payload = None
if "route_decision" not in st.session_state:
    st.session_state.route_decision = None

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

    turn = chat_service.next_assistant_turn(st.session_state.history)
    st.session_state.history.append({"role": "assistant", "content": turn.message})

    with st.chat_message("assistant"):
        st.markdown(turn.message)

    if turn.kind == "final" and turn.extracted and turn.route:
        st.session_state.final_payload = turn.extracted.model_dump()
        st.session_state.route_decision = turn.route.model_dump()

if st.session_state.final_payload:
    st.subheader("Extracted JSON")
    st.code(json.dumps(st.session_state.final_payload, indent=2), language="json")

if st.session_state.route_decision:
    route: dict[str, Any] = st.session_state.route_decision
    st.subheader("Routed Source")
    st.markdown(f"**{route['source_name']}**  ")
    st.markdown(f"Reason: {route['reason']}")
    st.markdown(f"URL: {route['source_url']}")

if st.button("Reset conversation"):
    st.session_state.history = []
    st.session_state.final_payload = None
    st.session_state.route_decision = None
    st.rerun()
