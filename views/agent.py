import uuid

import streamlit as st

from agent.agent import AgentConfigurationError, is_agent_configured
from services.agent_runner import ask_agent


def show_agent():
    """Rendert den Agenten-Chat mit persistenter Thread-ID."""
    st.title("Agent")
    st.caption("Lagerfragen stellen und operative Abläufe vorbereiten.")

    if "agent_thread_id" not in st.session_state:
        st.session_state.agent_thread_id = str(uuid.uuid4())

    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = []

    if not is_agent_configured():
        st.warning("Für den Agenten fehlt noch der NVIDIA_API_KEY.")
        return

    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Nachricht an den Agenten")
    if not user_input:
        return

    st.session_state.agent_messages.append({"role": "user", "content": user_input})
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
