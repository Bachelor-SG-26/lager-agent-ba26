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
