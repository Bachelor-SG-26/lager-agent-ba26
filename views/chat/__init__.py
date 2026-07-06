"""Chat-View: Haupt-Entry-Point mit Human-in-the-Loop und Live-Streaming."""
import uuid

import streamlit as st
import streamlit.components.v1 as components

from services.session import erstelle_session
from views.chat.processing import (
    execute_approved_tools,
    process_approval,
    process_user_input,
)
from views.chat.recovery import detect_pending_recovery, execute_recovery
from views.chat.state import (
    cancel_pending_tools,
    reset_state,
    stop_agent,
)
from views.chat.ui import render_chat_history, render_confirmation

# Re-Exports für Rueckwaertskompatibilitaet
__all__ = [
    "show_chat",
    "render_chat_history",
    "render_confirmation",
    "execute_approved_tools",
    "process_approval",
    "process_user_input",
    "cancel_pending_tools",
]


def _neues_gespraech():
    """Startet eine neue Chat-Session."""
    new_thread_id = str(uuid.uuid4())
    st.session_state.config = {"configurable": {"thread_id": new_thread_id}}
    st.session_state.messages = []
    reset_state()
    erstelle_session(new_thread_id)
    st.rerun()


def _reload_bei_seitenwechsel():
    """Loest einen echten Browser-Reload aus, wenn der Chat frisch betreten wird.

    Hintergrund: Streamlits st.rerun() reicht nicht, weil einige UI-Elemente
    (z.B. st.chat_input) nach Seitenwechseln manchmal nicht sauber re-mounten.
    Ein Full-Reload stellt einen konsistenten Zustand her.

    Guard: Nur reloaden wenn vorher eine andere Seite aktiv war. Nach dem Reload
    ist session_state leer — die Bedingung kann nicht nochmal ausloesen.
    """
    letzte = st.session_state.get("_letzte_seite")
    if letzte is not None and letzte != "Chat":
        st.session_state._letzte_seite = "Chat"
        # components.html rendert in einem echten iframe und führt das Script
        # zuverlässig beim ersten Render aus. st.html sanitized/verzögert
        # Scripts teilweise, wodurch der Reload erst beim zweiten Klick feuerte.
        components.html(
            "<script>window.parent.location.reload();</script>",
            height=0,
            width=0,
        )
        st.stop()


def _render_stop_button():
    """Stop-Button für laufende Vorgaenge (fix unten rechts per CSS)."""
    if st.button("Stopp", key="stop_icon_btn", type="secondary", help="Vorgang abbrechen"):
        st.session_state.stop_requested = True
        if st.session_state.warte_auf_bestaetigung and st.session_state.pending_tool_calls:
            cancel_pending_tools(
                reason="Nutzer hat den Vorgang manuell gestoppt.",
                user_msg="Vorgang wurde gestoppt.",
            )
        stop_agent()
        st.rerun()


def show_chat():
    """Chat-Seite mit Human-in-the-Loop und Live-Streaming."""
    _reload_bei_seitenwechsel()

    if st.session_state.pop("_trigger_new_chat", False):
        _neues_gespraech()

    # Phase 1: Recovery erkennen und Flags setzen (kein blocking)
    detect_pending_recovery()

    is_busy = (
        st.session_state.warte_auf_bestaetigung
        or "tool_approved" in st.session_state
        or st.session_state.agent_arbeitet
    )
    placeholder = "Agent arbeitet..." if st.session_state.agent_arbeitet else "Frag den Agenten..."

    # WICHTIG: Chat-Input UND Stop-Button FRUEH rendern — bevor langsame
    # Operationen (Recovery/Streaming) die Render-Reihenfolge verzoegern.
    # Sonst waren beide Elemente während Agent-Arbeit unsichtbar.
    user_input = st.chat_input(placeholder, disabled=is_busy)
    if is_busy:
        _render_stop_button()

    chat = st.container(key="chat_scroll_container", border=False)
    render_chat_history(chat)

    # Phase 2: Recovery mit Spinner ausführen (kann lange dauern bei API-Fehlern)
    if execute_recovery(chat):
        st.rerun()

    # State-basierte Verarbeitung
    if "tool_approved" in st.session_state:
        process_approval(chat)
    elif st.session_state.warte_auf_bestaetigung:
        render_confirmation(chat)
    elif "pending_input" in st.session_state:
        eingabe = st.session_state.pop("pending_input")
        process_user_input(chat, eingabe)
    elif user_input:
        st.session_state.pending_input = user_input
        st.session_state.agent_arbeitet = True
        st.rerun()
