from database.database import db_connection


def get_current_budget():
    """Lädt das neueste Quartalsbudget mit Verbrauch und Restbudget."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT id, quartal, jahr, gesamtbudget, verbrauchtes_budget
            FROM budget
            ORDER BY jahr DESC, quartal DESC
            LIMIT 1
        """)
        budget = cursor.fetchone()

    if not budget:
        return None

    total_budget = budget["gesamtbudget"]
    used_budget = budget["verbrauchtes_budget"]
    usage_ratio = used_budget / total_budget if total_budget else 0

    return {
        "id": budget["id"],
        "quartal": budget["quartal"],
        "jahr": budget["jahr"],
        "gesamtbudget": total_budget,
        "verbrauchtes_budget": used_budget,
        "freies_budget": total_budget - used_budget,
        "verbrauchsquote": usage_ratio,
    }


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

    budget = get_current_budget()
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


def get_inventory_products(only_low_stock=False, limit=0):
    """Lädt Produkte mit Bestand, Mindestbestand und Lieferantenstatus."""
    where_clause = "WHERE p.bestand < p.mindestbestand" if only_low_stock else ""
    limit_clause = "LIMIT ?" if limit and limit > 0 else ""
    params = (limit,) if limit and limit > 0 else ()

    with db_connection() as (_, cursor):
        cursor.execute(f"""
            SELECT
                p.id,
                p.name,
                p.bestand,
                p.mindestbestand,
                p.preis_pro_einheit,
                l.name AS lieferant,
                CASE
                    WHEN p.bestand < p.mindestbestand THEN 'kritisch'
                    ELSE 'ok'
                END AS status
            FROM produkte p
            LEFT JOIN lieferanten l ON l.id = p.standard_lieferant_id
            {where_clause}
            ORDER BY status DESC, p.name ASC
            {limit_clause}
        """, params)
        return [dict(row) for row in cursor.fetchall()]


def get_withdrawal_history(limit=20):
    """Lädt die letzten Entnahmen für die Entnahme-Ansicht."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                v.datum,
                p.name AS produkt,
                v.menge,
                v.grund
            FROM verbrauch v
            JOIN produkte p ON p.id = v.produkt_id
            ORDER BY v.datum DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_order_history(limit=30):
    """Lädt die letzten Bestellungen mit Produkt, Lieferant und Kosten."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                b.bestell_nr,
                b.datum,
                p.name AS produkt,
                l.name AS lieferant,
                b.menge,
                b.gesamtkosten,
                b.status
            FROM bestellungen b
            JOIN produkte p ON p.id = b.produkt_id
            LEFT JOIN lieferanten l ON l.id = b.lieferant_id
            ORDER BY b.datum DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
