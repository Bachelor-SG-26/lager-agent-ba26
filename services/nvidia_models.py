"""NVIDIA-Modellkatalog für die konfigurierbare LLM-Auswahl."""

from dataclasses import dataclass

from langchain_nvidia_ai_endpoints import ChatNVIDIA


DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"


@dataclass(frozen=True)
class NvidiaModel:
    """Beschreibt ein aktives NVIDIA-Chatmodell."""

    id: str
    supports_tools: bool


def lade_nvidia_modelle(api_key):
    """Lädt alle aktiven Chatmodelle, die für den API-Schlüssel sichtbar sind."""
    if not api_key or not api_key.strip():
        raise ValueError("Ein NVIDIA API Key ist erforderlich.")

    modelle = ChatNVIDIA.get_available_models(api_key=api_key.strip())
    aktive_modelle = {
        modell.id: NvidiaModel(
            id=modell.id,
            supports_tools=bool(modell.supports_tools),
        )
        for modell in modelle
        if modell.id and not modell.deprecated
    }
    return tuple(
        sorted(
            aktive_modelle.values(),
            key=lambda modell: (not modell.supports_tools, modell.id.casefold()),
        )
    )


def teste_nvidia_modell(api_key, model_id):
    """Prüft mit einer kurzen Anfrage, ob das ausgewählte Modell erreichbar ist."""
    if not api_key or not api_key.strip():
        raise ValueError("Ein NVIDIA API Key ist erforderlich.")
    if not model_id or not model_id.strip():
        raise ValueError("Ein KI-Modell ist erforderlich.")

    llm = ChatNVIDIA(
        model=model_id.strip(),
        api_key=api_key.strip(),
        max_completion_tokens=8,
    )
    llm.invoke("Antworte nur mit: ok")
    return True


def formatiere_modellfehler(error):
    """Übersetzt technische NVIDIA-Fehler in eine sichere UI-Meldung."""
    text = str(error).lower()
    if "401" in text or "403" in text or "not found for account" in text:
        return (
            "NVIDIA hat den Zugriff abgelehnt. Prüfe den API-Schlüssel oder "
            "erstelle unter build.nvidia.com einen neuen Schlüssel."
        )
    if "404" in text:
        return (
            "Das ausgewählte NVIDIA-Modell ist über diesen Zugang nicht erreichbar. "
            "Wähle ein anderes aktives Modell."
        )
    return "Die NVIDIA-Verbindung konnte gerade nicht geprüft werden."
