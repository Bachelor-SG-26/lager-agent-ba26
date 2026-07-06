from langchain_core.tools import tool
from database.database import db_connection
from services.logger import get_logger
from datetime import datetime

logger = get_logger("tools.entnahme")


@tool
def erfasse_entnahme(produkt_id: int, menge: int, grund: str = "Produktion") -> str:
    """Erfasst eine Materialentnahme aus dem Lager und reduziert den Bestand.

    Args:
        produkt_id: Die ID des Produkts
        menge: Die entnommene Menge
        grund: Der Grund der Entnahme (z.B. Produktion, Wartung, Montage)
    """
    if menge <= 0:
        return "Fehler: Menge muss größer als 0 sein."

    try:
        with db_connection(commit=True) as (conn, cursor):
            cursor.execute(
                "SELECT name, bestand, mindestbestand FROM produkte WHERE id = ?",
                (produkt_id,),
            )
            produkt = cursor.fetchone()

            if not produkt:
                return f"Fehler: Produkt mit ID {produkt_id} nicht gefunden."

            if menge > produkt[1]:
                return (
                    f"Nicht genug Bestand. "
                    f"Verfügbar: {produkt[1]} Stück, angefragt: {menge} Stück."
                )

            cursor.execute(
                "UPDATE produkte SET bestand = bestand - ? WHERE id = ?",
                (menge, produkt_id),
            )

            datum = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO verbrauch (produkt_id, menge, grund, datum)
                VALUES (?, ?, ?, ?)
            """, (produkt_id, menge, grund, datum))

        neuer_bestand = produkt[1] - menge

        logger.info(
            "Entnahme erfasst: Produkt=%s, Menge=%d, Grund=%s, Neuer Bestand=%d",
            produkt[0], menge, grund, neuer_bestand,
        )

        warnung = ""
        if neuer_bestand < produkt[2]:
            warnung = (
                f"\n  WARNUNG: Bestand ({neuer_bestand}) liegt unter "
                f"Mindestbestand ({produkt[2]}). Nachbestellung empfohlen."
            )
            logger.warning(
                "Bestand kritisch: %s hat %d/%d Stück",
                produkt[0], neuer_bestand, produkt[2],
            )

        return (
            f"Entnahme erfasst.\n"
            f"  Produkt:       {produkt[0]}\n"
            f"  Entnommen:     {menge} Stück\n"
            f"  Grund:         {grund}\n"
            f"  Neuer Bestand: {neuer_bestand} Stück{warnung}"
        )
    except Exception as e:
        logger.error("Fehler bei Entnahme (Produkt=%d, Menge=%d): %s", produkt_id, menge, e)
        return f"Fehler bei der Entnahme: {e}"
