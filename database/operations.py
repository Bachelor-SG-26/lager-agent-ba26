from datetime import datetime
import sqlite3

from database.database import db_connection


def record_withdrawal(product_id, amount, reason="Produktion"):
    """Erfasst eine Entnahme und reduziert den Lagerbestand atomar."""
    if amount <= 0:
        return {
            "success": False,
            "message": "Die Entnahmemenge muss größer als 0 sein.",
        }

    reason = (reason or "Produktion").strip() or "Produktion"

    with db_connection(commit=True) as (_, cursor):
        cursor.execute("""
            SELECT id, name, bestand, mindestbestand
            FROM produkte
            WHERE id = ?
        """, (product_id,))
        product = cursor.fetchone()

        if not product:
            return {
                "success": False,
                "message": f"Produkt mit ID {product_id} wurde nicht gefunden.",
            }

        if amount > product["bestand"]:
            return {
                "success": False,
                "message": (
                    f"Nicht genug Bestand für {product['name']}: "
                    f"{product['bestand']} Stück verfügbar."
                ),
            }

        new_stock = product["bestand"] - amount
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            "UPDATE produkte SET bestand = ? WHERE id = ?",
            (new_stock, product_id),
        )
        cursor.execute("""
            INSERT INTO verbrauch (produkt_id, menge, grund, datum)
            VALUES (?, ?, ?, ?)
        """, (product_id, amount, reason, date))

    return {
        "success": True,
        "product_id": product_id,
        "product_name": product["name"],
        "amount": amount,
        "reason": reason,
        "old_stock": product["bestand"],
        "new_stock": new_stock,
        "minimum_stock": product["mindestbestand"],
        "is_low_stock": new_stock < product["mindestbestand"],
    }


def create_budget(quarter, year, total_budget):
    """Legt ein neues Quartalsbudget an und verhindert doppelte Einträge."""
    if quarter not in (1, 2, 3, 4):
        return {
            "success": False,
            "message": "Das Quartal muss zwischen 1 und 4 liegen.",
        }

    if year < 2000:
        return {
            "success": False,
            "message": "Das Jahr ist ungültig.",
        }

    if total_budget <= 0:
        return {
            "success": False,
            "message": "Das Budget muss größer als 0 sein.",
        }

    try:
        with db_connection(commit=True) as (_, cursor):
            cursor.execute("""
                INSERT INTO budget (quartal, jahr, gesamtbudget, verbrauchtes_budget)
                VALUES (?, ?, ?, 0)
            """, (quarter, year, total_budget))
    except sqlite3.IntegrityError:
        return {
            "success": False,
            "message": f"Für Q{quarter}/{year} ist bereits ein Budget vorhanden.",
        }

    return {
        "success": True,
        "quarter": quarter,
        "year": year,
        "total_budget": total_budget,
    }


def create_supplier(name, contact="", delivery_days=3, rating=3.0):
    """Legt einen Lieferanten mit Basisbewertung und Lieferzeit an."""
    name = (name or "").strip()
    contact = (contact or "").strip()

    if not name:
        return {
            "success": False,
            "message": "Der Lieferantenname darf nicht leer sein.",
        }

    if delivery_days < 0:
        return {
            "success": False,
            "message": "Die Lieferzeit darf nicht negativ sein.",
        }

    if rating < 1 or rating > 5:
        return {
            "success": False,
            "message": "Die Bewertung muss zwischen 1 und 5 liegen.",
        }

    try:
        with db_connection(commit=True) as (_, cursor):
            cursor.execute("""
                INSERT INTO lieferanten (name, kontakt, lieferzeit_tage, bewertung)
                VALUES (?, ?, ?, ?)
            """, (name, contact, delivery_days, rating))
            supplier_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return {
            "success": False,
            "message": f"Der Lieferant {name} ist bereits vorhanden.",
        }

    return {
        "success": True,
        "supplier_id": supplier_id,
        "name": name,
        "contact": contact,
        "delivery_days": delivery_days,
        "rating": rating,
    }


def create_product(
    name,
    stock,
    minimum_stock,
    unit_price,
    supplier_id,
    supplier_price=None,
    supplier_delivery_days=None,
):
    """Legt ein Produkt an und verknüpft es mit einem Standardlieferanten."""
    name = (name or "").strip()
    if not name:
        return {
            "success": False,
            "message": "Der Produktname darf nicht leer sein.",
        }

    if stock < 0 or minimum_stock < 0:
        return {
            "success": False,
            "message": "Bestand und Mindestbestand dürfen nicht negativ sein.",
        }

    if unit_price <= 0:
        return {
            "success": False,
            "message": "Der Preis muss größer als 0 sein.",
        }

    supplier_price = unit_price if supplier_price is None else supplier_price
    if supplier_price <= 0:
        return {
            "success": False,
            "message": "Der Lieferantenpreis muss größer als 0 sein.",
        }

    try:
        with db_connection(commit=True) as (_, cursor):
            cursor.execute("SELECT lieferzeit_tage FROM lieferanten WHERE id = ?", (supplier_id,))
            supplier = cursor.fetchone()
            if not supplier:
                return {
                    "success": False,
                    "message": f"Lieferant mit ID {supplier_id} wurde nicht gefunden.",
                }

            delivery_days = supplier_delivery_days or supplier["lieferzeit_tage"]
            cursor.execute("""
                INSERT INTO produkte (
                    name, bestand, mindestbestand, preis_pro_einheit, standard_lieferant_id
                )
                VALUES (?, ?, ?, ?, ?)
            """, (name, stock, minimum_stock, unit_price, supplier_id))
            product_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO produkt_lieferanten (
                    produkt_id, lieferant_id, preis, lieferzeit_tage
                )
                VALUES (?, ?, ?, ?)
            """, (product_id, supplier_id, supplier_price, delivery_days))
    except sqlite3.IntegrityError:
        return {
            "success": False,
            "message": f"Das Produkt {name} ist bereits vorhanden.",
        }

    return {
        "success": True,
        "product_id": product_id,
        "name": name,
        "stock": stock,
        "minimum_stock": minimum_stock,
        "unit_price": unit_price,
        "supplier_id": supplier_id,
    }


def update_supplier(supplier_id, name=None, contact=None, delivery_days=None, rating=None):
    """Aktualisiert Lieferantendaten ohne bestehende Produktzuordnungen zu verlieren."""
    changes = {}
    if name is not None:
        name = name.strip()
        if not name:
            return {"success": False, "message": "Der Lieferantenname darf nicht leer sein."}
        changes["name"] = name

    if contact is not None:
        changes["kontakt"] = contact.strip()

    if delivery_days is not None:
        if delivery_days < 0:
            return {"success": False, "message": "Die Lieferzeit darf nicht negativ sein."}
        changes["lieferzeit_tage"] = delivery_days

    if rating is not None:
        if rating < 1 or rating > 5:
            return {"success": False, "message": "Die Bewertung muss zwischen 1 und 5 liegen."}
        changes["bewertung"] = rating

    if not changes:
        return {"success": False, "message": "Es wurden keine Änderungen übergeben."}

    try:
        with db_connection(commit=True) as (_, cursor):
            cursor.execute("SELECT id FROM lieferanten WHERE id = ?", (supplier_id,))
            if not cursor.fetchone():
                return {
                    "success": False,
                    "message": f"Lieferant mit ID {supplier_id} wurde nicht gefunden.",
                }

            assignments = ", ".join(f"{column} = ?" for column in changes)
            values = list(changes.values()) + [supplier_id]
            cursor.execute(f"UPDATE lieferanten SET {assignments} WHERE id = ?", values)
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Ein Lieferant mit diesem Namen existiert bereits."}

    return {
        "success": True,
        "supplier_id": supplier_id,
        "changed_fields": sorted(changes.keys()),
    }


def update_product(
    product_id,
    name=None,
    stock=None,
    minimum_stock=None,
    unit_price=None,
    supplier_id=None,
):
    """Aktualisiert Produktstammdaten und hält die Lieferantenverknüpfung konsistent."""
    changes = {}
    if name is not None:
        name = name.strip()
        if not name:
            return {"success": False, "message": "Der Produktname darf nicht leer sein."}
        changes["name"] = name

    if stock is not None:
        if stock < 0:
            return {"success": False, "message": "Der Bestand darf nicht negativ sein."}
        changes["bestand"] = stock

    if minimum_stock is not None:
        if minimum_stock < 0:
            return {"success": False, "message": "Der Mindestbestand darf nicht negativ sein."}
        changes["mindestbestand"] = minimum_stock

    if unit_price is not None:
        if unit_price <= 0:
            return {"success": False, "message": "Der Preis muss größer als 0 sein."}
        changes["preis_pro_einheit"] = unit_price

    if supplier_id is not None:
        changes["standard_lieferant_id"] = supplier_id

    if not changes:
        return {"success": False, "message": "Es wurden keine Änderungen übergeben."}

    try:
        with db_connection(commit=True) as (_, cursor):
            cursor.execute("""
                SELECT id, preis_pro_einheit, standard_lieferant_id
                FROM produkte
                WHERE id = ?
            """, (product_id,))
            product = cursor.fetchone()
            if not product:
                return {
                    "success": False,
                    "message": f"Produkt mit ID {product_id} wurde nicht gefunden.",
                }

            selected_supplier_id = supplier_id or product["standard_lieferant_id"]
            if supplier_id is not None:
                cursor.execute("SELECT lieferzeit_tage FROM lieferanten WHERE id = ?", (supplier_id,))
                supplier = cursor.fetchone()
                if not supplier:
                    return {
                        "success": False,
                        "message": f"Lieferant mit ID {supplier_id} wurde nicht gefunden.",
                    }
                supplier_delivery_days = supplier["lieferzeit_tage"]
            else:
                supplier_delivery_days = None

            assignments = ", ".join(f"{column} = ?" for column in changes)
            values = list(changes.values()) + [product_id]
            cursor.execute(f"UPDATE produkte SET {assignments} WHERE id = ?", values)

            if supplier_id is not None:
                cursor.execute("""
                    INSERT OR IGNORE INTO produkt_lieferanten (
                        produkt_id, lieferant_id, preis, lieferzeit_tage
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    product_id,
                    supplier_id,
                    unit_price or product["preis_pro_einheit"],
                    supplier_delivery_days,
                ))

            if unit_price is not None and selected_supplier_id is not None:
                cursor.execute("""
                    UPDATE produkt_lieferanten
                    SET preis = ?
                    WHERE produkt_id = ? AND lieferant_id = ?
                """, (unit_price, product_id, selected_supplier_id))
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Ein Produkt mit diesem Namen existiert bereits."}

    return {
        "success": True,
        "product_id": product_id,
        "changed_fields": sorted(changes.keys()),
    }


def create_order(product_id, amount, supplier_id=None):
    """Legt eine Bestellung an, erhöht den Bestand und belastet das Budget."""
    if amount <= 0:
        return {
            "success": False,
            "message": "Die Bestellmenge muss größer als 0 sein.",
        }

    with db_connection(commit=True) as (_, cursor):
        product, error = _load_order_product(cursor, product_id, supplier_id)
        if error:
            return {"success": False, "message": error}

        total_cost = amount * product["price"]
        budget, error = _load_available_budget(cursor, total_cost)
        if error:
            return {"success": False, "message": error}

        order_number = _next_order_number(cursor)
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO bestellungen (
                bestell_nr, produkt_id, lieferant_id, menge, gesamtkosten, status, datum
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            order_number,
            product_id,
            product["supplier_id"],
            amount,
            total_cost,
            "angelegt",
            date,
        ))
        cursor.execute(
            "UPDATE produkte SET bestand = bestand + ? WHERE id = ?",
            (amount, product_id),
        )
        cursor.execute(
            "UPDATE budget SET verbrauchtes_budget = verbrauchtes_budget + ? WHERE id = ?",
            (total_cost, budget["id"]),
        )

    return {
        "success": True,
        "order_number": order_number,
        "product_name": product["name"],
        "supplier_name": product["supplier_name"],
        "amount": amount,
        "total_cost": total_cost,
        "new_stock": product["stock"] + amount,
        "free_budget": budget["free_budget"] - total_cost,
    }


def _load_order_product(cursor, product_id, supplier_id=None):
    cursor.execute("""
        SELECT id, name, bestand, standard_lieferant_id
        FROM produkte
        WHERE id = ?
    """, (product_id,))
    product = cursor.fetchone()
    if not product:
        return None, f"Produkt mit ID {product_id} wurde nicht gefunden."

    selected_supplier_id = supplier_id or product["standard_lieferant_id"]
    if not selected_supplier_id:
        return None, f"Für {product['name']} ist kein Standardlieferant hinterlegt."

    cursor.execute("""
        SELECT l.id, l.name, pl.preis
        FROM produkt_lieferanten pl
        JOIN lieferanten l ON l.id = pl.lieferant_id
        WHERE pl.produkt_id = ? AND pl.lieferant_id = ?
    """, (product_id, selected_supplier_id))
    supplier = cursor.fetchone()
    if not supplier:
        return None, "Der gewählte Lieferant ist für dieses Produkt nicht hinterlegt."

    return {
        "name": product["name"],
        "stock": product["bestand"],
        "supplier_id": supplier["id"],
        "supplier_name": supplier["name"],
        "price": supplier["preis"],
    }, None


def _load_available_budget(cursor, total_cost):
    cursor.execute("""
        SELECT id, gesamtbudget, verbrauchtes_budget
        FROM budget
        ORDER BY jahr DESC, quartal DESC
        LIMIT 1
    """)
    budget = cursor.fetchone()
    if not budget:
        return None, "Es ist kein Budget hinterlegt."

    free_budget = budget["gesamtbudget"] - budget["verbrauchtes_budget"]
    if total_cost > free_budget:
        return None, (
            f"Budget überschritten: {total_cost:.2f} € benötigt, "
            f"aber nur {free_budget:.2f} € frei."
        )

    return {
        "id": budget["id"],
        "free_budget": free_budget,
    }, None


def _next_order_number(cursor):
    year = datetime.now().year
    cursor.execute("""
        SELECT MAX(CAST(SUBSTR(bestell_nr, 11) AS INTEGER)) AS number
        FROM bestellungen
        WHERE bestell_nr LIKE ?
    """, (f"BEST-{year}-%",))
    last_number = cursor.fetchone()["number"] or 0
    return f"BEST-{year}-{last_number + 1:04d}"
