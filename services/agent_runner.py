from langchain_core.messages import HumanMessage

from services import agent_bridge


def check_agent_readiness():
    """Prüft den Agent-Start, ohne bereits eine Modellanfrage zu senden."""
    agent_bridge.get_agent()
    return True


def ask_agent(message, thread_id):
    """Sendet eine Nachricht an den Agenten und gibt die letzte Antwort zurück."""
    result = agent_bridge.invoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": thread_id}},
    )

    messages = result.get("messages", [])
    if not messages:
        return "Es wurde keine Antwort erzeugt."
    return messages[-1].content


def stream_agent_response(message, thread_id):
    """Streamt die Antwort des Agenten als Textstücke."""
    config = {"configurable": {"thread_id": thread_id}}
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


def _latest_state_content(config):
    """Liest den letzten Antworttext aus dem Agent-State."""
    state = agent_bridge.get_state(config)
    values = getattr(state, "values", {})
    messages = values.get("messages", [])
    if not messages:
        return ""

    last_message = messages[-1]
    return getattr(last_message, "content", "") or ""
