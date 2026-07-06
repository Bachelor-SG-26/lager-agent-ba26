import streamlit as st
import pandas as pd
from database.database import db_connection


# ─────────────────────────────────────────
#  Daten laden
# ─────────────────────────────────────────


def _lade_alle_auswertungsdaten():
    """Liest alle Auswertungsdaten in einer einzigen Connection."""
    with db_connection() as (conn, cursor):
        cursor.execute("""
            SELECT tool_name, tool_args, status, datum
            FROM agent_log
            ORDER BY datum DESC
        """)
        log_daten = cursor.fetchall()

        cursor.execute("""
            SELECT status, COUNT(*) as anzahl
            FROM agent_log
            GROUP BY status
        """)
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT tool_name, COUNT(*) as anzahl
            FROM agent_log
            GROUP BY tool_name
            ORDER BY anzahl DESC
        """)
        tool_ranking = cursor.fetchall()

        cursor.execute("""
            SELECT DATE(datum) as tag, COUNT(*) as anzahl
            FROM agent_log
            GROUP BY DATE(datum)
            ORDER BY tag
        """)
        timeline = cursor.fetchall()

    return log_daten, status_counts, tool_ranking, timeline


# ─────────────────────────────────────────
#  Sektionen rendern
# ─────────────────────────────────────────


def _render_kpis(status_counts):
    """Zeigt KPI-Metriken: Gesamt, Akzeptiert, Abgelehnt, Quote."""
    gesamt = sum(status_counts.values())
    akzeptiert = status_counts.get("akzeptiert", 0) + status_counts.get("auto-akzeptiert", 0)
    abgelehnt = status_counts.get("abgelehnt", 0)
    quote = (akzeptiert / gesamt * 100) if gesamt > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Tool-Calls gesamt", gesamt)
    with col2:
        st.metric("Akzeptiert", akzeptiert)
    with col3:
        st.metric("Abgelehnt", abgelehnt)
    with col4:
        st.metric("Akzeptanzquote", f"{quote:.1f}%")


def _render_tool_ranking(daten):
    """Balken-Chart: Welche Tools am häufigsten aufgerufen wurden."""
    st.subheader("Tool-Nutzung (Ranking)")
    if not daten:
        st.info("Noch keine Tool-Aufrufe protokolliert.")
        return

    df = pd.DataFrame(daten, columns=["Tool", "Aufrufe"])
    st.bar_chart(df.set_index("Tool"))


def _render_status_chart(status_counts):
    """Balken-Chart: Akzeptiert vs. Abgelehnt."""
    st.subheader("Akzeptiert vs. Abgelehnt")
    if not status_counts:
        return

    rows = [{"Status": k, "Anzahl": v} for k, v in status_counts.items()]
    st.bar_chart(pd.DataFrame(rows).set_index("Status"))


def _render_timeline(daten):
    """Linien-Chart: Tool-Calls über Zeit."""
    st.subheader("Aktivität über Zeit")
    if not daten:
        st.info("Noch keine Daten vorhanden.")
        return

    df = pd.DataFrame(daten, columns=["Datum", "Aufrufe"])
    df["Datum"] = pd.to_datetime(df["Datum"])
    st.line_chart(df.set_index("Datum"))


def _render_log_tabelle(daten):
    """Tabelle mit allen protokollierten Tool-Calls."""
    st.subheader("Alle Tool-Calls (Log)")
    if not daten:
        st.info("Noch keine Einträge vorhanden.")
        return

    columns = ["Tool", "Argumente", "Status", "Datum"]
    st.dataframe(
        [dict(zip(columns, row)) for row in daten],
        width="stretch",
        hide_index=True,
    )


# ─────────────────────────────────────────
#  Hauptfunktion
# ─────────────────────────────────────────


def show_auswertung():
    """Auswertungs-Seite mit Agent-Nutzungsstatistiken."""
    st.title("Agent-Auswertung")

    log_daten, status_counts, tool_ranking, timeline = _lade_alle_auswertungsdaten()

    tab1, tab2, tab3 = st.tabs(["Übersicht", "Nutzung", "Log"])
    with tab1:
        _render_kpis(status_counts)
        st.divider()
        _render_status_chart(status_counts)
    with tab2:
        _render_tool_ranking(tool_ranking)
        st.divider()
        _render_timeline(timeline)
    with tab3:
        _render_log_tabelle(log_daten)
