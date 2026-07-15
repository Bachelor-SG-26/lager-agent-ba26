"""Tests für Produkt-Tool: Produkterstellung mit Validierung."""
import pytest
from agent.tools.produkte import erstelle_produkt


class TestErstelleProdukt:
    """Tests für die Produkt-Erstellung."""

    def test_erstellt_neues_produkt(self):
        """Ein neues Produkt sollte angelegt werden."""
        result = erstelle_produkt.invoke({
            "name": "Testschraube M99",
            "mindestbestand": 20,
            "preis_pro_einheit": 0.50,
            "lieferant_id": 1,
        })
        assert "erfolgreich angelegt" in result
        assert "Testschraube M99" in result
        assert "Bestand:         0" in result

    def test_lieferanten_zuordnung(self):
        """Das Produkt sollte automatisch dem Lieferanten zugeordnet werden."""
        result = erstelle_produkt.invoke({
            "name": "Zuordnungstest",
            "mindestbestand": 10,
            "preis_pro_einheit": 1.00,
            "lieferant_id": 1,
        })
        assert "erfolgreich angelegt" in result

        # Zuordnung in produkt_lieferanten prüfen
        from database.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM produkte WHERE name = 'Zuordnungstest'")
        produkt_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM produkt_lieferanten WHERE produkt_id = ?",
            (produkt_id,),
        )
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_verhindert_duplikat(self):
        """Ein Produkt mit gleichem Namen sollte abgelehnt werden."""
        result = erstelle_produkt.invoke({
            "name": "Schrauben M4x10",
            "mindestbestand": 50,
            "preis_pro_einheit": 0.05,
            "lieferant_id": 1,
        })
        assert "existiert bereits" in result

    def test_ungueltiger_lieferant(self):
        """Ein nicht existierender Lieferant sollte abgelehnt werden."""
        result = erstelle_produkt.invoke({
            "name": "Fehlprodukt",
            "mindestbestand": 10,
            "preis_pro_einheit": 1.00,
            "lieferant_id": 9999,
        })
        assert "Fehler" in result
        assert "nicht gefunden" in result

    def test_leerer_name(self):
        """Ein Produkt benötigt einen sichtbaren Namen."""
        result = erstelle_produkt.invoke({
            "name": "   ",
            "mindestbestand": 10,
            "preis_pro_einheit": 2.5,
            "lieferant_id": 1,
        })
        assert "Produktname darf nicht leer sein" in result
