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
