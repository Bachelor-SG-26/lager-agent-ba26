from langchain_core.tools import tool
from database.database import db_connection
from services.logger import get_logger
from config import LAGERBESTAND_DEFAULT_LIMIT, ENGPASS_DEFAULT_LIMIT

logger = get_logger("tools.lager")


@tool
def check_lagerbestand(
    limit: int = LAGERBESTAND_DEFAULT_LIMIT,
    suchbegriff: str = "",
) -> str:
    """Zeigt den Lagerbestand und sucht optional nach einem Produktnamen.

    Args:
        limit: Maximale Anzahl Produkte (Standard: 20, 0 = alle)
        suchbegriff: Optionaler vollständiger oder teilweiser Produktname
    """
    if limit < 0:
        return "Fehler: Limit darf nicht negativ sein."

    produktname = suchbegriff.strip()
    try:
        with db_connection() as (conn, cursor):
            parameter = []
            where = ""
            if produktname:
                where = "WHERE p.name LIKE ? COLLATE NOCASE"
                parameter.append(f"%{produktname}%")

            cursor.execute(
                f"SELECT COUNT(*) FROM produkte p {where}",
                parameter,
            )
            gesamt = cursor.fetchone()[0]

            query = f"""
                SELECT p.id, p.name, p.bestand, p.mindestbestand, p.preis_pro_einheit, l.name
                FROM produkte p
                JOIN lieferanten l ON p.standard_lieferant_id = l.id
                {where}
            """
            query_parameter = list(parameter)
            if produktname:
                query += " ORDER BY CASE WHEN p.name = ? COLLATE NOCASE THEN 0 ELSE 1 END, p.name"
                query_parameter.append(produktname)
            else:
                query += " ORDER BY p.name"
            if limit > 0:
                query += " LIMIT ?"
                query_parameter.append(limit)
            cursor.execute(query, query_parameter)
            produkte = cursor.fetchall()

        if not produkte:
            return f"Keine Produkte für '{produktname}' gefunden."

        angezeigt = len(produkte)
        if produktname:
            ergebnis = f"Produktsuche für '{produktname}' ({angezeigt} von {gesamt} Treffern):\n"
        else:
            ergebnis = f"Lagerbestand ({angezeigt} von {gesamt} Produkten):\n"
        for p in produkte:
            status = "[KRITISCH]" if p[2] < p[3] else "[OK]"
            ergebnis += (
                f"  [ID:{p[0]}] {p[1]}: {p[2]} Stück "
                f"| Min: {p[3]} | {p[4]:.2f} Euro/Stück "
                f"| Lieferant: {p[5]} {status}\n"
            )

        if limit > 0 and angezeigt < gesamt:
            ergebnis += (
                f"\nHinweis: {gesamt - angezeigt} weitere Treffer nicht angezeigt. "
                "Rufe mit limit=0 für alle auf."
            )

        return ergebnis
    except Exception as e:
        logger.error("Fehler bei Lagerbestand-Abfrage: %s", e)
        return f"Fehler beim Laden des Lagerbestands: {e}"


@tool
def check_engpaesse(limit: int = ENGPASS_DEFAULT_LIMIT) -> str:
    """Zeigt Produkte mit kritisch niedrigem Bestand, sortiert nach Dringlichkeit.

    Args:
        limit: Maximale Anzahl Produkte (Standard: 15, 0 = alle)
    """
    try:
        with db_connection() as (conn, cursor):
            cursor.execute(
                "SELECT COUNT(*) FROM produkte WHERE bestand < mindestbestand"
            )
            gesamt = cursor.fetchone()[0]

            query = """
                SELECT p.id, p.name, p.bestand, p.mindestbestand, p.preis_pro_einheit, l.name
                FROM produkte p
                JOIN lieferanten l ON p.standard_lieferant_id = l.id
                WHERE p.bestand < p.mindestbestand
                ORDER BY (p.mindestbestand - p.bestand) DESC
            """
            if limit > 0:
                query += f" LIMIT {limit}"
            cursor.execute(query)
            engpaesse = cursor.fetchall()

        if not engpaesse:
            return "Keine Engpässe — alle Bestände sind ausreichend."

        gesamtkosten = 0
        angezeigt = len(engpaesse)
        ergebnis = f"Engpässe ({angezeigt} von {gesamt}, sortiert nach Dringlichkeit):\n"
        for p in engpaesse:
            fehlmenge = p[3] - p[2]
            kosten = fehlmenge * p[4]
            gesamtkosten += kosten
            ergebnis += (
                f"  [ID:{p[0]}] {p[1]}: {p[2]}/{p[3]} Stück "
                f"(fehlen: {fehlmenge}) | Kosten: {kosten:.2f} Euro | {p[5]}\n"
            )

        ergebnis += f"\nGeschätzte Kosten für angezeigte Nachbestellungen: {gesamtkosten:.2f} Euro"

        if limit > 0 and angezeigt < gesamt:
            ergebnis += f"\nHinweis: {gesamt - angezeigt} weitere Engpässe nicht angezeigt. Rufe mit limit=0 für alle auf."

        return ergebnis
    except Exception as e:
        logger.error("Fehler bei Engpass-Abfrage: %s", e)
        return f"Fehler beim Laden der Engpässe: {e}"
