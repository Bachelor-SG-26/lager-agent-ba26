from agent.agent import build_agent


def get_agent():
    """Lädt den gecachten LangGraph-Agenten für Chat- und State-Aufrufe."""
    return build_agent()


def get_state(config):
    """Liest den aktuellen Graph-State für eine Chat-Konfiguration."""
    return get_agent().get_state(config)


def update_state(config, values):
    """Schreibt Werte in den Graph-State, zum Beispiel Tool-Ergebnisse."""
    return get_agent().update_state(config, values)


def invoke(input_data, config):
    """Führt den Agenten bis zur nächsten Antwort oder Unterbrechung aus."""
    return get_agent().invoke(input_data, config=config)


def stream(input_data, config, stream_mode):
    """Streamt Agent-Ereignisse für Chat-Ausgabe und spätere Tool-Steuerung."""
    return get_agent().stream(input_data, config=config, stream_mode=stream_mode)
