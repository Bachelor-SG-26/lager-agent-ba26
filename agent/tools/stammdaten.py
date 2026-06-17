from langchain_core.tools import tool

from database.operations import create_product, create_supplier, update_product, update_supplier


@tool
def erstelle_lieferant(
    name: str,
    kontakt: str = "",
    lieferzeit_tage: int = 3,
    bewertung: float = 3.0,
) -> str:
    """Legt einen neuen Lieferanten für die Stammdaten an."""
    result = create_supplier(name, kontakt, lieferzeit_tage, bewertung)
    if not result["success"]:
        return f"Fehler: {result['message']}"

    return (
        f"Lieferant angelegt: {result['name']} "
        f"(ID {result['supplier_id']}, Lieferzeit {result['delivery_days']} Tage, "
        f"Bewertung {result['rating']:.1f})."
    )


@tool
def erstelle_produkt(
    name: str,
    bestand: int,
    mindestbestand: int,
    preis_pro_einheit: float,
    lieferant_id: int,
) -> str:
    """Legt ein neues Produkt mit Standardlieferant an."""
    result = create_product(
        name=name,
        stock=bestand,
        minimum_stock=mindestbestand,
        unit_price=preis_pro_einheit,
        supplier_id=lieferant_id,
    )
    if not result["success"]:
        return f"Fehler: {result['message']}"

    return (
        f"Produkt angelegt: {result['name']} "
        f"(ID {result['product_id']}, Bestand {result['stock']} Stück, "
        f"Mindestbestand {result['minimum_stock']} Stück)."
    )


@tool
def aktualisiere_lieferant(
    lieferant_id: int,
    name: str = None,
    kontakt: str = None,
    lieferzeit_tage: int = None,
    bewertung: float = None,
) -> str:
    """Aktualisiert bestehende Lieferantenstammdaten."""
    result = update_supplier(lieferant_id, name, kontakt, lieferzeit_tage, bewertung)
    if not result["success"]:
        return f"Fehler: {result['message']}"

    return (
        f"Lieferant {result['supplier_id']} aktualisiert. "
        f"Geänderte Felder: {', '.join(result['changed_fields'])}."
    )


@tool
def aktualisiere_produkt(
    produkt_id: int,
    name: str = None,
    bestand: int = None,
    mindestbestand: int = None,
    preis_pro_einheit: float = None,
    lieferant_id: int = None,
) -> str:
    """Aktualisiert bestehende Produktstammdaten."""
    result = update_product(
        product_id=produkt_id,
        name=name,
        stock=bestand,
        minimum_stock=mindestbestand,
        unit_price=preis_pro_einheit,
        supplier_id=lieferant_id,
    )
    if not result["success"]:
        return f"Fehler: {result['message']}"

    return (
        f"Produkt {result['product_id']} aktualisiert. "
        f"Geänderte Felder: {', '.join(result['changed_fields'])}."
    )
