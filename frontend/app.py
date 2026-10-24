"""Chat frontend; all conversation and booking logic lives in the API."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")


def api_call(path, payload=None):
    headers = {"Content-Type": "application/json"}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    request = Request(
        f"{API_BASE_URL}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    with urlopen(request, timeout=150) as response:
        return json.load(response)


def send_message(message):
    if not st.session_state.token:
        session = api_call("/session", {})
        st.session_state.token = session["token"]
    return api_call("/chat", {"message": message})


st.set_page_config(page_title="HealthLink", page_icon="🏥")
st.title("HealthLink")
st.caption("Chat about symptoms, choose a doctor, and book an appointment in the demo clinic.")
st.caption("Not medical advice. No real clinic is contacted. Use fictional patient details.")

if "token" not in st.session_state:
    st.session_state.messages = []
    st.session_state.token = None
    st.session_state.pending_message = None

if st.sidebar.button("New chat"):
    st.session_state.messages = []
    st.session_state.token = None
    st.session_state.pending_message = None
    st.rerun()
st.sidebar.caption("A new chat does not cancel an existing booking.")

if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write("Hi! What symptoms are you experiencing? I'll ask a few questions, help you choose an appointment, and confirm before booking it.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Type your message…", max_chars=2000, disabled=bool(st.session_state.pending_message))
if prompt:
    st.session_state.pending_message = prompt
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

if st.session_state.pending_message:
    try:
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                result = send_message(st.session_state.pending_message)
        st.session_state.messages.append({"role": "assistant", "content": result["reply"]})
        st.session_state.pending_message = None
        st.rerun()
    except HTTPError as exc:
        try:
            detail = json.load(exc).get("detail", "The API could not complete this turn.")
        except ValueError:
            detail = "The API could not complete this turn."
        st.error(str(detail))
    except (URLError, TimeoutError, ValueError, OSError):
        st.error("Cannot reach the API. Check that it is running and API_BASE_URL is correct.")
    if st.button("Retry message"):
        st.rerun()
