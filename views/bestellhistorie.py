import streamlit as st
import pandas as pd
from database.database import db_connection


# ─────────────────────────────────────────
#  Daten laden
# ─────────────────────────────────────────


def _lade_bestellungen():
    """Lädt alle Bestellungen aus der Datenbank."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT b.bestell_nr, p.name, l.name, b.menge, b.gesamtkosten, b.datum
            FROM bestellungen b
            JOIN produkte p ON b.produkt_id = p.id
            LEFT JOIN lieferanten l ON b.lieferant_id = l.id
            ORDER BY b.datum DESC
        """)
        return cursor.fetchall()


# ─────────────────────────────────────────
#  Sektionen rendern
# ─────────────────────────────────────────


def _render_kpis(df):
    """Zeigt KPI-Metriken: Gesamtausgaben, Anzahl, Durchschnitt."""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gesamtausgaben", f"{df['Kosten (Euro)'].sum():.2f} Euro")
    with col2:
        st.metric("Bestellungen", len(df))
    with col3:
        durchschnitt = df["Kosten (Euro)"].mean() if len(df) else 0
        st.metric("Durchschn. Bestellwert", f"{durchschnitt:.2f} Euro")


def _render_monatschart(df):
    """Balken-Chart: Ausgaben pro Monat."""
    df = df.copy()
    df["Monat"] = pd.to_datetime(df["Datum"]).dt.to_period("M").astype(str)
    monatlich = df.groupby("Monat")["Kosten (Euro)"].sum().reset_index()
    if len(monatlich) > 1:
        st.subheader("Ausgaben pro Monat")
        st.bar_chart(monatlich.set_index("Monat"))


def _render_tabelle_und_export(df):
    """Zeigt Datentabelle und CSV-Export."""
    st.dataframe(df, width="stretch", hide_index=True)

    st.divider()
    st.download_button(
        label="Als CSV exportieren",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="bestellhistorie.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────
#  Hauptfunktion
# ─────────────────────────────────────────


def show_bestellhistorie():
    """Bestellhistorie-Seite mit KPIs, Chart, Tabelle und Export."""
    st.title("Bestellhistorie")

    bestellungen = _lade_bestellungen()
    if not bestellungen:
        st.info("Noch keine Bestellungen vorhanden.")
        return

    df = pd.DataFrame(bestellungen, columns=[
        "Bestell-Nr", "Produkt", "Lieferant", "Menge", "Kosten (Euro)", "Datum"
    ])

    _render_kpis(df)
    st.divider()
    _render_monatschart(df)
    st.divider()
    _render_tabelle_und_export(df)
