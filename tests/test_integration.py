"""Integration-Tests: Zusammenhängende Workflows testen.

Diese Tests prüfen ob mehrere Tools korrekt zusammenarbeiten
und die Datenbank-Konsistenz gewahrt bleibt.
"""
import pytest
import re
from unittest.mock import patch
from agent.tools.lager import check_lagerbestand, check_engpaesse
from agent.tools.bestellungen import erstelle_bestellung
from agent.tools.entnahme import erfasse_entnahme
from agent.tools.budget import check_budget
from agent.tools.prognose import prognostiziere_bedarf
from agent.tools.lieferanten import vergleiche_lieferanten
from database.database import get_connection


class TestEntnahmeUndEngpass:
    """Workflow: Entnahme führt zu Engpass, der erkannt wird."""

    def test_entnahme_erzeugt_engpass(self):
        """Nach Entnahme sollte das Produkt als Engpass erkannt werden."""
        # Produkt 2 (Schrauben M4x20): Bestand 80, Mindest 50 -> OK
        engpaesse_vorher = check_engpaesse.invoke({"limit": 0})

        # Bestand auf unter Minimum senken
        erfasse_entnahme.invoke({
            "produkt_id": 2,
            "menge": 40,
            "grund": "Produktion",
        })

        # Jetzt sollte es als Engpass erkannt werden
        engpaesse_nachher = check_engpaesse.invoke({"limit": 0})
        assert "Schrauben M4x20" in engpaesse_nachher


class TestBestellungUndBudget:
    """Workflow: Bestellung reduziert Budget korrekt."""

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_bestellung_reduziert_budget(self, mock_telegram):
        """Budget sollte nach Bestellung weniger Restbetrag haben."""
        budget_vorher = check_budget.invoke({})

        erstelle_bestellung.invoke({"produkt_id": 1, "menge": 100})

        budget_nachher = check_budget.invoke({})

        # Budget-Text hat sich geändert (andere Zahlen)
        assert budget_vorher != budget_nachher

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_bestellung_erhoeht_bestand(self, mock_telegram):
        """Bestand sollte nach Bestellung hoeher sein."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bestand FROM produkte WHERE id = 1")
        bestand_vorher = cursor.fetchone()[0]
        conn.close()

        erstelle_bestellung.invoke({"produkt_id": 1, "menge": 50})

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bestand FROM produkte WHERE id = 1")
        bestand_nachher = cursor.fetchone()[0]
        conn.close()

        assert bestand_nachher == bestand_vorher + 50


class TestEntnahmeUndPrognose:
    """Workflow: Entnahme beeinflusst die Bedarfsprognose."""

    def test_entnahme_wird_in_prognose_beruecksichtigt(self):
        """Neue Entnahmen sollten die Prognose verändern."""
        prognose_vorher = prognostiziere_bedarf.invoke({"produkt_id": 2})

        # Mehrere Entnahmen erfassen
        for _ in range(5):
            erfasse_entnahme.invoke({
                "produkt_id": 2,
                "menge": 3,
                "grund": "Produktion",
            })

        prognose_nachher = prognostiziere_bedarf.invoke({"produkt_id": 2})

        # Prognose sollte sich geändert haben (anderer Bestand, anderer Verbrauch)
        assert prognose_vorher != prognose_nachher


class TestKomplettWorkflow:
    """Workflow: Kompletter Prozess von Engpass-Erkennung bis Bestellung."""

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_engpass_erkennen_und_bestellen(self, mock_telegram):
        """Engpass erkennen -> Lieferanten vergleichen -> Bestellen -> Engpass behoben."""
        # 1. Engpass erkennen
        engpaesse = check_engpaesse.invoke({})
        assert "Schrauben M4x10" in engpaesse  # Bestand 3, Mindest 50

        # 2. Lieferanten vergleichen
        vergleich = vergleiche_lieferanten.invoke({"produkt_id": 1})
        assert "Empfehlung" in vergleich

        # 3. Prognose abrufen
        prognose = prognostiziere_bedarf.invoke({"produkt_id": 1})
        assert "Empfohlene Bestellung" in prognose

        # 4. Bestellen
        result = erstelle_bestellung.invoke({"produkt_id": 1, "menge": 100})
        assert "erfolgreich" in result

        # 5. Bestand prüfen — sollte jetzt über Minimum sein
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT bestand, mindestbestand FROM produkte WHERE id = 1"
        )
        bestand, mindest = cursor.fetchone()
        conn.close()
        assert bestand >= mindest

    @patch("agent.tools.bestellungen.send_telegram", return_value=True)
    def test_produktsuche_bis_bestellung_beim_empfohlenen_lieferanten(
        self,
        mock_telegram,
    ):
        """Ein Produktname wird bis zur eindeutigen Lieferantenbestellung aufgelöst."""
        suche = check_lagerbestand.invoke({
            "suchbegriff": "Sechskantmutter M10",
        })
        produkt_treffer = re.search(r"\[ID:(\d+)\]", suche)
        assert produkt_treffer
        produkt_id = int(produkt_treffer.group(1))

        vergleich = vergleiche_lieferanten.invoke({"produkt_id": produkt_id})
        empfehlung = re.search(r"Empfehlung: .+ \(ID: (\d+),", vergleich)
        assert empfehlung
        lieferant_id = int(empfehlung.group(1))

        bestellung = erstelle_bestellung.invoke({
            "produkt_id": produkt_id,
            "menge": 40,
            "lieferant_id": lieferant_id,
        })
        assert "Bestellung erfolgreich angelegt" in bestellung
        assert f"ID: {lieferant_id}" in bestellung


class TestDatenbank_Konsistenz:
    """Tests für die Datenbank-Integritaet."""

    def test_seed_daten_vollstaendig(self):
        """Alle Seed-Daten sollten korrekt angelegt sein."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM lieferanten")
        assert cursor.fetchone()[0] == 30

        cursor.execute("SELECT COUNT(*) FROM produkte")
        assert cursor.fetchone()[0] == 100

        cursor.execute("SELECT COUNT(*) FROM budget")
        assert cursor.fetchone()[0] == 2

        cursor.execute("SELECT COUNT(*) FROM verbrauch")
        verbrauch = cursor.fetchone()[0]
        assert verbrauch > 0

        cursor.execute("SELECT COUNT(*) FROM bestellungen")
        bestellungen = cursor.fetchone()[0]
        assert bestellungen > 0

        conn.close()

    def test_fremdschluessel_korrekt(self):
        """Alle Produkte sollten einen gültigen Lieferanten referenzieren."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM produkte p
            WHERE NOT EXISTS (
                SELECT 1 FROM lieferanten l WHERE l.id = p.standard_lieferant_id
            )
        """)
        assert cursor.fetchone()[0] == 0
        conn.close()

    def test_fremdschluesselpruefung_ist_aktiv(self):
        """Jede Anwendungsverbindung erzwingt deklarierte Fremdschlüssel."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1
        conn.close()
