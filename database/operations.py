from datetime import datetime

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
