import sqlite3
import os
from database.models import create_tables
from database.seed import seed_data
from config import DB_NAME
from services.logger import get_logger

logger = get_logger("database")


def get_connection():
    """Gibt eine Verbindung zur Datenbank zurück."""
    return sqlite3.connect(DB_NAME)


class db_connection:
    """Context-Manager für sichere Datenbankverbindungen mit automatischem Commit/Rollback."""

    def __init__(self, commit=False):
        self.commit = commit
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(DB_NAME)
        return self.conn, self.conn.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None and self.commit:
                self.conn.commit()
            elif exc_type is not None:
                self.conn.rollback()
                logger.error("DB-Fehler (Rollback): %s: %s", exc_type.__name__, exc_val)
            self.conn.close()
        return False


def init_db():
    """Initialisiert die Datenbank. Migriert automatisch bei Schema-Änderungen."""
    logger.info("Datenbank-Initialisierung gestartet (%s)", DB_NAME)
    conn = get_connection()
    cursor = conn.cursor()

    # Auto-Migration: altes Schema erkennen und neu aufbauen
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lieferanten'")
    if not cursor.fetchone():
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall() if t[0] != "sqlite_sequence"]
        if tables:
            logger.warning("Schema-Migration: Lösche alte Tabellen %s", tables)
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()

    create_tables(cursor)
    _migrate_agent_log(cursor)
    conn.commit()

    seed_data(cursor)
    conn.commit()
    conn.close()
    logger.info("Datenbank bereit")


def _migrate_agent_log(cursor):
    """Fügt neue Spalten in agent_log hinzu, ohne bestehende Daten zu löschen."""
    cursor.execute("PRAGMA table_info(agent_log)")
    columns = {row[1] for row in cursor.fetchall()}
    migrations = {
        "duration_ms": "INTEGER",
        "tool_call_id": "TEXT",
    }
    for column, column_type in migrations.items():
        if column in columns:
            continue
        cursor.execute(f"ALTER TABLE agent_log ADD COLUMN {column} {column_type}")
        logger.info("Schema-Migration: agent_log.%s hinzugefügt", column)


if __name__ == "__main__":
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print("Alte Datenbank gelöscht.")

    init_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM produkte")
    print(f"\n📦 Produkte in DB: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM produkte WHERE bestand < mindestbestand")
    print(f"🔴 Davon kritisch: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM lieferanten")
    print(f"🏭 Lieferanten: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM verbrauch")
    print(f"📤 Verbrauchseinträge: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM bestellungen")
    print(f"📋 Bestellungen: {cursor.fetchone()[0]}")
    cursor.execute("SELECT gesamtbudget FROM budget ORDER BY jahr DESC, quartal DESC LIMIT 1")
    print(f"💰 Aktuelles Budget: {cursor.fetchone()[0]}€")
    conn.close()
