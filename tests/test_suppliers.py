from agent.tools.lieferanten import vergleiche_lieferanten
from database.database import init_db
from database.operations import create_order
from database.queries import (
    get_order_history,
    get_supplier_options_for_product,
    get_supplier_overview,
    recommend_supplier,
)


def test_supplier_options_include_product_suppliers(test_database):
    init_db()

    product_name, suppliers = get_supplier_options_for_product(1)

    assert product_name == "Sechskantschraube M8x40 verzinkt"
    assert len(suppliers) >= 2
    assert {"preis", "lieferzeit_tage", "bewertung"}.issubset(suppliers[0])


def test_supplier_recommendation_returns_best_option(test_database):
    init_db()
    _, suppliers = get_supplier_options_for_product(1)

    recommendation = recommend_supplier(suppliers)

    assert recommendation["id"] in {supplier["id"] for supplier in suppliers}
    assert recommendation["score"] > 0


def test_supplier_overview_includes_operational_metrics(test_database):
    init_db()

    overview = get_supplier_overview()

    assert len(overview) >= 4
    assert {"produktanzahl", "durchschnittspreis", "bestellungen"}.issubset(overview[0])
    assert all(supplier["produktanzahl"] >= 1 for supplier in overview)
    assert overview == sorted(
        overview,
        key=lambda supplier: (-supplier["bewertung"], supplier["lieferzeit_tage"], supplier["name"]),
    )


def test_order_can_use_selected_supplier(test_database):
    init_db()
    _, suppliers = get_supplier_options_for_product(1)
    selected_supplier = suppliers[-1]

    result = create_order(product_id=1, amount=5, supplier_id=selected_supplier["id"])
    history = get_order_history(limit=1)

    assert result["success"] is True
    assert history[0]["lieferant"] == selected_supplier["name"]


def test_vergleiche_lieferanten_tool_returns_recommendation(test_database):
    init_db()

    result = vergleiche_lieferanten.invoke({"produkt_id": 1})

    assert "Lieferantenvergleich" in result
    assert "Empfehlung" in result


def test_vergleiche_lieferanten_handles_unknown_product(test_database):
    init_db()

    result = vergleiche_lieferanten.invoke({"produkt_id": 9999})

    assert "nicht gefunden" in result
