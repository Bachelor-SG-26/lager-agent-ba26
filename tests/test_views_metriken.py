"""Tests für die zeitbezogene Datenbasis der Metrikansicht."""

from datetime import datetime, timedelta

from database.database import db_connection
from views.metriken import _lade_bestellungen, _lade_tool_status


def test_metriken_filtern_iso_zeitstempel_nach_zeitraum():
    """Nur ausführungsbezogene Einträge der letzten 30 Tage werden geladen."""
    aktuell = datetime.now().isoformat(timespec="seconds")
    alt = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
    with db_connection(commit=True) as (conn, cursor):
        cursor.executemany(
            """
            INSERT INTO agent_log
                (tool_call_id, tool_name, status, datum, duration_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ("aktuell", "check_budget", "ausgefuehrt", aktuell, 12),
                ("alt", "check_budget", "ausgefuehrt", alt, 15),
                ("akzeptiert", "check_budget", "akzeptiert", aktuell, None),
            ),
        )

    daten = _lade_tool_status(30)

    assert daten["tool_call_id"].tolist() == ["aktuell"]


def test_bestellmetrik_filtert_iso_zeitstempel_nach_zeitraum():
    """Das Bestellvolumen berücksichtigt keine Bestellungen außerhalb des Zeitraums."""
    aktuell = datetime.now().isoformat(timespec="seconds")
    alt = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
    with db_connection(commit=True) as (conn, cursor):
        cursor.execute("UPDATE bestellungen SET datum = ?", (alt,))
        cursor.executemany(
            """
            INSERT INTO bestellungen
                (bestell_nr, produkt_id, lieferant_id, menge, gesamtkosten, datum)
            VALUES (?, 1, 1, 1, ?, ?)
            """,
            (
                ("METRIK-AKTUELL", 10.0, aktuell),
                ("METRIK-ALT", 20.0, alt),
            ),
        )

    daten = _lade_bestellungen(30)

    assert daten["gesamtkosten"].tolist() == [10.0]
