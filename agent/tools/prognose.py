from langchain_core.tools import tool

from database.queries import forecast_product_demand


@tool
def prognostiziere_bedarf(produkt_id: int, tage_voraus: int = 30) -> str:
    """Erstellt eine einfache Bedarfsprognose für ein Produkt."""
    forecast = forecast_product_demand(produkt_id, days_ahead=tage_voraus)
    if not forecast:
        return f"Fehler: Produkt mit ID {produkt_id} wurde nicht gefunden."

    coverage = (
        f"{forecast['coverage_days']} Tage"
        if forecast["coverage_days"] is not None
        else "nicht berechenbar"
    )

    return (
        f"Prognose für {forecast['product_name']}:\n"
        f"- Verbrauch der letzten {forecast['history_days']} Tage: "
        f"{forecast['total_consumption']} Stück\n"
        f"- Prognose für {forecast['days_ahead']} Tage: "
        f"{forecast['forecast_amount']} Stück\n"
        f"- Aktueller Bestand: {forecast['stock']} Stück\n"
        f"- Reichweite: {coverage}\n"
        f"- Empfohlene Bestellung: {forecast['recommended_order']} Stück"
    )


@tool
def prognostiziere_bedarf_batch(produkt_ids: list[int], tage_voraus: int = 30) -> str:
    """Erstellt Bedarfsprognosen für mehrere Produkte."""
    if not produkt_ids:
        return "Fehler: Es wurden keine Produkt-IDs übergeben."

    lines = [f"Bedarfsprognose für {len(produkt_ids)} Produkte:"]
    for product_id in produkt_ids:
        forecast = forecast_product_demand(product_id, days_ahead=tage_voraus)
        if not forecast:
            lines.append(f"- Produkt {product_id}: nicht gefunden")
            continue
        lines.append(
            f"- {forecast['product_name']}: "
            f"{forecast['forecast_amount']} Stück Bedarf, "
            f"{forecast['recommended_order']} Stück empfohlene Bestellung"
        )
    return "\n".join(lines)
