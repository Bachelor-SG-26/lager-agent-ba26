"""State-Handling für den Chat: Persistenz, Reset, Logging, Recovery-Utilities."""
import json
from datetime import datetime

import streamlit as st
from langchain_core.messages import ToolMessage

from database.database import db_connection
from services import agent_bridge
from services.session import speichere_nachricht
from services.logger import get_logger

logger = get_logger("views.chat.state")


# ─────────────────────────────────────────
#  Session-State-Helfer
# ─────────────────────────────────────────


def get_thread_id():
    """Gibt die aktuelle Thread-ID zurück."""
    return st.session_state.config["configurable"]["thread_id"]


def persist_message(role, content, tools_used=None):
    """Speichert eine Nachricht in session_state und DB."""
    msg = {"role": role, "content": content}
    if tools_used:
        msg["tools_used"] = tools_used
    st.session_state.messages.append(msg)
    speichere_nachricht(get_thread_id(), role, content, tools_used)


def reset_state():
    """Setzt alle Agent-Flags auf Ausgangszustand zurück."""
    st.session_state.warte_auf_bestaetigung = False
    st.session_state.pending_tool_calls = []
    st.session_state.pop("tools_used", None)
    st.session_state.pop("pending_input", None)
    st.session_state.pop("stop_requested", None)
    st.session_state.agent_arbeitet = False


def stop_requested():
    """Prüft, ob ein manueller Stop angefordert wurde."""
    return bool(st.session_state.get("stop_requested", False))


# ─────────────────────────────────────────
#  Tool-Logging
# ─────────────────────────────────────────


def log_tool_calls(tool_calls, status, duration_ms_by_call_id=None):
    """Schreibt Tool-Call-Ereignisse mit eindeutiger Aufruf-ID in agent_log."""
    duration_ms_by_call_id = duration_ms_by_call_id or {}
    try:
        datum = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with db_connection(commit=True) as (conn, cursor):
            for tc in tool_calls:
                args_str = json.dumps(tc["args"], ensure_ascii=False) if tc.get("args") else ""
                tool_call_id = tc.get("id")
                duration_ms = duration_ms_by_call_id.get(tool_call_id)
                cursor.execute(
                    """
                    INSERT INTO agent_log
                        (tool_call_id, tool_name, tool_args, status, datum, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (tool_call_id, tc["name"], args_str, status, datum, duration_ms),
                )
    except Exception as e:
        logger.error("Fehler beim Loggen der Tool-Calls: %s", e)


def status_aus_tool_result(content):
    """Leitet einen Log-Status aus dem Tool-Ergebnistext ab."""
    text = (content or "").strip().lower()
    if not text:
        return "ausgefuehrt"
    if "budget überschritten" in text:
        return "abgelehnt_budget"
    if text.startswith("fehler") or "nicht angelegt" in text:
        return "fehlgeschlagen"
    return "ausgefuehrt"


# ─────────────────────────────────────────
#  Agent-Abbruch / Stopp
# ─────────────────────────────────────────


def cancel_pending_tools(reason="Nutzer hat abgebrochen.", user_msg="Aktion wurde abgebrochen."):
    """Bricht die ausstehenden Tool-Aufrufe ab und informiert den Agenten."""
    tool_namen = [tc["name"] for tc in st.session_state.pending_tool_calls]
    logger.info("Tool-Calls abgelehnt: %s", ", ".join(tool_namen))
    log_tool_calls(st.session_state.pending_tool_calls, "abgelehnt")
    abbruch = [
        ToolMessage(content=reason, tool_call_id=tc["id"])
        for tc in st.session_state.pending_tool_calls
    ]
    agent_bridge.update_state(st.session_state.config, {"messages": abbruch})
    persist_message("assistant", user_msg)
    reset_state()
    st.rerun()


def stop_agent():
    """Stoppt den Agenten und stellt den letzten bekannten State wieder her."""
    logger.info("Agent manuell gestoppt")
    try:
        state = agent_bridge.get_state(st.session_state.config)
        if state.values.get("messages"):
            last_msg = state.values["messages"][-1]
            content = getattr(last_msg, "content", "")
            if content and not (hasattr(last_msg, "tool_calls") and last_msg.tool_calls):
                existing = st.session_state.messages
                if not existing or existing[-1].get("content") != content:
                    persist_message("assistant", content)
    except Exception as e:
        logger.warning("State-Abfrage beim Stoppen fehlgeschlagen: %s", e)
    reset_state()
