import os
import gc
import pytest
import sqlite3
from unittest.mock import patch
from database.models import create_tables
from database.seed import seed_data


os.environ.setdefault("LAGER_AGENT_LOG_FILE", os.path.join("logs", "lager_agent_test.log"))

TEST_DB = "test_lager.db"


@pytest.fixture(autouse=True)
def test_db():
    """Erstellt eine frische Test-Datenbank vor jedem Test."""
    # Alte Test-DB löschen falls vorhanden
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            gc.collect()
            os.remove(TEST_DB)

    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    create_tables(cursor)
    conn.commit()
    seed_data(cursor)
    conn.commit()
    conn.close()

    # get_connection auf Test-DB umleiten
    with patch("database.database.DB_NAME", TEST_DB):
        yield

    # Telegram-Batch-Timer abbrechen falls aktiv
    try:
        from agent.tools.bestellungen import _telegram_batch_lock, _telegram_batch, _telegram_timer
        import agent.tools.bestellungen as best_mod
        with _telegram_batch_lock:
            if best_mod._telegram_timer:
                best_mod._telegram_timer.cancel()
                best_mod._telegram_timer = None
            _telegram_batch.clear()
    except Exception:
        pass

    # Aufräumen
    gc.collect()
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            pass


@pytest.fixture
def db_cursor():
    """Gibt einen Cursor zur Test-Datenbank zurück."""
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    yield cursor, conn
    conn.close()
