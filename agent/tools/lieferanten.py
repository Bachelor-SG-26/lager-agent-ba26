from collections import Counter

from langchain_core.tools import tool
from database.database import db_connection
from services.logger import get_logger
from config import (
    LIEFERANT_GEWICHT_PREIS,
    LIEFERANT_GEWICHT_LIEFERZEIT,
    LIEFERANT_GEWICHT_BEWERTUNG,
    BATCH_DEFAULT_MAX_POSITIONEN,
)

logger = get_logger("tools.lieferanten")


# ─────────────────────────────────────────
#  Hilfsfunktionen
# ─────────────────────────────────────────


def _berechne_beste_empfehlung(lieferanten):
    """Berechnet den besten Lieferanten nach gewichteter Bewertung."""
    max_preis = max(x[1] for x in lieferanten)
    max_zeit = max(x[2] for x in lieferanten)

    best_score = -1
    best_name = lieferanten[0][0]

    for l in lieferanten:
        if len(lieferanten) > 1 and max_preis > 0:
            preis_score = 1 - (l[1] / max_preis)
        else:
            preis_score = 1.0
        if len(lieferanten) > 1 and max_zeit > 0:
            zeit_score = 1 - (l[2] / max_zeit)
        else:
            zeit_score = 1.0
        bewertung_score = l[3] / 5.0

        score = (preis_score * LIEFERANT_GEWICHT_PREIS
                + zeit_score * LIEFERANT_GEWICHT_LIEFERZEIT
                + bewertung_score * LIEFERANT_GEWICHT_BEWERTUNG)
        if score > best_score:
            best_score = score
            best_name = l[0]

    return best_name


def _formatiere_vergleich(produkt_name, lieferanten):
    """Formatiert die Lieferanten-Vergleichstabelle als Text."""
    guenstigster = lieferanten[0][2]

    ergebnis = f"Lieferantenvergleich für '{produkt_name}':\n\n"
    ergebnis += f"  {'ID':>3} {'Lieferant':<20} {'Preis':>8} {'Lieferzeit':>12} {'Bewertung':>10}  Status\n"
    ergebnis += f"  {'-' * 74}\n"

    for l in lieferanten:
        if l[5]:
            marker = "Standard"
        elif l[2] == guenstigster:
            marker = "Günstigster"
        else:
            marker = ""
        ergebnis += (
            f"  {l[0]:>3} {l[1]:<20} {l[2]:>6.2f} E {l[3]:>9} Tage "
            f"{l[4]:>8.1f}/5.0  {marker}\n"
        )

    bewertungsdaten = [
        (l[1], l[2], l[3], l[4], bool(l[5]))
        for l in lieferanten
    ]
    best_name = _berechne_beste_empfehlung(bewertungsdaten)
    best_id = next(l[0] for l in lieferanten if l[1] == best_name)
    ergebnis += (
        f"\n  Empfehlung: {best_name} "
        f"(ID: {best_id}, bestes Preis-Leistungs-Verhältnis)"
    )
    return ergebnis


# ─────────────────────────────────────────
#  Tools
# ─────────────────────────────────────────


@tool
def check_lieferanten(suchbegriff: str = "", limit: int = 20) -> str:
    """Listet vorhandene Lieferanten mit ID auf und filtert optional nach Namen.

    Args:
        suchbegriff: Optionaler vollständiger oder teilweiser Lieferantenname
        limit: Maximale Anzahl Ergebnisse, 0 liefert alle Treffer
    """
    if limit < 0:
        return "Fehler: Limit darf nicht negativ sein."

    try:
        with db_connection() as (conn, cursor):
            parameter = []
            where = ""
            if suchbegriff.strip():
                where = "WHERE name LIKE ? COLLATE NOCASE"
                parameter.append(f"%{suchbegriff.strip()}%")

            limit_sql = ""
            if limit > 0:
                limit_sql = "LIMIT ?"
                parameter.append(limit)

            cursor.execute(
                f"""
                SELECT id, name, kontakt, lieferzeit_tage, bewertung
                FROM lieferanten
                {where}
                ORDER BY name
                {limit_sql}
                """,
                parameter,
            )
            lieferanten = cursor.fetchall()

        if not lieferanten:
            return f"Keine Lieferanten für '{suchbegriff.strip()}' gefunden."

        zeilen = [f"Vorhandene Lieferanten ({len(lieferanten)} Treffer):"]
        for lieferant_id, name, kontakt, lieferzeit, bewertung in lieferanten:
            zeilen.append(
                f"  [{lieferant_id}] {name} | Kontakt: {kontakt} | "
                f"Lieferzeit: {lieferzeit} Tage | Bewertung: {bewertung:.1f}/5.0"
            )
        return "\n".join(zeilen)
    except Exception as e:
        logger.error("Fehler bei Lieferantensuche (%s): %s", suchbegriff, e)
        return f"Fehler beim Abrufen der Lieferanten: {e}"


@tool
def vergleiche_lieferanten(produkt_id: int) -> str:
    """Vergleicht alle verfügbaren Lieferanten für ein Produkt nach Preis, Lieferzeit und Bewertung.

    Args:
        produkt_id: Die ID des Produkts
    """
    try:
        with db_connection() as (conn, cursor):
            cursor.execute("SELECT name FROM produkte WHERE id = ?", (produkt_id,))
            produkt = cursor.fetchone()
            if not produkt:
                return f"Fehler: Produkt mit ID {produkt_id} nicht gefunden."

            cursor.execute("""
                SELECT
                    l.id,
                    l.name,
                    pl.preis,
                    COALESCE(pl.lieferzeit_tage, l.lieferzeit_tage) as lieferzeit,
                    l.bewertung,
                    CASE WHEN p.standard_lieferant_id = l.id THEN 1 ELSE 0 END as ist_standard
                FROM produkt_lieferanten pl
                JOIN lieferanten l ON pl.lieferant_id = l.id
                JOIN produkte p ON pl.produkt_id = p.id
                WHERE pl.produkt_id = ?
                ORDER BY pl.preis ASC
            """, (produkt_id,))
            lieferanten = cursor.fetchall()

        if not lieferanten:
            return f"Keine Lieferanten für '{produkt[0]}' hinterlegt."

        return _formatiere_vergleich(produkt[0], lieferanten)
    except Exception as e:
        logger.error("Fehler bei Lieferantenvergleich (Produkt=%d): %s", produkt_id, e)
        return f"Fehler beim Lieferantenvergleich: {e}"


@tool
def vergleiche_lieferanten_batch(produkt_ids: list[int]) -> str:
    """Vergleicht Lieferanten für mehrere Produkte in einem Aufruf.

    Nutze dieses Tool, wenn für 3 oder mehr Produkte ein Lieferantenvergleich
    durchgeführt werden soll. Liefert pro Produkt eine Vergleichstabelle sowie
    eine Zusammenfassung der häufigsten Empfehlung über alle Produkte hinweg.

    Args:
        produkt_ids: Liste von Produkt-IDs
    """
    if not produkt_ids:
        return "Fehler: Keine Produkt-IDs übergeben."

    if len(produkt_ids) > BATCH_DEFAULT_MAX_POSITIONEN:
        return (
            f"Fehler: Zu viele Produkt-IDs ({len(produkt_ids)}). "
            f"Maximal erlaubt: {BATCH_DEFAULT_MAX_POSITIONEN} pro Batch."
        )

    ergebnisse = []
    empfehlungen = []
    for idx, produkt_id in enumerate(produkt_ids, start=1):
        result = vergleiche_lieferanten.invoke({"produkt_id": produkt_id})
        ergebnisse.append(f"{idx}. Produkt-ID {produkt_id}\n{result}")

        # Empfehlung extrahieren für die Zusammenfassung
        marker = "Empfehlung: "
        pos = result.find(marker)
        if pos != -1:
            rest = result[pos + len(marker):]
            name = rest.split(" (")[0].strip()
            if name:
                empfehlungen.append(name)

    zusammenfassung = ""
    if empfehlungen:
        counter = Counter(empfehlungen)
        top = counter.most_common(3)
        zeilen = [
            f"    {name}: {anzahl}x empfohlen"
            for name, anzahl in top
        ]
        zusammenfassung = (
            "\n\n  Zusammenfassung (häufigste Empfehlung):\n"
            + "\n".join(zeilen)
        )

    return (
        f"Batch-Lieferantenvergleich abgeschlossen ({len(produkt_ids)} Produkte):\n\n"
        + "\n\n".join(ergebnisse)
        + zusammenfassung
    )


@tool
def erstelle_lieferant(
    name: str,
    kontakt: str,
    lieferzeit_tage: int,
    bewertung: float,
) -> str:
    """Legt einen neuen Lieferanten an.

    Args:
        name: Name des Lieferanten
        kontakt: Kontakt-Email des Lieferanten
        lieferzeit_tage: Durchschnittliche Lieferzeit in Tagen
        bewertung: Bewertung von 1.0 bis 5.0
    """
    if not 1.0 <= bewertung <= 5.0:
        return "Fehler: Bewertung muss zwischen 1.0 und 5.0 liegen."
    if lieferzeit_tage < 0:
        return "Fehler: Lieferzeit darf nicht negativ sein."
    if not name.strip():
        return "Fehler: Lieferantenname darf nicht leer sein."
    name = name.strip()

    try:
        with db_connection(commit=True) as (conn, cursor):
            cursor.execute(
                "SELECT id FROM lieferanten WHERE name = ? COLLATE NOCASE",
                (name,),
            )
            if cursor.fetchone():
                return f"Fehler: Lieferant '{name}' existiert bereits."

            cursor.execute("""
                INSERT INTO lieferanten (name, kontakt, lieferzeit_tage, bewertung)
                VALUES (?, ?, ?, ?)
            """, (name, kontakt, lieferzeit_tage, bewertung))

            lieferant_id = cursor.lastrowid

        logger.info("Lieferant angelegt: %s (ID=%d)", name, lieferant_id)

        return (
            f"Lieferant erfolgreich angelegt.\n"
            f"  ID:           {lieferant_id}\n"
            f"  Name:         {name}\n"
            f"  Kontakt:      {kontakt}\n"
            f"  Lieferzeit:   {lieferzeit_tage} Tage\n"
            f"  Bewertung:    {bewertung}/5.0"
        )
    except Exception as e:
        logger.error("Fehler bei Lieferant-Erstellung (%s): %s", name, e)
        return f"Fehler beim Anlegen des Lieferanten: {e}"
