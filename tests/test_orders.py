import pandas as pd

from agent.tools.bestellungen import (
    aktualisiere_bestellstatus,
    check_bestellhistorie,
    check_bestellvorschlaege,
    check_offene_bestellungen,
    erstelle_bestellung,
)
from database.database import db_connection, init_db
from database.operations import create_order, update_order_status
from database.queries import (
    get_current_budget,
    get_open_orders,
    get_order_cost_summary,
    get_order_cost_trend,
    get_order_history,
    get_order_status_summary,
    get_reorder_recommendations,
)
from views.bestellungen import _build_order_export


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


def test_order_export_contains_history_rows(test_database):
    init_db()

    result = create_order(product_id=1, amount=10)
    history = get_order_history(limit=1)
    csv_data = _build_order_export(pd.DataFrame(history)).decode("utf-8")

    assert "bestell_nr,datum,produkt,lieferant,menge,gesamtkosten,status" in csv_data
    assert result["order_number"] in csv_data
    assert "Sechskantschraube M8x40 verzinkt" in csv_data


def test_reorder_recommendations_include_critical_products(test_database):
    init_db()

    recommendations = get_reorder_recommendations(limit=5)

    assert recommendations
    assert recommendations[0]["empfohlene_menge"] > 0
    assert recommendations[0]["geschaetzte_kosten"] > 0


def test_open_orders_include_seeded_order(test_database):
    init_db()

    orders = get_open_orders()
    summary = get_order_status_summary()

    assert orders
    assert summary["open_count"] >= 1
    assert summary["open_cost"] > 0


def test_order_cost_trend_summarizes_recent_orders(test_database):
    init_db()

    trend = get_order_cost_trend(history_days=365)
    summary = get_order_cost_summary(history_days=365)

    assert trend
    assert trend[-1]["bestellungen"] >= 1
    assert summary["bestellungen"] >= trend[-1]["bestellungen"]
    assert summary["gesamtkosten"] >= 96
    assert summary["durchschnittskosten"] > 0


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


def test_check_bestellvorschlaege_tool_returns_recommendations(test_database):
    init_db()

    result = check_bestellvorschlaege.invoke({"limit": 5})

    assert "Nachbestellvorschläge" in result
    assert "geschätzte Kosten" in result


def test_check_offene_bestellungen_tool_returns_orders(test_database):
    init_db()

    result = check_offene_bestellungen.invoke({"limit": 5})

    assert "Offene Bestellungen" in result
    assert "BEST-" in result


def test_aktualisiere_bestellstatus_tool_returns_confirmation(test_database):
    init_db()
    order = create_order(product_id=1, amount=10)

    result = aktualisiere_bestellstatus.invoke({
        "bestell_nr": order["order_number"],
        "status": "geliefert",
    })

    assert "Status für" in result
    assert "geliefert" in result
