from agent.tools.lager import check_engpaesse, check_lagerbestand
from database.database import init_db
from database.queries import get_inventory_products


def test_inventory_products_include_status(test_database):
    init_db()

    products = get_inventory_products()

    assert products
    assert {"ok", "kritisch"}.intersection({product["status"] for product in products})


def test_inventory_can_filter_low_stock(test_database):
    init_db()

    products = get_inventory_products(only_low_stock=True)

    assert products
    assert all(product["bestand"] < product["mindestbestand"] for product in products)


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
