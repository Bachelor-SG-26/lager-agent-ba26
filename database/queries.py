import math
from datetime import datetime, timedelta

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


def get_budget_history(limit=12):
    """Lädt die letzten Quartalsbudgets inklusive Verbrauchsquote."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                id,
                quartal,
                jahr,
                gesamtbudget,
                verbrauchtes_budget,
                gesamtbudget - verbrauchtes_budget AS freies_budget,
                CASE
                    WHEN gesamtbudget > 0 THEN verbrauchtes_budget / gesamtbudget
                    ELSE 0
                END AS verbrauchsquote
            FROM budget
            ORDER BY jahr DESC, quartal DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_budget_trend(limit=12):
    """Lädt Budgetdaten chronologisch für Auswertungsdiagramme."""
    return list(reversed(get_budget_history(limit=limit)))


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
    inventory_value = get_inventory_value_summary()
    order_summary = get_order_status_summary()
    total_budget = budget["gesamtbudget"] if budget else 0
    used_budget = budget["verbrauchtes_budget"] if budget else 0

    return {
        "products": products,
        "low_stock": low_stock,
        "open_orders": order_summary["open_count"],
        "inventory_value": inventory_value["total_value"],
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


def get_reorder_recommendations(limit=10):
    """Erstellt Nachbestellvorschläge für kritische Bestände."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                p.id AS produkt_id,
                p.name AS produkt,
                p.bestand,
                p.mindestbestand,
                p.mindestbestand - p.bestand AS empfohlene_menge,
                l.name AS lieferant,
                COALESCE(pl.preis, p.preis_pro_einheit) AS preis,
                COALESCE(pl.lieferzeit_tage, l.lieferzeit_tage, 0) AS lieferzeit_tage,
                (p.mindestbestand - p.bestand)
                    * COALESCE(pl.preis, p.preis_pro_einheit) AS geschaetzte_kosten
            FROM produkte p
            LEFT JOIN lieferanten l ON l.id = p.standard_lieferant_id
            LEFT JOIN produkt_lieferanten pl
                ON pl.produkt_id = p.id
                AND pl.lieferant_id = p.standard_lieferant_id
            WHERE p.bestand < p.mindestbestand
            ORDER BY geschaetzte_kosten DESC, empfohlene_menge DESC, p.name ASC
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
                p.bestand * p.preis_pro_einheit AS lagerwert,
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


def get_inventory_value_summary():
    """Berechnet den aktuellen Warenwert des Lagerbestands."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                COUNT(*) AS products,
                COALESCE(SUM(bestand), 0) AS total_units,
                COALESCE(SUM(bestand * preis_pro_einheit), 0) AS total_value,
                COALESCE(SUM(
                    CASE
                        WHEN bestand < mindestbestand THEN bestand * preis_pro_einheit
                        ELSE 0
                    END
                ), 0) AS critical_value,
                COALESCE(AVG(preis_pro_einheit), 0) AS average_unit_price
            FROM produkte
        """)
        summary = cursor.fetchone()

    return {
        "products": summary["products"],
        "total_units": summary["total_units"],
        "total_value": summary["total_value"],
        "critical_value": summary["critical_value"],
        "average_unit_price": summary["average_unit_price"],
    }


def get_suppliers():
    """Lädt alle Lieferanten für Formulare und Stammdatenlisten."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT id, name, kontakt, lieferzeit_tage, bewertung
            FROM lieferanten
            ORDER BY name ASC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_supplier_overview():
    """Lädt Lieferanten mit Produktabdeckung und bisherigen Bestellungen."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                l.id,
                l.name,
                l.kontakt,
                l.lieferzeit_tage,
                l.bewertung,
                (
                    SELECT COUNT(*)
                    FROM produkt_lieferanten pl
                    WHERE pl.lieferant_id = l.id
                ) AS produktanzahl,
                (
                    SELECT COALESCE(AVG(pl.preis), 0)
                    FROM produkt_lieferanten pl
                    WHERE pl.lieferant_id = l.id
                ) AS durchschnittspreis,
                (
                    SELECT COUNT(*)
                    FROM bestellungen b
                    WHERE b.lieferant_id = l.id
                ) AS bestellungen
            FROM lieferanten l
            ORDER BY l.bewertung DESC, l.lieferzeit_tage ASC, l.name ASC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_supplier_options_for_product(product_id):
    """Lädt alle Lieferantenoptionen für ein Produkt inklusive Bewertung."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT name
            FROM produkte
            WHERE id = ?
        """, (product_id,))
        product = cursor.fetchone()
        if not product:
            return None, []

        cursor.execute("""
            SELECT
                l.id,
                l.name,
                l.lieferzeit_tage,
                l.bewertung,
                pl.preis,
                CASE
                    WHEN p.standard_lieferant_id = l.id THEN 1
                    ELSE 0
                END AS ist_standard
            FROM produkt_lieferanten pl
            JOIN lieferanten l ON l.id = pl.lieferant_id
            JOIN produkte p ON p.id = pl.produkt_id
            WHERE pl.produkt_id = ?
            ORDER BY pl.preis ASC, l.lieferzeit_tage ASC, l.bewertung DESC
        """, (product_id,))
        suppliers = [dict(row) for row in cursor.fetchall()]

    return product["name"], suppliers


def recommend_supplier(suppliers):
    """Wählt aus Lieferantenoptionen den besten Kompromiss aus."""
    if not suppliers:
        return None

    min_price = min(supplier["preis"] for supplier in suppliers)
    max_delivery = max(supplier["lieferzeit_tage"] for supplier in suppliers) or 1

    ranked = []
    for supplier in suppliers:
        price_score = min_price / supplier["preis"] if supplier["preis"] else 0
        delivery_score = 1 - ((supplier["lieferzeit_tage"] - 1) / max_delivery)
        rating_score = supplier["bewertung"] / 5
        score = (price_score * 0.45) + (delivery_score * 0.30) + (rating_score * 0.25)
        ranked.append({**supplier, "score": score})

    return max(ranked, key=lambda supplier: supplier["score"])


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


def get_order_cost_trend(history_days=180):
    """Fasst Bestellanzahl und Kosten pro Monat zusammen."""
    since = (datetime.now() - timedelta(days=history_days)).strftime("%Y-%m-%d %H:%M:%S")
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                strftime('%Y-%m', datum) AS monat,
                COUNT(*) AS bestellungen,
                COALESCE(SUM(gesamtkosten), 0) AS gesamtkosten
            FROM bestellungen
            WHERE datum >= ?
            GROUP BY strftime('%Y-%m', datum)
            ORDER BY monat ASC
        """, (since,))
        return [dict(row) for row in cursor.fetchall()]


def get_order_cost_summary(history_days=180):
    """Berechnet kompakte Kennzahlen für Bestellungen im Zeitraum."""
    trend = get_order_cost_trend(history_days=history_days)
    order_count = sum(row["bestellungen"] for row in trend)
    total_cost = sum(row["gesamtkosten"] for row in trend)

    return {
        "bestellungen": order_count,
        "gesamtkosten": total_cost,
        "durchschnittskosten": total_cost / order_count if order_count else 0,
    }


def get_order_status_summary():
    """Fasst Bestellungen nach Status und offenem Bestellwert zusammen."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT status, COUNT(*) AS count, COALESCE(SUM(gesamtkosten), 0) AS total_cost
            FROM bestellungen
            GROUP BY status
        """)
        rows = [dict(row) for row in cursor.fetchall()]

    by_status = {
        row["status"]: {
            "count": row["count"],
            "total_cost": row["total_cost"],
        }
        for row in rows
    }
    open_statuses = ("angelegt", "bestellt")
    return {
        "by_status": by_status,
        "open_count": sum(by_status.get(status, {}).get("count", 0) for status in open_statuses),
        "open_cost": sum(by_status.get(status, {}).get("total_cost", 0) for status in open_statuses),
    }


def get_open_orders(limit=10):
    """Lädt Bestellungen, die noch nicht geliefert oder storniert sind."""
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
            WHERE b.status IN ('angelegt', 'bestellt')
            ORDER BY b.datum ASC, b.id ASC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_activity_log(limit=50):
    """Lädt die letzten protokollierten Lageraktionen."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT bereich, beschreibung, referenz, erstellt_am
            FROM aktivitaeten
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_consumption_by_product(history_days=90, limit=10):
    """Fasst den Verbrauch der letzten Tage pro Produkt zusammen."""
    since = (datetime.now() - timedelta(days=history_days)).strftime("%Y-%m-%d %H:%M:%S")
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT
                p.id,
                p.name AS produkt,
                SUM(v.menge) AS verbrauch,
                COUNT(v.id) AS buchungen
            FROM verbrauch v
            JOIN produkte p ON p.id = v.produkt_id
            WHERE v.datum >= ?
            GROUP BY p.id, p.name
            ORDER BY verbrauch DESC
            LIMIT ?
        """, (since, limit))
        return [dict(row) for row in cursor.fetchall()]


def forecast_product_demand(product_id, days_ahead=30, history_days=90):
    """Berechnet eine einfache Bedarfsprognose aus historischem Verbrauch."""
    with db_connection() as (_, cursor):
        cursor.execute("""
            SELECT id, name, bestand, mindestbestand
            FROM produkte
            WHERE id = ?
        """, (product_id,))
        product = cursor.fetchone()
        if not product:
            return None

        since = (datetime.now() - timedelta(days=history_days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            SELECT COALESCE(SUM(menge), 0) AS verbrauch
            FROM verbrauch
            WHERE produkt_id = ? AND datum >= ?
        """, (product_id, since))
        total_consumption = cursor.fetchone()["verbrauch"]

    daily_consumption = total_consumption / history_days if history_days > 0 else 0
    forecast_amount = math.ceil(daily_consumption * days_ahead)
    coverage_days = None
    if daily_consumption > 0:
        coverage_days = math.floor(product["bestand"] / daily_consumption)

    recommended_order = max(
        0,
        product["mindestbestand"] + forecast_amount - product["bestand"],
    )

    return {
        "product_id": product["id"],
        "product_name": product["name"],
        "stock": product["bestand"],
        "minimum_stock": product["mindestbestand"],
        "history_days": history_days,
        "days_ahead": days_ahead,
        "total_consumption": total_consumption,
        "daily_consumption": daily_consumption,
        "forecast_amount": forecast_amount,
        "coverage_days": coverage_days,
        "recommended_order": recommended_order,
    }


def get_forecast_overview(days_ahead=30, history_days=90, limit=20):
    """Erstellt Prognosen für mehrere Produkte und sortiert nach Bestellbedarf."""
    products = get_inventory_products(limit=limit)
    forecasts = [
        forecast_product_demand(product["id"], days_ahead, history_days)
        for product in products
    ]
    return sorted(
        [forecast for forecast in forecasts if forecast],
        key=lambda forecast: (forecast["recommended_order"], forecast["forecast_amount"]),
        reverse=True,
    )
