import pandas as pd
import streamlit as st

from database.queries import (
    get_budget_trend,
    get_consumption_by_product,
    get_forecast_overview,
    get_order_cost_summary,
    get_order_cost_trend,
)


def show_auswertung():
    """Rendert Verbrauchsauswertung und Bedarfsprognose."""
    st.title("Auswertung")
    st.caption("Verbrauch verstehen und Nachbestellungen vorbereiten.")

    history_days = st.slider("Historie in Tagen", min_value=30, max_value=180, value=90, step=30)
    days_ahead = st.slider("Prognosezeitraum", min_value=7, max_value=90, value=30, step=7)

    _render_consumption(history_days)
    _render_forecast(days_ahead, history_days)
    _render_order_costs(history_days)
    _render_budget_trend()


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


def _render_order_costs(history_days):
    """Zeigt Bestellkosten als Monatsverlauf mit Exportmöglichkeit."""
    st.subheader("Bestellkosten")
    summary = get_order_cost_summary(history_days=history_days)
    trend = get_order_cost_trend(history_days=history_days)

    col_orders, col_costs, col_average = st.columns(3)
    col_orders.metric("Bestellungen", summary["bestellungen"])
    col_costs.metric("Gesamtkosten", f"{summary['gesamtkosten']:.2f} €")
    col_average.metric("Durchschnitt", f"{summary['durchschnittskosten']:.2f} €")

    if not trend:
        st.info("Für den gewählten Zeitraum liegen keine Bestellungen vor.")
        return

    df = pd.DataFrame(trend)
    st.bar_chart(df.set_index("monat")[["gesamtkosten"]])
    st.download_button(
        label="Bestellkosten exportieren",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="bestellkosten.csv",
        mime="text/csv",
    )


def _render_budget_trend():
    """Zeigt Budgetverbrauch und freien Betrag über die letzten Quartale."""
    st.subheader("Budget-Verlauf")
    trend = get_budget_trend(limit=12)
    if not trend:
        st.info("Es sind noch keine Budgets vorhanden.")
        return

    latest = trend[-1]
    col_total, col_used, col_free = st.columns(3)
    col_total.metric("Aktuelles Budget", f"{latest['gesamtbudget']:.2f} €")
    col_used.metric("Verbraucht", f"{latest['verbrauchtes_budget']:.2f} €")
    col_free.metric("Frei", f"{latest['freies_budget']:.2f} €")

    df = pd.DataFrame(trend)
    df["periode"] = df.apply(lambda row: f"Q{row['quartal']}/{row['jahr']}", axis=1)
    chart_df = df.rename(
        columns={
            "verbrauchtes_budget": "Verbraucht",
            "freies_budget": "Frei",
        }
    )
    st.bar_chart(chart_df.set_index("periode")[["Verbraucht", "Frei"]])
