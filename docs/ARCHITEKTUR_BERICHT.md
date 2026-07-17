# Lager-Agent Architekturbericht

## 1. Überblick

Der Lager-Agent ist eine Streamlit-Anwendung mit LangGraph-basiertem ReAct-Agent.

Kernideen:
- Human-in-the-Loop vor Tool-Ausführungen (`interrupt_before=["tools"]`)
- Persistente Agent-States (`checkpoints.db`) und Chat-Sessions (`lager.db`)
- Robuster Chat-Flow mit Recovery, Stop-Funktion und Fehlerbehandlung
- Batch-Tools für viele gleichartige Aktionen

## 2. Laufzeit-Architektur

Schichten:
1. Präsentation: `streamlit_app.py`, `views/*.py`, `views/styles.css`
2. Agent: `agent/agent.py`, `agent/tools/*.py`
3. Services: `services/session.py`, `services/telegram.py`, `services/logger.py`
4. Datenhaltung: `database/*.py`, `lager.db`, `checkpoints.db`

Externe Systeme:
- NVIDIA AI Endpoints (LLM)
- Telegram Bot API (optional)

## 3. Einstieg und Routing

Einstiegspunkt: `streamlit_app.py`

Startreihenfolge:
1. Globale CSS laden aus `views/styles.css`
2. Setup prüfen (`ist_konfiguriert()`)
3. DB initialisieren (`init_db()`)
4. Session State vorbereiten
5. Sidebar rendern (Sitzungen + Navigation)
6. Seitenrouting

Aktuelle Seiten:
- Agent
- Manuelle Bearbeitung
- Evaluation
- Dashboard
- Bestellhistorie
- Analysen
- Metriken
- Auswertung
- Einstellungen

Die Evaluationsseite führt anonymisierte Teilnehmer nach einem verpflichtenden
Kontextfragebogen durch zwei gegenbalancierte Durchläufe. Aufgabenbezogene
Lagerdaten werden kontrolliert vorbereitet und nach Abschluss zurückgesetzt.
Teilnehmer-, Aufgaben- und Ereignisdaten bleiben in separaten Evaluationstabellen
erhalten. Laufende Aufgaben werden über Teilnehmer- und Aufgabenparameter nach
einem Browser-Reload wiederhergestellt. Der Teilnehmer kann die Aufgabe fortsetzen
oder mit neuem Timer, neuen Fachdaten und bei Agenten-Aufgaben mit einer leeren
Chatsitzung wiederholen. Ein bestätigungspflichtiger Hard-Reset löscht ausschließlich
den gewählten Teilnehmerlauf einschließlich Aufgaben-Chats und stellt die Fachdaten
wieder her. Nach dem vollständigen Abschluss steht ein formatierter HTML-Bericht
mit Teilnehmerprofil, Zeiten, tatsächlichen Ausführungen, Kriterien, Ergebnissen
und Feedback zum Download bereit.

## 4. Datenbank und Persistenz

Primäre DB: `lager.db`

Checkpoint-DB: `checkpoints.db`

Tabellen:
- `lieferanten`
- `produkte`
- `produkt_lieferanten`
- `bestellungen`
- `budget`
- `verbrauch`
- `agent_log` (`tool_name`, `tool_args`, `status`, `datum`, `duration_ms`)
- `chat_sessions`
- `chat_nachrichten`

`database/database.py`:
- `get_connection()` für einfache Abfragen
- `db_connection` Context-Manager für Commit/Rollback
- `init_db()` inkl. kleiner Migration (`agent_log.duration_ms`)

## 5. Agent und Tools

`agent/agent.py`:
- Modell: über `NVIDIA_MODEL` konfigurierbar, aktiver Standard `meta/llama-3.1-70b-instruct`
- Aktive Modelle werden über den NVIDIA API Key geladen und in den Einstellungen ausgewählt.
- Der Agent wird verzögert aufgebaut; nach einem Modellwechsel wird sein Cache geleert.
- Prompt-Regeln für Batch-Nutzung, Lieferantenvergleich, Budgetprüfung und Format
- HITL via `interrupt_before=["tools"]`

Tool-Registry: `agent/tools/__init__.py` (17 Tools)
- Lager: `check_lagerbestand`, `check_engpaesse`
- Budget: `check_budget`, `erstelle_budget`
- Bestellung: `erstelle_bestellung`, `erstelle_bestellung_batch`, `check_bestellhistorie`
- `erstelle_bestellung` und `erstelle_bestellung_batch` können optional eine `lieferant_id` verwenden; ohne Angabe wird der Standardlieferant genutzt.
- Entnahme: `erfasse_entnahme`
- Prognose: `prognostiziere_bedarf`, `prognostiziere_bedarf_batch`
- Lieferanten: `check_lieferanten`, `vergleiche_lieferanten`, `vergleiche_lieferanten_batch`, `erstelle_lieferant`
- Produkte/Lieferanten Update: `erstelle_produkt`, `aktualisiere_produkt`, `aktualisiere_lieferant`

## 6. Chat-Flow (views/chat/ Package)

Der Chat ist in ein Package mit fünf Submodulen aufgeteilt:

- `__init__.py` - `show_chat()`, Orchestrierung, Seitenwechsel-Reload, Stop-Button
- `state.py` - Session-State-Helfer, `cancel_pending_tools()`, `status_aus_tool_result()`, Logging
- `ui.py` - Rendering: `render_message`, `render_chat_history`, `render_confirmation`, `render_empty_state`, Tool-Pills
- `processing.py` - Streaming, Tool-Ausführung, Smart-Approve
- `recovery.py` - Fehlerhaertung, Orphan-Tool-Call-Reparatur, API-Fehler-Behandlung

Die externe API bleibt stabil: `from views.chat import show_chat`.

Ausführliche Detail-Dokumentation mit Package-Diagramm, State-Maschine,
Stop-Flow, Recovery und API-Fehler-Mapping:
**[docs/CHAT_MODUL.md](CHAT_MODUL.md)** (Diagramm: `docs/diagrams/chat_package.mmd`).

Der folgende Abschnitt fasst die wichtigsten Punkte zusammen.

Wichtige Teile:
- `pending_input` Muster: Eingabe erfassen und im nächsten Rerun verarbeiten
- `warte_auf_bestaetigung` + `pending_tool_calls` für HITL
- Smart-Approve für Folgecalls gleichen Tool-Typs
- `MAX_TOOL_CALLS_PRO_SCHRITT` Schutzlimit
- Tool-Ausführungslogging in `agent_log` inkl. `duration_ms`

### Rendering-Reihenfolge (wichtig)

`st.chat_input` und der Stop-Button werden in `show_chat()` bewusst **vor**
`execute_recovery()` und den Verarbeitungs-Branches gerendert. Dadurch bleiben
Input-Feld und Stop-Button sichtbar, auch wenn anschliessende Operationen
(z. B. NVIDIA-API-Aufrufe) laenger blockieren. Der Stop-Button liegt per CSS
an einer fixen Position (unten rechts).

### Stop-Verhalten

Beim Stop:
- `stop_requested` wird gesetzt
- laufender Flow prüft `stop_requested` in Streaming-Schleifen
- offene Bestatigungen werden mit `state.cancel_pending_tools(...)` sauber abgebrochen
- State wird konsistent zurückgesetzt

### Recovery/Fehlerhaertung (views/chat/recovery.py)

Recovery-Funktionen:
- `detect_pending_recovery()`
- `execute_recovery(container)` - nutzt zentralen `handle_agent_error()` Helper

Spezialfall Orphan-Tool-Calls:
- `ist_invalid_chat_history(msg)` erkennt `INVALID_CHAT_HISTORY` (fehlende ToolMessage)
- `repair_orphan_tool_calls()` ergänzt fehlende ToolMessages

API-Fehler:
- `ist_api_fehler(msg)` erkennt 429 (Rate-Limit) sowie 502/503/504 (Gateway-Fehler/Timeout)
- `handle_agent_error(e)` mapped Fehler auf nutzerfreundliche Meldungen
  ("Die KI-API ist gerade nicht erreichbar ...") und setzt den State sauber zurück

### Seitenwechsel-Reload

Beim Wechsel von einer anderen Seite zurück zu "Chat" wird ein Browser-Reload
ausgelöst (`window.parent.location.reload()`), um hartnäckige Layout- und
Socket-Zustände zuverlässig zurücksetzen. Eine Guard über `_letzte_seite`
verhindert Reload-Schleifen.

## 7. Telemetrie, Metriken, Auswertung

`agent_log` Statuswerte:
- `akzeptiert`
- `auto-akzeptiert`
- `abgelehnt`
- `ausgefuehrt`
- `fehlgeschlagen`
- `abgelehnt_budget`

Seiten:
- `views/metriken.py`: KPI-Sicht (Erfolgsquoten, Budget-Blockrate, Batch-Quote, Durchschnitt und P95 Dauer)
- `views/auswertung.py`: Verlauf/Ranking/Log-Detail für Agent-Nutzung

## 8. Telegram und Nebenlaeufigkeit

`agent/tools/bestellungen.py`:
- `_bestell_lock` gegen Bestellnummer-Race-Conditions
- Telegram-Batching über Timer (3 Sekunden Fenster)

`services/telegram.py`:
- lädt `.env` vor jedem Versand neu
- loggt API-Fehlerantworten bei Nicht-200

## 9. Konfiguration

`config.py` enthält:
- DB-Pfade (`DATA_DIR`, `DB_NAME`, `CHECKPOINT_DB`)
- Budget-Schwellen
- Prognoseparameter
- Lieferantengewichte
- Analyse-Limits
- Tool-Limits (`MAX_TOOL_CALLS_PRO_SCHRITT`)
- Batch-Konfiguration (`BATCH_DEFAULT_MAX_POSITIONEN`, `BATCH_TRIGGER_ANZAHL`)

## 10. Teststatus und Risiken

Tests decken Tools, Integrationen und Session-Persistenz gut ab.

Ergänzt wurde gezielte Resilience-Abdeckung für Chat-Hilfslogik:
- Invalid-Chat-History-Erkennung
- Tool-Result-Status-Mapping
- Recovery fehlender ToolMessages

Weiterhin sinnvoll für Zukunft:
- End-to-End UI-Tests für den kompletten Stop/Resume-Flow in Streamlit
- Lasttests für sehr große Tool-Call-Ketten

