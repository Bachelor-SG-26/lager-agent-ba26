from langchain_core.messages import HumanMessage

from agent.agent import build_agent


def ask_agent(message, thread_id):
    """Sendet eine Nachricht an den Agenten und gibt die letzte Antwort zurück."""
    agent = build_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": thread_id}},
    )

    messages = result.get("messages", [])
    if not messages:
        return "Es wurde keine Antwort erzeugt."
    return messages[-1].content
