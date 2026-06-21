import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

import config


SETTINGS_FILE = ".env"
API_KEY_NAME = "NVIDIA_API_KEY"
MODEL_NAME = "NVIDIA_MODEL"


@dataclass(frozen=True)
class AgentSettings:
    """Bündelt die Laufzeitwerte für den Agenten."""

    api_key: str
    model: str


def get_settings_path():
    """Gibt den lokalen Speicherort der Agent-Einstellungen zurück."""
    return config.DATA_DIR / SETTINGS_FILE


def load_agent_settings():
    """Lädt Agent-Einstellungen aus Datei und laufender Umgebung."""
    file_values = _load_file_values()

    api_key = _value_from_environment_or_file(API_KEY_NAME, file_values, "")
    model = _value_from_environment_or_file(
        MODEL_NAME,
        file_values,
        config.DEFAULT_AGENT_MODEL,
    )

    return AgentSettings(
        api_key=(api_key or "").strip(),
        model=(model or config.DEFAULT_AGENT_MODEL).strip(),
    )


def save_agent_settings(api_key, model):
    """Speichert Agent-Einstellungen lokal und übernimmt sie für die Sitzung."""
    cleaned_api_key = (api_key or "").strip()
    cleaned_model = (model or config.DEFAULT_AGENT_MODEL).strip()

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    get_settings_path().write_text(
        "\n".join((
            _format_env_line(API_KEY_NAME, cleaned_api_key),
            _format_env_line(MODEL_NAME, cleaned_model),
        ))
        + "\n",
        encoding="utf-8",
    )

    _apply_runtime_value(API_KEY_NAME, cleaned_api_key)
    _apply_runtime_value(MODEL_NAME, cleaned_model)
    return AgentSettings(api_key=cleaned_api_key, model=cleaned_model)


def has_agent_api_key():
    """Prüft, ob ein API-Key für den Agenten hinterlegt ist."""
    return bool(load_agent_settings().api_key)


def _value_from_environment_or_file(name, file_values, default):
    """Bevorzugt gesetzte Umgebungswerte und nutzt die Datei als Rückfall."""
    if name in os.environ:
        return os.environ[name]
    return file_values.get(name) or default


def _load_file_values():
    """Kombiniert Projekt- und Datenordnerwerte für die lokale Konfiguration."""
    return {
        **dotenv_values(Path(".env")),
        **dotenv_values(get_settings_path()),
    }


def _format_env_line(name, value):
    """Formatiert einen Wert sicher für eine einfache .env-Datei."""
    escaped_value = (value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'{name}="{escaped_value}"'


def _apply_runtime_value(name, value):
    """Übernimmt gespeicherte Werte ohne Neustart in die aktuelle Sitzung."""
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)
