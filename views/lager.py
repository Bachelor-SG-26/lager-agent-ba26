import pandas as pd
import streamlit as st

from database.queries import get_inventory_products


def show_lager():
    st.title("Lager")
    st.caption("Bestände, Mindestbestände und Standardlieferanten.")

    only_low_stock = st.toggle("Nur kritische Bestände", value=False)
    products = get_inventory_products(only_low_stock=only_low_stock)

    if not products:
        st.success("Keine kritischen Bestände gefunden.")
        return

    df = pd.DataFrame(products)
    df["preis_pro_einheit"] = df["preis_pro_einheit"].map(lambda value: f"{value:.2f} €")

    st.dataframe(
        df,
        use_container_width=True,
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
