from langchain_core.tools import tool

from database.queries import get_supplier_options_for_product, recommend_supplier


def _format_currency(value):
    return f"{value:.2f} €"


@tool
def vergleiche_lieferanten(produkt_id: int) -> str:
    """Vergleicht Lieferanten eines Produkts nach Preis, Lieferzeit und Bewertung."""
    product_name, suppliers = get_supplier_options_for_product(produkt_id)
    if not product_name:
        return f"Fehler: Produkt mit ID {produkt_id} wurde nicht gefunden."
    if not suppliers:
        return "Für dieses Produkt sind keine Lieferanten hinterlegt."

    recommendation = recommend_supplier(suppliers)
    lines = [f"Lieferantenvergleich für {product_name}:"]
    for supplier in suppliers:
        standard = " Standardlieferant" if supplier["ist_standard"] else ""
        lines.append(
            f"- [{supplier['id']}] {supplier['name']}: "
            f"{_format_currency(supplier['preis'])}, "
            f"{supplier['lieferzeit_tage']} Tage, "
            f"Bewertung {supplier['bewertung']:.1f}{standard}"
        )

    lines.append(
        f"Empfehlung: {recommendation['name']} "
        f"({_format_currency(recommendation['preis'])}, "
        f"{recommendation['lieferzeit_tage']} Tage)."
    )
    return "\n".join(lines)
