# Architektur

## Überblick

`lager-agent` ist eine lokale Streamlit-Anwendung mit SQLite-Datenhaltung und
einem LangGraph-Agenten für lagerbezogene Fragen und operative Abläufe.

Die App ist in vier Schichten gegliedert:

1. `views/` rendert die Streamlit-Seiten.
2. `services/` kapselt Chat-, Agent- und Einstellungslogik.
3. `database/` stellt Schema, Seed-Daten, Abfragen und Geschäftsoperationen.
4. `agent/` bündelt Systemprompt, LangGraph-Aufbau und Tool-Registry.

## Datenhaltung

Die Hauptdatenbank liegt standardmäßig unter `data/lager.db`. Der Agent nutzt
zusätzlich `data/checkpoints.db`, damit Chat- und Tool-Zustände zwischen
Interaktionen erhalten bleiben.

Wichtige Tabellen:

- `produkte`
- `lieferanten`
- `produkt_lieferanten`
- `verbrauch`
- `bestellungen`
- `budget`
- `aktivitaeten`
- `chat_sessions`
- `chat_nachrichten`

## Agent-Flow

Der Agent wird erst bei Bedarf geladen. Dadurch kann die Anwendung auch ohne
API-Key starten und Einstellungen später über die Oberfläche übernehmen.

Der LangGraph-Agent arbeitet mit `interrupt_before=["tools"]`. Dadurch werden
geplante Aktionen zuerst in der Oberfläche angezeigt. Nach Bestätigung führt
der Agent die Aktion aus und schreibt das Ergebnis zurück in den Chat.

## Fehlerbehandlung

Bekannte API-Probleme werden als verständliche Chat-Meldung angezeigt. Bleibt
ein Tool-Aufruf durch einen unterbrochenen Lauf offen, ergänzt die Laufzeit eine
neutrale Tool-Nachricht und macht die Unterhaltung wieder nutzbar.

## Betrieb

Für lokale Entwicklung genügt:

```powershell
streamlit run streamlit_app.py
```

Für Container-Betrieb ist `docker compose up --build` vorgesehen. Laufzeitdaten
liegen dann im Volume `app-data`.
