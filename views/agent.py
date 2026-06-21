import uuid

import streamlit as st

from agent.agent import AgentConfigurationError, is_agent_configured
from services.agent_runner import ask_agent
from services.chat_session import (
    create_chat_session,
    get_latest_chat_session,
    list_chat_sessions,
    load_chat_messages,
    save_chat_message,
    update_chat_title_from_message,
)


def show_agent():
    """Rendert den Agenten-Chat mit persistenter Thread-ID."""
    st.title("Agent")
    st.caption("Lagerfragen stellen und operative Abläufe vorbereiten.")

    _ensure_chat_state()
    _render_session_controls()

    if not is_agent_configured():
        st.warning("Für den Agenten fehlt noch der NVIDIA API-Key.")
        return

    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Nachricht an den Agenten")
    if not user_input:
        return

    st.session_state.agent_messages.append({"role": "user", "content": user_input})
    save_chat_message(st.session_state.agent_thread_id, "user", user_input)
    update_chat_title_from_message(st.session_state.agent_thread_id, user_input)

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Agent arbeitet..."):
            try:
                answer = ask_agent(user_input, st.session_state.agent_thread_id)
            except AgentConfigurationError as error:
                answer = str(error)
            st.markdown(answer)

    st.session_state.agent_messages.append({"role": "assistant", "content": answer})
    save_chat_message(st.session_state.agent_thread_id, "assistant", answer)


def _ensure_chat_state():
    """Initialisiert die aktive Chat-Session aus der Datenbank."""
    if "agent_thread_id" not in st.session_state:
        latest_session = get_latest_chat_session()
        if latest_session:
            st.session_state.agent_thread_id = latest_session["thread_id"]
        else:
            st.session_state.agent_thread_id = create_chat_session(str(uuid.uuid4()))

    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = load_chat_messages(st.session_state.agent_thread_id)


def _render_session_controls():
    """Rendert einfache Steuerung für neue und bestehende Agent-Gespräche."""
    col_new, col_history = st.columns([1, 3])
    with col_new:
        if st.button("Neues Gespräch", width="stretch"):
            st.session_state.agent_thread_id = create_chat_session(str(uuid.uuid4()))
            st.session_state.agent_messages = []
            st.rerun()

    sessions = list_chat_sessions()
    if not sessions:
        return

    labels = {
        f"{session['titel']} ({session['erstellt_am']})": session
        for session in sessions
    }
    current_label = next(
        (
            label
            for label, session in labels.items()
            if session["thread_id"] == st.session_state.agent_thread_id
        ),
        next(iter(labels)),
    )
    with col_history:
        selected_label = st.selectbox(
            "Gespräch",
            list(labels.keys()),
            index=list(labels.keys()).index(current_label),
        )

    selected_session = labels[selected_label]
    if selected_session["thread_id"] != st.session_state.agent_thread_id:
        st.session_state.agent_thread_id = selected_session["thread_id"]
        st.session_state.agent_messages = load_chat_messages(selected_session["thread_id"])
        st.rerun()
