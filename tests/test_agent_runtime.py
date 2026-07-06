from types import SimpleNamespace

import pytest

from agent.agent import AgentConfigurationError, build_agent, is_agent_configured
from services.agent_runner import (
    ask_agent,
    build_agent_error_message,
    check_agent_readiness,
    continue_after_tool_confirmation,
    get_pending_tool_calls,
    repair_orphan_tool_calls,
    reject_pending_tool_calls,
    stream_agent_response,
)


def test_agent_configuration_detects_missing_key(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "")

    assert is_agent_configured() is False


def test_build_agent_requires_api_key(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "")

    with pytest.raises(AgentConfigurationError):
        build_agent()


def test_ask_agent_uses_same_configuration_guard(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "")

    with pytest.raises(AgentConfigurationError):
        ask_agent("Prüfe den Lagerbestand", "test-thread")


def test_agent_readiness_uses_agent_builder(monkeypatch):
    calls = []

    def fake_get_agent():
        calls.append("built")
        return object()

    monkeypatch.setattr("services.agent_runner.agent_bridge.get_agent", fake_get_agent)

    assert check_agent_readiness() is True
    assert calls == ["built"]


def test_ask_agent_uses_agent_bridge(monkeypatch):
    captured = {}

    def fake_invoke(input_data, config):
        captured["input"] = input_data
        captured["config"] = config
        return {"messages": [SimpleNamespace(content="Antwort bereit")]}

    monkeypatch.setattr("services.agent_runner.agent_bridge.invoke", fake_invoke)

    assert ask_agent("Prüfe den Lagerbestand", "thread-1") == "Antwort bereit"
    assert captured["config"]["configurable"]["thread_id"] == "thread-1"


def test_ask_agent_reports_pending_tool_calls(monkeypatch):
    tool_call = {"id": "call-1", "name": "check_lagerbestand", "args": {}}

    def fake_invoke(input_data, config):
        return {"messages": [SimpleNamespace(content="", tool_calls=[tool_call])]}

    monkeypatch.setattr("services.agent_runner.agent_bridge.invoke", fake_invoke)

    assert ask_agent("Prüfe den Lagerbestand", "thread-1") == (
        "Der Agent hat Aktionen vorbereitet, die bestätigt werden müssen."
    )


def test_stream_agent_response_yields_agent_chunks(monkeypatch):
    captured = {}

    def fake_stream(input_data, config, stream_mode):
        captured["input"] = input_data
        captured["config"] = config
        captured["stream_mode"] = stream_mode
        return iter((
            (SimpleNamespace(content="Ant"), {"langgraph_node": "agent"}),
            (SimpleNamespace(content="wort"), {"langgraph_node": "agent"}),
            (SimpleNamespace(content="ignoriert"), {"langgraph_node": "tools"}),
        ))

    monkeypatch.setattr("services.agent_runner.agent_bridge.stream", fake_stream)

    chunks = list(stream_agent_response("Hallo", "thread-2"))

    assert chunks == ["Ant", "wort"]
    assert captured["config"]["configurable"]["thread_id"] == "thread-2"
    assert captured["stream_mode"] == "messages"


def test_stream_agent_response_falls_back_to_state(monkeypatch):
    def fake_stream(input_data, config, stream_mode):
        return iter(())

    def fake_get_state(config):
        return SimpleNamespace(values={
            "messages": [SimpleNamespace(content="Antwort aus State")]
        })

    monkeypatch.setattr("services.agent_runner.agent_bridge.stream", fake_stream)
    monkeypatch.setattr("services.agent_runner.agent_bridge.get_state", fake_get_state)

    assert list(stream_agent_response("Hallo", "thread-3")) == ["Antwort aus State"]


def test_get_pending_tool_calls_reads_graph_state(monkeypatch):
    tool_call = {"id": "call-1", "name": "check_lagerbestand", "args": {}}

    def fake_get_state(config):
        return SimpleNamespace(values={
            "messages": [SimpleNamespace(content="", tool_calls=[tool_call])]
        })

    monkeypatch.setattr("services.agent_runner.agent_bridge.get_state", fake_get_state)

    assert get_pending_tool_calls("thread-4") == [tool_call]


def test_continue_after_tool_confirmation_returns_answer(monkeypatch):
    tool_call = {"id": "call-1", "name": "check_lagerbestand", "args": {}}

    def fake_get_state(config):
        return SimpleNamespace(values={
            "messages": [SimpleNamespace(content="", tool_calls=[tool_call])]
        })

    def fake_stream(input_data, config, stream_mode):
        return iter((
            {"tools": {"messages": [SimpleNamespace(content="Tool fertig")]}},
            {"agent": {"messages": [SimpleNamespace(content="Bestand geprüft")]}},
        ))

    monkeypatch.setattr("services.agent_runner.agent_bridge.get_state", fake_get_state)
    monkeypatch.setattr("services.agent_runner.agent_bridge.stream", fake_stream)

    answer, pending = continue_after_tool_confirmation("thread-5")

    assert answer == "Bestand geprüft"
    assert pending == []


def test_continue_after_tool_confirmation_auto_continues_same_tool(monkeypatch):
    tool_call = {"id": "call-1", "name": "check_engpaesse", "args": {}}
    calls = []

    def fake_get_state(config):
        return SimpleNamespace(values={
            "messages": [SimpleNamespace(content="", tool_calls=[tool_call])]
        })

    def fake_stream(input_data, config, stream_mode):
        calls.append(stream_mode)
        if len(calls) == 1:
            return iter((
                {"agent": {"messages": [SimpleNamespace(content="", tool_calls=[tool_call])]}},
            ))
        return iter((
            {"agent": {"messages": [SimpleNamespace(content="Keine Engpässe gefunden.")]}},
        ))

    monkeypatch.setattr("services.agent_runner.agent_bridge.get_state", fake_get_state)
    monkeypatch.setattr("services.agent_runner.agent_bridge.stream", fake_stream)

    answer, pending = continue_after_tool_confirmation("thread-5")

    assert answer == "Keine Engpässe gefunden."
    assert pending == []
    assert calls == ["updates", "updates"]


def test_continue_after_tool_confirmation_returns_tool_result_on_repeat(monkeypatch):
    tool_call = {"id": "call-1", "name": "check_engpaesse", "args": {}}
    captured = {}

    def fake_get_state(config):
        return SimpleNamespace(values={
            "messages": [SimpleNamespace(content="", tool_calls=[tool_call])]
        })

    def fake_stream(input_data, config, stream_mode):
        return iter((
            {"tools": {"messages": [SimpleNamespace(content="Keine Engpässe gefunden.")]}},
            {"agent": {"messages": [SimpleNamespace(content="", tool_calls=[tool_call])]}},
        ))

    def fake_update_state(config, values):
        captured["config"] = config
        captured["values"] = values

    monkeypatch.setattr("services.agent_runner.agent_bridge.get_state", fake_get_state)
    monkeypatch.setattr("services.agent_runner.agent_bridge.stream", fake_stream)
    monkeypatch.setattr("services.agent_runner.agent_bridge.update_state", fake_update_state)

    answer, pending = continue_after_tool_confirmation("thread-5")

    assert answer == "Keine Engpässe gefunden."
    assert pending == []
    assert captured["config"]["configurable"]["thread_id"] == "thread-5"
    assert captured["values"]["messages"][0].tool_call_id == "call-1"


def test_reject_pending_tool_calls_updates_graph_state(monkeypatch):
    tool_call = {"id": "call-1", "name": "check_lagerbestand", "args": {}}
    captured = {}

    def fake_get_state(config):
        return SimpleNamespace(values={
            "messages": [SimpleNamespace(content="", tool_calls=[tool_call])]
        })

    def fake_update_state(config, values):
        captured["config"] = config
        captured["values"] = values

    monkeypatch.setattr("services.agent_runner.agent_bridge.get_state", fake_get_state)
    monkeypatch.setattr("services.agent_runner.agent_bridge.update_state", fake_update_state)

    assert reject_pending_tool_calls("thread-6") == 1
    assert captured["config"]["configurable"]["thread_id"] == "thread-6"
    assert captured["values"]["messages"][0].tool_call_id == "call-1"


def test_repair_orphan_tool_calls_adds_missing_tool_messages(monkeypatch):
    tool_call = {"id": "call-1", "name": "check_lagerbestand", "args": {}}
    captured = {}

    def fake_get_state(config):
        return SimpleNamespace(values={
            "messages": [SimpleNamespace(content="", tool_calls=[tool_call])]
        })

    def fake_update_state(config, values):
        captured["config"] = config
        captured["values"] = values

    monkeypatch.setattr("services.agent_runner.agent_bridge.get_state", fake_get_state)
    monkeypatch.setattr("services.agent_runner.agent_bridge.update_state", fake_update_state)

    assert repair_orphan_tool_calls("thread-7") == 1
    assert captured["config"]["configurable"]["thread_id"] == "thread-7"
    assert captured["values"]["messages"][0].tool_call_id == "call-1"


def test_repair_orphan_tool_calls_ignores_answered_tools(monkeypatch):
    tool_call = {"id": "call-1", "name": "check_lagerbestand", "args": {}}

    def fake_get_state(config):
        return SimpleNamespace(values={
            "messages": [
                SimpleNamespace(content="", tool_calls=[tool_call]),
                SimpleNamespace(content="fertig", tool_call_id="call-1"),
            ]
        })

    monkeypatch.setattr("services.agent_runner.agent_bridge.get_state", fake_get_state)

    assert repair_orphan_tool_calls("thread-8") == 0


def test_build_agent_error_message_repairs_invalid_history(monkeypatch):
    def fake_repair(thread_id):
        return 1

    monkeypatch.setattr("services.agent_runner.repair_orphan_tool_calls", fake_repair)

    message = build_agent_error_message(
        "thread-9",
        Exception("INVALID_CHAT_HISTORY: missing ToolMessage"),
    )

    assert "Offene Aktionen wurden bereinigt" in message


def test_build_agent_error_message_handles_transient_api_error():
    message = build_agent_error_message(
        "thread-10",
        Exception("503 service unavailable"),
    )

    assert "KI-API ist gerade nicht erreichbar" in message
