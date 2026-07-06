"""Tests für Entnahme-Tool: Materialentnahme mit Bestandsprüfung."""
import pytest
from agent.tools.entnahme import erfasse_entnahme


class TestErfasseEntnahme:
    """Tests für die Materialentnahme."""

    def test_erfolgreiche_entnahme(self):
        """Eine gültige Entnahme sollte den Bestand reduzieren."""
        result = erfasse_entnahme.invoke({
            "produkt_id": 2,
            "menge": 1,
            "grund": "Produktion",
        })
        assert "Entnahme erfasst" in result
        assert "Produktion" in result

    def test_bestand_wird_reduziert(self):
        """Nach Entnahme sollte der Bestand gesunken sein."""
        from database.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bestand FROM produkte WHERE id = 2")
        alter_bestand = cursor.fetchone()[0]
        conn.close()

        erfasse_entnahme.invoke({
            "produkt_id": 2,
            "menge": 1,
            "grund": "Wartung",
        })

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bestand FROM produkte WHERE id = 2")
        neuer_bestand = cursor.fetchone()[0]
        conn.close()

        assert neuer_bestand == alter_bestand - 1

    def test_verbrauch_wird_protokolliert(self):
        """Die Entnahme sollte in der Verbrauchstabelle protokolliert werden."""
        from database.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verbrauch WHERE produkt_id = 2")
        vorher = cursor.fetchone()[0]
        conn.close()

        erfasse_entnahme.invoke({
            "produkt_id": 2,
            "menge": 1,
            "grund": "Montage",
        })

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verbrauch WHERE produkt_id = 2")
        nachher = cursor.fetchone()[0]
        conn.close()

        assert nachher == vorher + 1

    def test_zu_hohe_menge(self):
        """Entnahme über dem Bestand sollte abgelehnt werden."""
        result = erfasse_entnahme.invoke({
            "produkt_id": 2,
            "menge": 99999,
            "grund": "Produktion",
        })
        assert "Nicht genug Bestand" in result

    def test_ungueltige_produkt_id(self):
        """Eine nicht existierende Produkt-ID sollte einen Fehler liefern."""
        result = erfasse_entnahme.invoke({
            "produkt_id": 9999,
            "menge": 1,
            "grund": "Produktion",
        })
        assert "Fehler" in result
        assert "nicht gefunden" in result

    def test_warnung_unter_mindestbestand(self):
        """Faellt der Bestand unter Minimum, sollte eine Warnung erscheinen."""
        # Produkt 1 (Schrauben M4x10) hat Bestand 3, Mindest 50
        # Bestand ist bereits unter Minimum, also eine kleine Entnahme reicht
        result = erfasse_entnahme.invoke({
            "produkt_id": 1,
            "menge": 1,
            "grund": "Produktion",
        })
        assert "WARNUNG" in result
        assert "Nachbestellung empfohlen" in result
