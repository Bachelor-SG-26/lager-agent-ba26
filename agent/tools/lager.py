from langchain_core.tools import tool

from database.operations import correct_stock
from database.queries import get_inventory_products, get_inventory_value_summary


@tool
def check_lagerbestand(limit: int = 20) -> str:
    """Zeigt den aktuellen Lagerbestand mit Status und Standardlieferant."""
    products = get_inventory_products(limit=limit)
    if not products:
        return "Keine Produkte im Lager vorhanden."

    lines = ["Aktueller Lagerbestand:"]
    for product in products:
        status = "kritisch" if product["status"] == "kritisch" else "ok"
        lines.append(
            f"- [{product['id']}] {product['name']}: "
            f"{product['bestand']} Stück, Mindestbestand {product['mindestbestand']}, "
            f"Status {status}, Lieferant: {product['lieferant'] or 'nicht hinterlegt'}"
        )
    return "\n".join(lines)


@tool
def check_engpaesse(limit: int = 20) -> str:
    """Zeigt Produkte, deren Bestand unter dem Mindestbestand liegt."""
    products = get_inventory_products(only_low_stock=True, limit=limit)
    if not products:
        return "Keine Engpässe gefunden."

    lines = ["Kritische Bestände:"]
    for product in products:
        fehlmenge = product["mindestbestand"] - product["bestand"]
        lines.append(
            f"- [{product['id']}] {product['name']}: "
            f"{product['bestand']} Stück vorhanden, "
            f"{fehlmenge} Stück unter Mindestbestand"
        )
    return "\n".join(lines)


@tool
def check_lagerwert() -> str:
    """Zeigt den aktuellen Warenwert des Lagerbestands."""
    summary = get_inventory_value_summary()
    return (
        "Lagerwert:\n"
        f"- Produkte: {summary['products']}\n"
        f"- Einheiten: {summary['total_units']}\n"
        f"- Gesamtwert: {_format_currency(summary['total_value'])}\n"
        f"- Kritischer Wert: {_format_currency(summary['critical_value'])}\n"
        f"- Durchschnittspreis: {_format_currency(summary['average_unit_price'])}"
    )


@tool
def korrigiere_lagerbestand(produkt_id: int, neuer_bestand: int, grund: str = "Inventur") -> str:
    """Korrigiert den Lagerbestand eines Produkts nach einer Zählung."""
    result = correct_stock(produkt_id, neuer_bestand, grund)
    if not result["success"]:
        return f"Fehler: {result['message']}"

    return (
        f"Bestand für {result['product_name']} korrigiert: "
        f"{result['old_stock']} -> {result['new_stock']} Stück"
    )


def _format_currency(value):
    return f"{value:.2f} €"
