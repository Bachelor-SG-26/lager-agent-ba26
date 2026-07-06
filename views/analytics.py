import streamlit as st
import pandas as pd
from database.database import db_connection
from datetime import datetime, timedelta
from config import ANALYTICS_ZEITRAUM_TAGE, ANALYTICS_TOP_PRODUKTE_LIMIT


# ─────────────────────────────────────────
#  Daten laden
# ─────────────────────────────────────────


def _lade_verbrauch_timeline(cursor, seit):
    """Tagesverbrauch der letzten 90 Tage."""
    cursor.execute("""
        SELECT DATE(v.datum) as tag, SUM(v.menge) as gesamt
        FROM verbrauch v
        WHERE v.datum >= ?
        GROUP BY DATE(v.datum)
        ORDER BY tag
    """, (seit,))
    return cursor.fetchall()


def _lade_top_produkte(cursor, seit, limit=10):
    """Top N verbrauchte Produkte."""
    cursor.execute("""
        SELECT p.name, SUM(v.menge) as gesamt
        FROM verbrauch v
        JOIN produkte p ON v.produkt_id = p.id
        WHERE v.datum >= ?
        GROUP BY p.name
        ORDER BY gesamt DESC
        LIMIT ?
    """, (seit, limit))
    return cursor.fetchall()


def _lade_verbrauch_nach_grund(cursor, seit):
    """Verbrauch gruppiert nach Entnahmegrund."""
    cursor.execute("""
        SELECT grund, SUM(menge) as gesamt
        FROM verbrauch
        WHERE datum >= ?
        GROUP BY grund
        ORDER BY gesamt DESC
    """, (seit,))
    return cursor.fetchall()


def _lade_lieferanten(cursor):
    """Alle Lieferanten mit Produktanzahl."""
    cursor.execute("""
        SELECT l.name, l.bewertung, l.lieferzeit_tage, l.kontakt, COUNT(pl.id) as produkte
        FROM lieferanten l
        LEFT JOIN produkt_lieferanten pl ON l.id = pl.lieferant_id
        GROUP BY l.id
        ORDER BY l.bewertung DESC
    """)
    return cursor.fetchall()


def _lade_budget_verlauf(cursor):
    """Budget-Daten aller Quartale."""
    cursor.execute("""
        SELECT 'Q' || quartal || '/' || jahr as periode, gesamtbudget, verbrauchtes_budget
        FROM budget
        ORDER BY jahr, quartal
    """)
    return cursor.fetchall()


# ─────────────────────────────────────────
#  Sektionen rendern
# ─────────────────────────────────────────


def _render_verbrauch_timeline(daten):
    """Linien-Chart: Materialverbrauch über Zeit."""
    st.subheader(f"Materialverbrauch (letzte {ANALYTICS_ZEITRAUM_TAGE} Tage)")
    if not daten:
        st.info("Keine Verbrauchsdaten vorhanden.")
        return

    df = pd.DataFrame(daten, columns=["Datum", "Menge"])
    df["Datum"] = pd.to_datetime(df["Datum"])
    st.line_chart(df.set_index("Datum"))


def _render_top_produkte(daten):
    """Balken-Chart: Top 10 verbrauchte Produkte."""
    st.subheader(f"Top {ANALYTICS_TOP_PRODUKTE_LIMIT} verbrauchte Produkte ({ANALYTICS_ZEITRAUM_TAGE} Tage)")
    if not daten:
        st.info("Keine Verbrauchsdaten vorhanden.")
        return

    df = pd.DataFrame(daten, columns=["Produkt", "Verbrauch"])
    st.bar_chart(df.set_index("Produkt"))


def _render_verbrauch_nach_grund(daten):
    """Balken-Chart: Verbrauch nach Entnahmegrund."""
    st.subheader("Verbrauch nach Grund")
    if not daten:
        return

    df = pd.DataFrame(daten, columns=["Grund", "Menge"])
    st.bar_chart(df.set_index("Grund"))


def _render_lieferanten(daten):
    """Tabelle: Lieferanten-Übersicht."""
    st.subheader("Lieferanten-Übersicht")
    if not daten:
        return

    df = pd.DataFrame(
        daten,
        columns=["Lieferant", "Bewertung", "Lieferzeit (Tage)", "Kontakt", "Produkte"],
    )
    st.dataframe(df, width="stretch", hide_index=True)


def _render_budget_verlauf(daten):
    """Balken-Chart: Budget-Verlauf über Quartale."""
    st.subheader("Budget-Verlauf")
    if not daten:
        return

    df = pd.DataFrame(daten, columns=["Quartal", "Budget", "Verbraucht"])
    df["Verbleibend"] = df["Budget"] - df["Verbraucht"]
    st.bar_chart(df[["Quartal", "Verbraucht", "Verbleibend"]].set_index("Quartal"))


# ─────────────────────────────────────────
#  Hauptfunktion
# ─────────────────────────────────────────


def show_analytics():
    """Analytics-Seite mit Verbrauchs-, Lieferanten- und Budget-Analysen."""
    st.title("Analysen und Trends")

    seit = (datetime.now() - timedelta(days=ANALYTICS_ZEITRAUM_TAGE)).strftime("%Y-%m-%d")

    with db_connection() as (conn, cursor):
        verbrauch = _lade_verbrauch_timeline(cursor, seit)
        top_produkte = _lade_top_produkte(cursor, seit, ANALYTICS_TOP_PRODUKTE_LIMIT)
        nach_grund = _lade_verbrauch_nach_grund(cursor, seit)
        lieferanten = _lade_lieferanten(cursor)
        budget = _lade_budget_verlauf(cursor)

    tab1, tab2, tab3 = st.tabs(["Verbrauch", "Lieferanten", "Budget"])
    with tab1:
        _render_verbrauch_timeline(verbrauch)
        st.divider()
        _render_top_produkte(top_produkte)
        st.divider()
        _render_verbrauch_nach_grund(nach_grund)
    with tab2:
        _render_lieferanten(lieferanten)
    with tab3:
        _render_budget_verlauf(budget)
