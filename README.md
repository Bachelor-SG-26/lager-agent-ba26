# lager-agent

Ein Lagerverwaltungssystem mit Streamlit-Oberfläche, SQLite-Datenhaltung und einem LangGraph-basierten Agenten.
Der Agent prüft Bestände, erkennt Engpässe, vergleicht Lieferanten, erstellt Bestellungen und berechnet Prognosen. Kritische Schritte werden vor der Ausführung vom Nutzer bestätigt.

## Funktionsumfang

### KI-Agent (LangGraph ReAct)
- 16 spezialisierte Tools für Lager, Budget, Bestellung, Prognose, Lieferanten und Stammdaten
- Human-in-the-Loop mit Smart-Approve (gleicher Tool-Typ wird im Schritt automatisch fortgesetzt)
- Batch-Tools für Sammelbestellungen und Sammelprognosen
- Bestellungen können nach Lieferantenvergleich mit ausgewähltem Lieferanten angelegt werden
- Persistente Sessions via `SqliteSaver` (`checkpoints.db`)
- Schutzlimit für zu viele Tool-Calls pro Schritt
- Recovery bei unterbrochenen Agent-Läufen

### Web-Oberfläche (Streamlit)
- Agent mit Live-Streaming, Session-Verwaltung und Stop-Button
- Dashboard
- Manuelle Bearbeitung für Lager, Beschaffung, Entnahme, Budget und Stammdaten
- Geführte Evaluation mit anonymem Teilnehmerprofil, T1–T5, Reload-Wiederaufnahme, automatischer Prüfung, Hard-Reset und Abschlussbericht
- Bestellhistorie
- Analysen
- Metriken
- Auswertung
- Einstellungen (Setup erneut aufrufbar)

### Weitere Features
- Einrichtungsdialog für NVIDIA API Key und Telegram
- Docker-Setup als bevorzugter Startweg
- Telegram-Benachrichtigungen inkl. Batch-Sammelmeldung
- Strukturierte Logs in `logs/lager_agent.log`

## Projektstruktur

```text
lager-agent/
  agent/
    agent.py
    tools/
      __init__.py
      lager.py
      bestellungen.py
      budget.py
      entnahme.py
      prognose.py
      lieferanten.py
      produkte.py
      update.py
  database/
    database.py
    models.py
    seed.py
  services/
    agent_bridge.py
    logger.py
    session.py
    telegram.py
    evaluation.py
  views/
    chat/
      __init__.py
      state.py
      ui.py
      processing.py
      recovery.py
    sidebar.py
    dashboard.py
    manuell.py
    evaluation.py
    bestellhistorie.py
    analytics.py
    metriken.py
    auswertung.py
    setup.py
    styles.css
  docs/
    ARCHITEKTUR_BERICHT.md
    CHAT_MODUL.md
    diagrams/
      chat_package.mmd
      er_diagramm.mmd
      komponentendiagramm.mmd
      sequenz_chat_hitl.mmd
      sequenz_bestellung.mmd
      sequenz_state_recovery.mmd
  streamlit_app.py
  Dockerfile
  docker-compose.yml
  requirements.txt
```

## Technologie-Stack

| Komponente | Technologie |
|---|---|
| LLM | NVIDIA AI Endpoints (Modell in den Einstellungen auswählbar) |
| Agent-Framework | LangGraph |
| UI | Streamlit |
| Datenbank | SQLite |
| Logging | Python logging |
| Tests | pytest |

## Installation

### Docker (empfohlen)

```bash
git clone <repository-url>
cd lager-agent
docker compose up --build
```

Danach ist die App unter `http://localhost:8501` erreichbar.

Hinweis: Die Konfiguration erfolgt über den Setup-Dialog. Eine `.env.example` ist für den normalen Docker-Start nicht erforderlich.

### Lokal

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Beim ersten Start öffnet sich der Einrichtungsdialog. Dort werden der NVIDIA API Key, das gewünschte KI-Modell und optional Telegram-Daten gespeichert. Die Modellliste wird direkt über den hinterlegten NVIDIA-Schlüssel geladen und kann später in den Einstellungen aktualisiert werden. Die Erreichbarkeit der Auswahl lässt sich vor dem Speichern prüfen.

## Tests

```bash
python -m pytest tests/ -v
```

Die Tests nutzen eine isolierte Test-Datenbank und beeinflussen die produktive Datenbank nicht.

## Datenmodell (Kurzfassung)

Anwendungstabellen:
- `lieferanten`
- `produkte`
- `produkt_lieferanten`
- `bestellungen`
- `budget`
- `verbrauch`
- `agent_log` (inkl. `duration_ms`)
- `chat_sessions`
- `chat_nachrichten`

Siehe Details in:
- `docs/ARCHITEKTUR_BERICHT.md`
- `docs/diagrams/er_diagramm.mmd`
