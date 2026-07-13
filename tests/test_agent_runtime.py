"""Tests für den verzögerten und wechselbaren Agent-Aufbau."""

import agent.agent as agent_module


def test_build_agent_verwendet_gespeichertes_modell(monkeypatch):
    """Modell und Schlüssel werden beim Agent-Aufbau aus der Umgebung gelesen."""
    captured = {}

    def fake_chat_nvidia(**kwargs):
        captured["llm"] = kwargs
        return "fake-llm"

    def fake_create_react_agent(**kwargs):
        captured["agent"] = kwargs
        return "fake-agent"

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("NVIDIA_MODEL", "anbieter/modell-a")
    monkeypatch.setattr(agent_module, "ChatNVIDIA", fake_chat_nvidia)
    monkeypatch.setattr(agent_module, "create_react_agent", fake_create_react_agent)
    agent_module.build_agent.cache_clear()

    try:
        result = agent_module.build_agent()
    finally:
        agent_module.build_agent.cache_clear()

    assert result == "fake-agent"
    assert captured["llm"]["model"] == "anbieter/modell-a"
    assert captured["llm"]["api_key"] == "nvapi-test"
    assert captured["agent"]["model"] == "fake-llm"


def test_build_agent_cache_kann_nach_modellwechsel_geleert_werden(monkeypatch):
    """Nach dem Speichern erzeugt cache_clear einen Agenten für das neue Modell."""
    modelle = []

    def fake_chat_nvidia(**kwargs):
        modelle.append(kwargs["model"])
        return object()

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("NVIDIA_MODEL", "anbieter/modell-a")
    monkeypatch.setattr(agent_module, "ChatNVIDIA", fake_chat_nvidia)
    monkeypatch.setattr(agent_module, "create_react_agent", lambda **kwargs: object())
    agent_module.build_agent.cache_clear()

    try:
        agent_module.build_agent()
        monkeypatch.setenv("NVIDIA_MODEL", "anbieter/modell-b")
        agent_module.build_agent.cache_clear()
        agent_module.build_agent()
    finally:
        agent_module.build_agent.cache_clear()

    assert modelle == ["anbieter/modell-a", "anbieter/modell-b"]
