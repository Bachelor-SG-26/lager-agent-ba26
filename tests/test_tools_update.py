"""Tests für Update-Tools: Produkte und Lieferanten aktualisieren."""
import pytest
from agent.tools.update import aktualisiere_produkt, aktualisiere_lieferant


class TestAktualisiereProdukt:
    """Tests für das Aktualisieren von Produkten."""

    def test_aktualisiert_name(self):
        """Produktname sollte geändert werden können."""
        result = aktualisiere_produkt.invoke({
            "produkt_id": 1,
            "name": "Schrauben M4x10 verzinkt",
        })
        assert "aktualisiert" in result
        assert "Schrauben M4x10 verzinkt" in result

    def test_aktualisiert_mehrere_felder(self):
        """Mehrere Felder gleichzeitig sollten aktualisiert werden."""
        result = aktualisiere_produkt.invoke({
            "produkt_id": 2,
            "mindestbestand": 100,
            "preis_pro_einheit": 0.08,
        })
        assert "aktualisiert" in result
        assert "Mindestbestand" in result
        assert "Preis" in result

    def test_preis_bleibt_mit_standardlieferant_konsistent(self, db_cursor):
        """Der Produktpreis muss auch für Bestellungen beim Standardlieferanten gelten."""
        cursor, _ = db_cursor
        aktualisiere_produkt.invoke({
            "produkt_id": 1,
            "preis_pro_einheit": 0.42,
        })

        cursor.execute(
            """
            SELECT p.preis_pro_einheit, pl.preis
            FROM produkte p
            JOIN produkt_lieferanten pl
              ON pl.produkt_id = p.id
             AND pl.lieferant_id = p.standard_lieferant_id
            WHERE p.id = 1
            """
        )
        produktpreis, bestellpreis = cursor.fetchone()
        assert produktpreis == pytest.approx(0.42)
        assert bestellpreis == pytest.approx(0.42)

    def test_ungueltige_produkt_id(self):
        """Nicht existierende Produkt-ID sollte Fehler liefern."""
        result = aktualisiere_produkt.invoke({"produkt_id": 9999, "name": "Test"})
        assert "Fehler" in result
        assert "nicht gefunden" in result

    def test_duplikat_name_abgelehnt(self):
        """Ein bereits existierender Name sollte abgelehnt werden."""
        result = aktualisiere_produkt.invoke({
            "produkt_id": 1,
            "name": "Schrauben M4x20",  # Existiert bereits als Produkt 2
        })
        assert "Fehler" in result
        assert "existiert bereits" in result

    def test_keine_aenderungen(self):
        """Ohne Änderungen sollte eine Info-Meldung kommen."""
        result = aktualisiere_produkt.invoke({"produkt_id": 1})
        assert "Keine Änderungen" in result

    def test_aktualisiert_bestand(self):
        """Bestand sollte korrigiert werden können."""
        result = aktualisiere_produkt.invoke({
            "produkt_id": 1,
            "bestand": 999,
        })
        assert "aktualisiert" in result
        assert "Bestand" in result
        assert "999" in result

    def test_validiert_negative_produktwerte(self):
        """Negative oder ungueltige Produktwerte sollten abgelehnt werden."""
        faelle = [
            {"produkt_id": 1, "bestand": -1},
            {"produkt_id": 1, "mindestbestand": -1},
            {"produkt_id": 1, "preis_pro_einheit": 0},
            {"produkt_id": 1, "name": "   "},
        ]
        for payload in faelle:
            result = aktualisiere_produkt.invoke(payload)
            assert "Fehler" in result


class TestAktualisiereLieferant:
    """Tests für das Aktualisieren von Lieferanten."""

    def test_aktualisiert_name(self):
        """Lieferantenname sollte geändert werden können."""
        result = aktualisiere_lieferant.invoke({
            "lieferant_id": 1,
            "name": "Wuerth Deutschland",
        })
        assert "aktualisiert" in result
        assert "Wuerth Deutschland" in result

    def test_aktualisiert_bewertung(self):
        """Bewertung sollte aktualisiert werden können."""
        result = aktualisiere_lieferant.invoke({
            "lieferant_id": 1,
            "bewertung": 4.8,
        })
        assert "aktualisiert" in result
        assert "Bewertung" in result

    def test_ungueltige_bewertung(self):
        """Bewertung ausserhalb 1.0-5.0 sollte abgelehnt werden."""
        result = aktualisiere_lieferant.invoke({
            "lieferant_id": 1,
            "bewertung": 6.0,
        })
        assert "Fehler" in result
        assert "zwischen 1.0 und 5.0" in result

    def test_ungueltige_lieferant_id(self):
        """Nicht existierende Lieferant-ID sollte Fehler liefern."""
        result = aktualisiere_lieferant.invoke({
            "lieferant_id": 9999,
            "name": "Test",
        })
        assert "Fehler" in result
        assert "nicht gefunden" in result

    def test_duplikat_name_abgelehnt(self):
        """Ein bereits existierender Name sollte abgelehnt werden."""
        result = aktualisiere_lieferant.invoke({
            "lieferant_id": 1,
            "name": "Bossard",  # Existiert bereits
        })
        assert "Fehler" in result
        assert "existiert bereits" in result

    def test_keine_aenderungen(self):
        """Ohne Änderungen sollte eine Info-Meldung kommen."""
        result = aktualisiere_lieferant.invoke({"lieferant_id": 1})
        assert "Keine Änderungen" in result
def test_aktualisiere_lieferant_validiert_negative_lieferzeit():
    """Negative Lieferzeiten sollten abgelehnt werden."""
    result = aktualisiere_lieferant.invoke({
        "lieferant_id": 1,
        "lieferzeit_tage": -1,
    })
    assert "Fehler" in result
    assert "Lieferzeit" in result


def test_aktualisiere_lieferant_validiert_leeren_namen():
    """Leere Lieferantennamen sollten abgelehnt werden."""
    result = aktualisiere_lieferant.invoke({
        "lieferant_id": 1,
        "name": "   ",
    })
    assert "Fehler" in result
