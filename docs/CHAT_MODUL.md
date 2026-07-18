# Chat-Modul (views/chat/)

Detail-Dokumentation für das Chat-Package. Ergänzt Abschnitt 6 des
Architekturberichts (`docs/ARCHITEKTUR_BERICHT.md`).

## 1. Zweck und Umfang

Das Chat-Modul ist die zentrale Interaktionsfläche zwischen Benutzer und
ReAct-Agent. Neben reinem Rendering übernimmt es:

- Human-in-the-Loop-Bestätigung vor Tool-Ausführungen
- Streaming-Darstellung der Agent-Antwort
- Stop-Funktion während laufender Agent-Operationen
- Recovery nach Browser-Reload, Seitenwechsel oder API-Fehlern
- Reparatur von INVALID_CHAT_HISTORY-Zuständen (Orphan Tool-Calls)
- Einheitliches Mapping transienter API-Fehler (429/500/502/503/504)

Für Testbarkeit und Lesbarkeit ist der Chat in ein Package mit fünf Submodulen
aufgeteilt. Die externe API bleibt stabil: `from views.chat import show_chat`.

## 2. Package-Struktur

Siehe Diagramm: `docs/diagrams/chat_package.mmd`.

| Modul            | Verantwortung                                                        |
|------------------|----------------------------------------------------------------------|
| `__init__.py`    | `show_chat()`, Render-Reihenfolge, Seitenwechsel-Reload, Stop-Button |
| `state.py`       | Session-State-Helfer, Logging in `agent_log`, Cancel-Pfade           |
| `ui.py`          | Reine Rendering-Funktionen, keine Seiteneffekte auf Agent/DB         |
| `processing.py`  | Agent-Streaming, Tool-Ausführung, Smart-Approve                     |
| `recovery.py`    | Recovery-Erkennung, Orphan-Repair, zentrale Fehlerbehandlung         |

Regel: `ui.py` darf weder den Agenten noch die DB direkt ansprechen; es liest
nur aus `st.session_state` und ruft `state.py`-Helfer auf.

Alle Agent-Aufrufe laufen über `services/agent_bridge.py`, einen dünnen
Wrapper um `agent.agent.build_agent()`. Dadurch hängen die Chat-Module nicht
direkt an der LangGraph-API und lassen sich in Tests einfach stubben.

## 3. Rendering-Reihenfolge (wichtig)

`show_chat()` rendert Eingabefeld und Stop-Button **vor** `execute_recovery()`
und den Verarbeitungs-Branches. Hintergrund:

- NVIDIA-Endpoints können bei Fehlern minutenlang blockieren (502 nach 219s,
  504 nach 302s im Betrieb beobachtet).
- Wenn `st.chat_input` erst nach der langsamen Operation gerendert würde,
  wäre das Feld währenddessen unsichtbar und der Nutzer hätte keinen
  Stop-Knopf.

Daher:

```
show_chat()
  1. Seitenwechsel-Reload-Check
  2. Recovery-Detection (billig, kein Netz)
  3. Eingabefeld + Stop-Button RENDERN
  4. Chat-History RENDERN
  5. execute_recovery()   <-- darf blockieren
  6. State-basierte Branches (process_approval / confirmation / pending_input / user_input)
```

## 4. State-Maschine

Relevanter Session-State:

| Key                      | Zweck                                                  |
|--------------------------|--------------------------------------------------------|
| `messages`               | Sichtbare Chat-Nachrichten (persistiert über `services/session.py`) |
| `pending_input`          | Vom Nutzer gesendeter Text, der im nächsten Rerun verarbeitet wird |
| `warte_auf_bestaetigung` | Es liegen geplante Tool-Calls zur HITL-Freigabe vor    |
| `pending_tool_calls`     | Die konkret geplanten Calls (Name + Args)              |
| `tool_approved`          | Nutzer hat Ausführen/Abbrechen geklickt (True/False)  |
| `agent_arbeitet`         | Ein Streaming-Lauf ist aktiv                           |
| `stop_requested`         | Stop wurde angefordert                                 |

Branch-Logik in `show_chat()`:

```
if "tool_approved" in state:         -> process_approval(...)
elif warte_auf_bestaetigung:         -> render_confirmation(...)
elif "pending_input" in state:       -> Agent starten mit pending_input
elif user_input (neues chat_input):  -> pending_input setzen, rerun
```

## 5. Stop-Flow

1. Klick auf Stop setzt `stop_requested = True`
2. Laufender Streaming-Loop prüft `stop_requested` in jeder Iteration
3. Offene Bestätigungen werden mit `state.cancel_pending_tools(reason, user_msg)`
   abgebrochen; das legt eine Protokollzeile in `agent_log` an
   (Status `abgelehnt`) und schreibt eine Agent-Nachricht in den Verlauf
4. State wird konsistent zurückgesetzt: `warte_auf_bestaetigung = False`,
   `pending_tool_calls = []`, `agent_arbeitet = False`

Der Stop-Button ist per CSS an fixer Position (unten rechts) platziert,
damit er während des gesamten Agent-Laufs klickbar bleibt, unabhängig
von Scroll-Position und Container-Layout.

## 6. Recovery

Drei Auslöser:

- **Browser-Reload** während laufendem Stream
- **Seitenwechsel** (Chat -> Dashboard -> Chat): löst kompletten Browser-Reload
  aus (`window.parent.location.reload()`), mit Guard über `_letzte_seite`
  gegen Schleifen
- **Neue Session** mit offenem Checkpoint in `checkpoints.db`

`recovery.detect_pending_recovery()` prüft via `agent.get_state(config)`
auf offenen LangGraph-State. Fallunterscheidung:

- State `next` enthält Tool-Calls -> `warte_auf_bestaetigung` setzen,
  `render_confirmation()` zeigt sie erneut
- State ohne Tool-Calls -> `recovery.execute_recovery()` läuft mit
  `invoke(None)` weiter oder liest das letzte Ergebnis aus
- Kein verarbeitbarer State -> `state.reset_state()`

Beendet ein Modell einen Schritt ohne Text und ohne Tool-Aufruf, fordert
`processing.py` einmalig eine Fortsetzung anhand des vorhandenen Verlaufs an.
Neue schreibende Tool-Aufrufe durchlaufen weiterhin die normale Bestätigung.
Bleibt auch die Fortsetzung leer, wird ein verständlicher Hinweis zum erneuten
Versuch oder Modellwechsel angezeigt.

## 7. Orphan-Tool-Call-Reparatur

Wenn die Nachrichten-Historie einen `AIMessage` mit `tool_calls` enthält,
aber die zugehörige `ToolMessage` fehlt (z. B. durch Abbruch mitten im
Tool-Lauf), liefert der LLM-Endpoint `INVALID_CHAT_HISTORY`.

`recovery.ist_invalid_chat_history(msg)` erkennt diesen Zustand,
`recovery.repair_orphan_tool_calls()` füllt fehlende ToolMessages mit
einem neutralen Abbruch-Text auf. Der Nutzer bekommt den Hinweis
"bitte Anfrage erneut senden".

## 8. API-Fehler-Mapping

Zentraler Helper: `recovery.handle_agent_error(exception) -> bool`

- `recovery.ist_api_fehler(msg)` erkennt `429`, `500`, `502`, `503`, `504`
  (plus Klartextvarianten "too many requests", "bad gateway",
  "service unavailable", "gateway timeout")
- Gemappte Nutzer-Meldung: "Die KI-API ist gerade nicht erreichbar
  (Rate-Limit oder Serverfehler). Bitte warte einen Moment und versuche es erneut."
- Rückgabewert `True` signalisiert dem Aufrufer, dass der Fehler
  behandelt wurde; State wird sauber zurückgesetzt

Verwendet an zwei Stellen:

- `processing.py` im Streaming-Try/Except
- `recovery.execute_recovery()` ebenfalls im Except-Zweig

## 9. Logging in agent_log

`state.py` loggt über `services/logger.py` jeden Tool-Call mit:

- `tool_name`
- `tool_args` (JSON-serialisiert)
- `status` - einer von `akzeptiert`, `auto-akzeptiert`, `abgelehnt`,
  `ausgefuehrt`, `fehlgeschlagen`, `abgelehnt_budget`
- `datum`
- `duration_ms` - erst beim Übergang `akzeptiert` -> `ausgeführt` befüllt

Die Metriken- und Auswertungsseiten lesen ausschließlich diese Tabelle.

## 10. Abgrenzungen

Nicht im Chat-Modul:

- Agent-Definition, Tool-Implementierungen: `agent/`
- Datenbank-Zugriff für Tools: `agent/tools/*`
- Chat-Historien-Persistenz über Sessions hinweg: `services/session.py`
- KPI-/Auswertungsrendering: `views/metriken.py`, `views/auswertung.py`

## 11. Testabdeckung

`tests/test_views_chat_resilience.py` und `tests/test_views_chat_processing.py`
decken die reinen Helfer ab:

- `recovery.ist_invalid_chat_history`
- `recovery.ist_api_fehler`
- `state.status_aus_tool_result`
- `recovery.repair_orphan_tool_calls` (mit gemocktem Agent)
- Erkennung und einmalige Fortsetzung leerer Modellantworten

UI-Flows (Stop mitten im Stream, Reload-Recovery) sind aktuell manuell
getestet; ein E2E-Harness mit `streamlit.testing` ist möglich, aber nicht
Teil des aktuellen Umfangs.
