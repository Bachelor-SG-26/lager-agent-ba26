# lager-agent

KI-gestütztes Lagerverwaltungssystem für Bestandsprüfung, Entnahmen,
Bestellungen und Auswertungen.

## Ziel

Die Anwendung bündelt Lagerdaten, operative Workflows und einen assistierenden
Agenten in einer lokalen Weboberfläche. Kritische Aktionen wie Bestellungen
sollen nachvollziehbar vorbereitet und vor der Ausführung bestätigt werden.

## Funktionsbereiche

- Lagerbestand und Engpaesse anzeigen
- Entnahmen erfassen
- Budget und Bestellungen auswerten
- Lieferanten vergleichen
- Agenten-Chat für Lagerfragen und Workflows
- Lokale Persistenz mit SQLite

## Technologie

| Bereich | Technologie |
|---|---|
| Oberfläche | Streamlit |
| Datenhaltung | SQLite |
| Agent | LangGraph |
| Tests | pytest |

## Lokaler Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Projektstruktur

```text
lager-agent/
  agent/
  database/
  services/
  views/
  tests/
  config.py
  streamlit_app.py
  requirements.txt
```
"# lager-agent-ba26" 
