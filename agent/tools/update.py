from langchain_core.tools import tool
from database.database import db_connection
from services.logger import get_logger

logger = get_logger("tools.update")


@tool
def aktualisiere_produkt(
    produkt_id: int,
    name: str = None,
    mindestbestand: int = None,
    preis_pro_einheit: float = None,
    bestand: int = None,
) -> str:
    """Aktualisiert ein bestehendes Produkt. Nur angegebene Felder werden geändert.

    Args:
        produkt_id: Die ID des Produkts
        name: Neuer Produktname (optional)
        mindestbestand: Neuer Mindestbestand (optional)
        preis_pro_einheit: Neuer Preis pro Einheit in Euro (optional)
        bestand: Neuer Bestand (optional, nur für Korrekturen)
    """
    if name is not None and not name.strip():
        return "Fehler: Produktname darf nicht leer sein."
    if mindestbestand is not None and mindestbestand < 0:
        return "Fehler: Mindestbestand darf nicht negativ sein."
    if preis_pro_einheit is not None and preis_pro_einheit <= 0:
        return "Fehler: Preis muss groesser als 0 sein."
    if bestand is not None and bestand < 0:
        return "Fehler: Bestand darf nicht negativ sein."

    try:
        with db_connection(commit=True) as (conn, cursor):
            cursor.execute(
                "SELECT name, bestand, mindestbestand, preis_pro_einheit FROM produkte WHERE id = ?",
                (produkt_id,),
            )
            produkt = cursor.fetchone()

            if not produkt:
                return f"Fehler: Produkt mit ID {produkt_id} nicht gefunden."

            aenderungen = []
            params = []

            if name is not None:
                cursor.execute("SELECT id FROM produkte WHERE name = ? AND id != ?", (name, produkt_id))
                if cursor.fetchone():
                    return f"Fehler: Produkt '{name}' existiert bereits."
                aenderungen.append("name = ?")
                params.append(name)

            if mindestbestand is not None:
                aenderungen.append("mindestbestand = ?")
                params.append(mindestbestand)

            if preis_pro_einheit is not None:
                aenderungen.append("preis_pro_einheit = ?")
                params.append(preis_pro_einheit)

            if bestand is not None:
                aenderungen.append("bestand = ?")
                params.append(bestand)

            if not aenderungen:
                return "Keine Änderungen angegeben."

            params.append(produkt_id)
            sql = f"UPDATE produkte SET {', '.join(aenderungen)} WHERE id = ?"
            cursor.execute(sql, params)

        geaendert = []
        if name is not None:
            geaendert.append(f"  Name:            {produkt[0]} -> {name}")
        if bestand is not None:
            geaendert.append(f"  Bestand:         {produkt[1]} -> {bestand}")
        if mindestbestand is not None:
            geaendert.append(f"  Mindestbestand:  {produkt[2]} -> {mindestbestand}")
        if preis_pro_einheit is not None:
            geaendert.append(f"  Preis:           {produkt[3]:.2f} -> {preis_pro_einheit:.2f} Euro")

        logger.info("Produkt aktualisiert: ID=%d, Felder=%s", produkt_id, ", ".join(aenderungen))

        return (
            f"Produkt '{produkt[0]}' (ID: {produkt_id}) aktualisiert.\n"
            + "\n".join(geaendert)
        )
    except Exception as e:
        logger.error("Fehler bei Produkt-Update (ID=%d): %s", produkt_id, e)
        return f"Fehler beim Aktualisieren des Produkts: {e}"


@tool
def aktualisiere_lieferant(
    lieferant_id: int,
    name: str = None,
    kontakt: str = None,
    lieferzeit_tage: int = None,
    bewertung: float = None,
) -> str:
    """Aktualisiert einen bestehenden Lieferanten. Nur angegebene Felder werden geändert.

    Args:
        lieferant_id: Die ID des Lieferanten
        name: Neuer Name (optional)
        kontakt: Neue Kontakt-Email (optional)
        lieferzeit_tage: Neue Lieferzeit in Tagen (optional)
        bewertung: Neue Bewertung von 1.0 bis 5.0 (optional)
    """
    if bewertung is not None and not 1.0 <= bewertung <= 5.0:
        return "Fehler: Bewertung muss zwischen 1.0 und 5.0 liegen."
    if lieferzeit_tage is not None and lieferzeit_tage < 0:
        return "Fehler: Lieferzeit darf nicht negativ sein."
    if name is not None and not name.strip():
        return "Fehler: Lieferantenname darf nicht leer sein."

    try:
        with db_connection(commit=True) as (conn, cursor):
            cursor.execute(
                "SELECT name, kontakt, lieferzeit_tage, bewertung FROM lieferanten WHERE id = ?",
                (lieferant_id,),
            )
            lieferant = cursor.fetchone()

            if not lieferant:
                return f"Fehler: Lieferant mit ID {lieferant_id} nicht gefunden."

            aenderungen = []
            params = []

            if name is not None:
                cursor.execute("SELECT id FROM lieferanten WHERE name = ? AND id != ?", (name, lieferant_id))
                if cursor.fetchone():
                    return f"Fehler: Lieferant '{name}' existiert bereits."
                aenderungen.append("name = ?")
                params.append(name)

            if kontakt is not None:
                aenderungen.append("kontakt = ?")
                params.append(kontakt)

            if lieferzeit_tage is not None:
                aenderungen.append("lieferzeit_tage = ?")
                params.append(lieferzeit_tage)

            if bewertung is not None:
                aenderungen.append("bewertung = ?")
                params.append(bewertung)

            if not aenderungen:
                return "Keine Änderungen angegeben."

            params.append(lieferant_id)
            sql = f"UPDATE lieferanten SET {', '.join(aenderungen)} WHERE id = ?"
            cursor.execute(sql, params)

        geaendert = []
        if name is not None:
            geaendert.append(f"  Name:        {lieferant[0]} -> {name}")
        if kontakt is not None:
            geaendert.append(f"  Kontakt:     {lieferant[1]} -> {kontakt}")
        if lieferzeit_tage is not None:
            geaendert.append(f"  Lieferzeit:  {lieferant[2]} -> {lieferzeit_tage} Tage")
        if bewertung is not None:
            geaendert.append(f"  Bewertung:   {lieferant[3]:.1f} -> {bewertung:.1f}/5.0")

        logger.info("Lieferant aktualisiert: ID=%d, Felder=%s", lieferant_id, ", ".join(aenderungen))

        return (
            f"Lieferant '{lieferant[0]}' (ID: {lieferant_id}) aktualisiert.\n"
            + "\n".join(geaendert)
        )
    except Exception as e:
        logger.error("Fehler bei Lieferant-Update (ID=%d): %s", lieferant_id, e)
        return f"Fehler beim Aktualisieren des Lieferanten: {e}"
