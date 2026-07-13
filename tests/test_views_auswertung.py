"""Tests für aufrufbezogene Kennzahlen der Agent-Auswertung."""

from database.database import db_connection
from views.auswertung import _lade_alle_auswertungsdaten


def test_auswertung_zaehlt_statusereignisse_nicht_doppelt():
    """Freigabe und Ausführung desselben Calls ergeben nur einen Tool-Aufruf."""
    rows = [
        ("call-1", "check_engpaesse", '{"limit": 10}', "akzeptiert", "2026-07-13 10:00:00", None),
        ("call-1", "check_engpaesse", '{"limit": 10}', "ausgefuehrt", "2026-07-13 10:00:01", 100),
        ("call-2", "check_engpaesse", '{"limit": 10}', "auto-akzeptiert", "2026-07-13 10:01:00", None),
        ("call-2", "check_engpaesse", '{"limit": 10}', "fehlgeschlagen", "2026-07-13 10:01:01", 90),
        ("call-3", "erstelle_bestellung", '{"produkt_id": 1}', "abgelehnt", "2026-07-13 10:02:00", None),
    ]
    with db_connection(commit=True) as (conn, cursor):
        cursor.executemany(
            """
            INSERT INTO agent_log
                (tool_call_id, tool_name, tool_args, status, datum, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    log_daten, status_counts, tool_ranking, timeline = _lade_alle_auswertungsdaten()

    assert len(log_daten) == 5
    assert status_counts == {
        "abgelehnt": 1,
        "akzeptiert": 1,
        "auto-akzeptiert": 1,
    }
    assert tool_ranking == [("check_engpaesse", 2), ("erstelle_bestellung", 1)]
    assert timeline == [("2026-07-13", 3)]
