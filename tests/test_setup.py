"""Tests für die persistierte Anwendungs- und Modellkonfiguration."""

from pathlib import Path

from views import setup


def test_env_speichert_und_laed_modellauswahl(monkeypatch):
    """API-Schlüssel, Modell und optionale Werte bleiben gemeinsam erhalten."""
    env_verzeichnis = Path("data") / "test_setup_config"
    env_path = env_verzeichnis / ".env"
    if env_path.exists():
        env_path.unlink()
    if env_verzeichnis.exists():
        env_verzeichnis.rmdir()
    monkeypatch.setattr(setup, "ENV_PATH", env_path)
    werte = {
        "NVIDIA_API_KEY": "nvapi-test",
        "NVIDIA_MODEL": "anbieter/modell-a",
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_CHAT_ID": "123",
    }

    try:
        setup._speichere_env(werte)
        assert env_verzeichnis.is_dir()
        assert setup._lade_env_werte() == werte
    finally:
        if env_path.exists():
            env_path.unlink()
        if env_verzeichnis.exists():
            env_verzeichnis.rmdir()
