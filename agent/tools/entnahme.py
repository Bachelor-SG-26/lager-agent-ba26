from langchain_core.tools import tool

from database.operations import record_withdrawal


@tool
def erfasse_entnahme(produkt_id: int, menge: int, grund: str = "Produktion") -> str:
    """Erfasst eine Materialentnahme und aktualisiert den Lagerbestand."""
    result = record_withdrawal(produkt_id, menge, grund)
    if not result["success"]:
        return f"Fehler: {result['message']}"

    lines = [
        "Entnahme erfasst.",
        f"Produkt: {result['product_name']}",
        f"Menge: {result['amount']} Stück",
        f"Grund: {result['reason']}",
        f"Alter Bestand: {result['old_stock']} Stück",
        f"Neuer Bestand: {result['new_stock']} Stück",
    ]

    if result["is_low_stock"]:
        lines.append(
            f"Warnung: Der Bestand liegt unter dem Mindestbestand "
            f"({result['minimum_stock']} Stück)."
        )

    return "\n".join(lines)
