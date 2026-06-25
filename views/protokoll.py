import pandas as pd
import streamlit as st

from database.queries import get_activity_log


def show_protokoll():
    """Rendert das Protokoll der letzten operativen Aktionen."""
    st.title("Protokoll")
    st.caption("Letzte Entnahmen, Bestellungen und Budgetänderungen.")

    limit = st.slider("Einträge", min_value=10, max_value=100, value=30, step=10)
    entries = get_activity_log(limit=limit)
    if not entries:
        st.info("Noch keine Aktivitäten vorhanden.")
        return

    st.dataframe(
        pd.DataFrame(entries),
        width="stretch",
        hide_index=True,
        column_config={
            "bereich": "Bereich",
            "beschreibung": "Beschreibung",
            "referenz": "Referenz",
            "erstellt_am": "Zeitpunkt",
        },
    )
