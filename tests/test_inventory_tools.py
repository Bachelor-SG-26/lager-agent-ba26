from agent.tools.lager import (
    check_engpaesse,
    check_lagerbestand,
    check_lagerwert,
    korrigiere_lagerbestand,
)
from database.database import init_db
from database.operations import correct_stock
from database.queries import get_inventory_products, get_inventory_value_summary


def test_inventory_products_include_status(test_database):
    init_db()

    products = get_inventory_products()

    assert products
    assert {"ok", "kritisch"}.intersection({product["status"] for product in products})
    assert "lagerwert" in products[0]


def test_inventory_can_filter_low_stock(test_database):
    init_db()

    products = get_inventory_products(only_low_stock=True)

    assert products
    assert all(product["bestand"] < product["mindestbestand"] for product in products)


def test_inventory_value_summary_uses_stock_and_unit_price(test_database):
    init_db()

    summary = get_inventory_value_summary()

    assert summary["products"] >= 8
    assert summary["total_units"] > 0
    assert summary["total_value"] > summary["critical_value"] > 0


def test_correct_stock_updates_inventory(test_database):
    init_db()

    result = correct_stock(product_id=1, new_stock=77, reason="Inventur")
    products = get_inventory_products()
    product = next(product for product in products if product["id"] == 1)

    assert result["success"] is True
    assert result["old_stock"] == 120
    assert product["bestand"] == 77


def test_correct_stock_rejects_negative_stock(test_database):
    init_db()

    result = correct_stock(product_id=1, new_stock=-1, reason="Inventur")

    assert result["success"] is False
    assert "negativ" in result["message"]


def test_check_lagerbestand_returns_readable_summary(test_database):
    init_db()

    result = check_lagerbestand.invoke({"limit": 3})

    assert "Aktueller Lagerbestand" in result
    assert "Stück" in result


def test_check_engpaesse_returns_low_stock_items(test_database):
    init_db()

    result = check_engpaesse.invoke({"limit": 5})

    assert "Kritische Bestände" in result
    assert "unter Mindestbestand" in result


def test_check_lagerwert_returns_inventory_value(test_database):
    init_db()

    result = check_lagerwert.invoke({})

    assert "Lagerwert" in result
    assert "Gesamtwert" in result


def test_korrigiere_lagerbestand_tool_returns_confirmation(test_database):
    init_db()

    result = korrigiere_lagerbestand.invoke({
        "produkt_id": 1,
        "neuer_bestand": 77,
        "grund": "Inventur",
    })

    assert "Bestand für" in result
    assert "77 Stück" in result
