"""NVIDIA-Modellkatalog für die konfigurierbare LLM-Auswahl."""

from dataclasses import dataclass
from time import perf_counter

import requests
from langchain_nvidia_ai_endpoints import ChatNVIDIA


DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"
NVIDIA_CHAT_COMPLETIONS_URL = (
    "https://integrate.api.nvidia.com/v1/chat/completions"
)
MODELLTEST_TIMEOUT_SEKUNDEN = 20


@dataclass(frozen=True)
class NvidiaModel:
    """Beschreibt ein aktives NVIDIA-Chatmodell."""

    id: str
    supports_tools: bool


@dataclass(frozen=True)
class NvidiaModelTest:
    """Enthält Messwert und Empfehlung eines Modelltests."""

    dauer_sekunden: float
    bewertung: str
    empfohlen: bool
    begruendung: str


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


def bewerte_nvidia_modell(dauer_sekunden, supports_tools=None):
    """Bewertet Antwortzeit und gemeldete Tool-Unterstützung gemeinsam."""
    if dauer_sekunden < 0:
        raise ValueError("Die gemessene Dauer darf nicht negativ sein.")

    if supports_tools is False:
        return NvidiaModelTest(
            dauer_sekunden=dauer_sekunden,
            bewertung="Nicht empfohlen",
            empfohlen=False,
            begruendung=(
                "Das Modell meldet keine bestätigte Tool-Unterstützung, die für "
                "die Lagerfunktionen erforderlich ist."
            ),
        )
    if dauer_sekunden > 15:
        return NvidiaModelTest(
            dauer_sekunden=dauer_sekunden,
            bewertung="Nicht empfohlen",
            empfohlen=False,
            begruendung=(
                "Bereits die kurze Prüfanfrage war für eine flüssige Bedienung "
                "zu langsam."
            ),
        )
    if supports_tools is None:
        return NvidiaModelTest(
            dauer_sekunden=dauer_sekunden,
            bewertung="Bedingt geeignet",
            empfohlen=False,
            begruendung=(
                "Die Antwortzeit ist ausreichend, die Tool-Unterstützung konnte "
                "aber nicht bestätigt werden."
            ),
        )
    if dauer_sekunden <= 6:
        return NvidiaModelTest(
            dauer_sekunden=dauer_sekunden,
            bewertung="Empfohlen",
            empfohlen=True,
            begruendung="Schnelle Antwort und bestätigte Tool-Unterstützung.",
        )
    return NvidiaModelTest(
        dauer_sekunden=dauer_sekunden,
        bewertung="Bedingt geeignet",
        empfohlen=False,
        begruendung=(
            "Die Tool-Unterstützung ist bestätigt, die Antwortzeit kann bei "
            "umfangreicheren Aufgaben jedoch spürbar sein."
        ),
    )


def teste_nvidia_modell(api_key, model_id, supports_tools=None):
    """Misst eine kurze Modellantwort und leitet daraus eine Empfehlung ab."""
    if not api_key or not api_key.strip():
        raise ValueError("Ein NVIDIA API Key ist erforderlich.")
    if not model_id or not model_id.strip():
        raise ValueError("Ein KI-Modell ist erforderlich.")

    start = perf_counter()
    response = requests.post(
        NVIDIA_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Accept": "application/json",
        },
        json={
            "model": model_id.strip(),
            "messages": [
                {"role": "user", "content": "Antworte nur mit: ok"},
            ],
            "max_tokens": 8,
            "temperature": 0,
            "stream": False,
        },
        timeout=(5, MODELLTEST_TIMEOUT_SEKUNDEN),
    )
    response.raise_for_status()
    inhalt = response.json()
    if not inhalt.get("choices"):
        raise ValueError("Die Modellantwort enthält keine Ausgabe.")

    dauer_sekunden = perf_counter() - start
    return bewerte_nvidia_modell(dauer_sekunden, supports_tools)


def formatiere_modellfehler(error):
    """Übersetzt technische NVIDIA-Fehler in eine sichere UI-Meldung."""
    text = str(error).lower()
    if isinstance(error, requests.Timeout) or "timed out" in text:
        return (
            f"Das Modell hat nicht innerhalb von {MODELLTEST_TIMEOUT_SEKUNDEN} "
            "Sekunden geantwortet und wird daher nicht empfohlen."
        )
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
