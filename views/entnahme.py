import streamlit as st
import pandas as pd
from database.database import db_connection
from datetime import datetime


# ─────────────────────────────────────────
#  Daten laden
# ─────────────────────────────────────────


def _lade_produkte(cursor):
    """Lädt alle Produkte für das Entnahme-Formular."""
    cursor.execute("""
        SELECT p.id, p.name, p.bestand
        FROM produkte p
        ORDER BY p.name
    """)
    return cursor.fetchall()


def _lade_entnahme_historie(cursor, limit=50):
    """Lädt die letzten Entnahmen aus der Datenbank."""
    cursor.execute("""
        SELECT v.id, p.name, v.menge, v.grund, v.datum
        FROM verbrauch v
        JOIN produkte p ON v.produkt_id = p.id
        ORDER BY v.datum DESC
        LIMIT ?
    """, (limit,))
    return cursor.fetchall()


# ─────────────────────────────────────────
#  Sektionen rendern
# ─────────────────────────────────────────

HISTORIE_COLUMNS = ["ID", "Produkt", "Menge", "Grund", "Datum"]


def _render_entnahme_formular(produkte):
    """Zeigt das Entnahme-Formular und verarbeitet Eingaben."""
    st.subheader("Neue Entnahme erfassen")
    # Mapping Label -> (produkt_id, bestand). Kein zweites Lookup nötig.
    produkt_options = {
        f"{p[1]} (Bestand: {p[2]})": (p[0], p[2]) for p in produkte
    }

    with st.form("entnahme_form"):
        selected = st.selectbox("Produkt", list(produkt_options.keys()))
        menge = st.number_input("Menge", min_value=1, value=1)
        grund = st.selectbox(
            "Grund",
            ["Produktion", "Wartung", "Montage", "Reparatur", "Prototyp", "Sonstiges"],
        )
        submitted = st.form_submit_button("Entnahme erfassen", width="stretch")

    if submitted:
        produkt_id, bestand = produkt_options[selected]
        _verarbeite_entnahme(produkt_id, menge, bestand, grund)


def _verarbeite_entnahme(produkt_id, menge, bestand, grund):
    """Führt die Entnahme in der Datenbank durch."""
    if menge > bestand:
        st.error(f"Nicht genug Bestand. Verfügbar: {bestand} Stück")
        return

    try:
        with db_connection(commit=True) as (conn, cursor):
            cursor.execute(
                "UPDATE produkte SET bestand = bestand - ? WHERE id = ?",
                (menge, produkt_id),
            )
            cursor.execute("""
                INSERT INTO verbrauch (produkt_id, menge, grund, datum)
                VALUES (?, ?, ?, ?)
            """, (produkt_id, menge, grund, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        st.success(f"{menge} Stück entnommen. Neuer Bestand: {bestand - menge}")
        st.rerun()
    except Exception as e:
        st.error(f"Fehler bei der Entnahme: {e}")


def _render_entnahme_historie(entnahmen):
    """Zeigt Tabelle und CSV-Export der letzten Entnahmen."""
    st.subheader("Letzte Entnahmen")
    if not entnahmen:
        st.info("Noch keine Entnahmen vorhanden.")
        return

    df = pd.DataFrame(entnahmen, columns=HISTORIE_COLUMNS)
    st.dataframe(df, width="stretch", hide_index=True)

    st.download_button(
        label="Als CSV exportieren",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="entnahmen.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────
#  Hauptfunktion
# ─────────────────────────────────────────


def show_entnahme():
    """Entnahme-Seite mit Formular und Historie."""
    st.title("Materialentnahme")

    with db_connection() as (conn, cursor):
        produkte = _lade_produkte(cursor)
        entnahmen = _lade_entnahme_historie(cursor)

    _render_entnahme_formular(produkte)
    st.divider()
    _render_entnahme_historie(entnahmen)
