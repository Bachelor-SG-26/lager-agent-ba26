from langchain_core.tools import tool
from database.database import db_connection
from services.logger import get_logger
from datetime import datetime, timedelta
from config import (
    PROGNOSE_HISTORIE_TAGE,
    PROGNOSE_DEFAULT_TAGE_VORAUS,
    PROGNOSE_KRITISCH_TAGE,
    PROGNOSE_WARNUNG_TAGE,
    BATCH_DEFAULT_MAX_POSITIONEN,
)

logger = get_logger("tools.prognose")


@tool
def prognostiziere_bedarf(produkt_id: int, tage_voraus: int = PROGNOSE_DEFAULT_TAGE_VORAUS) -> str:
    """Prognostiziert den Materialverbrauch basierend auf historischen Daten.

    Analysiert den bisherigen Verbrauch und berechnet:
    - Durchschnittlichen Tagesverbrauch
    - Voraussichtliche Reichweite des aktuellen Bestands
    - Empfohlene Bestellmenge

    Args:
        produkt_id: Die ID des Produkts
        tage_voraus: Prognosezeitraum in Tagen (Standard: 30)
    """
    try:
        with db_connection() as (conn, cursor):
            cursor.execute("""
                SELECT name, bestand, mindestbestand, preis_pro_einheit
                FROM produkte WHERE id = ?
            """, (produkt_id,))
            produkt = cursor.fetchone()

            if not produkt:
                return f"Fehler: Produkt mit ID {produkt_id} nicht gefunden."

            vor_90_tagen = (datetime.now() - timedelta(days=PROGNOSE_HISTORIE_TAGE)).strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT datum, SUM(menge) as tages_verbrauch
                FROM verbrauch
                WHERE produkt_id = ? AND datum >= ?
                GROUP BY DATE(datum)
                ORDER BY datum
            """, (produkt_id, vor_90_tagen))
            verbrauch_daten = cursor.fetchall()

            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(menge), 0)
                FROM bestellungen
                WHERE produkt_id = ? AND datum >= ?
            """, (produkt_id, vor_90_tagen))
            bestell_info = cursor.fetchone()

        if not verbrauch_daten:
            return (
                f"Prognose für {produkt[0]}:\n"
                f"  Keine Verbrauchsdaten vorhanden — Prognose nicht möglich.\n"
                f"  Aktueller Bestand: {produkt[1]} Stück\n"
                f"  Hinweis: Erfasse Entnahmen, damit die Prognose funktioniert."
            )

        gesamt_verbrauch = sum(v[1] for v in verbrauch_daten)
        anzahl_tage_mit_verbrauch = len(verbrauch_daten)
        tage_zeitraum = PROGNOSE_HISTORIE_TAGE

        durchschnitt_pro_tag = gesamt_verbrauch / tage_zeitraum
        durchschnitt_pro_woche = durchschnitt_pro_tag * 7

        if durchschnitt_pro_tag > 0:
            reichweite_tage = produkt[1] / durchschnitt_pro_tag
        else:
            reichweite_tage = float("inf")

        bedarf_prognosezeitraum = durchschnitt_pro_tag * tage_voraus
        empfohlene_menge = max(0, int(bedarf_prognosezeitraum - produkt[1] + produkt[2]))
        empfohlene_kosten = empfohlene_menge * produkt[3]

        reichweite_status = ""
        if reichweite_tage < PROGNOSE_KRITISCH_TAGE:
            reichweite_status = " [KRITISCH]"
        elif reichweite_tage < PROGNOSE_WARNUNG_TAGE:
            reichweite_status = " [BALD NACHBESTELLEN]"

        ergebnis = (
            f"Bedarfsprognose für {produkt[0]}:\n\n"
            f"  Verbrauchsanalyse (letzte {tage_zeitraum} Tage):\n"
            f"    Gesamtverbrauch:       {gesamt_verbrauch} Stück\n"
            f"    Tage mit Verbrauch:    {anzahl_tage_mit_verbrauch} von {tage_zeitraum}\n"
            f"    Durchschnitt/Tag:      {durchschnitt_pro_tag:.1f} Stück\n"
            f"    Durchschnitt/Woche:    {durchschnitt_pro_woche:.1f} Stück\n\n"
            f"  Bestandssituation:\n"
            f"    Aktueller Bestand:     {produkt[1]} Stück\n"
            f"    Mindestbestand:        {produkt[2]} Stück\n"
            f"    Geschätzte Reichweite:  {reichweite_tage:.0f} Tage{reichweite_status}\n\n"
            f"  Prognose ({tage_voraus} Tage):\n"
            f"    Erwarteter Verbrauch:  {bedarf_prognosezeitraum:.0f} Stück\n"
            f"    Empfohlene Bestellung: {empfohlene_menge} Stück\n"
            f"    Geschätzte Kosten:     {empfohlene_kosten:.2f} Euro"
        )

        if bestell_info[0] > 0:
            ergebnis += (
                f"\n\n  Bestellhistorie ({tage_zeitraum} Tage):\n"
                f"    Anzahl Bestellungen:   {bestell_info[0]}\n"
                f"    Bestellte Menge:       {bestell_info[1]} Stück"
            )

        return ergebnis
    except Exception as e:
        logger.error("Fehler bei Prognose (Produkt=%d): %s", produkt_id, e)
        return f"Fehler bei der Bedarfsprognose: {e}"


@tool
def prognostiziere_bedarf_batch(produkt_ids: list[int], tage_voraus: int = PROGNOSE_DEFAULT_TAGE_VORAUS) -> str:
    """Erstellt Bedarfsprognosen für mehrere Produkte in einem Aufruf.

    Args:
        produkt_ids: Liste von Produkt-IDs
        tage_voraus: Prognosezeitraum in Tagen (Standard: 30)
    """
    if not produkt_ids:
        return "Fehler: Keine Produkt-IDs übergeben."

    if len(produkt_ids) > BATCH_DEFAULT_MAX_POSITIONEN:
        return (
            f"Fehler: Zu viele Produkt-IDs ({len(produkt_ids)}). "
            f"Maximal erlaubt: {BATCH_DEFAULT_MAX_POSITIONEN} pro Batch."
        )

    ergebnisse = []
    for idx, produkt_id in enumerate(produkt_ids, start=1):
        result = prognostiziere_bedarf.invoke(
            {"produkt_id": produkt_id, "tage_voraus": tage_voraus}
        )
        ergebnisse.append(f"{idx}. Produkt-ID {produkt_id}\n{result}")

    return (
        f"Batch-Prognose abgeschlossen ({len(produkt_ids)} Produkte, {tage_voraus} Tage):\n\n"
        + "\n\n".join(ergebnisse)
    )
