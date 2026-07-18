"""Tests für die testbaren Pfade in views/chat/processing und recovery:
Fehlerrouting über handle_agent_error und ist_api_fehler.
"""
from types import SimpleNamespace

from views.chat import processing, recovery, state


class AttrDict(dict):
    def __getattr__(self, item):
        if item in self:
            return self[item]
        raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value


def _patch(monkeypatch, session_state):
    """Patches st + persist_message + reset_state auf recovery- und state-Modul."""
    fake_st = SimpleNamespace(session_state=session_state)
    monkeypatch.setattr(recovery, "st", fake_st)
    monkeypatch.setattr(state, "st", fake_st)

    # persist_message ohne DB
    captured = {"messages": [], "resets": 0}

    def fake_persist(role, content, tools_used=None):
        captured["messages"].append({"role": role, "content": content})

    def fake_reset():
        captured["resets"] += 1

    monkeypatch.setattr(recovery, "persist_message", fake_persist)
    monkeypatch.setattr(recovery, "reset_state", fake_reset)
    return captured


# ─────────────────────────────────────────
#  ist_api_fehler
# ─────────────────────────────────────────


def test_ist_api_fehler_rate_limit():
    assert recovery.ist_api_fehler("HTTP 429 Too Many Requests") is True
    assert recovery.ist_api_fehler("rate limit") is False  # kein Code, zu generisch


def test_ist_api_fehler_gateway():
    assert recovery.ist_api_fehler("500 Internal Server Error") is True
    assert recovery.ist_api_fehler("502 Bad Gateway") is True
    assert recovery.ist_api_fehler("503 service unavailable") is True
    assert recovery.ist_api_fehler("Gateway Timeout after 300s") is True
    assert recovery.ist_api_fehler("504") is True


def test_ist_api_fehler_nichts():
    assert recovery.ist_api_fehler("") is False
    assert recovery.ist_api_fehler(None) is False
    assert recovery.ist_api_fehler("normaler Fehler") is False


def test_ist_modellzugriffsfehler_erkennt_nvidia_404():
    error = "[404] Not Found Function 'abc': Not found for account 'xyz'"
    assert recovery.ist_modellzugriffsfehler(error) is True
    assert recovery.ist_modellzugriffsfehler("[404] Not Found") is True
    assert recovery.ist_modellzugriffsfehler("Produkt nicht gefunden") is False


# ─────────────────────────────────────────
#  handle_agent_error Routing
# ─────────────────────────────────────────


def test_handle_agent_error_api_fehler_wird_behandelt(monkeypatch):
    session_state = AttrDict(
        {
            "config": {"configurable": {"thread_id": "t"}},
            "messages": [],
        }
    )
    captured = _patch(monkeypatch, session_state)

    err = Exception("HTTP 502 Bad Gateway after 219s")
    handled = recovery.handle_agent_error(err)

    assert handled is True
    assert captured["resets"] == 1
    assert len(captured["messages"]) == 1
    msg = captured["messages"][0]["content"]
    assert "KI-API" in msg or "API" in msg


def test_handle_agent_error_interner_serverfehler_wird_behandelt(monkeypatch):
    """NVIDIA-Fehler 500 werden ohne technische Rohdaten angezeigt."""
    session_state = AttrDict(
        {
            "config": {"configurable": {"thread_id": "t"}},
            "messages": [],
        }
    )
    captured = _patch(monkeypatch, session_state)

    err = Exception("[500] invalid type: unit variant, expected newtype variant")
    handled = recovery.handle_agent_error(err)

    assert handled is True
    assert captured["resets"] == 1
    assert captured["messages"][0]["content"] == (
        "Die KI-API ist gerade nicht erreichbar (Rate-Limit oder Serverfehler). "
        "Bitte warte einen Moment und versuche es erneut."
    )


def test_handle_agent_error_modellzugriff_wird_behandelt(monkeypatch):
    session_state = AttrDict(
        {
            "config": {"configurable": {"thread_id": "t"}},
            "messages": [],
        }
    )
    captured = _patch(monkeypatch, session_state)

    err = Exception("[404] Function 'abc': Not found for account 'xyz'")
    handled = recovery.handle_agent_error(err)

    assert handled is True
    assert captured["resets"] == 1
    msg = captured["messages"][0]["content"]
    assert "Einstellungen" in msg
    assert "account" not in msg.lower()


def test_handle_agent_error_invalid_history_mit_repair(monkeypatch):
    session_state = AttrDict(
        {
            "config": {"configurable": {"thread_id": "t"}},
            "messages": [],
        }
    )
    captured = _patch(monkeypatch, session_state)

    # repair_orphan_tool_calls auf "1 repariert" mocken
    monkeypatch.setattr(recovery, "repair_orphan_tool_calls", lambda: 1)

    err = Exception("Found AIMessages with tool_calls that do not have a corresponding ToolMessage")
    handled = recovery.handle_agent_error(err)

    assert handled is True
    assert captured["resets"] == 1
    assert "bereinigt" in captured["messages"][0]["content"].lower()


def test_handle_agent_error_invalid_history_ohne_repair(monkeypatch):
    session_state = AttrDict(
        {
            "config": {"configurable": {"thread_id": "t"}},
            "messages": [],
        }
    )
    captured = _patch(monkeypatch, session_state)
    monkeypatch.setattr(recovery, "repair_orphan_tool_calls", lambda: 0)

    err = Exception("INVALID_CHAT_HISTORY detected")
    handled = recovery.handle_agent_error(err)

    assert handled is True
    assert captured["resets"] == 1
    assert "ungültigen" in captured["messages"][0]["content"].lower()


def test_handle_agent_error_unbekannter_fehler_wird_nicht_behandelt(monkeypatch):
    session_state = AttrDict(
        {
            "config": {"configurable": {"thread_id": "t"}},
            "messages": [],
        }
    )
    captured = _patch(monkeypatch, session_state)

    err = ValueError("irgendein anderer Fehler")
    handled = recovery.handle_agent_error(err)

    assert handled is False
    assert captured["resets"] == 0
    assert captured["messages"] == []


def test_erkennt_leere_agentenantwort():
    """Nur Nachrichten ohne Text und Tool-Aufrufe gelten als leer."""
    assert processing._ist_leere_agentenantwort(
        SimpleNamespace(content="", tool_calls=[])
    )
    assert not processing._ist_leere_agentenantwort(
        SimpleNamespace(content="Antwort", tool_calls=[])
    )
    assert not processing._ist_leere_agentenantwort(
        SimpleNamespace(content="", tool_calls=[{"name": "check_budget"}])
    )


def test_fordert_nach_leerer_antwort_einmalige_fortsetzung_an(monkeypatch):
    """Die Recovery ergänzt eine interne Fortsetzungsanweisung."""
    session_state = AttrDict({"config": {"configurable": {"thread_id": "t"}}})
    monkeypatch.setattr(processing, "st", SimpleNamespace(session_state=session_state))
    antwort = SimpleNamespace(content="Fortgesetzt", tool_calls=[])
    captured = {}

    def fake_invoke(input_, config):
        captured["input"] = input_
        captured["config"] = config
        return {"messages": [antwort]}

    monkeypatch.setattr(processing.agent_bridge, "invoke", fake_invoke)

    result = processing._setze_nach_leerer_antwort_fort()

    assert result is antwort
    assert "letzte Modellausgabe war leer" in captured["input"]["messages"][0].content
    assert captured["config"] == session_state.config
