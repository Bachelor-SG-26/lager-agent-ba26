from types import SimpleNamespace

import pytest

from agent.agent import AgentConfigurationError, build_agent, is_agent_configured
from services.agent_runner import ask_agent, check_agent_readiness, stream_agent_response


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
