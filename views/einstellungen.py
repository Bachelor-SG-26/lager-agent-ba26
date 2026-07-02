import streamlit as st

from agent.agent import AgentConfigurationError, build_agent
from services.agent_runner import check_agent_readiness
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

    if submitted:
        save_agent_settings(api_key, model)
        build_agent.cache_clear()
        st.success("Einstellungen gespeichert.")

    if st.button("Agent testen", width="stretch", disabled=not has_agent_api_key()):
        _render_agent_readiness()


def _render_agent_readiness():
    """Baut den Agenten lokal auf und zeigt die Startbereitschaft an."""
    try:
        check_agent_readiness()
    except AgentConfigurationError as error:
        st.error(str(error))
    except Exception as error:
        st.error(f"Agent konnte nicht gestartet werden: {error}")
    else:
        settings = load_agent_settings()
        st.success(f"Agent ist startbereit. Modell: {settings.model}")
