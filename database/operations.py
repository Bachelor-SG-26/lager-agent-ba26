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
