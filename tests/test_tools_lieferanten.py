"""Tests für Lieferanten-Tools: Vergleich und Erstellung."""
import pytest
from agent.tools.lieferanten import (
    vergleiche_lieferanten,
    vergleiche_lieferanten_batch,
    erstelle_lieferant,
)
from config import BATCH_DEFAULT_MAX_POSITIONEN


class TestVergleicheLieferanten:
    """Tests für den Lieferantenvergleich mit gewichteter Bewertung."""

    def test_zeigt_vergleich(self):
        """Für Produkt 1 (Schrauben M4x10) sollte ein Vergleich angezeigt werden."""
        result = vergleiche_lieferanten.invoke({"produkt_id": 1})
        assert "Lieferantenvergleich" in result
        assert "Schrauben M4x10" in result

    def test_zeigt_standard_lieferant(self):
        """Der Standard-Lieferant sollte markiert sein."""
        result = vergleiche_lieferanten.invoke({"produkt_id": 1})
        assert "Standard" in result

    def test_zeigt_empfehlung(self):
        """Es sollte eine Empfehlung gegeben werden."""
        result = vergleiche_lieferanten.invoke({"produkt_id": 1})
        assert "Empfehlung:" in result
        assert "Preis-Leistungs-Verhältnis" in result

    def test_ungueltige_produkt_id(self):
        """Nicht existierendes Produkt sollte Fehler liefern."""
        result = vergleiche_lieferanten.invoke({"produkt_id": 9999})
        assert "Fehler" in result

    def test_zeigt_preis_und_lieferzeit(self):
        """Preis und Lieferzeit sollten für jeden Lieferanten angezeigt werden."""
        result = vergleiche_lieferanten.invoke({"produkt_id": 1})
        assert "Tage" in result
        assert "E" in result  # Euro-Abkuerzung


class TestVergleicheLieferantenBatch:
    """Tests für den Batch-Lieferantenvergleich."""

    def test_leere_liste_liefert_fehler(self):
        result = vergleiche_lieferanten_batch.invoke({"produkt_ids": []})
        assert "Fehler" in result
        assert "Keine Produkt-IDs" in result

    def test_zu_viele_ids_liefert_fehler(self):
        ids = list(range(1, BATCH_DEFAULT_MAX_POSITIONEN + 2))
        result = vergleiche_lieferanten_batch.invoke({"produkt_ids": ids})
        assert "Fehler" in result
        assert "Zu viele" in result

    def test_vergleicht_mehrere_produkte(self):
        result = vergleiche_lieferanten_batch.invoke({"produkt_ids": [1, 2]})
        assert "Batch-Lieferantenvergleich" in result
        assert "1. Produkt-ID 1" in result
        assert "2. Produkt-ID 2" in result
        assert "Lieferantenvergleich" in result

    def test_enthaelt_zusammenfassung(self):
        result = vergleiche_lieferanten_batch.invoke({"produkt_ids": [1, 2, 3]})
        assert "Zusammenfassung" in result
        assert "empfohlen" in result

    def test_nicht_existierendes_produkt_wird_gemeldet(self):
        """Einzelne ungültige ID bricht den Batch nicht ab."""
        result = vergleiche_lieferanten_batch.invoke({"produkt_ids": [1, 9999]})
        assert "Batch-Lieferantenvergleich" in result
        assert "1. Produkt-ID 1" in result
        assert "2. Produkt-ID 9999" in result
        assert "nicht gefunden" in result


class TestErstelleLieferant:
    """Tests für die Lieferanten-Erstellung."""

    def test_erstellt_neuen_lieferant(self):
        """Ein neuer Lieferant sollte angelegt werden."""
        result = erstelle_lieferant.invoke({
            "name": "TestLieferant GmbH",
            "kontakt": "test@test.de",
            "lieferzeit_tage": 3,
            "bewertung": 4.0,
        })
        assert "erfolgreich angelegt" in result
        assert "TestLieferant GmbH" in result

    def test_verhindert_duplikat(self):
        """Ein Lieferant mit gleichem Namen sollte abgelehnt werden."""
        result = erstelle_lieferant.invoke({
            "name": "Würth",
            "kontakt": "test@test.de",
            "lieferzeit_tage": 3,
            "bewertung": 4.0,
        })
        assert "existiert bereits" in result

    def test_validiert_bewertung(self):
        """Bewertung ausserhalb 1.0-5.0 sollte abgelehnt werden."""
        result = erstelle_lieferant.invoke({
            "name": "Ungültig AG",
            "kontakt": "test@test.de",
            "lieferzeit_tage": 3,
            "bewertung": 6.0,
        })
        assert "Fehler" in result
        assert "zwischen 1.0 und 5.0" in result


def test_erstelle_lieferant_validiert_negative_lieferzeit():
    """Negative Lieferzeiten sollten abgelehnt werden."""
    result = erstelle_lieferant.invoke({
        "name": "Negativzeit GmbH",
        "kontakt": "test@test.de",
        "lieferzeit_tage": -1,
        "bewertung": 4.0,
    })
    assert "Fehler" in result
    assert "Lieferzeit" in result
