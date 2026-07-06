"""Sidebar-Rendering: Session-Verwaltung und Navigation."""
import uuid
import streamlit as st

from services.session import (
    erstelle_session,
    lade_alle_sessions,
    lade_letzte_session,
    lade_nachrichten,
    loesche_session,
    benenne_session_um,
)


# ─────────────────────────────────────────
#  Session-Wechsel
# ─────────────────────────────────────────


def _wechsle_session(thread_id):
    """Wechselt zu einer bestehenden Session."""
    st.session_state.config = {"configurable": {"thread_id": thread_id}}
    st.session_state.messages = lade_nachrichten(thread_id)
    st.session_state.warte_auf_bestaetigung = False
    st.session_state.pending_tool_calls = []
    st.session_state.agent_arbeitet = False
    st.rerun()


def _loesche_und_wechsle(thread_id_zu_loeschen):
    """Löscht eine Session und wechselt zur nächsten verfügbaren."""
    loesche_session(thread_id_zu_loeschen)
    naechste = lade_letzte_session()
    if naechste:
        _wechsle_session(naechste)
    else:
        new_id = str(uuid.uuid4())
        erstelle_session(new_id)
        _wechsle_session(new_id)


# ─────────────────────────────────────────
#  Navigation
# ─────────────────────────────────────────


def _nav_button(label, key_name):
    """Einheitlicher Seitenbutton mit aktivem Zustand."""
    is_active = st.session_state.seite == label
    btn_type = "primary" if is_active else "secondary"
    if st.button(label, key=key_name, width="stretch", type=btn_type):
        st.session_state.seite = label
        st.rerun()


def _render_session_liste():
    """Zeigt alle Sessions mit Umbenennen- und Löschen-Menue."""
    sessions = lade_alle_sessions()
    if not sessions:
        return

    aktuelle_thread_id = st.session_state.config["configurable"]["thread_id"]
    for thread_id, titel, erstellt_am in sessions:
        ist_aktiv = thread_id == aktuelle_thread_id
        col_name, col_menu = st.columns([6, 1])
        with col_name:
            btn_type = "secondary" if ist_aktiv else "tertiary"
            if st.button(
                titel,
                key=f"session_{thread_id}",
                width="stretch",
                disabled=ist_aktiv,
                type=btn_type,
                help=titel,
            ):
                _wechsle_session(thread_id)
        with col_menu:
            with st.popover("⋯", help="Session-Optionen"):
                neuer_name = st.text_input(
                    "Umbenennen",
                    value=titel,
                    key=f"rename_{thread_id}",
                )
                if st.button("Speichern", key=f"save_rename_{thread_id}"):
                    if neuer_name and neuer_name != titel:
                        benenne_session_um(thread_id, neuer_name)
                        st.rerun()
                st.divider()
                if st.button(
                    "Löschen",
                    key=f"del_{thread_id}",
                    type="primary",
                ):
                    _loesche_und_wechsle(thread_id)


# ─────────────────────────────────────────
#  Hauptfunktion
# ─────────────────────────────────────────


def render_sidebar():
    """Rendert die komplette Sidebar (Sessions + Navigation + Einstellungen)."""
    with st.sidebar:
        st.markdown("<div class='sidebar-brand'>Lager-Agent</div>", unsafe_allow_html=True)
        st.markdown("<div class='sidebar-sub'>Lagerautomation & Agent</div>", unsafe_allow_html=True)
        st.divider()

        st.caption("Sitzungen")
        if st.button("Neues Gespräch", key="nav_new_chat", width="stretch", type="primary"):
            st.session_state.seite = "Chat"
            st.session_state._trigger_new_chat = True
            st.rerun()

        _render_session_liste()

        st.divider()
        st.caption("Arbeitsbereich")
        _nav_button("Chat", "nav_chat")
        _nav_button("Dashboard", "nav_dashboard")
        _nav_button("Entnahme", "nav_entnahme")

        st.divider()
        st.caption("Verlauf")
        _nav_button("Bestellhistorie", "nav_bestellhistorie")

        st.divider()
        st.caption("Insights")
        _nav_button("Analysen", "nav_analysen")
        _nav_button("Metriken", "nav_metriken")
        _nav_button("Auswertung", "nav_auswertung")

        st.divider()
        if st.button("Einstellungen", key="nav_settings", width="stretch"):
            st.session_state.seite = "Einstellungen"
            st.rerun()
