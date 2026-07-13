"""Fehler-Recovery und State-Detection für den Chat."""
import streamlit as st
from langchain_core.messages import ToolMessage

from services import agent_bridge
from services.logger import get_logger
from views.chat.state import persist_message, reset_state

logger = get_logger("views.chat.recovery")


# ─────────────────────────────────────────
#  Fehler-Klassifikation
# ─────────────────────────────────────────


def ist_api_fehler(error_msg):
    """Prüft ob ein transientes API-Problem vorliegt (Rate-Limit oder Gateway)."""
    text = (error_msg or "").lower()
    return (
        "429" in text
        or "too many requests" in text
        or "502" in text
        or "bad gateway" in text
        or "503" in text
        or "service unavailable" in text
        or "504" in text
        or "gateway timeout" in text
    )


def ist_modellzugriffsfehler(error_msg):
    """Prüft, ob das ausgewählte Modell für den Account nicht verfügbar ist."""
    text = (error_msg or "").lower()
    return "404" in text and (
        "not found" in text or "integrate.api.nvidia.com" in text
    )


def ist_invalid_chat_history(error_msg):
    """Prüft, ob der Graph-Checkpoint unvollständige Tool-Calls enthält."""
    text = (error_msg or "").lower()
    return (
        "invalid_chat_history" in text
        or "tool_calls that do not have a corresponding toolmessage" in text
    )


# ─────────────────────────────────────────
#  Orphan-Tool-Call-Recovery
# ─────────────────────────────────────────


def repair_orphan_tool_calls():
    """Ergänzt fehlende ToolMessages für offene Tool-Calls im Graph-State.

    Returns:
        int: Anzahl der ergänzten ToolMessages.
    """
    try:
        state = agent_bridge.get_state(st.session_state.config)
        messages = state.values.get("messages", [])
        if not messages:
            return 0

        called_ids = []
        answered_ids = set()

        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tc_id = tc.get("id")
                    if tc_id:
                        called_ids.append(tc_id)

            tool_call_id = getattr(msg, "tool_call_id", None)
            if tool_call_id:
                answered_ids.add(tool_call_id)

        missing_ids = [tc_id for tc_id in called_ids if tc_id not in answered_ids]
        if not missing_ids:
            return 0

        recovery_messages = [
            ToolMessage(
                content="Automatische Recovery: Tool-Aufruf wurde nach Fehler abgebrochen.",
                tool_call_id=tc_id,
            )
            for tc_id in missing_ids
        ]
        agent_bridge.update_state(st.session_state.config, {"messages": recovery_messages})
        logger.warning(
            "Recovery abgeschlossen: %s offene Tool-Calls mit ToolMessage ergänzt.",
            len(recovery_messages),
        )
        return len(recovery_messages)
    except Exception as e:
        logger.warning("Recovery für orphan tool calls fehlgeschlagen: %s", e)
        return 0


def handle_agent_error(error: Exception) -> bool:
    """Zentrales Error-Handling für Agent-Aufrufe.

    Schreibt eine passende User-Nachricht in den Chat (persistiert sie),
    ruft reset_state() auf und gibt True zurück, wenn ein bekannter Fehler
    behandelt wurde, sonst False.
    """
    error_msg = str(error)
    if ist_invalid_chat_history(error_msg):
        repaired = repair_orphan_tool_calls()
        if repaired > 0:
            persist_message(
                "assistant",
                "Der letzte Lauf war unvollständig. Ich habe offene Tool-Aufrufe "
                "automatisch bereinigt. Bitte sende deine Anfrage erneut.",
            )
        else:
            persist_message(
                "assistant",
                "Die Unterhaltung hat einen ungültigen Tool-Status. Bitte starte ein "
                "neues Gespräch in der Sidebar.",
            )
        reset_state()
        return True
    if ist_modellzugriffsfehler(error_msg):
        logger.warning("Ausgewähltes NVIDIA-Modell nicht verfügbar.")
        persist_message(
            "assistant",
            "Das ausgewählte KI-Modell ist für diesen NVIDIA-Zugang nicht verfügbar. "
            "Bitte wähle in den Einstellungen ein anderes Modell aus.",
        )
        reset_state()
        return True
    if ist_api_fehler(error_msg):
        logger.warning("API nicht erreichbar: %s", error)
        persist_message(
            "assistant",
            "Die KI-API ist gerade nicht erreichbar (Rate-Limit oder Gateway-Fehler). "
            "Bitte warte einen Moment und versuche es erneut.",
        )
        reset_state()
        return True
    return False


# ─────────────────────────────────────────
#  Pending-State-Detection (nach Reload)
# ─────────────────────────────────────────


def detect_pending_recovery():
    """Prüft den Graph-State und setzt Flags korrekt (blockiert nicht).

    Wird VOR dem UI-Rendering aufgerufen, damit Input-Feld korrekt
    gesperrt wird. Fragt den Graph nur ab wenn nötig:
    - Nach Browser-Reload (_recovery_checked fehlt im session_state)
    - Wenn agent_arbeitet oder warte_auf_bestaetigung gesetzt ist
    """
    if "pending_input" in st.session_state or "tool_approved" in st.session_state:
        return

    nach_reload = "_recovery_checked" not in st.session_state
    hat_aktive_flags = st.session_state.agent_arbeitet or st.session_state.warte_auf_bestaetigung

    if not nach_reload and not hat_aktive_flags:
        return

    st.session_state._recovery_checked = True

    try:
        state = agent_bridge.get_state(st.session_state.config)
        if not state.values.get("messages"):
            if hat_aktive_flags:
                reset_state()
            return

        if state.next:
            last_msg = state.values["messages"][-1]
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                st.session_state.warte_auf_bestaetigung = True
                st.session_state.pending_tool_calls = last_msg.tool_calls
                st.session_state.agent_arbeitet = False
            else:
                st.session_state.agent_arbeitet = True
                st.session_state.warte_auf_bestaetigung = False
        else:
            if st.session_state.agent_arbeitet:
                pass  # execute_recovery wird die Antwort persistieren
            elif st.session_state.warte_auf_bestaetigung:
                reset_state()
    except Exception as e:
        logger.warning("Recovery-Erkennung fehlgeschlagen: %s", e)


def execute_recovery(container):
    """Führt Recovery mit Spinner im Chat-Container durch.

    Returns:
        True wenn ein Rerun nötig ist, False sonst.
    """
    if not st.session_state.agent_arbeitet or "pending_input" in st.session_state:
        return False
    with container:
        with st.chat_message("assistant"):
            with st.spinner("Agent antwortet..."):
                try:
                    state = agent_bridge.get_state(st.session_state.config)
                    if not state.values.get("messages"):
                        reset_state()
                        return True

                    if state.next:
                        result = agent_bridge.invoke(None, st.session_state.config)
                        last_msg = result["messages"][-1]
                    else:
                        last_msg = state.values["messages"][-1]

                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        st.session_state.warte_auf_bestaetigung = True
                        st.session_state.pending_tool_calls = last_msg.tool_calls
                        st.session_state.agent_arbeitet = False
                        return True

                    content = getattr(last_msg, "content", "")
                    if content and not hasattr(last_msg, "tool_call_id"):
                        existing = st.session_state.messages
                        if not existing or existing[-1].get("content") != content:
                            tools = st.session_state.get("tools_used")
                            persist_message("assistant", content, tools if tools else None)
                except Exception as e:
                    # Bekannte transiente Fehler (429/502/504) als Chat-Nachricht melden,
                    # statt stumm im Log zu versenken.
                    if not handle_agent_error(e):
                        logger.warning("Recovery fehlgeschlagen: %s", e)

    reset_state()
    return True
