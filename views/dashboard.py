import streamlit as st


def show_dashboard():
    st.title("Dashboard")
    st.caption("Übersicht für Lagerbestand, Bestellungen und Budget.")

    col_lager, col_bestellungen, col_budget = st.columns(3)
    col_lager.metric("Produkte", "0")
    col_bestellungen.metric("Offene Engpaesse", "0")
    col_budget.metric("Budgetstatus", "Bereit")

    st.info("Die Datenbasis wird im nächsten Schritt eingerichtet.")
