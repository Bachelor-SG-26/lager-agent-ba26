import streamlit as st

from database.queries import (
    get_activity_log,
    get_current_budget,
    get_dashboard_summary,
    get_low_stock_products,
)


def _format_currency(value):
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def show_dashboard():
    st.title("Dashboard")
    st.caption("Übersicht für Lagerbestand, Bestellungen und Budget.")

    summary = get_dashboard_summary()
    col_lager, col_bestellungen, col_orders, col_value, col_budget = st.columns(5)
    col_lager.metric("Produkte", summary["products"])
    col_bestellungen.metric("Offene Engpässe", summary["low_stock"])
    col_orders.metric("Offene Bestellungen", summary["open_orders"])
    col_value.metric("Lagerwert", _format_currency(summary["inventory_value"]))
    col_budget.metric("Freies Budget", _format_currency(summary["free_budget"]))

    budget = get_current_budget()
    if budget:
        st.subheader(f"Budget Q{budget['quartal']}/{budget['jahr']}")
        st.progress(min(budget["verbrauchsquote"], 1.0))
        st.caption(
            f"{_format_currency(budget['verbrauchtes_budget'])} von "
            f"{_format_currency(budget['gesamtbudget'])} verbraucht"
        )

    st.subheader("Kritische Bestände")
    products = get_low_stock_products()
    if not products:
        st.success("Alle Bestände liegen über dem Mindestbestand.")
    else:
        st.dataframe(
            products,
            width="stretch",
            hide_index=True,
            column_config={
                "name": "Produkt",
                "bestand": "Bestand",
                "mindestbestand": "Mindestbestand",
                "lieferant": "Standardlieferant",
            },
        )

    st.subheader("Letzte Aktivitäten")
    activities = get_activity_log(limit=5)
    if not activities:
        st.info("Noch keine Aktivitäten vorhanden.")
        return

    st.dataframe(
        activities,
        width="stretch",
        hide_index=True,
        column_config={
            "bereich": "Bereich",
            "beschreibung": "Beschreibung",
            "referenz": "Referenz",
            "erstellt_am": "Zeitpunkt",
        },
    )
