import streamlit as st

from agent.agent import build_agent
from services.settings import has_agent_api_key, load_agent_settings, save_agent_settings


def show_einstellungen():
    """Rendert die lokalen Einstellungen für den Agenten."""
    st.title("Einstellungen")
    st.caption("Agent-Zugangsdaten und Modell verwalten.")

    settings = load_agent_settings()
    if has_agent_api_key():
        st.success("Agent ist konfiguriert.")
    else:
        st.warning("NVIDIA API-Key fehlt.")

    with st.form("agent_settings_form"):
        api_key = st.text_input(
            "NVIDIA API-Key",
            value=settings.api_key,
            type="password",
        )
        model = st.text_input("Modell", value=settings.model)
        submitted = st.form_submit_button("Speichern", width="stretch")

    if not submitted:
        return

    save_agent_settings(api_key, model)
    build_agent.cache_clear()
    st.success("Einstellungen gespeichert.")
