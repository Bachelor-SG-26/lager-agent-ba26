import pandas as pd
import streamlit as st

from database.queries import get_consumption_by_product, get_forecast_overview


def show_auswertung():
    """Rendert Verbrauchsauswertung und Bedarfsprognose."""
    st.title("Auswertung")
    st.caption("Verbrauch verstehen und Nachbestellungen vorbereiten.")

    history_days = st.slider("Historie in Tagen", min_value=30, max_value=180, value=90, step=30)
    days_ahead = st.slider("Prognosezeitraum", min_value=7, max_value=90, value=30, step=7)

    _render_consumption(history_days)
    _render_forecast(days_ahead, history_days)


def _render_consumption(history_days):
    st.subheader("Verbrauch nach Produkt")
    consumption = get_consumption_by_product(history_days=history_days)
    if not consumption:
        st.info("Für den gewählten Zeitraum liegen keine Entnahmen vor.")
        return

    st.dataframe(
        pd.DataFrame(consumption),
        width="stretch",
        hide_index=True,
        column_config={
            "id": "ID",
            "produkt": "Produkt",
            "verbrauch": "Verbrauch",
            "buchungen": "Buchungen",
        },
    )


def _render_forecast(days_ahead, history_days):
    st.subheader("Bedarfsprognose")
    forecasts = get_forecast_overview(days_ahead=days_ahead, history_days=history_days)
    if not forecasts:
        st.info("Es sind noch keine Produkte vorhanden.")
        return

    df = pd.DataFrame(forecasts)
    df["daily_consumption"] = df["daily_consumption"].map(lambda value: round(value, 2))
    st.dataframe(
        df[
            [
                "product_name",
                "stock",
                "minimum_stock",
                "forecast_amount",
                "coverage_days",
                "recommended_order",
            ]
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "product_name": "Produkt",
            "stock": "Bestand",
            "minimum_stock": "Mindestbestand",
            "forecast_amount": "Prognosebedarf",
            "coverage_days": "Reichweite",
            "recommended_order": "Bestellvorschlag",
        },
    )
