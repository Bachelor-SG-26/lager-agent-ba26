from pathlib import Path

import pytest

import config
from database.database import db_connection, init_db
from database.queries import get_dashboard_summary, get_low_stock_products


@pytest.fixture
def test_database(monkeypatch):
    db_path = Path("test_lager.db")
    if db_path.exists():
        db_path.unlink()

    monkeypatch.setattr(config, "DATA_DIR", Path("."))
    monkeypatch.setattr(config, "DB_NAME", db_path)

    yield db_path

    if db_path.exists():
        db_path.unlink()


def test_init_db_creates_core_tables(test_database):
    init_db()

    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """)
        rows = cursor.fetchall()

    table_names = {row["name"] for row in rows}
    assert "produkte" in table_names
    assert "lieferanten" in table_names
    assert "budget" in table_names
    assert "bestellungen" in table_names


def test_init_db_seeds_inventory_data(test_database):
    init_db()

    with db_connection() as (_, cursor):
        cursor.execute("SELECT COUNT(*) AS count FROM produkte")
        product_count = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) AS count FROM lieferanten")
        supplier_count = cursor.fetchone()

    assert product_count["count"] >= 8
    assert supplier_count["count"] >= 4


def test_dashboard_summary_uses_seed_data(test_database):
    init_db()

    summary = get_dashboard_summary()

    assert summary["products"] >= 8
    assert summary["low_stock"] >= 1
    assert summary["free_budget"] > 0


def test_low_stock_products_are_sorted(test_database):
    init_db()

    products = get_low_stock_products(limit=3)

    assert products
    assert products[0]["bestand"] < products[0]["mindestbestand"]
