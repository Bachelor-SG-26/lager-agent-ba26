# ─────────────────────────────────────────
#  Zentrale Konfiguration
# ─────────────────────────────────────────

import os
from pathlib import Path

# Daten-Verzeichnis (für Docker-Volume oder lokale Nutzung)
DATA_DIR = Path(os.getenv("DATA_DIR", "."))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Datenbank
DB_NAME = str(DATA_DIR / "lager.db")
CHECKPOINT_DB = str(DATA_DIR / "checkpoints.db")

# Budget-Schwellwerte (Prozent des Gesamtbudgets)
BUDGET_WARNUNG_PROZENT = 70
BUDGET_KRITISCH_PROZENT = 90

# Prognose
PROGNOSE_HISTORIE_TAGE = 90
PROGNOSE_DEFAULT_TAGE_VORAUS = 30
PROGNOSE_KRITISCH_TAGE = 14
PROGNOSE_WARNUNG_TAGE = 30

# Lieferanten-Bewertung (Gewichtung, Summe = 1.0)
LIEFERANT_GEWICHT_PREIS = 0.4
LIEFERANT_GEWICHT_LIEFERZEIT = 0.3
LIEFERANT_GEWICHT_BEWERTUNG = 0.3

# Analysen
ANALYTICS_ZEITRAUM_TAGE = 90
ANALYTICS_TOP_PRODUKTE_LIMIT = 10

# Tool-Limits (schuetzt den LLM-Kontext vor zu großen Antworten)
LAGERBESTAND_DEFAULT_LIMIT = 20
ENGPASS_DEFAULT_LIMIT = 20
BESTELLHISTORIE_DEFAULT_LIMIT = 60
MAX_TOOL_CALLS_PRO_SCHRITT = 20

# Batch-Tools
BATCH_DEFAULT_MAX_POSITIONEN = 25
BATCH_TRIGGER_ANZAHL = 8

# Seed-Daten
SEED_BUDGET_BETRAG = 5000.00
SEED_VORQUARTAL_VERBRAUCHT = 3200.00
