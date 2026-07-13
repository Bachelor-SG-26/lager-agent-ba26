import streamlit as st
import pandas as pd
from database.database import db_connection


EXECUTION_STATUSES = ("ausgefuehrt", "fehlgeschlagen", "abgelehnt_budget")


def _lade_tool_status(zeitraum_tage):
    query = """
        SELECT tool_call_id, tool_name, status, datum, duration_ms
        FROM agent_log
        WHERE datum >= datetime('now', ?)
          AND status IN ('ausgefuehrt', 'fehlgeschlagen', 'abgelehnt_budget')
    """
    with db_connection() as (conn, cursor):
        df = pd.read_sql_query(query, conn, params=(f"-{zeitraum_tage} days",))
    if not df.empty:
        df["datum"] = pd.to_datetime(df["datum"], errors="coerce")
    return df


def _lade_bestellungen(zeitraum_tage):
    query = """
        SELECT datum, gesamtkosten
        FROM bestellungen
        WHERE datum >= datetime('now', ?)
    """
    with db_connection() as (conn, cursor):
        df = pd.read_sql_query(query, conn, params=(f"-{zeitraum_tage} days",))
    if not df.empty:
        df["datum"] = pd.to_datetime(df["datum"], errors="coerce")
    return df


def _quote(zaehler, nenner):
    return (zaehler / nenner * 100.0) if nenner else 0.0


def _p95(values):
    if values.empty:
        return 0.0
    return float(values.quantile(0.95))


def _render_kpis(log_df, best_df):
    gesamt_exec = len(log_df)
    erfolgreich = int((log_df["status"] == "ausgefuehrt").sum()) if gesamt_exec else 0
    fehl = int((log_df["status"] == "fehlgeschlagen").sum()) if gesamt_exec else 0
    budget_block = int((log_df["status"] == "abgelehnt_budget").sum()) if gesamt_exec else 0

    bestell_calls = log_df[log_df["tool_name"].isin(["erstelle_bestellung", "erstelle_bestellung_batch"])]
    bestell_gesamt = len(bestell_calls)
    bestell_erfolg = int((bestell_calls["status"] == "ausgefuehrt").sum()) if bestell_gesamt else 0

    prognose_calls = log_df[
        log_df["tool_name"].isin(["prognostiziere_bedarf", "prognostiziere_bedarf_batch"])
    ]
    batch_calls = log_df[
        log_df["tool_name"].isin(["erstelle_bestellung_batch", "prognostiziere_bedarf_batch"])
    ]
    batch_quote = _quote(len(batch_calls), len(bestell_calls) + len(prognose_calls))
    durations = log_df.loc[log_df["duration_ms"].notna(), "duration_ms"] if gesamt_exec else pd.Series(dtype=float)
    avg_dauer = float(durations.mean()) if not durations.empty else 0.0
    p95_dauer = _p95(durations) if not durations.empty else 0.0

    auftragsvolumen = float(best_df["gesamtkosten"].sum()) if not best_df.empty else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tool-Erfolgsquote", f"{_quote(erfolgreich, gesamt_exec):.1f}%")
    col2.metric("Bestell-Erfolgsquote", f"{_quote(bestell_erfolg, bestell_gesamt):.1f}%")
    col3.metric("Budget-Blockrate", f"{_quote(budget_block, bestell_gesamt):.1f}%")
    col4.metric("Batch-Quote", f"{batch_quote:.1f}%")

    col5, col6, col7 = st.columns(3)
    col5.metric("Ausgeführte Tool-Calls", erfolgreich)
    col6.metric("Fehlgeschlagene Tool-Calls", fehl)
    col7.metric("Bestellvolumen", f"{auftragsvolumen:.2f} Euro")

    col8, col9 = st.columns(2)
    col8.metric("Ø Tool-Dauer", f"{avg_dauer:.0f} ms")
    col9.metric("P95 Tool-Dauer", f"{p95_dauer:.0f} ms")


def _render_status_chart(log_df):
    st.subheader("Tool-Status Verteilung")
    if log_df.empty:
        st.info("Keine ausführungsbezogenen Tool-Logs im gewählten Zeitraum.")
        return
    status_counts = log_df.groupby("status").size().reset_index(name="anzahl")
    st.bar_chart(status_counts.set_index("status"))


def _render_tool_ranking(log_df):
    st.subheader("Top Tools (ausgefuehrt)")
    if log_df.empty:
        return
    ranking = (
        log_df[log_df["status"] == "ausgefuehrt"]
        .groupby("tool_name")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .reset_index(name="anzahl")
    )
    if ranking.empty:
        st.info("Keine erfolgreichen Tool-Ausführungen im Zeitraum.")
        return
    st.bar_chart(ranking.set_index("tool_name"))


def _render_timeline(log_df):
    st.subheader("Aktivität pro Tag")
    if log_df.empty:
        return
    timeline = (
        log_df.assign(tag=log_df["datum"].dt.date)
        .groupby("tag")
        .size()
        .reset_index(name="anzahl")
    )
    timeline["tag"] = pd.to_datetime(timeline["tag"])
    st.line_chart(timeline.set_index("tag"))


def _render_dauer_pro_tool(log_df):
    st.subheader("Laufzeit pro Tool")
    if log_df.empty:
        return
    df = log_df[log_df["duration_ms"].notna()].copy()
    if df.empty:
        st.info("Noch keine Laufzeiten aufgezeichnet.")
        return
    laufzeit = (
        df.groupby("tool_name")["duration_ms"]
        .mean()
        .sort_values(ascending=False)
        .reset_index(name="avg_duration_ms")
    )
    st.bar_chart(laufzeit.set_index("tool_name"))


def _render_detail_table(log_df):
    st.subheader("Detailtabelle")
    if log_df.empty:
        return
    anzeigen = log_df.sort_values("datum", ascending=False).copy()
    anzeigen["datum"] = anzeigen["datum"].dt.strftime("%Y-%m-%d %H:%M:%S")
    if "duration_ms" in anzeigen.columns:
        anzeigen["duration_ms"] = anzeigen["duration_ms"].fillna(0).astype(int)
    anzeigen = anzeigen.rename(
        columns={
            "tool_call_id": "Aufruf-ID",
            "tool_name": "Tool",
            "status": "Status",
            "datum": "Datum",
            "duration_ms": "Dauer (ms)",
        }
    )
    st.dataframe(anzeigen, width="stretch", hide_index=True)


def show_metriken():
    st.title("Metriken")
    zeitraum_tage = st.selectbox("Zeitraum", [7, 14, 30, 90], index=2)

    log_df = _lade_tool_status(zeitraum_tage)
    best_df = _lade_bestellungen(zeitraum_tage)

    _render_kpis(log_df, best_df)
    st.divider()
    _render_status_chart(log_df)
    st.divider()
    _render_tool_ranking(log_df)
    st.divider()
    _render_timeline(log_df)
    st.divider()
    _render_dauer_pro_tool(log_df)
    st.divider()
    _render_detail_table(log_df)
