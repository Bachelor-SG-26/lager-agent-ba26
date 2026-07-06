from langchain_core.tools import tool
from database.database import db_connection
from services.logger import get_logger
from datetime import datetime
from config import BUDGET_WARNUNG_PROZENT, BUDGET_KRITISCH_PROZENT

logger = get_logger("tools.budget")


@tool
def check_budget() -> str:
    """Zeigt das aktuelle und vergangene Quartalsbudgets mit Verbrauch."""
    try:
        with db_connection() as (conn, cursor):
            jetzt = datetime.now()
            quartal = (jetzt.month - 1) // 3 + 1

            cursor.execute("""
                SELECT quartal, jahr, gesamtbudget, verbrauchtes_budget
                FROM budget
                ORDER BY jahr DESC, quartal DESC
            """)
            budgets = cursor.fetchall()

        if not budgets:
            return "Keine Budgetdaten gefunden."

        ergebnis = "Budget-Übersicht:\n\n"
        for b in budgets:
            verbleibend = b[2] - b[3]
            prozent = (b[3] / b[2]) * 100 if b[2] > 0 else 0
            ist_aktuell = b[0] == quartal and b[1] == jetzt.year
            marker = " [AKTUELL]" if ist_aktuell else ""
            status = (
                "[KRITISCH]" if prozent > BUDGET_KRITISCH_PROZENT
                else "[WARNUNG]" if prozent > BUDGET_WARNUNG_PROZENT
                else "[OK]"
            )

            ergebnis += (
                f"  Q{b[0]}/{b[1]}{marker}:\n"
                f"    Gesamt: {b[2]:.2f} Euro | Verbraucht: {b[3]:.2f} Euro ({prozent:.1f}%) "
                f"| Verbleibend: {verbleibend:.2f} Euro | {status}\n\n"
            )

        return ergebnis
    except Exception as e:
        logger.error("Fehler bei Budget-Abfrage: %s", e)
        return f"Fehler beim Laden des Budgets: {e}"


@tool
def erstelle_budget(quartal: int, jahr: int, gesamtbudget: float) -> str:
    """Legt ein neues Quartalsbudget an.

    Args:
        quartal: Quartal (1-4)
        jahr: Jahr (z.B. 2026)
        gesamtbudget: Gesamtbudget in Euro für das Quartal
    """
    if quartal not in (1, 2, 3, 4):
        return "Fehler: Quartal muss zwischen 1 und 4 liegen."
    if gesamtbudget <= 0:
        return "Fehler: Gesamtbudget muss größer als 0 sein."

    try:
        with db_connection(commit=True) as (conn, cursor):
            cursor.execute(
                "SELECT id FROM budget WHERE quartal = ? AND jahr = ?",
                (quartal, jahr),
            )
            if cursor.fetchone():
                return f"Fehler: Budget für Q{quartal}/{jahr} existiert bereits."

            cursor.execute("""
                INSERT INTO budget (quartal, jahr, gesamtbudget, verbrauchtes_budget)
                VALUES (?, ?, ?, 0)
            """, (quartal, jahr, gesamtbudget))

        logger.info("Budget angelegt: Q%d/%d, %.2f Euro", quartal, jahr, gesamtbudget)

        return (
            f"Budget erfolgreich angelegt.\n"
            f"  Quartal:       Q{quartal}/{jahr}\n"
            f"  Gesamtbudget:  {gesamtbudget:.2f} Euro\n"
            f"  Verbraucht:    0.00 Euro"
        )
    except Exception as e:
        logger.error("Fehler bei Budget-Erstellung: %s", e)
        return f"Fehler beim Anlegen des Budgets: {e}"
