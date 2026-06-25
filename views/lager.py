import pandas as pd
import streamlit as st

from database.operations import correct_stock
from database.queries import get_inventory_products


def show_lager():
    """Rendert Lagerbestand und manuelle Bestandskorrektur."""
    st.title("Lager")
    st.caption("Bestände, Mindestbestände und Standardlieferanten.")

    only_low_stock = st.toggle("Nur kritische Bestände", value=False)
    products = get_inventory_products(only_low_stock=only_low_stock)

    if not products:
        st.success("Keine kritischen Bestände gefunden.")
        return

    if _render_stock_correction(products):
        products = get_inventory_products(only_low_stock=only_low_stock)

    df = pd.DataFrame(products)
    df["preis_pro_einheit"] = df["preis_pro_einheit"].map(lambda value: f"{value:.2f} €")

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "id": "ID",
            "name": "Produkt",
            "bestand": "Bestand",
            "mindestbestand": "Mindestbestand",
            "preis_pro_einheit": "Preis",
            "lieferant": "Standardlieferant",
            "status": "Status",
        },
    )


def _render_stock_correction(products):
    """Rendert ein Formular für gezählte Bestandskorrekturen."""
    product_options = {
        f"{product['id']} - {product['name']} ({product['bestand']} Stück)": product
        for product in products
    }

    with st.expander("Bestand korrigieren"):
        with st.form("bestand_korrektur_form"):
            selected_label = st.selectbox("Produkt", list(product_options.keys()))
            selected_product = product_options[selected_label]
            new_stock = st.number_input(
                "Gezählter Bestand",
                min_value=0,
                step=1,
                value=int(selected_product["bestand"]),
            )
            reason = st.text_input("Grund", value="Inventur")
            submitted = st.form_submit_button("Bestand speichern")

    if not submitted:
        return False

    result = correct_stock(selected_product["id"], int(new_stock), reason)
    if result["success"]:
        st.success(
            f"Bestand für {result['product_name']} wurde auf {result['new_stock']} gesetzt."
        )
        if result["is_low_stock"]:
            st.warning("Der Bestand liegt unter dem Mindestbestand.")
        return True

    st.error(result["message"])
    return False
