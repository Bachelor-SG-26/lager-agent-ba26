import sys
import types
from types import SimpleNamespace

fake_agent_module = types.ModuleType("agent.agent")
fake_agent_module.build_agent = lambda: SimpleNamespace()
sys.modules.setdefault("agent.agent", fake_agent_module)

from views.chat import recovery, state


class AttrDict(dict):
    """Dict mit Attributzugriff für session_state-Mocks."""

    def __getattr__(self, item):
        if item in self:
            return self[item]
        raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value


class FakeState:
    def __init__(self, messages):
        self.values = {"messages": messages}


class FakeMessage:
    def __init__(self, tool_calls=None, tool_call_id=None):
        self.tool_calls = tool_calls or []
        self.tool_call_id = tool_call_id


def _patch_session_state(monkeypatch):
    session_state = AttrDict(
        {
            "config": {"configurable": {"thread_id": "test-thread"}},
        }
    )
    monkeypatch.setattr(recovery, "st", SimpleNamespace(session_state=session_state))


def test_ist_invalid_chat_history_erkennt_fehler():
    msg = "Found AIMessages with tool_calls that do not have a corresponding ToolMessage"
    assert recovery.ist_invalid_chat_history(msg) is True
    assert recovery.ist_invalid_chat_history("random error") is False


def test_status_aus_tool_result_mapping():
    assert state.status_aus_tool_result("Fehler: xyz") == "fehlgeschlagen"
    assert state.status_aus_tool_result("BUDGET ÜBERSCHRITTEN") == "abgelehnt_budget"
    assert (
        state.status_aus_tool_result(
            "BUDGET ÜBERSCHRITTEN\nBestellung wurde NICHT angelegt."
        )
        == "abgelehnt_budget"
    )
    assert state.status_aus_tool_result("Bestellung erfolgreich") == "ausgefuehrt"


def test_repair_orphan_tool_calls_ergaenzt_fehlende_toolmessage(monkeypatch):
    _patch_session_state(monkeypatch)

    updates = []

    class FakeAgent:
        def get_state(self, _config):
            return FakeState(
                [
                    FakeMessage(
                        tool_calls=[
                            {"id": "call-1", "name": "vergleiche_lieferanten", "args": {"produkt_id": 1}}
                        ]
                    ),
                    FakeMessage(tool_call_id="call-2"),
                ]
            )

        def update_state(self, _config, payload):
            updates.append(payload)

    monkeypatch.setattr(recovery, "agent_bridge", FakeAgent())

    repaired = recovery.repair_orphan_tool_calls()

    assert repaired == 1
    assert len(updates) == 1
    assert len(updates[0]["messages"]) == 1
    assert updates[0]["messages"][0].tool_call_id == "call-1"


def test_repair_orphan_tool_calls_noop_wenn_nichts_offen(monkeypatch):
    _patch_session_state(monkeypatch)

    class FakeAgent:
        def get_state(self, _config):
            return FakeState(
                [
                    FakeMessage(
                        tool_calls=[
                            {"id": "call-1", "name": "check_budget", "args": {}}
                        ]
                    ),
                    FakeMessage(tool_call_id="call-1"),
                ]
            )

        def update_state(self, _config, payload):
            raise AssertionError("update_state darf hier nicht aufgerufen werden")

    monkeypatch.setattr(recovery, "agent_bridge", FakeAgent())

    repaired = recovery.repair_orphan_tool_calls()
    assert repaired == 0
