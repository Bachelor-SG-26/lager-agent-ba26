from langchain_core.tools import tool
from database.database import db_connection
from services.logger import get_logger

logger = get_logger("tools.produkte")


@tool
def erstelle_produkt(
    name: str,
    mindestbestand: int,
    preis_pro_einheit: float,
    lieferant_id: int,
) -> str:
    """Legt ein neues Produkt im Lager an.

    Args:
        name: Name des Produkts
        mindestbestand: Mindestbestand ab dem nachbestellt werden soll
        preis_pro_einheit: Preis pro Einheit in Euro
        lieferant_id: ID des Standard-Lieferanten
    """
    if not name.strip():
        return "Fehler: Produktname darf nicht leer sein."
    if mindestbestand < 0:
        return "Fehler: Mindestbestand darf nicht negativ sein."
    if preis_pro_einheit <= 0:
        return "Fehler: Preis muss größer als 0 sein."

    try:
        with db_connection(commit=True) as (conn, cursor):
            cursor.execute("SELECT name FROM lieferanten WHERE id = ?", (lieferant_id,))
            lieferant = cursor.fetchone()
            if not lieferant:
                return f"Fehler: Lieferant mit ID {lieferant_id} nicht gefunden."

            cursor.execute("SELECT id FROM produkte WHERE name = ?", (name,))
            if cursor.fetchone():
                return f"Fehler: Produkt '{name}' existiert bereits."

            cursor.execute("""
                INSERT INTO produkte (name, bestand, mindestbestand, preis_pro_einheit, standard_lieferant_id)
                VALUES (?, 0, ?, ?, ?)
            """, (name, mindestbestand, preis_pro_einheit, lieferant_id))

            produkt_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO produkt_lieferanten (produkt_id, lieferant_id, preis, lieferzeit_tage)
                VALUES (?, ?, ?, ?)
            """, (produkt_id, lieferant_id, preis_pro_einheit, None))

        logger.info("Produkt angelegt: %s (ID=%d)", name, produkt_id)

        return (
            f"Produkt erfolgreich angelegt.\n"
            f"  ID:              {produkt_id}\n"
            f"  Name:            {name}\n"
            f"  Mindestbestand:  {mindestbestand} Stück\n"
            f"  Preis:           {preis_pro_einheit:.2f} Euro/Stück\n"
            f"  Lieferant:       {lieferant[0]}\n"
            f"  Bestand:         0 (Erstbestellung empfohlen)"
        )
    except Exception as e:
        logger.error("Fehler bei Produkt-Erstellung (%s): %s", name, e)
        return f"Fehler beim Anlegen des Produkts: {e}"
