"""Tests für Lager-Tools: Bestandsabfrage und Engpass-Erkennung."""
import pytest
from unittest.mock import patch
from agent.tools.lager import check_lagerbestand, check_engpaesse


class TestCheckLagerbestand:
    """Tests für die Lagerbestandsabfrage."""

    def test_gibt_alle_produkte_zurueck(self):
        """Lagerbestand sollte alle 100 Seed-Produkte auflisten."""
        result = check_lagerbestand.invoke({"limit": 0})
        assert "Lagerbestand (" in result
        # Stichproben aus den Seed-Daten
        assert "Schrauben M4x10" in result
        assert "Kabelbinder 200mm 100er Pack" in result

    def test_zeigt_kritischen_status(self):
        """Produkte unter Mindestbestand sollten als KRITISCH markiert sein."""
        result = check_lagerbestand.invoke({})
        assert "[KRITISCH]" in result

    def test_zeigt_ok_status(self):
        """Produkte über Mindestbestand sollten als OK markiert sein."""
        result = check_lagerbestand.invoke({})
        assert "[OK]" in result

    def test_zeigt_preis_und_lieferant(self):
        """Jeder Eintrag sollte Preis und Lieferant enthalten."""
        result = check_lagerbestand.invoke({})
        assert "Euro/Stück" in result
        assert "Lieferant:" in result

    def test_sucht_produkt_nach_exaktem_namen(self):
        """Ein genauer Produktname sollte direkt den passenden Datensatz liefern."""
        result = check_lagerbestand.invoke({"suchbegriff": "Sechskantmutter M10"})

        assert "Produktsuche für 'Sechskantmutter M10' (1 von 1 Treffern)" in result
        assert "Sechskantmutter M10" in result
        assert "Sechskantmutter M8" not in result
        assert "[ID:" in result

    def test_sucht_produkte_teilweise_und_ohne_beachtung_der_grossschreibung(self):
        """Teilnamen sollten unabhängig von Groß- und Kleinschreibung funktionieren."""
        result = check_lagerbestand.invoke(
            {"suchbegriff": "sechskantmutter m1", "limit": 0}
        )

        assert "Sechskantmutter M10" in result
        assert "Sechskantmutter M12" in result
        assert "Sechskantmutter M8" not in result

    def test_meldet_wenn_keine_produkte_gefunden_werden(self):
        """Eine erfolglose Suche sollte eine klare Rückmeldung liefern."""
        result = check_lagerbestand.invoke({"suchbegriff": "Nicht vorhanden"})

        assert result == "Keine Produkte für 'Nicht vorhanden' gefunden."

    def test_lehnt_negatives_limit_ab(self):
        """Negative Ergebnisgrenzen sind ungültig."""
        result = check_lagerbestand.invoke({"limit": -1})

        assert result == "Fehler: Limit darf nicht negativ sein."


class TestCheckEngpaesse:
    """Tests für die Engpass-Erkennung."""

    def test_findet_engpaesse(self):
        """Es sollten kritische Produkte gefunden werden (Seed hat viele unter Minimum)."""
        result = check_engpaesse.invoke({})
        assert "Engpässe (" in result
        assert "fehlen:" in result

    def test_sortiert_nach_dringlichkeit(self):
        """Engpässe sollten nach groesster Fehlmenge sortiert sein."""
        result = check_engpaesse.invoke({})
        assert "sortiert nach Dringlichkeit" in result

    def test_zeigt_gesamtkosten(self):
        """Die Gesamtkosten für Nachbestellungen sollten berechnet werden."""
        result = check_engpaesse.invoke({})
        assert "Geschätzte Kosten für angezeigte Nachbestellungen" in result
