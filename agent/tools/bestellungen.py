from langchain_core.tools import tool

from database.operations import create_order, update_order_status
from database.queries import get_order_history, get_reorder_recommendations


def _format_currency(value):
    return f"{value:.2f} €"


@tool
def erstelle_bestellung(produkt_id: int, menge: int, lieferant_id: int = None) -> str:
    """Legt eine Bestellung an und aktualisiert Bestand sowie Budget."""
    result = create_order(produkt_id, menge, lieferant_id)
    if not result["success"]:
        return f"Fehler: {result['message']}"

    return (
        "Bestellung angelegt.\n"
        f"Bestellnummer: {result['order_number']}\n"
        f"Produkt: {result['product_name']}\n"
        f"Lieferant: {result['supplier_name']}\n"
        f"Menge: {result['amount']} Stück\n"
        f"Kosten: {_format_currency(result['total_cost'])}\n"
        f"Neuer Bestand: {result['new_stock']} Stück\n"
        f"Freies Budget: {_format_currency(result['free_budget'])}"
    )


@tool
def check_bestellhistorie(limit: int = 20) -> str:
    """Zeigt die letzten Bestellungen mit Kosten und Status."""
    orders = get_order_history(limit=limit)
    if not orders:
        return "Keine Bestellungen vorhanden."

    lines = ["Bestellhistorie:"]
    for order in orders:
        lines.append(
            f"- {order['bestell_nr']}: {order['produkt']} bei "
            f"{order['lieferant'] or 'unbekannt'}, {order['menge']} Stück, "
            f"{_format_currency(order['gesamtkosten'])}, Status {order['status']}"
        )
    return "\n".join(lines)


@tool
def check_bestellvorschlaege(limit: int = 10) -> str:
    """Zeigt Produkte mit konkretem Nachbestellbedarf."""
    recommendations = get_reorder_recommendations(limit=limit)
    if not recommendations:
        return "Keine Nachbestellungen nötig."

    lines = ["Nachbestellvorschläge:"]
    for recommendation in recommendations:
        lines.append(
            f"- [{recommendation['produkt_id']}] {recommendation['produkt']}: "
            f"{recommendation['empfohlene_menge']} Stück bei "
            f"{recommendation['lieferant'] or 'unbekannt'}, "
            f"geschätzte Kosten {_format_currency(recommendation['geschaetzte_kosten'])}"
        )
    return "\n".join(lines)


@tool
def aktualisiere_bestellstatus(bestell_nr: str, status: str) -> str:
    """Aktualisiert den Status einer Bestellung."""
    result = update_order_status(bestell_nr, status)
    if not result["success"]:
        return f"Fehler: {result['message']}"

    return (
        f"Status für {result['order_number']} aktualisiert: "
        f"{result['old_status']} -> {result['status']}"
    )
