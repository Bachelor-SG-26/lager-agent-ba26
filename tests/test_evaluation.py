"""End-to-End-Tests für den automatisierten Evaluationsablauf."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent.tools.bestellungen import erstelle_bestellung
from agent.tools.entnahme import erfasse_entnahme
from agent.tools.lager import check_lagerbestand
from agent.tools.produkte import erstelle_produkt
from agent.tools.update import aktualisiere_produkt
from database.database import db_connection
from services.evaluation import (
    exportiere_ereignisse_csv,
    exportiere_aufgaben_csv,
    exportiere_teilnehmerbericht_html,
    hole_aktive_aufgabe,
    hole_aktuellen_durchlauf,
    hole_durchlaeufe,
    hole_teilnehmerprofil,
    registriere_teilnehmer,
    schliesse_aufgabe_ab,
    setze_teilnehmer_evaluation_zurueck,
    speichere_aufgabenfeedback,
    speichere_sus,
    starte_aufgabe,
    starte_aufgabe_neu,
    wiederhole_aufgabe,
)
from services.session import erstelle_session, speichere_nachricht
import services.evaluation as evaluation_service
import views.chat.state as chat_state
import views.evaluation as evaluation_view
import views.manuell as manuell_view


class SessionState(dict):
    """Ergänzt für View-Tests den Attributzugriff von Streamlit Session State."""

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


TEST_PROFIL = {
    "altersgruppe": "25–34",
    "berufsbereich": "IT oder Softwareentwicklung",
    "lager_erfahrung": "Unter 1 Jahr",
    "digitale_kenntnisse": 4,
    "ki_erfahrung": "Regelmäßig",
    "vorherige_kenntnis": False,
}


def _registriere(teilnehmer_code):
    """Registriert einen Testteilnehmer mit vollständig validiertem Profil."""
    registriere_teilnehmer(teilnehmer_code, True, TEST_PROFIL)


def test_teilnehmer_erhaelt_gegenbalancierte_durchlaeufe():
    """Teilnehmercode und Reihenfolge werden reproduzierbar zugeordnet."""
    _registriere("P2")

    durchlaeufe = hole_durchlaeufe("P2")

    assert [(lauf["modus"], lauf["szenario"]) for lauf in durchlaeufe] == [
        ("Agent", "A"),
        ("Manuell", "B"),
    ]


def test_teilnehmerprofil_ist_verpflichtend_und_wird_exportiert():
    """Alle Kontextmerkmale werden validiert, gespeichert und im Bericht ausgegeben."""
    unvollstaendig = dict(TEST_PROFIL)
    unvollstaendig["ki_erfahrung"] = None

    with pytest.raises(ValueError, match="KI-Chatbots"):
        registriere_teilnehmer("P1", True, unvollstaendig)

    _registriere("P1")
    profil = hole_teilnehmerprofil("P1")
    bericht = exportiere_teilnehmerbericht_html("P1").decode("utf-8")

    assert profil == {
        **TEST_PROFIL,
        "vorherige_kenntnis": 0,
    }
    assert "Teilnehmerprofil" in bericht
    assert "25–34" in bericht
    assert "IT oder Softwareentwicklung" in bericht
    assert "Anwendung vorher bekannt" in bericht


def test_aufgabe_setzt_fachdaten_auf_und_nach_abschluss_zurueck(db_cursor):
    """Aufgabendaten werden kontrolliert aufgebaut und der normale Seed wiederhergestellt."""
    _registriere("P1")
    durchlauf = hole_aktuellen_durchlauf("P1")

    aufgabe = starte_aufgabe(durchlauf["id"], "T1")
    cursor, conn = db_cursor
    cursor.execute("SELECT bestand, mindestbestand FROM produkte WHERE name = 'Schrauben M4x10'")
    assert cursor.fetchone() == (7, 25)

    ergebnis = schliesse_aufgabe_ab(
        aufgabe["id"],
        {"bestand": 7, "mindestbestand": 25, "fehlmenge": 18},
    )

    assert ergebnis["erfolgreich"] is True
    cursor.execute("SELECT bestand, mindestbestand FROM produkte WHERE name = 'Schrauben M4x10'")
    assert cursor.fetchone() == (3, 50)
    cursor.execute("SELECT erfolgreich FROM evaluation_aufgaben WHERE id = ?", (aufgabe["id"],))
    assert cursor.fetchone()[0] == 1


def test_kompletter_durchlauf_validiert_alle_fuenf_aufgaben():
    """Lesende und schreibende Aufgaben werden anhand realer SQL-Zustände geprüft."""
    _registriere("P1")
    durchlauf = hole_aktuellen_durchlauf("P1")

    t1 = starte_aufgabe(durchlauf["id"], "T1")
    assert schliesse_aufgabe_ab(
        t1["id"], {"bestand": 7, "mindestbestand": 25, "fehlmenge": 18}
    )["erfolgreich"]

    t2 = starte_aufgabe(durchlauf["id"], "T2")
    assert t2["erwartung"]["empfohlene_bestellmenge"] == 20
    assert schliesse_aufgabe_ab(
        t2["id"], {"empfohlene_bestellmenge": 20}
    )["erfolgreich"]

    t3 = starte_aufgabe(durchlauf["id"], "T3")
    bestellung = erstelle_bestellung.invoke(
        {
            "produkt_id": t3["erwartung"]["produkt_id"],
            "menge": t3["erwartung"]["menge"],
            "lieferant_id": t3["erwartung"]["lieferant_id"],
        }
    )
    assert "erfolgreich" in bestellung.lower()
    assert schliesse_aufgabe_ab(t3["id"])["erfolgreich"]

    t4 = starte_aufgabe(durchlauf["id"], "T4")
    entnahme = erfasse_entnahme.invoke(
        {
            "produkt_id": t4["erwartung"]["produkt_id"],
            "menge": t4["erwartung"]["menge"],
            "grund": t4["erwartung"]["grund"],
        }
    )
    assert "Entnahme erfasst" in entnahme
    assert schliesse_aufgabe_ab(t4["id"])["erfolgreich"]

    t5 = starte_aufgabe(durchlauf["id"], "T5")
    produkt = erstelle_produkt.invoke(
        {
            "name": t5["erwartung"]["produkt"],
            "mindestbestand": t5["erwartung"]["mindestbestand_start"],
            "preis_pro_einheit": t5["erwartung"]["preis"],
            "lieferant_id": t5["erwartung"]["lieferant_id"],
        }
    )
    assert "erfolgreich" in produkt.lower()
    with db_connection() as (conn, cursor):
        cursor.execute("SELECT id FROM produkte WHERE name = ?", (t5["erwartung"]["produkt"],))
        produkt_id = cursor.fetchone()[0]
    aktualisierung = aktualisiere_produkt.invoke(
        {
            "produkt_id": produkt_id,
            "mindestbestand": t5["erwartung"]["mindestbestand_ziel"],
        }
    )
    assert "aktualisiert" in aktualisierung.lower()
    assert schliesse_aufgabe_ab(t5["id"])["erfolgreich"]

    score = speichere_sus(durchlauf["id"], [3] * 10, "Testfeedback")
    assert score == 50.0
    assert hole_aktuellen_durchlauf("P1")["position"] == 2


def test_falsche_t3_aktion_wird_als_tatsaechlicher_zustand_gespeichert(monkeypatch):
    """Auch eine fachlich falsche Bestellung bleibt statt eines leeren Ergebnisses sichtbar."""
    _registriere("P1")
    durchlauf = hole_aktuellen_durchlauf("P1")
    t1 = starte_aufgabe(durchlauf["id"], "T1")
    schliesse_aufgabe_ab(
        t1["id"], {"bestand": 7, "mindestbestand": 25, "fehlmenge": 18}
    )
    t2 = starte_aufgabe(durchlauf["id"], "T2")
    schliesse_aufgabe_ab(t2["id"], {"empfohlene_bestellmenge": 20})
    t3 = starte_aufgabe(durchlauf["id"], "T3")

    fake_st = SimpleNamespace(session_state={"_evaluation_task_id": t3["id"]})
    monkeypatch.setattr(manuell_view, "st", fake_st)
    manuell_view._rufe_tool_auf(
        erstelle_bestellung,
        {
            "produkt_id": t3["erwartung"]["produkt_id"],
            "menge": 39,
            "lieferant_id": t3["erwartung"]["lieferant_id"],
        },
    )

    ergebnis = schliesse_aufgabe_ab(t3["id"])
    with db_connection(commit=True) as (conn, cursor):
        cursor.execute(
            "SELECT antwort_json FROM evaluation_aufgaben WHERE id = ?",
            (t3["id"],),
        )
        antwort = json.loads(cursor.fetchone()[0])
        cursor.execute(
            "UPDATE evaluation_aufgaben SET antwort_json = '{}' WHERE id = ?",
            (t3["id"],),
        )

    bericht = exportiere_teilnehmerbericht_html("P1").decode("utf-8")

    assert ergebnis["erfolgreich"] is False
    assert antwort["beobachteter_zustand"]["neue_bestellungen"][0]["menge"] == 39
    assert "Fachliche Aktionen" in bericht
    assert "erstelle_bestellung" in bericht
    assert "39" in bericht


def test_aufgaben_muessen_in_fester_reihenfolge_starten():
    """Eine spätere Aufgabe kann nicht vor T1 gestartet werden."""
    _registriere("P3")
    durchlauf = hole_aktuellen_durchlauf("P3")

    try:
        starte_aufgabe(durchlauf["id"], "T3")
    except ValueError as exc:
        assert "T1" in str(exc)
    else:
        raise AssertionError("T3 durfte nicht vor T1 gestartet werden.")


def test_export_enthaelt_anonyme_aufgabendaten():
    """Der CSV-Export enthält Teilnehmercode und keine Personennamen."""
    _registriere("P4")
    durchlauf = hole_aktuellen_durchlauf("P4")
    aufgabe = starte_aufgabe(durchlauf["id"], "T1", "test-thread")
    schliesse_aufgabe_ab(
        aufgabe["id"],
        {"bestand": 7, "mindestbestand": 25, "fehlmenge": 18},
    )

    export = exportiere_aufgaben_csv().decode("utf-8-sig")

    assert "teilnehmer_code" in export
    assert "P4" in export
    assert "T1" in export
    assert hole_aktive_aufgabe(aufgabe["id"]) is None


def test_agent_und_manuell_schreiben_in_gemeinsames_evaluationslog(monkeypatch):
    """Beide Bedienmodi erzeugen Ereignisse mit demselben Aufgabenkontext."""
    _registriere("P5")
    durchlauf = hole_aktuellen_durchlauf("P5")
    aufgabe = starte_aufgabe(durchlauf["id"], "T1")

    fake_st = SimpleNamespace(session_state={"_evaluation_task_id": aufgabe["id"]})
    monkeypatch.setattr(manuell_view, "st", fake_st)
    manuell_view._rufe_tool_auf(check_lagerbestand, {"limit": 1})

    monkeypatch.setattr(chat_state, "st", fake_st)
    chat_state.log_tool_calls(
        [{"id": "agent-call-1", "name": "check_lagerbestand", "args": {"limit": 1}}],
        "ausgefuehrt",
        {"agent-call-1": 25},
    )

    with db_connection() as (conn, cursor):
        cursor.execute(
            """
            SELECT quelle, aktion, status, dauer_ms
            FROM evaluation_ereignisse
            WHERE aufgabe_id = ? AND aktion = 'check_lagerbestand'
            ORDER BY id
            """,
            (aufgabe["id"],),
        )
        ereignisse = cursor.fetchall()

    assert ereignisse[0][0] == "Manuell"
    assert ereignisse[1] == ("Agent", "check_lagerbestand", "ausgefuehrt", 25)


def test_laufende_aufgabe_kann_nach_unterbrechung_neu_gestartet_werden():
    """Ein Neustart setzt Timer, Fachdaten und Agentensitzung nachvollziehbar zurück."""
    _registriere("P2")
    durchlauf = hole_aktuellen_durchlauf("P2")
    aufgabe = starte_aufgabe(durchlauf["id"], "T1", "alter-thread")

    neu = starte_aufgabe_neu(aufgabe["id"], "neuer-thread")

    assert neu["id"] == aufgabe["id"]
    assert neu["chat_thread_id"] == "neuer-thread"
    assert neu["erwartung"]["bestand"] == 7
    with db_connection() as (conn, cursor):
        cursor.execute(
            """
            SELECT aktion, status, dauer_ms
            FROM evaluation_ereignisse
            WHERE aufgabe_id = ? ORDER BY id DESC LIMIT 1
            """,
            (aufgabe["id"],),
        )
        ereignis = cursor.fetchone()
    assert ereignis[0:2] == ("aufgabe_neu_gestartet", "neu_gestartet")
    assert ereignis[2] >= 0


def test_beendete_einzelaufgabe_kann_nachvollziehbar_wiederholt_werden():
    """Nur der neue Versuch zählt, während Ergebnis und Grund des alten erhalten bleiben."""
    _registriere("P1")
    durchlauf = hole_aktuellen_durchlauf("P1")

    erstelle_session("alter-wiederholung-thread")
    speichere_nachricht("alter-wiederholung-thread", "user", "Alter Versuch")
    t1 = starte_aufgabe(durchlauf["id"], "T1", "alter-wiederholung-thread")
    assert not schliesse_aufgabe_ab(
        t1["id"],
        {"bestand": 0, "mindestbestand": 0, "fehlmenge": 0},
    )["erfolgreich"]
    speichere_aufgabenfeedback(t1["id"], 5, "Verbindung war unterbrochen")

    t2 = starte_aufgabe(durchlauf["id"], "T2")
    assert schliesse_aufgabe_ab(
        t2["id"],
        {"empfohlene_bestellmenge": 20},
    )["erfolgreich"]
    speichere_aufgabenfeedback(t2["id"], 2, "Unverändert")

    wiederholt = wiederhole_aufgabe(
        durchlauf["id"],
        "T1",
        "Internet- oder Verbindungsproblem",
        "wiederholung-thread",
    )

    assert wiederholt["id"] == t1["id"]
    assert wiederholt["chat_thread_id"] == "wiederholung-thread"
    with db_connection() as (conn, cursor):
        cursor.execute(
            """
            SELECT aufgabe_code, status, dauer_ms, erfolgreich, schwierigkeit
            FROM evaluation_aufgaben
            WHERE durchlauf_id = ? ORDER BY aufgabe_code
            """,
            (durchlauf["id"],),
        )
        aufgaben = cursor.fetchall()
        cursor.execute(
            """
            SELECT argumente_json FROM evaluation_ereignisse
            WHERE aufgabe_id = ? AND aktion = 'aufgabe_wiederholt'
            """,
            (t1["id"],),
        )
        wiederholungsereignis = json.loads(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM chat_sessions WHERE thread_id = ?",
            ("alter-wiederholung-thread",),
        )
        alte_sitzungen = cursor.fetchone()[0]

    assert aufgaben[0] == ("T1", "laufend", None, None, None)
    assert aufgaben[1][0:2] == ("T2", "abgeschlossen")
    assert aufgaben[1][2] is not None
    assert aufgaben[1][3:5] == (1, 2)
    assert alte_sitzungen == 0
    assert wiederholungsereignis["wiederholungsgrund"] == "Internet- oder Verbindungsproblem"
    assert wiederholungsereignis["vorheriger_versuch"] == 1
    assert wiederholungsereignis["neuer_versuch"] == 2
    assert wiederholungsereignis["vorheriges_ergebnis"]["erfolgreich"] is False

    assert schliesse_aufgabe_ab(
        t1["id"],
        {"bestand": 7, "mindestbestand": 25, "fehlmenge": 18},
    )["erfolgreich"]
    speichere_aufgabenfeedback(t1["id"], 2, "Wiederholung erfolgreich")

    bericht = exportiere_teilnehmerbericht_html("P1").decode("utf-8")
    aufgaben_csv = exportiere_aufgaben_csv().decode("utf-8-sig")
    ereignisse_csv = exportiere_ereignisse_csv().decode("utf-8-sig")

    assert "Versuch 2" not in bericht
    assert "Internet- oder Verbindungsproblem" not in bericht
    assert "Vorheriges Ergebnis" not in bericht
    assert "Wiederholung erfolgreich" in bericht
    assert "versuch" in aufgaben_csv.splitlines()[0]
    assert "versuch" in ereignisse_csv.splitlines()[0]
    assert "aufgabe_wiederholt" in ereignisse_csv


def test_hard_reset_loescht_nur_gewaehlte_evaluation_und_aufgabenchat(
    monkeypatch, request
):
    """Der vollständige Neustart entfernt einen Lauf und stellt den Seed wieder her."""
    _registriere("P1")
    _registriere("P2")
    durchlauf = hole_aktuellen_durchlauf("P2")
    starte_aufgabe(durchlauf["id"], "T1", "reset-test-thread")
    erstelle_session("reset-test-thread")
    speichere_nachricht("reset-test-thread", "user", "Testnachricht")

    checkpoint_db = Path("test_checkpoints.sqlite")
    checkpoint_db.unlink(missing_ok=True)
    request.addfinalizer(lambda: checkpoint_db.unlink(missing_ok=True))
    with closing(sqlite3.connect(checkpoint_db)) as conn:
        conn.execute("CREATE TABLE writes (thread_id TEXT)")
        conn.execute("CREATE TABLE checkpoints (thread_id TEXT)")
        conn.execute("INSERT INTO writes VALUES ('reset-test-thread')")
        conn.execute("INSERT INTO checkpoints VALUES ('reset-test-thread')")
        conn.commit()
    monkeypatch.setattr(evaluation_service, "CHECKPOINT_DB", str(checkpoint_db))

    ergebnis = setze_teilnehmer_evaluation_zurueck("P2")

    with db_connection() as (conn, cursor):
        cursor.execute(
            "SELECT COUNT(*) FROM evaluation_teilnehmende WHERE teilnehmer_code = 'P2'"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT COUNT(*) FROM evaluation_teilnehmende WHERE teilnehmer_code = 'P1'"
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT COUNT(*) FROM chat_sessions WHERE thread_id = 'reset-test-thread'"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT bestand, mindestbestand FROM produkte WHERE name = 'Schrauben M4x10'"
        )
        assert cursor.fetchone() == (3, 50)
    with closing(sqlite3.connect(checkpoint_db)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM writes").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0
    assert ergebnis == {"teilnehmer_code": "P2", "chat_sitzungen": 1}


def test_teilnehmerbericht_enthält_kriterien_und_maskiert_eingaben():
    """Der HTML-Bericht bündelt Prüfkriterien ohne unsichere Nutzereingaben."""
    _registriere("P1")
    durchlauf = hole_aktuellen_durchlauf("P1")
    aufgabe = starte_aufgabe(durchlauf["id"], "T1")
    schliesse_aufgabe_ab(
        aufgabe["id"],
        {"bestand": 7, "mindestbestand": 25, "fehlmenge": 18},
    )
    speichere_aufgabenfeedback(aufgabe["id"], 3, "<script>nicht ausführen</script>")

    bericht = exportiere_teilnehmerbericht_html("P1").decode("utf-8")

    assert "<h4>Soll</h4>" in bericht
    assert "Eingegebene Werte korrekt" in bericht
    assert "Teilnehmerprofil" in bericht
    assert "&lt;script&gt;nicht ausführen&lt;/script&gt;" in bericht
    assert "NVIDIA_API_KEY" not in bericht


def test_reload_stellt_aufgabe_und_leeren_aufgabenchat_wieder_her(monkeypatch):
    """Query-Parameter rekonstruieren Aufgabe, Seite und zugehörige Chatsitzung."""
    _registriere("P2")
    durchlauf = hole_aktuellen_durchlauf("P2")
    aufgabe = starte_aufgabe(durchlauf["id"], "T1", "aufgaben-thread")
    fake_st = SimpleNamespace(
        session_state=SessionState(
            {
                "config": {"configurable": {"thread_id": "fremder-thread"}},
                "messages": [{"role": "user", "content": "alte Nachricht"}],
            }
        ),
        query_params={
            "evaluation_task": str(aufgabe["id"]),
            "evaluation_participant": "P2",
        },
    )
    monkeypatch.setattr(evaluation_view, "st", fake_st)
    monkeypatch.setattr(evaluation_view, "lade_nachrichten", lambda thread_id: [])
    reset = Mock()
    monkeypatch.setattr(evaluation_view, "reset_state", reset)

    wiederhergestellt = evaluation_view.restore_evaluation_context()

    assert wiederhergestellt["id"] == aufgabe["id"]
    assert fake_st.session_state.seite == "Agent"
    assert fake_st.session_state.messages == []
    assert fake_st.session_state["_evaluation_resume_notice"] == aufgabe["id"]
    assert fake_st.session_state.config["configurable"]["thread_id"] == "aufgaben-thread"
    reset.assert_called_once()
