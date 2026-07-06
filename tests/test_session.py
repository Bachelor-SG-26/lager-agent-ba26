"""Tests für die Session-Verwaltung: Erstellen, Laden, Löschen."""
import pytest
from services.session import (
    erstelle_session,
    aktualisiere_session_titel,
    lade_alle_sessions,
    lade_letzte_session,
    speichere_nachricht,
    lade_nachrichten,
    loesche_session,
    benenne_session_um,
)


class TestSessionErstellen:
    """Tests für das Erstellen und Laden von Sessions."""

    def test_erstellt_session(self):
        """Eine neue Session sollte in der DB angelegt werden."""
        erstelle_session("test-session-1")
        sessions = lade_alle_sessions()
        thread_ids = [s[0] for s in sessions]
        assert "test-session-1" in thread_ids

    def test_doppeltes_erstellen_ignoriert(self):
        """Doppeltes Erstellen mit gleicher thread_id sollte keinen Fehler werfen."""
        erstelle_session("test-doppelt")
        erstelle_session("test-doppelt")  # Sollte keinen Fehler werfen
        sessions = lade_alle_sessions()
        count = sum(1 for s in sessions if s[0] == "test-doppelt")
        assert count == 1


class TestSessionTitel:
    """Tests für die automatische Titel-Vergabe."""

    def test_setzt_titel(self):
        """Der Titel sollte auf die erste Nachricht gesetzt werden."""
        erstelle_session("test-titel")
        aktualisiere_session_titel("test-titel", "Wie ist der Lagerbestand?")
        sessions = lade_alle_sessions()
        session = next(s for s in sessions if s[0] == "test-titel")
        assert session[1] == "Wie ist der Lagerbestand?"

    def test_kuerzt_langen_titel(self):
        """Titel laenger als 50 Zeichen sollten gekuerzt werden."""
        erstelle_session("test-lang")
        langer_text = "A" * 100
        aktualisiere_session_titel("test-lang", langer_text)
        sessions = lade_alle_sessions()
        session = next(s for s in sessions if s[0] == "test-lang")
        assert session[1].endswith("...")
        assert len(session[1]) == 53  # 50 + "..."


class TestNachrichten:
    """Tests für das Speichern und Laden von Nachrichten."""

    def test_speichert_und_laedt_nachricht(self):
        """Nachrichten sollten gespeichert und wieder geladen werden können."""
        erstelle_session("test-msg")
        speichere_nachricht("test-msg", "user", "Hallo Agent")
        speichere_nachricht("test-msg", "assistant", "Hallo! Wie kann ich helfen?")

        msgs = lade_nachrichten("test-msg")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hallo Agent"
        assert msgs[1]["role"] == "assistant"

    def test_speichert_tools_used(self):
        """Die tools_used Liste sollte korrekt serialisiert werden."""
        erstelle_session("test-tools")
        speichere_nachricht(
            "test-tools", "assistant", "Ergebnis",
            tools_used=["check_lagerbestand", "check_engpaesse"],
        )

        msgs = lade_nachrichten("test-tools")
        assert msgs[0]["tools_used"] == ["check_lagerbestand", "check_engpaesse"]

    def test_leere_session_gibt_leere_liste(self):
        """Eine Session ohne Nachrichten sollte eine leere Liste liefern."""
        msgs = lade_nachrichten("nicht-existent")
        assert msgs == []


class TestSessionLoeschen:
    """Tests für das Löschen von Sessions."""

    def test_loescht_session_und_nachrichten(self):
        """Beim Löschen sollten Session und Nachrichten entfernt werden."""
        erstelle_session("test-del")
        speichere_nachricht("test-del", "user", "Test")
        speichere_nachricht("test-del", "assistant", "Antwort")

        loesche_session("test-del")

        sessions = lade_alle_sessions()
        thread_ids = [s[0] for s in sessions]
        assert "test-del" not in thread_ids

        msgs = lade_nachrichten("test-del")
        assert msgs == []


class TestSessionUmbenennen:
    """Tests für das Umbenennen von Sessions."""

    def test_benennt_session_um(self):
        """Der Titel einer Session sollte geändert werden können."""
        erstelle_session("test-rename")
        benenne_session_um("test-rename", "Neuer Titel")
        sessions = lade_alle_sessions()
        session = next(s for s in sessions if s[0] == "test-rename")
        assert session[1] == "Neuer Titel"

    def test_umbenennen_ueberschreibt_alten_titel(self):
        """Auch ein bereits manuell gesetzter Titel sollte überschrieben werden."""
        erstelle_session("test-rename2")
        aktualisiere_session_titel("test-rename2", "Erster Titel")
        benenne_session_um("test-rename2", "Zweiter Titel")
        sessions = lade_alle_sessions()
        session = next(s for s in sessions if s[0] == "test-rename2")
        assert session[1] == "Zweiter Titel"


class TestLetzteSession:
    """Tests für das Laden der letzten Session."""

    def test_gibt_neueste_session_zurueck(self):
        """lade_letzte_session sollte die zuletzt erstellte Session liefern."""
        import time
        erstelle_session("test-alt")
        time.sleep(1.1)  # Sicherstellen dass der Zeitstempel sich unterscheidet
        erstelle_session("test-neu")
        letzte = lade_letzte_session()
        assert letzte == "test-neu"
