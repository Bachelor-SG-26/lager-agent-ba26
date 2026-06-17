from agent.tools.stammdaten import erstelle_lieferant, erstelle_produkt
from database.database import init_db
from database.operations import create_product, create_supplier
from database.queries import get_inventory_products, get_suppliers


def test_create_supplier_adds_supplier(test_database):
    init_db()

    result = create_supplier("Metallhandel Süd", "kontakt@metall-sued.de", 2, 4.6)
    suppliers = get_suppliers()

    assert result["success"] is True
    assert any(supplier["name"] == "Metallhandel Süd" for supplier in suppliers)


def test_create_supplier_rejects_duplicate_name(test_database):
    init_db()

    create_supplier("Metallhandel Süd", "kontakt@metall-sued.de", 2, 4.6)
    result = create_supplier("Metallhandel Süd", "kontakt@metall-sued.de", 2, 4.6)

    assert result["success"] is False
    assert "bereits vorhanden" in result["message"]


def test_create_product_adds_inventory_item(test_database):
    init_db()

    result = create_product(
        name="Passfeder 8x7x40",
        stock=40,
        minimum_stock=20,
        unit_price=0.65,
        supplier_id=1,
    )
    products = get_inventory_products()

    assert result["success"] is True
    assert any(product["name"] == "Passfeder 8x7x40" for product in products)


def test_create_product_rejects_unknown_supplier(test_database):
    init_db()

    result = create_product(
        name="Kupplungselement 20 mm",
        stock=12,
        minimum_stock=5,
        unit_price=8.40,
        supplier_id=9999,
    )

    assert result["success"] is False
    assert "Lieferant" in result["message"]


def test_erstelle_lieferant_tool_returns_confirmation(test_database):
    init_db()

    result = erstelle_lieferant.invoke({
        "name": "Metallhandel Süd",
        "kontakt": "kontakt@metall-sued.de",
        "lieferzeit_tage": 2,
        "bewertung": 4.6,
    })

    assert "Lieferant angelegt" in result


def test_erstelle_produkt_tool_returns_confirmation(test_database):
    init_db()

    result = erstelle_produkt.invoke({
        "name": "Passfeder 8x7x40",
        "bestand": 40,
        "mindestbestand": 20,
        "preis_pro_einheit": 0.65,
        "lieferant_id": 1,
    })

    assert "Produkt angelegt" in result
