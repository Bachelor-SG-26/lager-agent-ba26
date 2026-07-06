import streamlit as st
import pandas as pd
from database.database import db_connection
from datetime import datetime


# ─────────────────────────────────────────
#  Daten laden
# ─────────────────────────────────────────


def get_lagerbestand():
    """Holt alle Produkte aus der DB."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT p.id, p.name, p.bestand, p.mindestbestand, p.preis_pro_einheit, l.name
            FROM produkte p
            JOIN lieferanten l ON p.standard_lieferant_id = l.id
            ORDER BY p.name
        """)
        return cursor.fetchall()


def get_budget():
    """Holt das aktuelle Quartalsbudget."""
    with db_connection() as (conn, cursor):
        quartal = (datetime.now().month - 1) // 3 + 1
        cursor.execute("""
            SELECT gesamtbudget, verbrauchtes_budget
            FROM budget WHERE quartal = ? AND jahr = ?
        """, (quartal, datetime.now().year))
        return cursor.fetchone()


# ─────────────────────────────────────────
#  Sektionen rendern
# ─────────────────────────────────────────


def _render_kpis(df):
    """Zeigt KPI-Metriken: Produkte, Kritisch, OK, Lagerwert."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Produkte gesamt", len(df))
    with col2:
        st.metric("Kritisch", int((df["Status"] == "KRITISCH").sum()))
    with col3:
        st.metric("OK", int((df["Status"] == "OK").sum()))
    with col4:
        lagerwert = (df["Bestand"] * df["Preis (Euro)"]).sum()
        st.metric("Lagerwert", f"{lagerwert:.2f} Euro")


def _render_kritische_chart(df):
    """Balken-Chart: Kritische Bestaende vs. Mindestbestand."""
    kritische = df[df["Status"] == "KRITISCH"]
    if kritische.empty:
        return

    st.subheader("Kritische Bestaende vs. Mindestbestand")
    st.bar_chart(kritische.set_index("Name")[["Bestand", "Mindestbestand"]])


def _render_produkt_tabelle(df):
    """Filterbarer Produkttabellen-Bereich."""
    filter_option = st.selectbox(
        "Filter", ["Alle Produkte", "Nur kritische", "Nur OK"]
    )
    if filter_option == "Nur kritische":
        df = df[df["Status"] == "KRITISCH"]
    elif filter_option == "Nur OK":
        df = df[df["Status"] == "OK"]

    st.dataframe(df, width="stretch", hide_index=True)


# ─────────────────────────────────────────
#  Hauptfunktion
# ─────────────────────────────────────────


def show_dashboard():
    """Dashboard mit KPIs, Chart und filterbarer Produkttabelle."""
    st.title("Lagerbestand Übersicht")

    produkte = get_lagerbestand()
    df = pd.DataFrame(produkte, columns=[
        "ID", "Name", "Bestand", "Mindestbestand", "Preis (Euro)", "Lieferant"
    ])
    df["Status"] = df.apply(
        lambda r: "KRITISCH" if r["Bestand"] < r["Mindestbestand"] else "OK",
        axis=1,
    )

    _render_kpis(df)
    st.divider()

    col_left, col_right = st.columns([1, 1.2], gap="large")
    with col_left:
        _render_kritische_chart(df)
    with col_right:
        st.subheader("Produkte")
        _render_produkt_tabelle(df)
