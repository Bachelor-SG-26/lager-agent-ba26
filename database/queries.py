from database.database import db_connection


def get_dashboard_summary():
    with db_connection() as (_, cursor):
        cursor.execute("SELECT COUNT(*) AS count FROM produkte")
        products = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM produkte
            WHERE bestand < mindestbestand
        """)
        low_stock = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT gesamtbudget, verbrauchtes_budget
            FROM budget
            ORDER BY jahr DESC, quartal DESC
            LIMIT 1
        """)
        budget = cursor.fetchone()

    total_budget = budget["gesamtbudget"] if budget else 0
    used_budget = budget["verbrauchtes_budget"] if budget else 0

    return {
        "products": products,
        "low_stock": low_stock,
        "total_budget": total_budget,
        "used_budget": used_budget,
        "free_budget": total_budget - used_budget,
    }


def get_low_stock_products(limit=5):
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                p.name,
                p.bestand,
                p.mindestbestand,
                l.name AS lieferant
            FROM produkte p
            LEFT JOIN lieferanten l ON l.id = p.standard_lieferant_id
            WHERE p.bestand < p.mindestbestand
            ORDER BY (p.mindestbestand - p.bestand) DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
