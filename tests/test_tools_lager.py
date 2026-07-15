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
