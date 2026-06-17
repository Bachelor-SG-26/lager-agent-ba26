from agent.tools.stammdaten import aktualisiere_lieferant, aktualisiere_produkt
from database.database import db_connection, init_db
from database.operations import update_product, update_supplier
from database.queries import get_inventory_products, get_suppliers


def test_update_supplier_changes_fields(test_database):
    init_db()

    result = update_supplier(
        supplier_id=1,
        name="Schrauben Müller Süd GmbH",
        contact="sued@schrauben-mueller.de",
        delivery_days=3,
        rating=4.8,
    )
    suppliers = get_suppliers()

    assert result["success"] is True
    assert any(supplier["name"] == "Schrauben Müller Süd GmbH" for supplier in suppliers)


def test_update_supplier_rejects_invalid_rating(test_database):
    init_db()

    result = update_supplier(supplier_id=1, rating=6.0)

    assert result["success"] is False
    assert "Bewertung" in result["message"]


def test_update_product_changes_inventory_fields(test_database):
    init_db()

    result = update_product(
        product_id=1,
        name="Sechskantschraube M8x45 verzinkt",
        stock=140,
        minimum_stock=90,
        unit_price=0.21,
    )
    products = get_inventory_products()

    assert result["success"] is True
    assert any(
        product["name"] == "Sechskantschraube M8x45 verzinkt"
        and product["bestand"] == 140
        for product in products
    )


def test_update_product_changes_default_supplier(test_database):
    init_db()

    result = update_product(product_id=1, supplier_id=2)

    assert result["success"] is True
    with db_connection() as (_, cursor):
        cursor.execute("SELECT standard_lieferant_id FROM produkte WHERE id = 1")
        product = cursor.fetchone()
    assert product["standard_lieferant_id"] == 2


def test_aktualisiere_lieferant_tool_returns_changed_fields(test_database):
    init_db()

    result = aktualisiere_lieferant.invoke({
        "lieferant_id": 1,
        "lieferzeit_tage": 3,
        "bewertung": 4.8,
    })

    assert "Lieferant 1 aktualisiert" in result
    assert "bewertung" in result


def test_aktualisiere_produkt_tool_returns_changed_fields(test_database):
    init_db()

    result = aktualisiere_produkt.invoke({
        "produkt_id": 1,
        "bestand": 140,
        "mindestbestand": 90,
    })

    assert "Produkt 1 aktualisiert" in result
    assert "bestand" in result
