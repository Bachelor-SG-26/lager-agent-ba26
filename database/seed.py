from datetime import datetime, timedelta


SUPPLIERS = (
    ("Schrauben Müller GmbH", "einkauf@schrauben-mueller.de", 2, 4.7),
    ("Industriebedarf Nord", "service@industriebedarf-nord.de", 4, 4.2),
    ("Normteile Direkt", "kontakt@normteile-direkt.de", 1, 4.4),
    ("Werkzeugtechnik Becker", "vertrieb@becker-technik.de", 5, 4.0),
)

PRODUCTS = (
    ("Sechskantschraube M8x40 verzinkt", 120, 80, 0.18, "Schrauben Müller GmbH"),
    ("Unterlegscheibe M8 Edelstahl", 65, 100, 0.07, "Normteile Direkt"),
    ("Kugellager 6204-2RS", 18, 25, 4.80, "Industriebedarf Nord"),
    ("Hydraulikschlauch DN12", 12, 10, 18.50, "Werkzeugtechnik Becker"),
    ("Sicherheitshandschuhe Größe 9", 34, 30, 3.20, "Industriebedarf Nord"),
    ("Kabelbinder 200 mm schwarz", 420, 250, 0.03, "Normteile Direkt"),
    ("Schmieröl ISO VG 46", 9, 15, 42.00, "Werkzeugtechnik Becker"),
    ("Sensorhalter Aluminium", 22, 20, 6.90, "Schrauben Müller GmbH"),
)


def seed_data(cursor):
    if _table_has_rows(cursor, "produkte"):
        return

    suppliers = _seed_suppliers(cursor)
    products = _seed_products(cursor, suppliers)
    _seed_product_suppliers(cursor, products, suppliers)
    _seed_budget(cursor)
    _seed_consumption(cursor, products)
    _seed_orders(cursor, products, suppliers)


def _table_has_rows(cursor, table):
    cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")
    return cursor.fetchone() is not None


def _seed_suppliers(cursor):
    supplier_ids = {}
    for name, contact, delivery_days, rating in SUPPLIERS:
        cursor.execute("""
            INSERT INTO lieferanten (name, kontakt, lieferzeit_tage, bewertung)
            VALUES (?, ?, ?, ?)
        """, (name, contact, delivery_days, rating))
        supplier_ids[name] = cursor.lastrowid
    return supplier_ids


def _seed_products(cursor, suppliers):
    product_ids = {}
    for name, stock, minimum_stock, price, default_supplier in PRODUCTS:
        cursor.execute("""
            INSERT INTO produkte (
                name, bestand, mindestbestand, preis_pro_einheit, standard_lieferant_id
            )
            VALUES (?, ?, ?, ?, ?)
        """, (name, stock, minimum_stock, price, suppliers[default_supplier]))
        product_ids[name] = cursor.lastrowid
    return product_ids


def _seed_product_suppliers(cursor, products, suppliers):
    for product_name, _, _, price, default_supplier in PRODUCTS:
        product_id = products[product_name]
        default_supplier_id = suppliers[default_supplier]
        cursor.execute("""
            INSERT INTO produkt_lieferanten (produkt_id, lieferant_id, preis, lieferzeit_tage)
            SELECT ?, id, ?, lieferzeit_tage FROM lieferanten WHERE id = ?
        """, (product_id, price, default_supplier_id))

        for supplier_name, supplier_id in suppliers.items():
            if supplier_id == default_supplier_id:
                continue
            alternative_price = round(price * (1.05 + (supplier_id % 3) * 0.04), 2)
            cursor.execute("""
                INSERT INTO produkt_lieferanten (produkt_id, lieferant_id, preis, lieferzeit_tage)
                SELECT ?, id, ?, lieferzeit_tage FROM lieferanten WHERE name = ?
            """, (product_id, alternative_price, supplier_name))


def _seed_budget(cursor):
    today = datetime.now()
    quarter = (today.month - 1) // 3 + 1
    cursor.execute("""
        INSERT INTO budget (quartal, jahr, gesamtbudget, verbrauchtes_budget)
        VALUES (?, ?, ?, ?)
    """, (quarter, today.year, 5000.00, 1180.50))


def _seed_consumption(cursor, products):
    today = datetime.now()
    entries = (
        ("Unterlegscheibe M8 Edelstahl", 40, "Montage", 2),
        ("Kugellager 6204-2RS", 8, "Instandhaltung", 4),
        ("Schmieröl ISO VG 46", 3, "Wartung", 7),
        ("Sechskantschraube M8x40 verzinkt", 60, "Montage", 10),
    )
    for product_name, amount, reason, days_ago in entries:
        date = today - timedelta(days=days_ago)
        cursor.execute("""
            INSERT INTO verbrauch (produkt_id, menge, grund, datum)
            VALUES (?, ?, ?, ?)
        """, (products[product_name], amount, reason, date.strftime("%Y-%m-%d %H:%M:%S")))


def _seed_orders(cursor, products, suppliers):
    today = datetime.now()
    cursor.execute("""
        INSERT INTO bestellungen (
            bestell_nr, produkt_id, lieferant_id, menge, gesamtkosten, status, datum
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        f"BEST-{today.year}-0001",
        products["Kugellager 6204-2RS"],
        suppliers["Industriebedarf Nord"],
        20,
        96.00,
        "angelegt",
        today.strftime("%Y-%m-%d %H:%M:%S"),
    ))
