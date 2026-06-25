from agent.tools.bestellungen import (
    aktualisiere_bestellstatus,
    check_bestellhistorie,
    erstelle_bestellung,
)
from database.database import db_connection, init_db
from database.operations import create_order, update_order_status
from database.queries import get_current_budget, get_order_history


def test_create_order_increases_stock(test_database):
    init_db()

    result = create_order(product_id=1, amount=10)

    assert result["success"] is True
    assert result["new_stock"] == 130


def test_create_order_updates_budget(test_database):
    init_db()
    budget_before = get_current_budget()

    result = create_order(product_id=1, amount=10)
    budget_after = get_current_budget()

    assert result["success"] is True
    assert budget_after["verbrauchtes_budget"] > budget_before["verbrauchtes_budget"]


def test_create_order_writes_history_entry(test_database):
    init_db()

    result = create_order(product_id=1, amount=10)
    history = get_order_history(limit=1)

    assert history[0]["bestell_nr"] == result["order_number"]
    assert history[0]["produkt"] == "Sechskantschraube M8x40 verzinkt"


def test_create_order_rejects_budget_overflow(test_database):
    init_db()

    result = create_order(product_id=7, amount=9999)

    assert result["success"] is False
    assert "Budget überschritten" in result["message"]


def test_failed_order_does_not_change_stock(test_database):
    init_db()

    with db_connection() as (_, cursor):
        cursor.execute("SELECT bestand FROM produkte WHERE id = 7")
        stock_before = cursor.fetchone()["bestand"]

    create_order(product_id=7, amount=9999)

    with db_connection() as (_, cursor):
        cursor.execute("SELECT bestand FROM produkte WHERE id = 7")
        stock_after = cursor.fetchone()["bestand"]

    assert stock_after == stock_before


def test_update_order_status_changes_history(test_database):
    init_db()
    result = create_order(product_id=1, amount=10)

    status_result = update_order_status(result["order_number"], "geliefert")
    history = get_order_history(limit=1)

    assert status_result["success"] is True
    assert history[0]["status"] == "geliefert"


def test_update_order_status_rejects_invalid_status(test_database):
    init_db()
    result = create_order(product_id=1, amount=10)

    status_result = update_order_status(result["order_number"], "offen")

    assert status_result["success"] is False
    assert "ungültig" in status_result["message"]


def test_erstelle_bestellung_tool_returns_summary(test_database):
    init_db()

    result = erstelle_bestellung.invoke({
        "produkt_id": 1,
        "menge": 10,
    })

    assert "Bestellung angelegt" in result
    assert "Freies Budget" in result


def test_check_bestellhistorie_tool_returns_orders(test_database):
    init_db()
    create_order(product_id=1, amount=10)

    result = check_bestellhistorie.invoke({"limit": 5})

    assert "Bestellhistorie" in result
    assert "Sechskantschraube M8x40 verzinkt" in result


def test_aktualisiere_bestellstatus_tool_returns_confirmation(test_database):
    init_db()
    order = create_order(product_id=1, amount=10)

    result = aktualisiere_bestellstatus.invoke({
        "bestell_nr": order["order_number"],
        "status": "geliefert",
    })

    assert "Status für" in result
    assert "geliefert" in result
