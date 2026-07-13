"""Tests für eindeutiges Logging wiederholter Tool-Aufrufe."""

import sqlite3

from database.database import _migrate_agent_log, db_connection
from views.chat.state import log_tool_calls


def test_migration_ergaenzt_tool_call_id_in_altbestand():
    """Bestehende agent_log Tabellen erhalten die neue Aufruf-ID ohne Datenverlust."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE agent_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT NOT NULL,
            tool_args TEXT,
            status TEXT NOT NULL,
            datum TEXT NOT NULL,
            duration_ms INTEGER
        )
        """
    )

    _migrate_agent_log(cursor)
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(agent_log)")}
    conn.close()

    assert "tool_call_id" in columns


def test_identische_tool_aufrufe_werden_getrennt_protokolliert():
    """Gleicher Tool-Name und gleiche Argumente bleiben über ihre IDs unterscheidbar."""
    erster_call = {
        "id": "call-1",
        "name": "check_engpaesse",
        "args": {"limit": 10},
    }
    zweiter_call = {
        "id": "call-2",
        "name": "check_engpaesse",
        "args": {"limit": 10},
    }

    log_tool_calls([erster_call], "akzeptiert")
    log_tool_calls([erster_call], "ausgefuehrt", {"call-1": 120})
    log_tool_calls([zweiter_call], "auto-akzeptiert")
    log_tool_calls([zweiter_call], "ausgefuehrt", {"call-2": 95})

    with db_connection() as (conn, cursor):
        cursor.execute(
            """
            SELECT tool_call_id, status, duration_ms
            FROM agent_log
            WHERE tool_name = 'check_engpaesse'
            ORDER BY id
            """
        )
        rows = cursor.fetchall()

    assert rows == [
        ("call-1", "akzeptiert", None),
        ("call-1", "ausgefuehrt", 120),
        ("call-2", "auto-akzeptiert", None),
        ("call-2", "ausgefuehrt", 95),
    ]
