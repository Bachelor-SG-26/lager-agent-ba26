from langchain_core.tools import tool

from database.queries import get_inventory_products


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
