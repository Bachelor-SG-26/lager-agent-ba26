import pandas as pd
import streamlit as st

from database.operations import create_order
from database.queries import (
    get_inventory_products,
    get_order_history,
    get_supplier_options_for_product,
    recommend_supplier,
)


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
        selected_product = product_options[selected_label]
        _, suppliers = get_supplier_options_for_product(selected_product["id"])
        recommendation = recommend_supplier(suppliers)
        supplier_options = {
            (
                f"{supplier['name']} - {_format_currency(supplier['preis'])} - "
                f"{supplier['lieferzeit_tage']} Tage"
            ): supplier
            for supplier in suppliers
        }
        recommended_label = next(
            (
                label
                for label, supplier in supplier_options.items()
                if recommendation and supplier["id"] == recommendation["id"]
            ),
            None,
        )
        selected_supplier_label = st.selectbox(
            "Lieferant",
            list(supplier_options.keys()),
            index=list(supplier_options.keys()).index(recommended_label)
            if recommended_label in supplier_options
            else 0,
        )
        amount = st.number_input("Menge", min_value=1, step=1)
        submitted = st.form_submit_button("Bestellung anlegen")

    if submitted:
        supplier = supplier_options[selected_supplier_label]
        result = create_order(selected_product["id"], int(amount), supplier["id"])
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
