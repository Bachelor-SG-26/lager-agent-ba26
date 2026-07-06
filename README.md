# lager-agent

KI-gestütztes Lagerverwaltungssystem für Bestandsprüfung, Entnahmen,
Bestellungen, Budgetkontrolle und Auswertungen.

## Überblick

Die Anwendung bündelt Lagerdaten, operative Workflows und einen assistierenden
Agenten in einer lokalen Streamlit-Oberfläche. Kritische Aktionen wie
Bestellungen oder Bestandsänderungen werden vom Agenten vorbereitet und vor der
Ausführung bestätigt.

## Funktionsbereiche

- Dashboard mit Lagerkennzahlen
- Lagerbestand, Engpässe und Lagerwert
- Entnahmen mit Bestandsaktualisierung
- Budgetverwaltung und Bestellanlage
- Lieferanten- und Produktstammdaten
- Auswertungen zu Verbrauch, Budget und Bestellungen
- Agenten-Chat mit Tool-Bestätigung
- Einstellungsseite für Modell und API-Key
- Aktivitätsprotokoll für operative Änderungen

## Technologie

| Bereich | Technologie |
| --- | --- |
| Oberfläche | Streamlit |
| Datenhaltung | SQLite |
| Agent | LangGraph |
| Modellanbindung | NVIDIA AI Endpoints |
| Tests | pytest |

## Lokaler Start

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Die App ist danach unter `http://localhost:8501` erreichbar.

## Agent-Konfiguration

Der Agent kann über die Seite `Einstellungen` konfiguriert werden. Alternativ
kann eine lokale `.env` im Projektverzeichnis oder im Datenordner genutzt
werden.

```env
NVIDIA_API_KEY="..."
NVIDIA_MODEL="meta/llama-3.1-70b-instruct"
```

Lokale Laufzeitdaten liegen standardmäßig im Ordner `data/` und werden nicht
versioniert.

## Start mit Docker

```powershell
docker compose up --build
```

Die Anwendung nutzt dabei ein persistentes Volume für SQLite-Daten,
Checkpoints und lokale Einstellungen.

## Projektstruktur

```text
lager-agent/
  agent/        LangGraph-Agent und Tools
  database/     SQLite-Schema, Seed-Daten und Operationen
  services/     Agent-, Chat- und Einstellungsservices
  views/        Streamlit-Seiten
  tests/        Automatisierte Tests
  docs/         Architektur- und Betriebsnotizen
```
