import pytest

from agent.agent import AgentConfigurationError, build_agent, is_agent_configured
from services.agent_runner import ask_agent


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
