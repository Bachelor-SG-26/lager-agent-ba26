import pandas as pd
import streamlit as st

from database.operations import create_order
from database.queries import get_inventory_products, get_order_history


def _format_currency(value):
    return f"{value:.2f} €"


def show_bestellungen():
    """Rendert Bestellformular und Bestellhistorie."""
    st.title("Bestellungen")
    st.caption("Material nachbestellen und Budgetauswirkung direkt prüfen.")

    products = get_inventory_products()
    if not products:
        st.info("Es sind noch keine Produkte vorhanden.")
        return

    product_options = {
        f"{product['name']} ({product['lieferant']})": product
        for product in products
    }

    with st.form("bestellung_form"):
        selected_label = st.selectbox("Produkt", list(product_options.keys()))
        amount = st.number_input("Menge", min_value=1, step=1)
        submitted = st.form_submit_button("Bestellung anlegen")

    if submitted:
        product = product_options[selected_label]
        result = create_order(product["id"], int(amount))
        if result["success"]:
            st.success(
                f"{result['order_number']} wurde angelegt: "
                f"{result['amount']} Stück {result['product_name']}."
            )
            st.caption(f"Kosten: {_format_currency(result['total_cost'])}")
        else:
            st.error(result["message"])

    history = get_order_history()
    st.subheader("Bestellhistorie")
    if not history:
        st.info("Noch keine Bestellungen vorhanden.")
        return

    df = pd.DataFrame(history)
    df["gesamtkosten"] = df["gesamtkosten"].map(_format_currency)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "bestell_nr": "Bestellnummer",
            "datum": "Datum",
            "produkt": "Produkt",
            "lieferant": "Lieferant",
            "menge": "Menge",
            "gesamtkosten": "Kosten",
            "status": "Status",
        },
    )
