import pandas as pd
import streamlit as st

from database.operations import create_product, create_supplier, update_product, update_supplier
from database.queries import get_inventory_products, get_suppliers


def show_stammdaten():
    """Rendert Formulare für Produkt- und Lieferantenstammdaten."""
    st.title("Stammdaten")
    st.caption("Produkte und Lieferanten für die Lagerprozesse pflegen.")

    tab_products, tab_suppliers = st.tabs(["Produkte", "Lieferanten"])
    with tab_products:
        _render_product_form()
        _render_product_update_form()
        _render_product_table()

    with tab_suppliers:
        _render_supplier_form()
        _render_supplier_update_form()
        _render_supplier_table()


def _render_product_form():
    suppliers = get_suppliers()
    if not suppliers:
        st.info("Lege zuerst einen Lieferanten an.")
        return

    supplier_options = {supplier["name"]: supplier for supplier in suppliers}
    with st.form("produkt_form"):
        name = st.text_input("Produktname")
        stock = st.number_input("Bestand", min_value=0, step=1)
        minimum_stock = st.number_input("Mindestbestand", min_value=0, step=1)
        unit_price = st.number_input("Preis pro Einheit", min_value=0.01, step=0.01)
        supplier_label = st.selectbox("Standardlieferant", list(supplier_options.keys()))
        submitted = st.form_submit_button("Produkt anlegen")

    if submitted:
        supplier = supplier_options[supplier_label]
        result = create_product(
            name=name,
            stock=int(stock),
            minimum_stock=int(minimum_stock),
            unit_price=float(unit_price),
            supplier_id=supplier["id"],
        )
        if result["success"]:
            st.success(f"{result['name']} wurde angelegt.")
        else:
            st.error(result["message"])


def _render_product_update_form():
    products = get_inventory_products()
    suppliers = get_suppliers()
    if not products or not suppliers:
        return

    product_options = {f"{product['id']} - {product['name']}": product for product in products}
    supplier_options = {supplier["name"]: supplier for supplier in suppliers}

    with st.expander("Produkt bearbeiten"):
        selected_label = st.selectbox("Produkt auswählen", list(product_options.keys()))
        product = product_options[selected_label]
        supplier_names = list(supplier_options.keys())
        current_supplier_index = supplier_names.index(product["lieferant"]) if product["lieferant"] in supplier_options else 0

        with st.form("produkt_update_form"):
            name = st.text_input("Produktname", value=product["name"], key="produkt_update_name")
            stock = st.number_input(
                "Bestand",
                min_value=0,
                step=1,
                value=int(product["bestand"]),
                key="produkt_update_bestand",
            )
            minimum_stock = st.number_input(
                "Mindestbestand",
                min_value=0,
                step=1,
                value=int(product["mindestbestand"]),
                key="produkt_update_mindestbestand",
            )
            unit_price = st.number_input(
                "Preis pro Einheit",
                min_value=0.01,
                step=0.01,
                value=float(product["preis_pro_einheit"]),
                key="produkt_update_preis",
            )
            supplier_label = st.selectbox(
                "Standardlieferant",
                supplier_names,
                index=current_supplier_index,
                key="produkt_update_lieferant",
            )
            submitted = st.form_submit_button("Produkt aktualisieren")

        if submitted:
            supplier = supplier_options[supplier_label]
            result = update_product(
                product_id=product["id"],
                name=name,
                stock=int(stock),
                minimum_stock=int(minimum_stock),
                unit_price=float(unit_price),
                supplier_id=supplier["id"],
            )
            if result["success"]:
                st.success("Produkt wurde aktualisiert.")
            else:
                st.error(result["message"])


def _render_product_table():
    products = get_inventory_products()
    st.subheader("Produkte")
    st.dataframe(
        pd.DataFrame(products),
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


def _render_supplier_form():
    with st.form("lieferant_form"):
        name = st.text_input("Name")
        contact = st.text_input("Kontakt")
        delivery_days = st.number_input("Lieferzeit in Tagen", min_value=0, step=1, value=3)
        rating = st.slider("Bewertung", min_value=1.0, max_value=5.0, value=3.0, step=0.1)
        submitted = st.form_submit_button("Lieferant anlegen")

    if submitted:
        result = create_supplier(
            name=name,
            contact=contact,
            delivery_days=int(delivery_days),
            rating=float(rating),
        )
        if result["success"]:
            st.success(f"{result['name']} wurde angelegt.")
        else:
            st.error(result["message"])


def _render_supplier_update_form():
    suppliers = get_suppliers()
    if not suppliers:
        return

    supplier_options = {f"{supplier['id']} - {supplier['name']}": supplier for supplier in suppliers}
    with st.expander("Lieferant bearbeiten"):
        selected_label = st.selectbox("Lieferant auswählen", list(supplier_options.keys()))
        supplier = supplier_options[selected_label]

        with st.form("lieferant_update_form"):
            name = st.text_input("Name", value=supplier["name"], key="lieferant_update_name")
            contact = st.text_input("Kontakt", value=supplier["kontakt"] or "", key="lieferant_update_kontakt")
            delivery_days = st.number_input(
                "Lieferzeit in Tagen",
                min_value=0,
                step=1,
                value=int(supplier["lieferzeit_tage"]),
                key="lieferant_update_lieferzeit",
            )
            rating = st.slider(
                "Bewertung",
                min_value=1.0,
                max_value=5.0,
                value=float(supplier["bewertung"]),
                step=0.1,
                key="lieferant_update_bewertung",
            )
            submitted = st.form_submit_button("Lieferant aktualisieren")

        if submitted:
            result = update_supplier(
                supplier_id=supplier["id"],
                name=name,
                contact=contact,
                delivery_days=int(delivery_days),
                rating=float(rating),
            )
            if result["success"]:
                st.success("Lieferant wurde aktualisiert.")
            else:
                st.error(result["message"])


def _render_supplier_table():
    suppliers = get_suppliers()
    st.subheader("Lieferanten")
    st.dataframe(
        pd.DataFrame(suppliers),
        width="stretch",
        hide_index=True,
        column_config={
            "id": "ID",
            "name": "Name",
            "kontakt": "Kontakt",
            "lieferzeit_tage": "Lieferzeit",
            "bewertung": "Bewertung",
        },
    )
