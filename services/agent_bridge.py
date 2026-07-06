"""Duenner Wrapper um den LangGraph-Agent.

Entkoppelt die View-Schicht vom konkreten Agent-Objekt. Views importieren
Funktionen aus diesem Modul, nicht `agent.agent.agent` direkt. Dadurch
lässt sich der Agent in Tests einfach stubben (einfaches monkeypatch
auf dieses Modul), und Änderungen an der Agent-API bleiben lokal.

Alle Funktionen delegieren 1:1 an den LangGraph-Agent und sind bewusst
ohne zusätzliche Logik, damit sich das Verhalten der Views nicht ändert.
"""
from agent.agent import agent


def get_state(config):
    """Liest den aktuellen Graph-State für die gegebene Config."""
    return agent.get_state(config)


def update_state(config, values):
    """Schreibt Werte in den Graph-State (z. B. ToolMessages für Recovery)."""
    return agent.update_state(config, values)


def invoke(input_, config):
    """Führt den Graph bis zum nächsten Interrupt oder Ende aus."""
    return agent.invoke(input_, config=config)


def stream(input_, config, stream_mode):
    """Streamt Graph-Events (Modi: 'updates' oder 'messages')."""
    return agent.stream(input_, config=config, stream_mode=stream_mode)
