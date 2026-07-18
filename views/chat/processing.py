"""Agent-Verarbeitung: User-Input streamen und bestätigte Tools ausführen."""
import time

import streamlit as st
from langchain_core.messages import HumanMessage

from config import MAX_TOOL_CALLS_PRO_SCHRITT, BATCH_TRIGGER_ANZAHL
from services import agent_bridge
from services.logger import get_logger
from services.session import aktualisiere_session_titel
from views.chat.state import (
    cancel_pending_tools,
    get_thread_id,
    log_tool_calls,
    persist_message,
    reset_state,
    status_aus_tool_result,
    stop_requested,
)
from views.chat.recovery import handle_agent_error

logger = get_logger("views.chat.processing")

_LEERE_ANTWORT_FORTSETZUNG = (
    "Die letzte Modellausgabe war leer. Setze die ursprüngliche Nutzeranfrage "
    "anhand der vorhandenen Tool-Ergebnisse fort. Antworte entweder mit dem "
    "nächsten erforderlichen Tool-Aufruf oder mit einer vollständigen Antwort."
)


def _ist_leere_agentenantwort(message):
    """Erkennt einen beendeten Agentenschritt ohne Text und ohne Tool-Aufruf."""
    if message is None:
        return False
    content = str(getattr(message, "content", "") or "").strip()
    tool_calls = getattr(message, "tool_calls", None) or []
    return not content and not tool_calls


def _setze_nach_leerer_antwort_fort():
    """Fordert einmalig eine verwertbare Fortsetzung vom Agenten an."""
    logger.warning("Leere Agentenantwort erkannt, einmalige Fortsetzung wird angefordert.")
    result = agent_bridge.invoke(
        {"messages": [HumanMessage(content=_LEERE_ANTWORT_FORTSETZUNG)]},
        st.session_state.config,
    )
    messages = result.get("messages", [])
    return messages[-1] if messages else None


# ─────────────────────────────────────────
#  Tool-Ausführung
# ─────────────────────────────────────────


def execute_approved_tools(container):
    """Führt bestätigte Tools aus und zeigt Live-Fortschritt via Streaming."""
    tool_namen = [tc["name"] for tc in st.session_state.pending_tool_calls]
    logger.info("Tool-Calls akzeptiert: %s", ", ".join(tool_namen))
    log_tool_calls(st.session_state.pending_tool_calls, "akzeptiert")
    genehmigte_tools = {tc["name"] for tc in st.session_state.pending_tool_calls}
    tools_used = st.session_state.get("tools_used", [])
    final_content = None
    call_index = {tc["id"]: tc for tc in st.session_state.pending_tool_calls if tc.get("id")}
    call_started_at = {
        tc["id"]: time.perf_counter()
        for tc in st.session_state.pending_tool_calls
        if tc.get("id")
    }
    geloggte_ausfuehrungen = set()

    with container:
        with st.chat_message("assistant"):
            status = st.empty()
            status.caption("Verarbeite...")

            try:
                while True:
                    if stop_requested():
                        status.empty()
                        persist_message("assistant", "Vorgang wurde gestoppt.")
                        reset_state()
                        st.rerun()
                    needs_more = False
                    new_calls = []

                    for event in agent_bridge.stream(
                        None, st.session_state.config, "updates"
                    ):
                        if stop_requested():
                            status.empty()
                            persist_message("assistant", "Vorgang wurde gestoppt.")
                            reset_state()
                            st.rerun()
                        for node_name, node_data in event.items():
                            if node_name == "tools" and "messages" in node_data:
                                for msg in node_data["messages"]:
                                    if hasattr(msg, "name") and msg.name:
                                        tools_used.append(msg.name)
                                    tool_call_id = getattr(msg, "tool_call_id", None)
                                    if (
                                        tool_call_id
                                        and tool_call_id in call_index
                                        and tool_call_id not in geloggte_ausfuehrungen
                                    ):
                                        status_tool = status_aus_tool_result(
                                            getattr(msg, "content", "")
                                        )
                                        duration_ms = None
                                        if tool_call_id in call_started_at:
                                            duration_ms = int(
                                                (time.perf_counter() - call_started_at[tool_call_id]) * 1000
                                            )
                                        log_tool_calls(
                                            [call_index[tool_call_id]],
                                            status_tool,
                                            {tool_call_id: duration_ms},
                                        )
                                        geloggte_ausfuehrungen.add(tool_call_id)
                                status.caption("Verarbeite: " + " → ".join(tools_used))
                            elif node_name == "agent" and "messages" in node_data:
                                last = node_data["messages"][-1]
                                if hasattr(last, "tool_calls") and last.tool_calls:
                                    needs_more = True
                                    new_calls = last.tool_calls
                                    for tc in new_calls:
                                        tc_id = tc.get("id")
                                        if tc_id:
                                            call_index[tc_id] = tc
                                            if tc_id not in call_started_at:
                                                call_started_at[tc_id] = time.perf_counter()
                                else:
                                    final_content = last.content

                    if not needs_more:
                        break

                    neue_tools = {tc["name"] for tc in new_calls}
                    if len(new_calls) > MAX_TOOL_CALLS_PRO_SCHRITT:
                        st.session_state.pending_tool_calls = new_calls
                        cancel_pending_tools(
                            reason=(
                                f"Zu viele Tool-Calls in einem Schritt ({len(new_calls)}). "
                                f"Maximal erlaubt: {MAX_TOOL_CALLS_PRO_SCHRITT}."
                            ),
                            user_msg=(
                                f"Aktion abgebrochen: Der Agent hat {len(new_calls)} Tool-Calls "
                                f"in einem Schritt geplant. Bitte Anfrage aufteilen oder ab "
                                f"{BATCH_TRIGGER_ANZAHL} ähnlichen Aktionen Batch-Tools nutzen."
                            ),
                        )
                    if neue_tools.issubset(genehmigte_tools):
                        log_tool_calls(new_calls, "auto-akzeptiert")
                        continue
                    else:
                        st.session_state.tools_used = tools_used
                        st.session_state.warte_auf_bestaetigung = True
                        st.session_state.pending_tool_calls = new_calls
                        st.rerun()
            except Exception as e:
                status.empty()
                if handle_agent_error(e):
                    st.rerun()
                logger.error("Fehler bei Tool-Ausführung: %s", e)
                persist_message("assistant", f"Ein Fehler ist aufgetreten: {e}")
                reset_state()
                st.rerun()

    # Ergebnis verarbeiten
    if final_content:
        persist_message("assistant", final_content, tools_used if tools_used else None)
    else:
        try:
            state = agent_bridge.get_state(st.session_state.config)
            if state.values.get("messages"):
                last = state.values["messages"][-1]
                if _ist_leere_agentenantwort(last):
                    last = _setze_nach_leerer_antwort_fort()

                if last and getattr(last, "tool_calls", None):
                    new_calls = last.tool_calls
                    if len(new_calls) > MAX_TOOL_CALLS_PRO_SCHRITT:
                        st.session_state.pending_tool_calls = new_calls
                        cancel_pending_tools(
                            reason=(
                                f"Zu viele Tool-Calls in einem Schritt ({len(new_calls)}). "
                                f"Maximal erlaubt: {MAX_TOOL_CALLS_PRO_SCHRITT}."
                            ),
                            user_msg="Aktion wegen zu vieler geplanter Aufrufe abgebrochen.",
                        )
                    st.session_state.tools_used = tools_used
                    st.session_state.warte_auf_bestaetigung = True
                    st.session_state.pending_tool_calls = new_calls
                    st.session_state.agent_arbeitet = False
                    st.rerun()

                if last and str(getattr(last, "content", "") or "").strip():
                    persist_message("assistant", last.content, tools_used if tools_used else None)
                else:
                    persist_message(
                        "assistant",
                        "Das ausgewählte Modell hat keine verwertbare Antwort geliefert. "
                        "Bitte versuche die Anfrage erneut oder wähle ein anderes Modell.",
                    )
        except Exception as e:
            if handle_agent_error(e):
                st.rerun()
            logger.warning("Fallback State-Abfrage fehlgeschlagen: %s", e)
            persist_message(
                "assistant",
                "Die Bearbeitung konnte nach einer leeren Modellantwort nicht "
                "fortgesetzt werden. Bitte versuche die Anfrage erneut.",
            )
    reset_state()
    st.rerun()


def process_approval(container):
    """Verarbeitet eine Tool-Bestätigung oder -Ablehnung."""
    approved = st.session_state.pop("tool_approved")

    if approved:
        execute_approved_tools(container)
    else:
        cancel_pending_tools()


# ─────────────────────────────────────────
#  User-Input-Verarbeitung (Streaming)
# ─────────────────────────────────────────


def process_user_input(container, user_input):
    """Verarbeitet eine Benutzereingabe mit Live-Token-Streaming."""
    if stop_requested():
        persist_message("assistant", "Vorgang wurde gestoppt.")
        reset_state()
        st.rerun()
        return

    persist_message("user", user_input)

    # Titel der Session setzen bei erster Nachricht
    if len(st.session_state.messages) == 1:
        aktualisiere_session_titel(get_thread_id(), user_input)

    with container:
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            thinking = st.empty()
            full_text = ""

            try:
                with st.spinner("Agent antwortet..."):
                    for chunk, metadata in agent_bridge.stream(
                        {"messages": [HumanMessage(content=user_input)]},
                        st.session_state.config,
                        "messages",
                    ):
                        if stop_requested():
                            thinking.empty()
                            persist_message("assistant", "Vorgang wurde gestoppt.")
                            reset_state()
                            st.rerun()
                            return
                        if metadata.get("langgraph_node") != "agent":
                            continue
                        if hasattr(chunk, "content") and chunk.content:
                            full_text += chunk.content
                            thinking.markdown(full_text + " ▌")
            except Exception as e:
                thinking.empty()
                if handle_agent_error(e):
                    st.rerun()
                    return
                logger.warning("Streaming fehlgeschlagen, Fallback auf invoke(): %s", e)
                if not full_text:
                    try:
                        with st.spinner("Agent antwortet..."):
                            agent_bridge.invoke(
                                {"messages": [HumanMessage(content=user_input)]},
                                st.session_state.config,
                            )
                    except Exception as e2:
                        if handle_agent_error(e2):
                            st.rerun()
                            return
                        logger.error("Fehler bei Agent-Aufruf: %s", e2)
                        persist_message("assistant", f"Ein Fehler ist aufgetreten: {e2}")
                        reset_state()
                        st.rerun()
                        return

            # Finalen State prüfen
            state = agent_bridge.get_state(st.session_state.config)
            last_msg = state.values["messages"][-1]

            if not full_text and _ist_leere_agentenantwort(last_msg):
                try:
                    last_msg = _setze_nach_leerer_antwort_fort()
                except Exception as e:
                    if handle_agent_error(e):
                        st.rerun()
                        return
                    logger.warning("Fortsetzung nach leerer Agentenantwort fehlgeschlagen: %s", e)

            if last_msg and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                if len(last_msg.tool_calls) > MAX_TOOL_CALLS_PRO_SCHRITT:
                    st.session_state.pending_tool_calls = last_msg.tool_calls
                    cancel_pending_tools(
                        reason=(
                            f"Zu viele Tool-Calls in einem Schritt ({len(last_msg.tool_calls)}). "
                            f"Maximal erlaubt: {MAX_TOOL_CALLS_PRO_SCHRITT}."
                        ),
                        user_msg=(
                            f"Aktion abgebrochen: Der Agent hat {len(last_msg.tool_calls)} Tool-Calls "
                            f"in einem Schritt geplant. Bitte Anfrage aufteilen oder ab "
                            f"{BATCH_TRIGGER_ANZAHL} ähnlichen Aktionen Batch-Tools nutzen."
                        ),
                    )

                if full_text:
                    thinking.markdown(full_text)
                    persist_message("assistant", full_text)
                else:
                    thinking.empty()

                st.session_state.warte_auf_bestaetigung = True
                st.session_state.pending_tool_calls = last_msg.tool_calls
                st.session_state.tools_used = []
                st.session_state.agent_arbeitet = False
                st.rerun()
            else:
                content = full_text or str(getattr(last_msg, "content", "") or "").strip()
                if not content:
                    content = (
                        "Das ausgewählte Modell hat keine verwertbare Antwort geliefert. "
                        "Bitte versuche die Anfrage erneut oder wähle ein anderes Modell."
                    )
                thinking.markdown(content)
                persist_message("assistant", content)
                reset_state()
                st.rerun()
