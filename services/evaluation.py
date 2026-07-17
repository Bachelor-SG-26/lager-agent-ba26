"""Persistente Ablauflogik für die vergleichende Systemevaluation."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from html import escape
from io import StringIO

from agent.tools.lieferanten import _berechne_beste_empfehlung
from config import CHECKPOINT_DB, PROGNOSE_HISTORIE_TAGE
from database.database import db_connection
from database.seed import seed_data
from services.nvidia_models import DEFAULT_NVIDIA_MODEL


TEILNEHMER_CODES = ("P1", "P2", "P3", "P4", "P5")
AUFGABEN_CODES = ("T1", "T2", "T3", "T4", "T5")

ALTERSGRUPPEN = ("18–24", "25–34", "35–44", "45–54", "55+")
BERUFSBEREICHE = (
    "Logistik, Lager oder Beschaffung",
    "IT oder Softwareentwicklung",
    "Kaufmännischer Bereich oder Verwaltung",
    "Technik oder Produktion",
    "Studium oder Ausbildung",
    "Anderer Bereich",
)
LAGER_ERFAHRUNGEN = ("Keine", "Unter 1 Jahr", "1–3 Jahre", "Mehr als 3 Jahre")
KI_ERFAHRUNGEN = ("Nie", "Selten", "Regelmäßig", "Häufig")

TEILNEHMER_PLAN = {
    "P1": (("Manuell", "A"), ("Agent", "B")),
    "P2": (("Agent", "A"), ("Manuell", "B")),
    "P3": (("Manuell", "B"), ("Agent", "A")),
    "P4": (("Agent", "B"), ("Manuell", "A")),
    "P5": (("Manuell", "A"), ("Agent", "B")),
}

SUS_AUSSAGEN = (
    "Ich denke, dass ich diesen Bedienmodus häufig nutzen würde.",
    "Ich fand diesen Bedienmodus unnötig komplex.",
    "Ich fand diesen Bedienmodus einfach zu benutzen.",
    "Ich glaube, dass ich Unterstützung benötigen würde, um diesen Bedienmodus zu nutzen.",
    "Ich fand, dass die Funktionen in diesem Bedienmodus gut zusammenarbeiten.",
    "Ich fand, dass dieser Bedienmodus zu viele Inkonsistenzen enthält.",
    "Ich kann mir vorstellen, dass die meisten Personen diesen Bedienmodus schnell erlernen.",
    "Ich fand diesen Bedienmodus umständlich zu benutzen.",
    "Ich fühlte mich bei der Nutzung dieses Bedienmodus sicher.",
    "Ich musste viel lernen, bevor ich diesen Bedienmodus verwenden konnte.",
)

AUFGABEN = {
    "T1": {
        "titel": "Lagerstatus ermitteln",
        "szenarien": {
            "A": {"produkt": "Schrauben M4x10", "bestand": 7, "mindestbestand": 25},
            "B": {"produkt": "Sechskantmutter M8", "bestand": 12, "mindestbestand": 30},
        },
    },
    "T2": {
        "titel": "Bedarf prognostizieren",
        "szenarien": {
            "A": {
                "produkt": "Schrauben M4x20",
                "bestand": 20,
                "mindestbestand": 10,
                "verbrauch_pro_eintrag": 3,
            },
            "B": {
                "produkt": "Sechskantmutter M6",
                "bestand": 55,
                "mindestbestand": 15,
                "verbrauch_pro_eintrag": 6,
            },
        },
    },
    "T3": {
        "titel": "Lieferanten vergleichen und bestellen",
        "szenarien": {
            "A": {"produkt": "Schrauben M8x40", "bestand": 20, "menge": 40},
            "B": {"produkt": "Sechskantmutter M10", "bestand": 20, "menge": 40},
        },
    },
    "T4": {
        "titel": "Materialentnahme erfassen",
        "szenarien": {
            "A": {
                "produkt": "Schrauben M4x20",
                "bestand": 80,
                "menge": 12,
                "grund": "Wartung",
            },
            "B": {
                "produkt": "Schrauben M8x40",
                "bestand": 75,
                "menge": 12,
                "grund": "Montage",
            },
        },
    },
    "T5": {
        "titel": "Produkt anlegen und bearbeiten",
        "szenarien": {
            "A": {
                "produkt": "Prüfadapter A",
                "mindestbestand_start": 12,
                "mindestbestand_ziel": 18,
                "preis": 4.50,
                "lieferant": "RS Components",
            },
            "B": {
                "produkt": "Montagehalter B",
                "mindestbestand_start": 8,
                "mindestbestand_ziel": 14,
                "preis": 6.20,
                "lieferant": "Misumi",
            },
        },
    },
}


def _jetzt():
    """Liefert einen maschinenlesbaren UTC-Zeitstempel."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _als_dict(cursor, row):
    """Wandelt eine Datenbankzeile anhand der Cursorbeschreibung um."""
    if row is None:
        return None
    return {spalte[0]: wert for spalte, wert in zip(cursor.description, row)}


def _hole_eine(cursor, sql, parameter=()):
    """Führt eine Abfrage aus und gibt die erste Zeile als Dictionary zurück."""
    cursor.execute(sql, parameter)
    return _als_dict(cursor, cursor.fetchone())


def _hole_alle(cursor, sql, parameter=()):
    """Führt eine Abfrage aus und gibt alle Zeilen als Dictionaries zurück."""
    cursor.execute(sql, parameter)
    spalten = [spalte[0] for spalte in cursor.description]
    return [dict(zip(spalten, row)) for row in cursor.fetchall()]


def _json_dumps(wert):
    """Serialisiert Evaluationsdaten einheitlich und umlauttreu."""
    return json.dumps(wert, ensure_ascii=False, default=str)


def _json_loads(wert, standard=None):
    """Liest optionale JSON-Daten mit einem sicheren Standardwert."""
    if not wert:
        return {} if standard is None else standard
    return json.loads(wert)


def _pruefe_teilnehmer_code(teilnehmer_code):
    """Verhindert unbekannte oder versehentlich falsch geschriebene Codes."""
    if teilnehmer_code not in TEILNEHMER_CODES:
        raise ValueError("Unbekannter Teilnehmercode.")


def _pruefe_teilnehmerprofil(profil):
    """Validiert die sechs anonymen Kontextmerkmale des Teilnehmerprofils."""
    profil = profil or {}
    if profil.get("altersgruppe") not in ALTERSGRUPPEN:
        raise ValueError("Bitte wählen Sie eine Altersgruppe aus.")
    if profil.get("berufsbereich") not in BERUFSBEREICHE:
        raise ValueError("Bitte wählen Sie einen beruflichen Bereich aus.")
    if profil.get("lager_erfahrung") not in LAGER_ERFAHRUNGEN:
        raise ValueError("Bitte geben Sie Ihre Erfahrung mit Lagerprozessen an.")
    if profil.get("ki_erfahrung") not in KI_ERFAHRUNGEN:
        raise ValueError("Bitte geben Sie Ihre Erfahrung mit KI-Chatbots an.")
    digitale_kenntnisse = profil.get("digitale_kenntnisse")
    if digitale_kenntnisse is None or int(digitale_kenntnisse) not in range(1, 6):
        raise ValueError("Die digitalen Kenntnisse müssen zwischen 1 und 5 liegen.")
    vorherige_kenntnis = profil.get("vorherige_kenntnis")
    if vorherige_kenntnis not in (True, False, 0, 1):
        raise ValueError("Bitte geben Sie die vorherige Kenntnis der Anwendung an.")
    return {
        "altersgruppe": profil["altersgruppe"],
        "berufsbereich": profil["berufsbereich"],
        "lager_erfahrung": profil["lager_erfahrung"],
        "digitale_kenntnisse": int(digitale_kenntnisse),
        "ki_erfahrung": profil["ki_erfahrung"],
        "vorherige_kenntnis": int(bool(vorherige_kenntnis)),
    }


def hole_aufgabeninfo(aufgabe_code, szenario):
    """Gibt Titel, Arbeitsauftrag und benötigte Antwortfelder zurück."""
    if aufgabe_code not in AUFGABEN_CODES or szenario not in ("A", "B"):
        raise ValueError("Unbekannte Aufgabe oder unbekanntes Szenario.")

    daten = AUFGABEN[aufgabe_code]["szenarien"][szenario]
    if aufgabe_code == "T1":
        anweisung = (
            f"Ermitteln Sie für das Produkt **{daten['produkt']}** den aktuellen Bestand, "
            "den Mindestbestand und die daraus resultierende Fehlmenge."
        )
        felder = (
            ("bestand", "Aktueller Bestand"),
            ("mindestbestand", "Mindestbestand"),
            ("fehlmenge", "Fehlmenge"),
        )
    elif aufgabe_code == "T2":
        anweisung = (
            f"Erstellen Sie für **{daten['produkt']}** eine Bedarfsprognose für 30 Tage "
            "und halten Sie die empfohlene Bestellmenge fest."
        )
        felder = (("empfohlene_bestellmenge", "Empfohlene Bestellmenge"),)
    elif aufgabe_code == "T3":
        anweisung = (
            f"Vergleichen Sie die verfügbaren Lieferanten für **{daten['produkt']}**. "
            f"Bestellen Sie anschließend **{daten['menge']} Stück** beim empfohlenen Lieferanten."
        )
        felder = ()
    elif aufgabe_code == "T4":
        anweisung = (
            f"Erfassen Sie für **{daten['produkt']}** eine Entnahme von "
            f"**{daten['menge']} Stück** mit dem Grund **{daten['grund']}**."
        )
        felder = ()
    else:
        anweisung = (
            f"Legen Sie das Produkt **{daten['produkt']}** mit Mindestbestand "
            f"**{daten['mindestbestand_start']}**, Preis **{daten['preis']:.2f} Euro** und "
            f"Standardlieferant **{daten['lieferant']}** an. Ändern Sie danach den "
            f"Mindestbestand auf **{daten['mindestbestand_ziel']}**."
        )
        felder = ()

    return {
        "code": aufgabe_code,
        "titel": AUFGABEN[aufgabe_code]["titel"],
        "anweisung": anweisung,
        "antwortfelder": felder,
    }


def teilnehmer_existiert(teilnehmer_code):
    """Prüft, ob ein Teilnehmer bereits registriert wurde."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    with db_connection() as (conn, cursor):
        cursor.execute(
            "SELECT 1 FROM evaluation_teilnehmende WHERE teilnehmer_code = ?",
            (teilnehmer_code,),
        )
        return cursor.fetchone() is not None


def hole_teilnehmerprofil(teilnehmer_code):
    """Lädt die anonymen Kontextmerkmale eines registrierten Teilnehmers."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    with db_connection() as (conn, cursor):
        return _hole_eine(
            cursor,
            """
            SELECT altersgruppe, berufsbereich, lager_erfahrung,
                   digitale_kenntnisse, ki_erfahrung, vorherige_kenntnis
            FROM evaluation_teilnehmende WHERE teilnehmer_code = ?
            """,
            (teilnehmer_code,),
        )


def teilnehmerprofil_vollstaendig(teilnehmer_code):
    """Prüft, ob alle sechs Profilangaben gespeichert wurden."""
    profil = hole_teilnehmerprofil(teilnehmer_code)
    return bool(profil) and all(wert is not None for wert in profil.values())


def speichere_teilnehmerprofil(teilnehmer_code, profil):
    """Speichert ein validiertes Profil ohne Namen oder genaue Altersangabe."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    profil = _pruefe_teilnehmerprofil(profil)
    with db_connection(commit=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE evaluation_teilnehmende
            SET altersgruppe = ?, berufsbereich = ?, lager_erfahrung = ?,
                digitale_kenntnisse = ?, ki_erfahrung = ?, vorherige_kenntnis = ?
            WHERE teilnehmer_code = ?
            """,
            (
                profil["altersgruppe"],
                profil["berufsbereich"],
                profil["lager_erfahrung"],
                profil["digitale_kenntnisse"],
                profil["ki_erfahrung"],
                profil["vorherige_kenntnis"],
                teilnehmer_code,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("Der Teilnehmercode wurde noch nicht registriert.")


def registriere_teilnehmer(teilnehmer_code, einwilligung_bestaetigt, profil):
    """Registriert einen anonymen Teilnehmer und legt beide Durchläufe an."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    if not einwilligung_bestaetigt:
        raise ValueError("Die freiwillige Teilnahme muss bestätigt werden.")
    profil = _pruefe_teilnehmerprofil(profil)

    with db_connection(commit=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT OR IGNORE INTO evaluation_teilnehmende
                (teilnehmer_code, einwilligung_am, altersgruppe, berufsbereich,
                 lager_erfahrung, digitale_kenntnisse, ki_erfahrung,
                 vorherige_kenntnis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                teilnehmer_code,
                _jetzt(),
                profil["altersgruppe"],
                profil["berufsbereich"],
                profil["lager_erfahrung"],
                profil["digitale_kenntnisse"],
                profil["ki_erfahrung"],
                profil["vorherige_kenntnis"],
            ),
        )
        for position, (modus, szenario) in enumerate(
            TEILNEHMER_PLAN[teilnehmer_code], start=1
        ):
            cursor.execute(
                """
                INSERT OR IGNORE INTO evaluation_durchlaeufe
                    (teilnehmer_code, position, modus, szenario)
                VALUES (?, ?, ?, ?)
                """,
                (teilnehmer_code, position, modus, szenario),
            )


def setze_teilnehmer_evaluation_zurueck(teilnehmer_code):
    """Löscht einen Evaluationslauf vollständig und stellt die Fachdaten wieder her."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    with db_connection(commit=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT a.chat_thread_id
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE d.teilnehmer_code = ? AND a.chat_thread_id IS NOT NULL
            """,
            (teilnehmer_code,),
        )
        thread_ids = [row[0] for row in cursor.fetchall()]
        cursor.execute(
            """
            DELETE FROM evaluation_ereignisse
            WHERE aufgabe_id IN (
                SELECT a.id FROM evaluation_aufgaben a
                JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
                WHERE d.teilnehmer_code = ?
            )
            """,
            (teilnehmer_code,),
        )
        cursor.execute(
            """
            DELETE FROM evaluation_aufgaben
            WHERE durchlauf_id IN (
                SELECT id FROM evaluation_durchlaeufe WHERE teilnehmer_code = ?
            )
            """,
            (teilnehmer_code,),
        )
        cursor.execute(
            "DELETE FROM evaluation_durchlaeufe WHERE teilnehmer_code = ?",
            (teilnehmer_code,),
        )
        cursor.execute(
            "DELETE FROM evaluation_teilnehmende WHERE teilnehmer_code = ?",
            (teilnehmer_code,),
        )
        for thread_id in thread_ids:
            cursor.execute(
                "DELETE FROM chat_nachrichten WHERE thread_id = ?",
                (thread_id,),
            )
            cursor.execute(
                "DELETE FROM chat_sessions WHERE thread_id = ?",
                (thread_id,),
            )
        _setze_fachdaten_zurueck(cursor)

    if thread_ids and os.path.exists(CHECKPOINT_DB):
        with closing(sqlite3.connect(CHECKPOINT_DB)) as checkpoint_conn:
            checkpoint_cursor = checkpoint_conn.cursor()
            checkpoint_cursor.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            tabellen = {row[0] for row in checkpoint_cursor.fetchall()}
            for tabelle in ("writes", "checkpoints"):
                if tabelle not in tabellen:
                    continue
                for thread_id in thread_ids:
                    checkpoint_cursor.execute(
                        f"DELETE FROM {tabelle} WHERE thread_id = ?",
                        (thread_id,),
                    )
            checkpoint_conn.commit()
    return {"teilnehmer_code": teilnehmer_code, "chat_sitzungen": len(thread_ids)}


def hole_durchlaeufe(teilnehmer_code):
    """Lädt beide zugewiesenen Durchläufe eines Teilnehmers."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    with db_connection() as (conn, cursor):
        cursor.execute(
            """
            SELECT id, teilnehmer_code, position, modus, szenario, status,
                   gestartet_am, abgeschlossen_am, modell_id, sus_score, feedback
            FROM evaluation_durchlaeufe
            WHERE teilnehmer_code = ?
            ORDER BY position
            """,
            (teilnehmer_code,),
        )
        spalten = [spalte[0] for spalte in cursor.description]
        return [dict(zip(spalten, row)) for row in cursor.fetchall()]


def hole_aktuellen_durchlauf(teilnehmer_code):
    """Gibt den ersten noch nicht abgeschlossenen Durchlauf zurück."""
    return next(
        (lauf for lauf in hole_durchlaeufe(teilnehmer_code) if lauf["status"] != "abgeschlossen"),
        None,
    )


def hole_aufgabenstatus(durchlauf_id):
    """Lädt den Bearbeitungsstatus aller bereits angelegten Aufgaben."""
    with db_connection() as (conn, cursor):
        cursor.execute(
            """
            SELECT id, aufgabe_code, status, dauer_ms, erfolgreich,
                   schwierigkeit, kommentar, abgeschlossen_am
            FROM evaluation_aufgaben
            WHERE durchlauf_id = ?
            ORDER BY id
            """,
            (durchlauf_id,),
        )
        spalten = [spalte[0] for spalte in cursor.description]
        return {row[1]: dict(zip(spalten, row)) for row in cursor.fetchall()}


def naechste_aufgabe(durchlauf_id):
    """Bestimmt die nächste Aufgabe in der verbindlichen Reihenfolge T1 bis T5."""
    status = hole_aufgabenstatus(durchlauf_id)
    for code in AUFGABEN_CODES:
        if code not in status:
            return code
    return None


def _loesche_fachdaten(cursor):
    """Entfernt ausschließlich veränderliche Lagerdaten, nicht die Evaluation."""
    tabellen = (
        "bestellungen",
        "verbrauch",
        "produkt_lieferanten",
        "produkte",
        "lieferanten",
        "budget",
    )
    for tabelle in tabellen:
        cursor.execute(f"DELETE FROM {tabelle}")
    platzhalter = ", ".join("?" for _ in tabellen)
    cursor.execute(
        f"DELETE FROM sqlite_sequence WHERE name IN ({platzhalter})",
        tabellen,
    )


def _setze_fachdaten_zurueck(cursor):
    """Stellt den reproduzierbaren Ausgangsdatenbestand wieder her."""
    _loesche_fachdaten(cursor)
    seed_data(cursor)


def setze_fachdaten_zurueck():
    """Setzt die fachlichen Tabellen zurück und bewahrt Evaluationsdaten."""
    with db_connection(commit=True) as (conn, cursor):
        _setze_fachdaten_zurueck(cursor)


def _produkt(cursor, name):
    """Lädt ein Produkt anhand seines eindeutigen Seed-Namens."""
    produkt = _hole_eine(
        cursor,
        "SELECT id, name, bestand, mindestbestand FROM produkte WHERE name = ?",
        (name,),
    )
    if not produkt:
        raise RuntimeError(f"Evaluationsprodukt '{name}' fehlt.")
    return produkt


def _bereite_aufgabe_vor(cursor, aufgabe_code, szenario):
    """Erzeugt den kontrollierten Datenzustand und die erwartete Lösung."""
    daten = AUFGABEN[aufgabe_code]["szenarien"][szenario]

    if aufgabe_code == "T1":
        produkt = _produkt(cursor, daten["produkt"])
        cursor.execute(
            "UPDATE produkte SET bestand = ?, mindestbestand = ? WHERE id = ?",
            (daten["bestand"], daten["mindestbestand"], produkt["id"]),
        )
        return {
            "produkt_id": produkt["id"],
            "produkt": daten["produkt"],
            "bestand": daten["bestand"],
            "mindestbestand": daten["mindestbestand"],
            "fehlmenge": daten["mindestbestand"] - daten["bestand"],
        }

    if aufgabe_code == "T2":
        produkt = _produkt(cursor, daten["produkt"])
        cursor.execute(
            "UPDATE produkte SET bestand = ?, mindestbestand = ? WHERE id = ?",
            (daten["bestand"], daten["mindestbestand"], produkt["id"]),
        )
        cursor.execute("DELETE FROM verbrauch WHERE produkt_id = ?", (produkt["id"],))
        heute = datetime.now()
        for tage in range(1, 31):
            datum = (heute - timedelta(days=tage)).strftime("%Y-%m-%d")
            cursor.execute(
                """
                INSERT INTO verbrauch (produkt_id, menge, grund, datum)
                VALUES (?, ?, 'Produktion', ?)
                """,
                (produkt["id"], daten["verbrauch_pro_eintrag"], datum),
            )
        gesamt = daten["verbrauch_pro_eintrag"] * 30
        durchschnitt = gesamt / PROGNOSE_HISTORIE_TAGE
        empfehlung = max(
            0,
            int(durchschnitt * 30 - daten["bestand"] + daten["mindestbestand"]),
        )
        return {
            "produkt_id": produkt["id"],
            "produkt": daten["produkt"],
            "empfohlene_bestellmenge": empfehlung,
        }

    if aufgabe_code == "T3":
        produkt = _produkt(cursor, daten["produkt"])
        cursor.execute(
            "UPDATE produkte SET bestand = ? WHERE id = ?",
            (daten["bestand"], produkt["id"]),
        )
        cursor.execute(
            """
            SELECT l.id, l.name, pl.preis,
                   COALESCE(pl.lieferzeit_tage, l.lieferzeit_tage), l.bewertung,
                   CASE WHEN p.standard_lieferant_id = l.id THEN 1 ELSE 0 END
            FROM produkt_lieferanten pl
            JOIN lieferanten l ON l.id = pl.lieferant_id
            JOIN produkte p ON p.id = pl.produkt_id
            WHERE pl.produkt_id = ?
            ORDER BY pl.preis
            """,
            (produkt["id"],),
        )
        lieferanten = cursor.fetchall()
        empfehlung = _berechne_beste_empfehlung(
            [(row[1], row[2], row[3], row[4], bool(row[5])) for row in lieferanten]
        )
        lieferant = next(row for row in lieferanten if row[1] == empfehlung)
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM bestellungen")
        letzte_bestellung = cursor.fetchone()[0]
        budget = _hole_eine(
            cursor,
            "SELECT id, verbrauchtes_budget FROM budget ORDER BY jahr DESC, quartal DESC LIMIT 1",
        )
        return {
            "produkt_id": produkt["id"],
            "produkt": daten["produkt"],
            "menge": daten["menge"],
            "lieferant_id": lieferant[0],
            "lieferant": lieferant[1],
            "einzelpreis": lieferant[2],
            "ausgangsbestand": daten["bestand"],
            "letzte_bestellung_id": letzte_bestellung,
            "budget_id": budget["id"],
            "budget_verbraucht": budget["verbrauchtes_budget"],
        }

    if aufgabe_code == "T4":
        produkt = _produkt(cursor, daten["produkt"])
        cursor.execute(
            "UPDATE produkte SET bestand = ? WHERE id = ?",
            (daten["bestand"], produkt["id"]),
        )
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM verbrauch")
        letzter_verbrauch = cursor.fetchone()[0]
        return {
            "produkt_id": produkt["id"],
            "produkt": daten["produkt"],
            "menge": daten["menge"],
            "grund": daten["grund"],
            "ausgangsbestand": daten["bestand"],
            "letzter_verbrauch_id": letzter_verbrauch,
        }

    lieferant = _hole_eine(
        cursor,
        "SELECT id, name FROM lieferanten WHERE name = ?",
        (daten["lieferant"],),
    )
    return {
        "produkt": daten["produkt"],
        "mindestbestand_start": daten["mindestbestand_start"],
        "mindestbestand_ziel": daten["mindestbestand_ziel"],
        "preis": daten["preis"],
        "lieferant_id": lieferant["id"],
        "lieferant": lieferant["name"],
    }


def starte_aufgabe(durchlauf_id, aufgabe_code, chat_thread_id=None):
    """Bereitet eine Aufgabe vor, startet den Timer und protokolliert den Beginn."""
    if aufgabe_code not in AUFGABEN_CODES:
        raise ValueError("Unbekannte Evaluationsaufgabe.")

    with db_connection(commit=True) as (conn, cursor):
        durchlauf = _hole_eine(
            cursor,
            """
            SELECT id, teilnehmer_code, modus, szenario, status
            FROM evaluation_durchlaeufe WHERE id = ?
            """,
            (durchlauf_id,),
        )
        if not durchlauf or durchlauf["status"] == "abgeschlossen":
            raise ValueError("Dieser Durchlauf kann nicht gestartet werden.")

        cursor.execute(
            """
            SELECT 1
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE d.teilnehmer_code = ? AND a.status = 'laufend'
            """,
            (durchlauf["teilnehmer_code"],),
        )
        if cursor.fetchone():
            raise ValueError("Es läuft bereits eine Aufgabe für diesen Teilnehmer.")

        cursor.execute(
            """
            SELECT aufgabe_code FROM evaluation_aufgaben
            WHERE durchlauf_id = ? ORDER BY id
            """,
            (durchlauf_id,),
        )
        erledigt = [row[0] for row in cursor.fetchall()]
        erwartete_aufgabe = next((code for code in AUFGABEN_CODES if code not in erledigt), None)
        if aufgabe_code != erwartete_aufgabe:
            raise ValueError(f"Als Nächstes muss {erwartete_aufgabe} bearbeitet werden.")

        _setze_fachdaten_zurueck(cursor)
        erwartung = _bereite_aufgabe_vor(cursor, aufgabe_code, durchlauf["szenario"])
        gestartet_am = _jetzt()
        cursor.execute(
            """
            INSERT INTO evaluation_aufgaben
                (durchlauf_id, aufgabe_code, status, gestartet_am,
                 erwartung_json, chat_thread_id)
            VALUES (?, ?, 'laufend', ?, ?, ?)
            """,
            (
                durchlauf_id,
                aufgabe_code,
                gestartet_am,
                _json_dumps(erwartung),
                chat_thread_id,
            ),
        )
        aufgabe_id = cursor.lastrowid
        cursor.execute(
            """
            UPDATE evaluation_durchlaeufe
            SET status = 'laufend',
                gestartet_am = COALESCE(gestartet_am, ?),
                modell_id = COALESCE(modell_id, ?)
            WHERE id = ?
            """,
            (
                gestartet_am,
                (
                    os.getenv("NVIDIA_MODEL") or DEFAULT_NVIDIA_MODEL
                    if durchlauf["modus"] == "Agent"
                    else None
                ),
                durchlauf_id,
            ),
        )
        _protokolliere_ereignis(
            cursor,
            aufgabe_id,
            durchlauf["modus"],
            str(uuid.uuid4()),
            "aufgabe_gestartet",
            {"aufgabe": aufgabe_code, "szenario": durchlauf["szenario"]},
            "gestartet",
            None,
        )

    return hole_aktive_aufgabe(aufgabe_id)


def hole_aktive_aufgabe(aufgabe_id):
    """Lädt eine laufende Aufgabe mit Teilnehmer- und Durchlaufskontext."""
    if not aufgabe_id:
        return None
    with db_connection() as (conn, cursor):
        aufgabe = _hole_eine(
            cursor,
            """
            SELECT a.id, a.durchlauf_id, a.aufgabe_code, a.status,
                   a.gestartet_am, a.erwartung_json, a.chat_thread_id,
                   d.teilnehmer_code, d.modus, d.szenario, d.position
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE a.id = ? AND a.status = 'laufend'
            """,
            (aufgabe_id,),
        )
    if aufgabe:
        aufgabe["erwartung"] = _json_loads(aufgabe.pop("erwartung_json"))
        aufgabe["info"] = hole_aufgabeninfo(aufgabe["aufgabe_code"], aufgabe["szenario"])
    return aufgabe


def starte_aufgabe_neu(aufgabe_id, chat_thread_id=None):
    """Setzt eine unterbrochene Aufgabe zurück und startet ihre Messung erneut."""
    neu_gestartet_am = _jetzt()
    with db_connection(commit=True) as (conn, cursor):
        aufgabe = _hole_eine(
            cursor,
            """
            SELECT a.id, a.aufgabe_code, a.status, a.gestartet_am,
                   d.modus, d.szenario
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE a.id = ?
            """,
            (aufgabe_id,),
        )
        if not aufgabe or aufgabe["status"] != "laufend":
            raise ValueError("Nur eine laufende Aufgabe kann neu gestartet werden.")

        unterbrochene_dauer_ms = _dauer_seit(
            aufgabe["gestartet_am"], neu_gestartet_am
        )
        _setze_fachdaten_zurueck(cursor)
        erwartung = _bereite_aufgabe_vor(
            cursor,
            aufgabe["aufgabe_code"],
            aufgabe["szenario"],
        )
        cursor.execute(
            """
            UPDATE evaluation_aufgaben
            SET gestartet_am = ?, abgeschlossen_am = NULL, dauer_ms = NULL,
                erwartung_json = ?, antwort_json = NULL, erfolgreich = NULL,
                validierung_json = NULL, schwierigkeit = NULL, kommentar = NULL,
                chat_thread_id = ?
            WHERE id = ?
            """,
            (
                neu_gestartet_am,
                _json_dumps(erwartung),
                chat_thread_id,
                aufgabe_id,
            ),
        )
        _protokolliere_ereignis(
            cursor,
            aufgabe_id,
            aufgabe["modus"],
            str(uuid.uuid4()),
            "aufgabe_neu_gestartet",
            {
                "vorheriger_start": aufgabe["gestartet_am"],
                "unterbrochene_dauer_ms": unterbrochene_dauer_ms,
            },
            "neu_gestartet",
            unterbrochene_dauer_ms,
        )

    return hole_aktive_aufgabe(aufgabe_id)


def hole_laufende_aufgabe_fuer_teilnehmer(teilnehmer_code):
    """Findet eine nach einem Reload noch aktive Aufgabe."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    with db_connection() as (conn, cursor):
        cursor.execute(
            """
            SELECT a.id
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE d.teilnehmer_code = ? AND a.status = 'laufend'
            ORDER BY a.id DESC LIMIT 1
            """,
            (teilnehmer_code,),
        )
        row = cursor.fetchone()
    return hole_aktive_aufgabe(row[0]) if row else None


def _protokolliere_ereignis(
    cursor,
    aufgabe_id,
    quelle,
    ereignis_id,
    aktion,
    argumente,
    status,
    dauer_ms,
):
    """Schreibt ein Ereignis innerhalb einer bestehenden Transaktion."""
    cursor.execute(
        """
        INSERT INTO evaluation_ereignisse
            (aufgabe_id, quelle, ereignis_id, aktion, argumente_json,
             status, dauer_ms, erstellt_am)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            aufgabe_id,
            quelle,
            ereignis_id,
            aktion,
            _json_dumps(argumente or {}),
            status,
            dauer_ms,
            _jetzt(),
        ),
    )


def protokolliere_ereignis(
    aufgabe_id,
    quelle,
    aktion,
    argumente=None,
    status="ausgeführt",
    dauer_ms=None,
    ereignis_id=None,
):
    """Protokolliert eine Agenten- oder manuelle Aktion für die aktive Aufgabe."""
    if not aufgabe_id:
        return
    with db_connection(commit=True) as (conn, cursor):
        _protokolliere_ereignis(
            cursor,
            aufgabe_id,
            quelle,
            ereignis_id or str(uuid.uuid4()),
            aktion,
            argumente,
            status,
            dauer_ms,
        )


def _validiere_aufgabe(cursor, aufgabe_code, erwartung, antworten):
    """Prüft eine Aufgabe anhand der Antwort oder des realen Datenbankzustands."""
    if aufgabe_code == "T1":
        pruefungen = {
            schluessel: int(antworten.get(schluessel, -1)) == int(erwartung[schluessel])
            for schluessel in ("bestand", "mindestbestand", "fehlmenge")
        }
        beobachtung = {
            schluessel: antworten.get(schluessel)
            for schluessel in ("bestand", "mindestbestand", "fehlmenge")
        }
        return all(pruefungen.values()), {"felder_korrekt": pruefungen}, beobachtung

    if aufgabe_code == "T2":
        korrekt = int(antworten.get("empfohlene_bestellmenge", -1)) == int(
            erwartung["empfohlene_bestellmenge"]
        )
        beobachtung = {
            "empfohlene_bestellmenge": antworten.get("empfohlene_bestellmenge")
        }
        return korrekt, {"bestellmenge_korrekt": korrekt}, beobachtung

    if aufgabe_code == "T3":
        cursor.execute(
            """
            SELECT b.id, b.produkt_id, b.lieferant_id, b.menge, b.gesamtkosten
            FROM bestellungen b
            WHERE b.id > ?
            ORDER BY b.id
            """,
            (erwartung["letzte_bestellung_id"],),
        )
        bestellungen = cursor.fetchall()
        bestellungen_ist = [
            {
                "bestellung_id": row[0],
                "produkt_id": row[1],
                "lieferant_id": row[2],
                "menge": row[3],
                "gesamtkosten": row[4],
            }
            for row in bestellungen
        ]
        erwartete_kosten = erwartung["menge"] * erwartung["einzelpreis"]
        bestellung_korrekt = len(bestellungen) == 1 and (
            bestellungen[0][1] == erwartung["produkt_id"]
            and bestellungen[0][2] == erwartung["lieferant_id"]
            and bestellungen[0][3] == erwartung["menge"]
            and abs(bestellungen[0][4] - erwartete_kosten) < 0.001
        )
        produkt = _hole_eine(
            cursor,
            "SELECT bestand FROM produkte WHERE id = ?",
            (erwartung["produkt_id"],),
        )
        budget = _hole_eine(
            cursor,
            "SELECT verbrauchtes_budget FROM budget WHERE id = ?",
            (erwartung["budget_id"],),
        )
        bestand_korrekt = produkt["bestand"] == erwartung["ausgangsbestand"] + erwartung["menge"]
        budget_korrekt = abs(
            budget["verbrauchtes_budget"]
            - (erwartung["budget_verbraucht"] + erwartete_kosten)
        ) < 0.001
        details = {
            "genau_eine_bestellung": len(bestellungen) == 1,
            "bestellung_korrekt": bestellung_korrekt,
            "bestand_korrekt": bestand_korrekt,
            "budget_korrekt": budget_korrekt,
        }
        beobachtung = {
            "neue_bestellungen": bestellungen_ist,
            "bestand_nachher": produkt["bestand"],
            "budgetverbrauch_nachher": budget["verbrauchtes_budget"],
        }
        return all(details.values()), details, beobachtung

    if aufgabe_code == "T4":
        cursor.execute(
            """
            SELECT produkt_id, menge, grund
            FROM verbrauch WHERE id > ? ORDER BY id
            """,
            (erwartung["letzter_verbrauch_id"],),
        )
        entnahmen = cursor.fetchall()
        entnahmen_ist = [
            {"produkt_id": row[0], "menge": row[1], "grund": row[2]}
            for row in entnahmen
        ]
        entnahme_korrekt = len(entnahmen) == 1 and (
            entnahmen[0][0] == erwartung["produkt_id"]
            and entnahmen[0][1] == erwartung["menge"]
            and entnahmen[0][2] == erwartung["grund"]
        )
        produkt = _hole_eine(
            cursor,
            "SELECT bestand FROM produkte WHERE id = ?",
            (erwartung["produkt_id"],),
        )
        bestand_korrekt = produkt["bestand"] == erwartung["ausgangsbestand"] - erwartung["menge"]
        details = {
            "genau_eine_entnahme": len(entnahmen) == 1,
            "entnahme_korrekt": entnahme_korrekt,
            "bestand_korrekt": bestand_korrekt,
        }
        beobachtung = {
            "neue_entnahmen": entnahmen_ist,
            "bestand_nachher": produkt["bestand"],
        }
        return all(details.values()), details, beobachtung

    produkt = _hole_eine(
        cursor,
        """
        SELECT id, bestand, mindestbestand, preis_pro_einheit, standard_lieferant_id
        FROM produkte WHERE name = ?
        """,
        (erwartung["produkt"],),
    )
    produkt_korrekt = bool(produkt) and (
        produkt["bestand"] == 0
        and produkt["mindestbestand"] == erwartung["mindestbestand_ziel"]
        and abs(produkt["preis_pro_einheit"] - erwartung["preis"]) < 0.001
        and produkt["standard_lieferant_id"] == erwartung["lieferant_id"]
    )
    zuordnung_korrekt = False
    if produkt:
        cursor.execute(
            """
            SELECT 1 FROM produkt_lieferanten
            WHERE produkt_id = ? AND lieferant_id = ?
            """,
            (produkt["id"], erwartung["lieferant_id"]),
        )
        zuordnung_korrekt = cursor.fetchone() is not None
    details = {
        "produkt_korrekt": produkt_korrekt,
        "lieferantenzuordnung_korrekt": zuordnung_korrekt,
    }
    beobachtung = {
        "produkt_gefunden": bool(produkt),
        "produktdaten": produkt or {},
        "lieferantenzuordnung_vorhanden": zuordnung_korrekt,
    }
    return all(details.values()), details, beobachtung


def _dauer_seit(gestartet_am, beendet_am):
    """Berechnet eine robuste Dauer zwischen zwei ISO-Zeitstempeln."""
    start = datetime.fromisoformat(gestartet_am)
    ende = datetime.fromisoformat(beendet_am)
    return max(0, int((ende - start).total_seconds() * 1000))


def schliesse_aufgabe_ab(aufgabe_id, antworten=None):
    """Stoppt die Zeit, validiert das Ergebnis und setzt die Fachdaten zurück."""
    antworten = antworten or {}
    beendet_am = _jetzt()
    with db_connection(commit=True) as (conn, cursor):
        aufgabe = _hole_eine(
            cursor,
            """
            SELECT a.id, a.aufgabe_code, a.status, a.gestartet_am,
                   a.erwartung_json, d.modus
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE a.id = ?
            """,
            (aufgabe_id,),
        )
        if not aufgabe or aufgabe["status"] != "laufend":
            raise ValueError("Die Aufgabe ist nicht mehr aktiv.")

        erwartung = _json_loads(aufgabe["erwartung_json"])
        erfolgreich, validierung, beobachtung = _validiere_aufgabe(
            cursor,
            aufgabe["aufgabe_code"],
            erwartung,
            antworten,
        )
        dauer_ms = _dauer_seit(aufgabe["gestartet_am"], beendet_am)
        cursor.execute(
            """
            UPDATE evaluation_aufgaben
            SET status = 'abgeschlossen', abgeschlossen_am = ?, dauer_ms = ?,
                antwort_json = ?, erfolgreich = ?, validierung_json = ?
            WHERE id = ?
            """,
            (
                beendet_am,
                dauer_ms,
                _json_dumps(
                    {
                        "formular": antworten,
                        "beobachteter_zustand": beobachtung,
                    }
                ),
                int(erfolgreich),
                _json_dumps(validierung),
                aufgabe_id,
            ),
        )
        _protokolliere_ereignis(
            cursor,
            aufgabe_id,
            aufgabe["modus"],
            str(uuid.uuid4()),
            "aufgabe_abgeschlossen",
            {"antworten": antworten, "beobachteter_zustand": beobachtung},
            "erfolgreich" if erfolgreich else "fachlich_fehlerhaft",
            dauer_ms,
        )
        _setze_fachdaten_zurueck(cursor)

    return {
        "aufgabe_id": aufgabe_id,
        "erfolgreich": erfolgreich,
        "dauer_ms": dauer_ms,
    }


def brich_aufgabe_ab(aufgabe_id):
    """Markiert eine Aufgabe als abgebrochen und stellt die Fachdaten wieder her."""
    beendet_am = _jetzt()
    with db_connection(commit=True) as (conn, cursor):
        aufgabe = _hole_eine(
            cursor,
            """
            SELECT a.id, a.status, a.gestartet_am, d.modus
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE a.id = ?
            """,
            (aufgabe_id,),
        )
        if not aufgabe or aufgabe["status"] != "laufend":
            raise ValueError("Die Aufgabe ist nicht mehr aktiv.")
        dauer_ms = _dauer_seit(aufgabe["gestartet_am"], beendet_am)
        cursor.execute(
            """
            UPDATE evaluation_aufgaben
            SET status = 'abgebrochen', abgeschlossen_am = ?, dauer_ms = ?,
                erfolgreich = 0, validierung_json = ?
            WHERE id = ?
            """,
            (beendet_am, dauer_ms, _json_dumps({"grund": "Abbruch"}), aufgabe_id),
        )
        _protokolliere_ereignis(
            cursor,
            aufgabe_id,
            aufgabe["modus"],
            str(uuid.uuid4()),
            "aufgabe_abgebrochen",
            {},
            "abgebrochen",
            dauer_ms,
        )
        _setze_fachdaten_zurueck(cursor)


def hole_offenes_aufgabenfeedback(teilnehmer_code):
    """Findet die älteste abgeschlossene Aufgabe ohne subjektive Bewertung."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    with db_connection() as (conn, cursor):
        return _hole_eine(
            cursor,
            """
            SELECT a.id, a.aufgabe_code, a.status, a.dauer_ms, d.modus, d.szenario
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE d.teilnehmer_code = ?
              AND a.status IN ('abgeschlossen', 'abgebrochen')
              AND a.schwierigkeit IS NULL
            ORDER BY a.id LIMIT 1
            """,
            (teilnehmer_code,),
        )


def speichere_aufgabenfeedback(aufgabe_id, schwierigkeit, kommentar):
    """Speichert die Bewertung nach gestopptem Aufgabentimer."""
    if not 1 <= int(schwierigkeit) <= 7:
        raise ValueError("Die Schwierigkeit muss zwischen 1 und 7 liegen.")
    with db_connection(commit=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE evaluation_aufgaben
            SET schwierigkeit = ?, kommentar = ?
            WHERE id = ? AND status IN ('abgeschlossen', 'abgebrochen')
            """,
            (int(schwierigkeit), kommentar.strip(), aufgabe_id),
        )


def _berechne_sus_score(antworten):
    """Berechnet den SUS-Gesamtwert aus zehn Antworten von 1 bis 5."""
    if len(antworten) != 10 or any(int(wert) not in range(1, 6) for wert in antworten):
        raise ValueError("Für den SUS werden zehn Antworten von 1 bis 5 benötigt.")
    punkte = 0
    for index, wert in enumerate(map(int, antworten), start=1):
        punkte += wert - 1 if index % 2 else 5 - wert
    return punkte * 2.5


def speichere_sus(durchlauf_id, antworten, feedback):
    """Speichert den Modusfragebogen und schließt den Durchlauf ab."""
    score = _berechne_sus_score(antworten)
    with db_connection(commit=True) as (conn, cursor):
        cursor.execute(
            """
            SELECT COUNT(*) FROM evaluation_aufgaben
            WHERE durchlauf_id = ?
              AND status IN ('abgeschlossen', 'abgebrochen')
            """,
            (durchlauf_id,),
        )
        if cursor.fetchone()[0] != len(AUFGABEN_CODES):
            raise ValueError("Vor dem Fragebogen müssen alle fünf Aufgaben beendet sein.")
        cursor.execute(
            """
            UPDATE evaluation_durchlaeufe
            SET status = 'abgeschlossen', abgeschlossen_am = ?,
                sus_antworten = ?, sus_score = ?, feedback = ?
            WHERE id = ?
            """,
            (_jetzt(), _json_dumps(list(map(int, antworten))), score, feedback.strip(), durchlauf_id),
        )
    return score


def speichere_abschlussfeedback(teilnehmer_code, bevorzugter_modus, kommentar):
    """Speichert die abschließende Präferenz nach beiden Durchläufen."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    if bevorzugter_modus not in ("Agent", "Manuell", "Kein Unterschied"):
        raise ValueError("Unbekannte Präferenz.")
    with db_connection(commit=True) as (conn, cursor):
        cursor.execute(
            """
            UPDATE evaluation_teilnehmende
            SET bevorzugter_modus = ?, abschluss_kommentar = ?, abgeschlossen_am = ?
            WHERE teilnehmer_code = ?
            """,
            (bevorzugter_modus, kommentar.strip(), _jetzt(), teilnehmer_code),
        )


def hole_teilnehmerabschluss(teilnehmer_code):
    """Lädt den Abschlussstatus eines Teilnehmers."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    with db_connection() as (conn, cursor):
        return _hole_eine(
            cursor,
            """
            SELECT bevorzugter_modus, abschluss_kommentar, abgeschlossen_am
            FROM evaluation_teilnehmende WHERE teilnehmer_code = ?
            """,
            (teilnehmer_code,),
        )


def _csv_aus_abfrage(sql):
    """Erzeugt eine Excel-kompatible UTF-8-CSV aus einer Abfrage."""
    with db_connection() as (conn, cursor):
        cursor.execute(sql)
        spalten = [spalte[0] for spalte in cursor.description]
        zeilen = cursor.fetchall()
    ausgabe = StringIO()
    writer = csv.writer(ausgabe, delimiter=";", lineterminator="\n")
    writer.writerow(spalten)
    writer.writerows(zeilen)
    return ("\ufeff" + ausgabe.getvalue()).encode("utf-8")


def exportiere_aufgaben_csv():
    """Exportiert Teilnehmer-, Durchlauf- und Aufgabenergebnisse gemeinsam."""
    return _csv_aus_abfrage(
        """
        SELECT d.teilnehmer_code, t.altersgruppe, t.berufsbereich,
               t.lager_erfahrung, t.digitale_kenntnisse, t.ki_erfahrung,
               t.vorherige_kenntnis, d.position, d.modus, d.szenario,
               a.aufgabe_code, a.status, a.gestartet_am, a.abgeschlossen_am,
               a.dauer_ms, a.erfolgreich, a.antwort_json, a.validierung_json,
               a.schwierigkeit, a.kommentar, d.modell_id, d.sus_score, d.feedback
        FROM evaluation_durchlaeufe d
        JOIN evaluation_teilnehmende t
          ON t.teilnehmer_code = d.teilnehmer_code
        LEFT JOIN evaluation_aufgaben a ON a.durchlauf_id = d.id
        ORDER BY d.teilnehmer_code, d.position, a.id
        """
    )


def exportiere_ereignisse_csv():
    """Exportiert alle Agenten- und manuellen Ereignisse mit Aufgabenkontext."""
    return _csv_aus_abfrage(
        """
        SELECT d.teilnehmer_code, d.modus, d.szenario, a.aufgabe_code,
               e.quelle, e.ereignis_id, e.aktion, e.argumente_json,
               e.status, e.dauer_ms, e.erstellt_am
        FROM evaluation_ereignisse e
        JOIN evaluation_aufgaben a ON a.id = e.aufgabe_id
        JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
        ORDER BY e.id
        """
    )


_BERICHT_LABELS = {
    "altersgruppe": "Altersgruppe",
    "berufsbereich": "Beruflicher Bereich",
    "lager_erfahrung": "Erfahrung mit Lager oder Beschaffung",
    "digitale_kenntnisse": "Digitale Kenntnisse (1–5)",
    "ki_erfahrung": "Erfahrung mit KI-Chatbots",
    "vorherige_kenntnis": "Anwendung vorher bekannt",
    "produkt": "Produkt",
    "produkt_id": "Produkt-ID",
    "bestand": "Bestand",
    "ausgangsbestand": "Ausgangsbestand",
    "mindestbestand": "Mindestbestand",
    "mindestbestand_start": "Mindestbestand beim Anlegen",
    "mindestbestand_ziel": "Geforderter Mindestbestand",
    "fehlmenge": "Fehlmenge",
    "empfohlene_bestellmenge": "Empfohlene Bestellmenge",
    "menge": "Menge",
    "grund": "Grund",
    "lieferant": "Lieferant",
    "lieferant_id": "Lieferanten-ID",
    "einzelpreis": "Einzelpreis",
    "preis": "Preis",
    "budget_verbraucht": "Budgetverbrauch vor der Aufgabe",
    "felder_korrekt": "Eingegebene Werte korrekt",
    "bestellmenge_korrekt": "Empfohlene Bestellmenge korrekt",
    "genau_eine_bestellung": "Genau eine neue Bestellung",
    "bestellung_korrekt": "Produkt, Lieferant, Menge und Kosten korrekt",
    "bestand_korrekt": "Bestand korrekt fortgeschrieben",
    "budget_korrekt": "Budget korrekt fortgeschrieben",
    "genau_eine_entnahme": "Genau eine neue Entnahme",
    "entnahme_korrekt": "Produkt, Menge und Grund korrekt",
    "produkt_korrekt": "Produktdaten und Zielwert korrekt",
    "lieferantenzuordnung_korrekt": "Lieferantenzuordnung korrekt",
    "formular": "Formulareingaben",
    "beobachteter_zustand": "Tatsächlich beobachteter Zustand",
    "neue_bestellungen": "Neu angelegte Bestellungen",
    "neue_entnahmen": "Neu angelegte Entnahmen",
    "bestand_nachher": "Bestand nach der Aktion",
    "budgetverbrauch_nachher": "Budgetverbrauch nach der Aktion",
    "produkt_gefunden": "Gefordertes Produkt gefunden",
    "produktdaten": "Tatsächliche Produktdaten",
    "lieferantenzuordnung_vorhanden": "Lieferantenzuordnung vorhanden",
    "protokollierte_aktionen": "Protokollierte fachliche Aktionen",
    "aktion": "Aktion",
    "status": "Status",
    "argumente": "Argumente",
}


def _bericht_wert(wert):
    """Formatiert verschachtelte Berichtsdaten als sichere HTML-Ausgabe."""
    if isinstance(wert, dict):
        zeilen = []
        for schluessel, teilwert in wert.items():
            label = _BERICHT_LABELS.get(schluessel, schluessel.replace("_", " ").title())
            zeilen.append(
                f"<tr><th>{escape(label)}</th><td>{_bericht_wert(teilwert)}</td></tr>"
            )
        return f"<table class='detail-table'>{''.join(zeilen)}</table>"
    if isinstance(wert, list):
        if not wert:
            return "<span class='muted'>Keine Einträge</span>"
        eintraege = "".join(
            f"<li>{_bericht_wert(teilwert)}</li>" for teilwert in wert
        )
        return f"<ol class='detail-list'>{eintraege}</ol>"
    if isinstance(wert, bool):
        css = "ok" if wert else "nicht-ok"
        text = "Erfüllt" if wert else "Nicht erfüllt"
        return f"<span class='{css}'>{text}</span>"
    if wert is None or wert == "":
        return "<span class='muted'>–</span>"
    return escape(str(wert))


def _hole_teilnehmerbericht_daten(teilnehmer_code):
    """Lädt alle fachlichen und subjektiven Daten eines Teilnehmers."""
    _pruefe_teilnehmer_code(teilnehmer_code)
    with db_connection() as (conn, cursor):
        teilnehmer = _hole_eine(
            cursor,
            "SELECT * FROM evaluation_teilnehmende WHERE teilnehmer_code = ?",
            (teilnehmer_code,),
        )
        if not teilnehmer:
            raise ValueError("Für diesen Teilnehmercode liegen keine Daten vor.")
        durchlaeufe = _hole_alle(
            cursor,
            """
            SELECT * FROM evaluation_durchlaeufe
            WHERE teilnehmer_code = ? ORDER BY position
            """,
            (teilnehmer_code,),
        )
        aufgaben = _hole_alle(
            cursor,
            """
            SELECT a.*, d.position, d.modus, d.szenario
            FROM evaluation_aufgaben a
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE d.teilnehmer_code = ?
            ORDER BY d.position, a.id
            """,
            (teilnehmer_code,),
        )
        ereignisse = _hole_alle(
            cursor,
            """
            SELECT e.*, a.aufgabe_code, d.position, d.modus, d.szenario
            FROM evaluation_ereignisse e
            JOIN evaluation_aufgaben a ON a.id = e.aufgabe_id
            JOIN evaluation_durchlaeufe d ON d.id = a.durchlauf_id
            WHERE d.teilnehmer_code = ?
            ORDER BY e.id
            """,
            (teilnehmer_code,),
        )

    for aufgabe in aufgaben:
        aufgabe["erwartung"] = _json_loads(aufgabe.pop("erwartung_json"))
        aufgabe["antwort"] = _json_loads(aufgabe.pop("antwort_json"))
        aufgabe["validierung"] = _json_loads(aufgabe.pop("validierung_json"))
    for ereignis in ereignisse:
        ereignis["argumente"] = _json_loads(ereignis.pop("argumente_json"))
    return teilnehmer, durchlaeufe, aufgaben, ereignisse


def exportiere_teilnehmerbericht_html(teilnehmer_code):
    """Erzeugt einen vollständigen, druckbaren Abschlussbericht als HTML-Datei."""
    teilnehmer, durchlaeufe, aufgaben, ereignisse = _hole_teilnehmerbericht_daten(
        teilnehmer_code
    )
    erfolgreich = sum(1 for aufgabe in aufgaben if aufgabe["erfolgreich"] == 1)
    beendet = sum(
        1
        for aufgabe in aufgaben
        if aufgabe["status"] in ("abgeschlossen", "abgebrochen")
    )
    profil = {
        "altersgruppe": teilnehmer["altersgruppe"],
        "berufsbereich": teilnehmer["berufsbereich"],
        "lager_erfahrung": teilnehmer["lager_erfahrung"],
        "digitale_kenntnisse": teilnehmer["digitale_kenntnisse"],
        "ki_erfahrung": teilnehmer["ki_erfahrung"],
        "vorherige_kenntnis": (
            "Ja"
            if teilnehmer["vorherige_kenntnis"] == 1
            else "Nein"
            if teilnehmer["vorherige_kenntnis"] == 0
            else None
        ),
    }

    durchlauf_zeilen = []
    for lauf in durchlaeufe:
        modell = lauf["modell_id"] if lauf["modus"] == "Agent" else None
        durchlauf_zeilen.append(
            "<tr>"
            f"<td>{lauf['position']}</td>"
            f"<td>{escape(lauf['modus'])}</td>"
            f"<td>{escape(lauf['szenario'])}</td>"
            f"<td>{escape(lauf['status'])}</td>"
            f"<td>{_bericht_wert(modell)}</td>"
            f"<td>{_bericht_wert(lauf['sus_score'])}</td>"
            f"<td>{_bericht_wert(lauf['feedback'])}</td>"
            "</tr>"
        )

    aufgaben_zeilen = []
    detail_abschnitte = []
    for aufgabe in aufgaben:
        titel = AUFGABEN[aufgabe["aufgabe_code"]]["titel"]
        dauer = (
            f"{aufgabe['dauer_ms'] / 1000:.1f} s"
            if aufgabe["dauer_ms"] is not None
            else "–"
        )
        bewertung = (
            "Erfüllt"
            if aufgabe["erfolgreich"] == 1
            else "Nicht erfüllt"
            if aufgabe["erfolgreich"] == 0
            else "Offen"
        )
        status_css = "ok" if aufgabe["erfolgreich"] == 1 else "nicht-ok"
        aufgaben_zeilen.append(
            "<tr>"
            f"<td>{escape(aufgabe['aufgabe_code'])}</td>"
            f"<td>{escape(titel)}</td>"
            f"<td>{escape(aufgabe['modus'])}</td>"
            f"<td>{escape(aufgabe['szenario'])}</td>"
            f"<td>{dauer}</td>"
            f"<td><span class='{status_css}'>{bewertung}</span></td>"
            f"<td>{_bericht_wert(aufgabe['schwierigkeit'])}</td>"
            "</tr>"
        )

        task_events = [
            ereignis
            for ereignis in ereignisse
            if ereignis["aufgabe_id"] == aufgabe["id"]
        ]
        erfasste_ausfuehrung = aufgabe["antwort"]
        if not erfasste_ausfuehrung:
            fachliche_ereignisse = [
                {
                    "aktion": ereignis["aktion"],
                    "status": ereignis["status"],
                    "argumente": ereignis["argumente"],
                }
                for ereignis in task_events
                if ereignis["aktion"]
                not in {
                    "aufgabe_gestartet",
                    "aufgabe_neu_gestartet",
                    "aufgabe_abgeschlossen",
                    "aufgabe_abgebrochen",
                }
            ]
            erfasste_ausfuehrung = {
                "protokollierte_aktionen": fachliche_ereignisse
            }
        ereignis_zeilen = []
        for ereignis in task_events:
            ereignis_zeilen.append(
                "<tr>"
                f"<td>{escape(ereignis['erstellt_am'])}</td>"
                f"<td>{escape(ereignis['aktion'])}</td>"
                f"<td>{escape(ereignis['status'])}</td>"
                f"<td>{_bericht_wert(ereignis['dauer_ms'])}</td>"
                f"<td>{_bericht_wert(ereignis['argumente'])}</td>"
                "</tr>"
            )
        info = hole_aufgabeninfo(aufgabe["aufgabe_code"], aufgabe["szenario"])
        detail_abschnitte.append(
            f"""
            <section class="task-detail">
              <h3>{escape(aufgabe['aufgabe_code'])} · {escape(titel)}</h3>
              <p>{escape(info['anweisung'].replace('**', ''))}</p>
              <div class="detail-grid">
                <div><h4>Vorausgesetzter Zustand</h4>{_bericht_wert(aufgabe['erwartung'])}</div>
                <div><h4>Erfasste Ausführung</h4>{_bericht_wert(erfasste_ausfuehrung)}</div>
                <div><h4>Prüfergebnis</h4>{_bericht_wert(aufgabe['validierung'])}</div>
                <div><h4>Rückmeldung</h4><p>Schwierigkeit: {_bericht_wert(aufgabe['schwierigkeit'])}</p><p>{_bericht_wert(aufgabe['kommentar'])}</p></div>
              </div>
              <h4>Ereignisprotokoll</h4>
              <table><thead><tr><th>Zeitpunkt</th><th>Aktion</th><th>Status</th><th>Dauer ms</th><th>Argumente</th></tr></thead>
              <tbody>{''.join(ereignis_zeilen)}</tbody></table>
            </section>
            """
        )

    erstellt_am = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Evaluationsbericht {escape(teilnehmer_code)}</title>
  <style>
    :root {{ --ink:#172033; --muted:#64748b; --line:#d9e0ea; --surface:#f6f8fb; --accent:#d9343e; --ok:#16794a; --bad:#b4232d; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); font:14px/1.5 Arial, sans-serif; background:#eef2f6; }}
    main {{ width:min(1120px, calc(100% - 32px)); margin:28px auto; background:white; padding:36px; box-shadow:0 8px 32px rgba(23,32,51,.08); }}
    h1,h2,h3,h4 {{ margin:0 0 10px; }} h1 {{ font-size:28px; }} h2 {{ margin-top:30px; padding-bottom:8px; border-bottom:2px solid var(--ink); }} h3 {{ font-size:18px; }} h4 {{ font-size:14px; }}
    .meta {{ color:var(--muted); margin-bottom:24px; }}
    .summary {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:20px 0; }}
    .metric {{ border:1px solid var(--line); padding:14px; background:var(--surface); }} .metric strong {{ display:block; font-size:22px; }}
    table {{ width:100%; border-collapse:collapse; margin:10px 0 18px; }} th,td {{ border:1px solid var(--line); padding:8px 9px; text-align:left; vertical-align:top; }} thead th {{ background:var(--surface); }}
    .detail-table {{ margin:0; }} .detail-table th {{ width:48%; background:var(--surface); }}
    .detail-list {{ margin:0; padding-left:1.25rem; }} .detail-list li+li {{ margin-top:6px; }}
    .task-detail {{ break-inside:avoid; margin:22px 0; padding:18px; border:1px solid var(--line); }}
    .detail-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:14px 0; }} .detail-grid>div {{ padding:12px; background:var(--surface); }}
    .ok {{ color:var(--ok); font-weight:700; }} .nicht-ok {{ color:var(--bad); font-weight:700; }} .muted {{ color:var(--muted); }}
    .note {{ border-left:4px solid var(--accent); padding:10px 14px; background:#fff5f5; }}
    footer {{ margin-top:30px; color:var(--muted); font-size:12px; }}
    @media(max-width:760px) {{ main {{ width:100%; margin:0; padding:20px; }} .summary,.detail-grid {{ grid-template-columns:1fr; }} table {{ font-size:12px; }} }}
    @media print {{ body {{ background:white; }} main {{ width:100%; margin:0; box-shadow:none; padding:0; }} }}
  </style>
</head>
<body><main>
  <h1>Evaluationsbericht</h1>
  <p class="meta">Teilnehmercode {escape(teilnehmer_code)} · Erstellt am {erstellt_am}</p>
  <div class="summary">
    <div class="metric"><span>Beendete Aufgaben</span><strong>{beendet}/10</strong></div>
    <div class="metric"><span>Fachlich erfüllt</span><strong>{erfolgreich}/{beendet}</strong></div>
    <div class="metric"><span>Bevorzugter Modus</span><strong>{_bericht_wert(teilnehmer['bevorzugter_modus'])}</strong></div>
  </div>
  <p class="note">Die fachliche Bewertung basiert bei T1 und T2 auf den eingegebenen Ergebnissen. Bei T3 bis T5 wird der tatsächlich erzeugte Datenbankzustand geprüft. Neustarts und alle Agenten- beziehungsweise manuellen Aktionen bleiben im Ereignisprotokoll erhalten.</p>
  <h2>Teilnehmerprofil</h2>
  {_bericht_wert(profil)}
  <h2>Durchläufe</h2>
  <table><thead><tr><th>Nr.</th><th>Modus</th><th>Szenario</th><th>Status</th><th>Modell</th><th>SUS</th><th>Feedback</th></tr></thead><tbody>{''.join(durchlauf_zeilen)}</tbody></table>
  <h2>Aufgabenübersicht</h2>
  <table><thead><tr><th>Code</th><th>Aufgabe</th><th>Modus</th><th>Szenario</th><th>Dauer</th><th>Ergebnis</th><th>Schwierigkeit</th></tr></thead><tbody>{''.join(aufgaben_zeilen)}</tbody></table>
  <h2>Aufgabendetails</h2>
  {''.join(detail_abschnitte)}
  <h2>Abschluss</h2>
  <p><strong>Präferenz:</strong> {_bericht_wert(teilnehmer['bevorzugter_modus'])}</p>
  <p><strong>Begründung:</strong> {_bericht_wert(teilnehmer['abschluss_kommentar'])}</p>
  <footer>Anonymisierter Export aus der Evaluation des Lager-Agenten. Der Bericht enthält keine API-Schlüssel oder Personennamen.</footer>
</main></body></html>"""
    return html.encode("utf-8")
