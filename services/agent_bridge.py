"""Dünner Wrapper um den LangGraph-Agent.

Entkoppelt die View-Schicht vom konkreten Agent-Objekt. Views importieren
Funktionen aus diesem Modul, nicht den konkreten Agenten direkt. Dadurch
lässt sich der Agent in Tests einfach ersetzen und ein Modellwechsel bleibt
auf dieses Modul begrenzt.

Alle Funktionen delegieren 1:1 an den LangGraph-Agent und sind bewusst
ohne zusätzliche Logik, damit sich das Verhalten der Views nicht ändert.
"""
from agent.agent import build_agent


def _get_agent():
    """Gibt den Agenten für die aktuell gespeicherte Modellkonfiguration zurück."""
    return build_agent()


def get_state(config):
    """Liest den aktuellen Graph-State für die gegebene Config."""
    return _get_agent().get_state(config)


def update_state(config, values):
    """Schreibt Werte in den Graph-State (z. B. ToolMessages für Recovery)."""
    return _get_agent().update_state(config, values)


def invoke(input_, config):
    """Führt den Graph bis zum nächsten Interrupt oder Ende aus."""
    return _get_agent().invoke(input_, config=config)


def stream(input_, config, stream_mode):
    """Streamt Graph-Events (Modi: 'updates' oder 'messages')."""
    return _get_agent().stream(input_, config=config, stream_mode=stream_mode)
