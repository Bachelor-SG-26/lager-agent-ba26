from datetime import datetime

import pandas as pd
import streamlit as st

from database.operations import create_budget
from database.queries import get_budget_history, get_current_budget


def show_budget():
    """Rendert Budgetstatus, Budgetanlage und Budgethistorie."""
    st.title("Budget")
    st.caption("Quartalsbudget verwalten und Verbrauch prüfen.")

    _render_current_budget()
    _render_budget_form()
    _render_budget_history()


def _render_current_budget():
    """Zeigt das aktuellste Budget als kompakte Kennzahlen."""
    budget = get_current_budget()
    if not budget:
        st.info("Es ist noch kein Budget hinterlegt.")
        return

    col_total, col_used, col_free = st.columns(3)
    col_total.metric("Gesamtbudget", _format_currency(budget["gesamtbudget"]))
    col_used.metric("Verbraucht", _format_currency(budget["verbrauchtes_budget"]))
    col_free.metric("Frei", _format_currency(budget["freies_budget"]))

    st.subheader(f"Q{budget['quartal']}/{budget['jahr']}")
    st.progress(min(max(budget["verbrauchsquote"], 0), 1))
    st.caption(f"{budget['verbrauchsquote'] * 100:.1f}% verbraucht")


def _render_budget_form():
    """Erfasst ein neues Quartalsbudget über ein schlankes Formular."""
    today = datetime.now()
    default_quarter = (today.month - 1) // 3 + 1

    with st.form("budget_form"):
        quarter = st.selectbox(
            "Quartal",
            [1, 2, 3, 4],
            index=default_quarter - 1,
            format_func=lambda value: f"Q{value}",
        )
        year = st.number_input("Jahr", min_value=2000, max_value=2100, value=today.year, step=1)
        total_budget = st.number_input(
            "Gesamtbudget",
            min_value=0.01,
            value=5000.00,
            step=100.00,
        )
        submitted = st.form_submit_button("Budget anlegen")

    if not submitted:
        return

    result = create_budget(int(quarter), int(year), float(total_budget))
    if result["success"]:
        st.success(
            f"Budget Q{result['quarter']}/{result['year']} wurde angelegt."
        )
    else:
        st.error(result["message"])


def _render_budget_history():
    """Listet bestehende Budgets für schnelle Kontrolle auf."""
    history = get_budget_history()
    st.subheader("Budgethistorie")
    if not history:
        st.info("Noch keine Budgets vorhanden.")
        return

    df = pd.DataFrame(history)
    df["gesamtbudget"] = df["gesamtbudget"].map(_format_currency)
    df["verbrauchtes_budget"] = df["verbrauchtes_budget"].map(_format_currency)
    df["freies_budget"] = df["freies_budget"].map(_format_currency)
    df["verbrauchsquote"] = df["verbrauchsquote"].map(lambda value: f"{value * 100:.1f}%")

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "id": "ID",
            "quartal": "Quartal",
            "jahr": "Jahr",
            "gesamtbudget": "Gesamtbudget",
            "verbrauchtes_budget": "Verbraucht",
            "freies_budget": "Frei",
            "verbrauchsquote": "Verbrauch",
        },
    )


def _format_currency(value):
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
