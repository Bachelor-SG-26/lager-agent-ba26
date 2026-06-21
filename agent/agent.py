import sqlite3
from functools import lru_cache

from dotenv import load_dotenv

from agent.tools import ALL_TOOLS
from config import CHECKPOINT_DB, DATA_DIR
from services.settings import load_agent_settings

SYSTEM_PROMPT = """Du bist ein Lagerbestandsassistent für ein Industrielager.

Regeln:
- Antworte kurz und auf Deutsch.
- Nutze Tools, wenn Zahlen aus Lager, Budget, Bestellungen oder Stammdaten gebraucht werden.
- Prüfe vor Bestellungen immer Lagerbestand, Budget und Lieferantenoptionen.
- Lege keine Bestellung an, wenn Budget oder Produktdaten unklar sind.
- Erkläre operative Ergebnisse mit Produktname, Menge, Kosten und Bestand.
"""


class AgentConfigurationError(RuntimeError):
    """Meldet fehlende Agent-Konfiguration ohne die App beim Start zu blockieren."""


def _load_environment():
    """Lädt lokale Umgebungswerte aus Datenordner und Projektverzeichnis."""
    load_dotenv(DATA_DIR / ".env")
    load_dotenv()


def is_agent_configured():
    """Prüft, ob der Agent mit einem Modellschlüssel gestartet werden kann."""
    _load_environment()
    return bool(load_agent_settings().api_key)


@lru_cache(maxsize=1)
def build_agent():
    """Erzeugt den LangGraph-Agenten erst bei Bedarf."""
    _load_environment()
    settings = load_agent_settings()
    api_key = settings.api_key
    if not api_key:
        raise AgentConfigurationError("NVIDIA_API_KEY ist nicht gesetzt.")

    from langchain_nvidia_ai_endpoints import ChatNVIDIA
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.prebuilt import create_react_agent

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    checkpointer = SqliteSaver(checkpoint_conn)

    model = ChatNVIDIA(
        model=settings.model,
        api_key=api_key,
        max_completion_tokens=4096,
    )

    return create_react_agent(
        model=model,
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        name="lager_agent",
    )
