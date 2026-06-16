import pandas as pd
import streamlit as st

from database.operations import record_withdrawal
from database.queries import get_inventory_products, get_withdrawal_history


def show_entnahme():
    """Rendert das Formular zum Erfassen manueller Materialentnahmen."""
    st.title("Entnahme")
    st.caption("Material aus dem Lager buchen und den Verbrauch dokumentieren.")

    products = get_inventory_products()
    if not products:
        st.info("Es sind noch keine Produkte vorhanden.")
        return

    product_options = {
        f"{product['name']} ({product['bestand']} Stück verfügbar)": product
        for product in products
    }

    with st.form("entnahme_form"):
        selected_label = st.selectbox("Produkt", list(product_options.keys()))
        amount = st.number_input("Menge", min_value=1, step=1)
        reason = st.text_input("Grund", value="Produktion")
        submitted = st.form_submit_button("Entnahme erfassen")

    if submitted:
        product = product_options[selected_label]
        result = record_withdrawal(product["id"], int(amount), reason)
        if result["success"]:
            st.success(
                f"{result['amount']} Stück {result['product_name']} wurden entnommen."
            )
            if result["is_low_stock"]:
                st.warning("Der neue Bestand liegt unter dem Mindestbestand.")
        else:
            st.error(result["message"])

    history = get_withdrawal_history()
    st.subheader("Letzte Entnahmen")
    if not history:
        st.info("Noch keine Entnahmen erfasst.")
        return

    st.dataframe(
        pd.DataFrame(history),
        width="stretch",
        hide_index=True,
        column_config={
            "datum": "Datum",
            "produkt": "Produkt",
            "menge": "Menge",
            "grund": "Grund",
        },
    )
