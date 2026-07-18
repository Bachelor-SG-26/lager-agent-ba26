import threading
from langchain_core.tools import tool
from database.database import db_connection
from services.telegram import send_telegram
from services.logger import get_logger
from datetime import datetime
from config import BESTELLHISTORIE_DEFAULT_LIMIT, BATCH_DEFAULT_MAX_POSITIONEN

logger = get_logger("tools.bestellungen")

# Lock verhindert parallele Bestell-Nr Kollisionen bei gleichzeitigen Tool-Calls
_bestell_lock = threading.Lock()

# Telegram-Batch: sammelt Bestellungen und sendet eine Zusammenfassung
_telegram_batch = []
_telegram_batch_lock = threading.Lock()
_telegram_timer = None
_TELEGRAM_BATCH_DELAY = 3.0  # Sekunden warten auf weitere Bestellungen


# ─────────────────────────────────────────
#  Hilfsfunktionen: DB
# ─────────────────────────────────────────


def _pruefe_budget(cursor, gesamtkosten):
    """Prüft ob genug Budget vorhanden ist. Gibt (budget_row, fehler) zurück."""
    jetzt = datetime.now()
    quartal = (jetzt.month - 1) // 3 + 1
    cursor.execute("""
        SELECT id, gesamtbudget, verbrauchtes_budget
        FROM budget WHERE quartal = ? AND jahr = ?
    """, (quartal, jetzt.year))
    budget = cursor.fetchone()

    if not budget:
        return None, "Fehler: Kein Budget für dieses Quartal gefunden."

    verbleibend = budget[1] - budget[2]
    if gesamtkosten > verbleibend:
        return None, (
            f"BUDGET ÜBERSCHRITTEN\n"
            f"  Bestellkosten:  {gesamtkosten:.2f} Euro\n"
            f"  Verbleibend:    {verbleibend:.2f} Euro\n"
            f"  Fehlbetrag:     {gesamtkosten - verbleibend:.2f} Euro\n"
            f"  Bestellung wurde NICHT angelegt."
        )

    return budget, None


def _generiere_bestell_nr(cursor):
    """Erzeugt die nächste Bestellnummer im Format BEST-YYYY-NNNN."""
    jahr = datetime.now().year
    cursor.execute(
        "SELECT MAX(CAST(SUBSTR(bestell_nr, 11) AS INTEGER)) FROM bestellungen WHERE bestell_nr LIKE ?",
        (f"BEST-{jahr}-%",),
    )
    letzte = cursor.fetchone()[0] or 0
    return f"BEST-{jahr}-{letzte + 1:04d}"


def _lade_bestellprodukt(cursor, produkt_id, lieferant_id=None):
    """Lädt Produktdaten mit ausgewähltem oder Standard-Lieferanten."""
    cursor.execute("""
        SELECT p.name, p.bestand, p.standard_lieferant_id
        FROM produkte p
        WHERE p.id = ?
    """, (produkt_id,))
    produkt = cursor.fetchone()

    if not produkt:
        return None, f"Fehler: Produkt mit ID {produkt_id} nicht gefunden."

    ziel_lieferant_id = lieferant_id if lieferant_id is not None else produkt[2]
    if ziel_lieferant_id is None:
        return None, f"Fehler: Für Produkt '{produkt[0]}' ist kein Standardlieferant hinterlegt."

    cursor.execute("""
        SELECT l.id, l.name, pl.preis
        FROM produkt_lieferanten pl
        JOIN lieferanten l ON pl.lieferant_id = l.id
        WHERE pl.produkt_id = ? AND pl.lieferant_id = ?
    """, (produkt_id, ziel_lieferant_id))
    lieferant = cursor.fetchone()

    if not lieferant:
        return None, (
            f"Fehler: Lieferant mit ID {ziel_lieferant_id} ist für "
            f"Produkt '{produkt[0]}' nicht hinterlegt."
        )

    return {
        "name": produkt[0],
        "bestand": produkt[1],
        "lieferant_id": lieferant[0],
        "lieferant_name": lieferant[1],
        "preis": lieferant[2],
    }, None


def _fuehre_bestellung_aus(cursor, produkt_id, produkt, menge, gesamtkosten, budget):
    """Erstellt Bestellung, aktualisiert Bestand und Budget. Gibt die Bestellnummer zurück."""
    datum = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    bestell_nr = _generiere_bestell_nr(cursor)
    cursor.execute("""
        INSERT INTO bestellungen (bestell_nr, produkt_id, lieferant_id, menge, gesamtkosten, datum)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (bestell_nr, produkt_id, produkt["lieferant_id"], menge, gesamtkosten, datum))

    cursor.execute(
        "UPDATE produkte SET bestand = bestand + ? WHERE id = ?",
        (menge, produkt_id),
    )
    cursor.execute(
        "UPDATE budget SET verbrauchtes_budget = verbrauchtes_budget + ? WHERE id = ?",
        (gesamtkosten, budget[0]),
    )
    return bestell_nr


# ─────────────────────────────────────────
#  Hilfsfunktionen: Telegram-Batch
# ─────────────────────────────────────────


def _telegram_batch_hinzufuegen(
    bestell_nr, produkt_name, lieferant_name, menge, gesamtkosten, neuer_bestand, verbleibend
):
    """Fügt eine Bestellung zum Telegram-Batch hinzu und startet den Sende-Timer."""
    global _telegram_timer
    with _telegram_batch_lock:
        _telegram_batch.append({
            "bestell_nr": bestell_nr,
            "produkt": produkt_name,
            "lieferant": lieferant_name,
            "menge": menge,
            "kosten": gesamtkosten,
            "bestand": neuer_bestand,
            "budget": verbleibend,
        })
        if _telegram_timer:
            _telegram_timer.cancel()
        _telegram_timer = threading.Timer(_TELEGRAM_BATCH_DELAY, _telegram_batch_senden)
        _telegram_timer.daemon = True
        _telegram_timer.start()


def _telegram_batch_senden():
    """Sendet gesammelte Bestellungen als eine Telegram-Nachricht."""
    global _telegram_timer
    with _telegram_batch_lock:
        if not _telegram_batch:
            return
        batch = list(_telegram_batch)
        _telegram_batch.clear()
        _telegram_timer = None

    try:
        send_ok = False
        if len(batch) == 1:
            b = batch[0]
            send_ok = send_telegram(
                f"<b>Neue Bestellung</b>\n"
                f"Bestell-Nr: {b['bestell_nr']}\n"
                f"Produkt: {b['produkt']}\n"
                f"Lieferant: {b['lieferant']}\n"
                f"Menge: {b['menge']} Stück\n"
                f"Kosten: {b['kosten']:.2f} Euro\n"
                f"Neuer Bestand: {b['bestand']} Stück\n"
                f"Verbl. Budget: {b['budget']:.2f} Euro"
            )
        else:
            gesamt = sum(b["kosten"] for b in batch)
            zeilen = "\n".join(
                f"  {b['bestell_nr']} | {b['produkt']} | {b['lieferant']} | "
                f"{b['menge']} St. | {b['kosten']:.2f} Euro"
                for b in batch
            )
            send_ok = send_telegram(
                f"<b>Sammelbestellung ({len(batch)} Positionen)</b>\n\n"
                f"{zeilen}\n\n"
                f"<b>Gesamtkosten: {gesamt:.2f} Euro</b>"
            )
        if send_ok:
            logger.info("Telegram-Batch gesendet: %d Bestellung(en)", len(batch))
        else:
            logger.warning("Telegram-Batch konnte nicht gesendet werden: %d Bestellung(en)", len(batch))
    except Exception as e:
        logger.error("Fehler beim Senden des Telegram-Batch: %s", e)


# ─────────────────────────────────────────
#  Tools
# ─────────────────────────────────────────


@tool
def erstelle_bestellung(produkt_id: int, menge: int, lieferant_id: int = None) -> str:
    """Legt eine neue Bestellung an, aktualisiert Bestand und Budget.

    Args:
        produkt_id: Die ID des Produkts
        menge: Die Anzahl der zu bestellenden Einheiten
        lieferant_id: Optional die ID des ausgewählten Lieferanten.
            Ohne Angabe wird der Standardlieferant genutzt.
    """
    if menge <= 0:
        return "Fehler: Menge muss größer als 0 sein."

    try:
        with _bestell_lock:
            with db_connection(commit=True) as (conn, cursor):
                produkt, fehler = _lade_bestellprodukt(cursor, produkt_id, lieferant_id)
                if fehler:
                    return fehler

                gesamtkosten = menge * produkt["preis"]

                budget, fehler = _pruefe_budget(cursor, gesamtkosten)
                if fehler:
                    return fehler

                verbleibend = budget[1] - budget[2]
                bestell_nr = _fuehre_bestellung_aus(
                    cursor, produkt_id, produkt, menge, gesamtkosten, budget
                )

        neuer_bestand = produkt["bestand"] + menge
        verbleibend_neu = verbleibend - gesamtkosten

        logger.info(
            "Bestellung %s angelegt: Produkt=%s, Lieferant=%s, Menge=%d, Kosten=%.2f",
            bestell_nr, produkt["name"], produkt["lieferant_name"], menge, gesamtkosten,
        )

        _telegram_batch_hinzufuegen(
            bestell_nr,
            produkt["name"],
            produkt["lieferant_name"],
            menge,
            gesamtkosten,
            neuer_bestand,
            verbleibend_neu,
        )

        return (
            f"Bestellung erfolgreich angelegt.\n"
            f"  Bestell-Nr:       {bestell_nr}\n"
            f"  Produkt:          {produkt['name']}\n"
            f"  Lieferant:        {produkt['lieferant_name']} (ID: {produkt['lieferant_id']})\n"
            f"  Menge:            {menge} Stück\n"
            f"  Kosten:           {gesamtkosten:.2f} Euro\n"
            f"  Neuer Bestand:    {neuer_bestand} Stück\n"
            f"  Verbl. Budget:    {verbleibend_neu:.2f} Euro"
        )
    except Exception as e:
        logger.error(
            "Fehler bei Bestellung (Produkt=%d, Lieferant=%s, Menge=%d): %s",
            produkt_id, lieferant_id, menge, e,
        )
        return f"Fehler bei der Bestellung: {e}"


@tool
def erstelle_bestellung_batch(positionen: list[dict]) -> str:
    """Legt mehrere Bestellungen in einem Aufruf an.

    Args:
        positionen: Liste mit Einträgen im Format
            [{"produkt_id": 1, "menge": 10, "lieferant_id": 2}, ...]
            lieferant_id ist optional; ohne Angabe wird der Standardlieferant genutzt.
    """
    if not positionen:
        return "Fehler: Keine Positionen übergeben."

    if len(positionen) > BATCH_DEFAULT_MAX_POSITIONEN:
        return (
            f"Fehler: Zu viele Positionen ({len(positionen)}). "
            f"Maximal erlaubt: {BATCH_DEFAULT_MAX_POSITIONEN} pro Batch."
        )

    erfolgreich = 0
    fehlgeschlagen = 0
    details = []

    for idx, pos in enumerate(positionen, start=1):
        produkt_id = pos.get("produkt_id")
        menge = pos.get("menge")
        lieferant_id = pos.get("lieferant_id")

        if produkt_id is None or menge is None:
            fehlgeschlagen += 1
            details.append(f"{idx}. Fehler: Position ohne produkt_id oder menge.")
            continue

        args = {"produkt_id": produkt_id, "menge": menge}
        if lieferant_id is not None:
            args["lieferant_id"] = lieferant_id
        result = erstelle_bestellung.invoke(args)
        if result.startswith("Bestellung erfolgreich angelegt."):
            erfolgreich += 1
        else:
            fehlgeschlagen += 1
        details.append(f"{idx}. {result}")

    return (
        f"Sammelbestellung abgeschlossen ({len(positionen)} Positionen):\n"
        f"  Erfolgreich:   {erfolgreich}\n"
        f"  Fehlgeschlagen: {fehlgeschlagen}\n\n"
        f"Details:\n" + "\n\n".join(details)
    )


@tool
def check_bestellhistorie(limit: int = BESTELLHISTORIE_DEFAULT_LIMIT) -> str:
    """Zeigt bisherige Bestellungen mit Kosten und Lieferant.

    Args:
        limit: Maximale Anzahl Bestellungen (Standard: 20, 0 = alle)
    """
    if limit < 0:
        return "Fehler: Limit darf nicht negativ sein."

    try:
        with db_connection() as (conn, cursor):
            cursor.execute("SELECT COUNT(*) FROM bestellungen")
            gesamt_anzahl = cursor.fetchone()[0]

            query = """
                SELECT b.bestell_nr, p.name, l.name, b.menge, b.gesamtkosten, b.datum
                FROM bestellungen b
                JOIN produkte p ON b.produkt_id = p.id
                LEFT JOIN lieferanten l ON b.lieferant_id = l.id
                ORDER BY b.datum DESC
            """
            if limit > 0:
                query += " LIMIT ?"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)
            bestellungen = cursor.fetchall()

        if not bestellungen:
            return "Keine Bestellungen vorhanden."

        angezeigt = len(bestellungen)
        gesamt = sum(b[4] for b in bestellungen)
        ergebnis = f"Bestellhistorie ({angezeigt} von {gesamt_anzahl}):\n"
        for b in bestellungen:
            lieferant = b[2] or "Unbekannt"
            ergebnis += (
                f"  [{b[0]}] {b[1]} | {lieferant} "
                f"| {b[3]} Stück | {b[4]:.2f} Euro | {b[5]}\n"
            )
        ergebnis += f"\nGesamtausgaben (angezeigt): {gesamt:.2f} Euro"

        if limit > 0 and angezeigt < gesamt_anzahl:
            ergebnis += f"\nHinweis: {gesamt_anzahl - angezeigt} weitere Bestellungen nicht angezeigt. Rufe mit limit=0 für alle auf."

        return ergebnis
    except Exception as e:
        logger.error("Fehler bei Bestellhistorie: %s", e)
        return f"Fehler beim Laden der Bestellhistorie: {e}"
