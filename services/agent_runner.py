from langchain_core.messages import HumanMessage, ToolMessage

from services import agent_bridge


TRANSIENT_ERROR_MARKERS = (
    "429",
    "too many requests",
    "502",
    "bad gateway",
    "503",
    "service unavailable",
    "504",
    "gateway timeout",
)

INVALID_HISTORY_MARKERS = (
    "invalid_chat_history",
    "tool_calls that do not have a corresponding toolmessage",
)


def check_agent_readiness():
    """Prüft den Agent-Start, ohne bereits eine Modellanfrage zu senden."""
    agent_bridge.get_agent()
    return True


def ask_agent(message, thread_id):
    """Sendet eine Nachricht an den Agenten und gibt die letzte Antwort zurück."""
    result = agent_bridge.invoke(
        {"messages": [HumanMessage(content=message)]},
        config=_agent_config(thread_id),
    )

    messages = result.get("messages", [])
    if not messages:
        return "Es wurde keine Antwort erzeugt."
    if _tool_calls_from_message(messages[-1]):
        return "Der Agent hat Aktionen vorbereitet, die bestätigt werden müssen."
    return messages[-1].content


def stream_agent_response(message, thread_id):
    """Streamt die Antwort des Agenten als Textstücke."""
    config = _agent_config(thread_id)
    input_data = {"messages": [HumanMessage(content=message)]}
    emitted = False

    for chunk, metadata in agent_bridge.stream(input_data, config, "messages"):
        if metadata.get("langgraph_node") != "agent":
            continue
        content = getattr(chunk, "content", "")
        if not content:
            continue
        emitted = True
        yield content

    if not emitted:
        content = _latest_state_content(config)
        if content:
            yield content


def get_pending_tool_calls(thread_id):
    """Liest vorbereitete Tool-Aufrufe aus dem Agent-State."""
    state = agent_bridge.get_state(_agent_config(thread_id))
    values = getattr(state, "values", {})
    messages = values.get("messages", [])
    if not messages:
        return []
    return _tool_calls_from_message(messages[-1])


def continue_after_tool_confirmation(thread_id):
    """Führt bestätigte Tool-Aufrufe aus und gibt Antwort oder neue Tools zurück."""
    config = _agent_config(thread_id)
    approved_tools = {
        tool_call.get("name")
        for tool_call in get_pending_tool_calls(thread_id)
        if tool_call.get("name")
    }

    for _ in range(2):
        last_message, tool_content = _continue_agent_once(config)

        if last_message is None:
            content = _latest_state_content(config)
            return content, []

        pending_tool_calls = _tool_calls_from_message(last_message)
        if not pending_tool_calls:
            return getattr(last_message, "content", "") or "", []

        next_tools = {
            tool_call.get("name")
            for tool_call in pending_tool_calls
            if tool_call.get("name")
        }
        if next_tools and next_tools.issubset(approved_tools):
            if tool_content:
                return tool_content, []
            continue

        return "", pending_tool_calls

    return "", get_pending_tool_calls(thread_id)


def reject_pending_tool_calls(thread_id, reason="Aktion wurde abgebrochen."):
    """Beendet vorbereitete Tool-Aufrufe ohne Ausführung im Agent-State."""
    tool_calls = get_pending_tool_calls(thread_id)
    if not tool_calls:
        return 0

    messages = [
        ToolMessage(content=reason, tool_call_id=tool_call["id"])
        for tool_call in tool_calls
        if tool_call.get("id")
    ]
    if messages:
        agent_bridge.update_state(_agent_config(thread_id), {"messages": messages})
    return len(messages)


def repair_orphan_tool_calls(thread_id):
    """Ergänzt fehlende ToolMessages, wenn ein Agent-Lauf unterbrochen wurde."""
    state = agent_bridge.get_state(_agent_config(thread_id))
    values = getattr(state, "values", {})
    messages = values.get("messages", [])
    if not messages:
        return 0

    called_ids = []
    answered_ids = set()
    for message in messages:
        for tool_call in _tool_calls_from_message(message):
            tool_call_id = tool_call.get("id")
            if tool_call_id:
                called_ids.append(tool_call_id)

        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id:
            answered_ids.add(tool_call_id)

    missing_ids = [
        tool_call_id
        for tool_call_id in dict.fromkeys(called_ids)
        if tool_call_id not in answered_ids
    ]
    recovery_messages = [
        ToolMessage(
            content="Automatische Bereinigung: Aktion wurde nach einem Fehler abgebrochen.",
            tool_call_id=tool_call_id,
        )
        for tool_call_id in missing_ids
    ]
    if recovery_messages:
        agent_bridge.update_state(
            _agent_config(thread_id),
            {"messages": recovery_messages},
        )
    return len(recovery_messages)


def build_agent_error_message(thread_id, error):
    """Erzeugt eine stabile Chat-Meldung für bekannte Agent-Fehler."""
    error_text = str(error)
    normalized_error = error_text.lower()

    if _contains_marker(normalized_error, INVALID_HISTORY_MARKERS):
        try:
            repaired = repair_orphan_tool_calls(thread_id)
        except Exception:
            repaired = 0
        if repaired:
            return (
                "Der letzte Agent-Lauf war unvollständig. "
                "Offene Aktionen wurden bereinigt. Bitte sende deine Anfrage erneut."
            )
        return (
            "Die Unterhaltung hat einen ungültigen Aktionsstatus. "
            "Bitte starte ein neues Gespräch."
        )

    if _contains_marker(normalized_error, TRANSIENT_ERROR_MARKERS):
        return (
            "Die KI-API ist gerade nicht erreichbar. "
            "Bitte warte kurz und versuche es erneut."
        )

    return f"Agent konnte nicht antworten: {error}"


def _latest_state_content(config):
    """Liest den letzten Antworttext aus dem Agent-State."""
    state = agent_bridge.get_state(config)
    values = getattr(state, "values", {})
    messages = values.get("messages", [])
    if not messages:
        return ""

    last_message = messages[-1]
    if _tool_calls_from_message(last_message):
        return ""
    return getattr(last_message, "content", "") or ""


def _continue_agent_once(config):
    """Setzt den Agenten genau einen Graph-Schritt fort."""
    last_message = None
    tool_content = ""
    for event in agent_bridge.stream(None, config, "updates"):
        for node_name, node_data in event.items():
            messages = node_data.get("messages", []) if isinstance(node_data, dict) else []
            if messages:
                last_message = messages[-1]
                if node_name == "tools":
                    tool_content = getattr(last_message, "content", "") or tool_content
    return last_message, tool_content


def _agent_config(thread_id):
    """Erstellt die LangGraph-Konfiguration für eine Chat-Session."""
    return {"configurable": {"thread_id": thread_id}}


def _tool_calls_from_message(message):
    """Extrahiert Tool-Aufrufe unabhängig vom konkreten Message-Typ."""
    return getattr(message, "tool_calls", None) or []


def _contains_marker(text, markers):
    """Prüft, ob ein Fehlertext einen bekannten Marker enthält."""
    return any(marker in text for marker in markers)
