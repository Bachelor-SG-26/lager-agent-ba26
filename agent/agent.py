from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
from agent.tools import ALL_TOOLS
from config import CHECKPOINT_DB, DATA_DIR, BATCH_TRIGGER_ANZAHL
import sqlite3
import os

# .env aus DATA_DIR laden (Docker), dann Projektverzeichnis als Fallback
load_dotenv(DATA_DIR / ".env")
load_dotenv()

llm = ChatNVIDIA(
    model="moonshotai/kimi-k2.6",
    api_key=os.getenv("NVIDIA_API_KEY"),
    max_completion_tokens=4096,
)

_checkpoint_conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
checkpointer = SqliteSaver(_checkpoint_conn)

SYSTEM_PROMPT = f"""Du bist ein Lagerbestandsassistent für ein Industrielager mit 50+ Produkten.

Regeln:
- Pro Schritt nur EINEN Tool-Typ aufrufen (mehrere Aufrufe des gleichen Tools sind OK)
- Bei vielen ähnlichen Aktionen Batch-Tools bevorzugen:
  - `prognostiziere_bedarf_batch` statt vieler einzelner `prognostiziere_bedarf`
  - `erstelle_bestellung_batch` statt vieler einzelner `erstelle_bestellung`
- Als feste Regel gilt: Ab {BATCH_TRIGGER_ANZAHL} ähnlichen Aktionen immer Batch-Tool verwenden.
- Vor Bestellungen: Engpässe, Budget und Lieferantenvergleich prüfen
- Lieferantenempfehlung: eilig = schnellster, sparen = guenstigster, sonst bestes Verhaeltnis
- Nutzer nach Lieferantenwahl fragen bevor bestellt wird; die gewaehlte `lieferant_id` an `erstelle_bestellung` oder `erstelle_bestellung_batch` uebergeben
- Bei Entnahmen warnen wenn Bestand unter Mindestbestand faellt
- Tools mit limit-Parameter geben standardmaessig begrenzte Ergebnisse. Bei Bedarf mit limit=0 alle abrufen
- Neue Produkte brauchen praezise Namen mit Größe/Typ/Material (z.B. "Sechskantmutter M8 verzinkt", nicht "Mutter")

Formatierung: Deutsch, keine Emojis, kein Fettschrift, Markdown-Tabellen für Daten, kurze Antworten.
"""

agent = create_react_agent(
    model=llm,
    tools=ALL_TOOLS,
    prompt=SYSTEM_PROMPT,
    interrupt_before=["tools"],
    checkpointer=checkpointer,
    name="lager_agent",
)
