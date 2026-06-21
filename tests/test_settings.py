import os
from pathlib import Path

import pytest

import config
from services.settings import load_agent_settings, save_agent_settings


@pytest.fixture
def local_settings_dir(monkeypatch):
    settings_dir = Path("test_agent_settings")
    _clean_settings_dir(settings_dir)
    settings_dir.mkdir()

    monkeypatch.setattr(config, "DATA_DIR", settings_dir)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)

    yield settings_dir

    _clean_settings_dir(settings_dir)


def test_load_agent_settings_uses_default_model(local_settings_dir):
    settings = load_agent_settings()

    assert settings.api_key == ""
    assert settings.model == config.DEFAULT_AGENT_MODEL


def test_save_agent_settings_writes_file_and_runtime_values(local_settings_dir):
    settings = save_agent_settings("test-key", "test-model")
    settings_file = local_settings_dir / ".env"

    assert settings.api_key == "test-key"
    assert settings.model == "test-model"
    assert "NVIDIA_API_KEY=\"test-key\"" in settings_file.read_text(encoding="utf-8")
    assert os.environ["NVIDIA_API_KEY"] == "test-key"
    assert os.environ["NVIDIA_MODEL"] == "test-model"


def test_environment_values_have_priority(local_settings_dir, monkeypatch):
    save_agent_settings("file-key", "file-model")
    monkeypatch.setenv("NVIDIA_API_KEY", "env-key")
    monkeypatch.setenv("NVIDIA_MODEL", "env-model")

    settings = load_agent_settings()

    assert settings.api_key == "env-key"
    assert settings.model == "env-model"


def _clean_settings_dir(settings_dir):
    settings_file = settings_dir / ".env"
    if settings_file.exists():
        settings_file.unlink()
    if settings_dir.exists():
        settings_dir.rmdir()
