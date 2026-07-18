"""Tests für Budget-Tools: Abfrage und Erstellung."""
import pytest
from agent.tools.budget import check_budget, erstelle_budget


class TestCheckBudget:
    """Tests für die Budget-Abfrage."""

    def test_zeigt_budget_uebersicht(self):
        """Budget-Abfrage sollte mindestens die Seed-Budgets zeigen."""
        result = check_budget.invoke({})
        assert "Budget-Übersicht:" in result
        assert "Euro" in result

    def test_zeigt_aktuelles_quartal(self):
        """Das aktuelle Quartal sollte markiert sein."""
        result = check_budget.invoke({})
        assert "[AKTUELL]" in result

    def test_zeigt_status(self):
        """Budget-Status (OK/WARNUNG/KRITISCH) sollte angezeigt werden."""
        result = check_budget.invoke({})
        assert any(s in result for s in ["[OK]", "[WARNUNG]", "[KRITISCH]"])

    def test_zeigt_verbrauchsprozent(self):
        """Verbrauchsprozent sollte berechnet werden."""
        result = check_budget.invoke({})
        assert "%" in result


class TestErstelleBudget:
    """Tests für die Budget-Erstellung."""

    def test_erstellt_neues_budget(self):
        """Ein neues Budget für ein freies Quartal sollte angelegt werden."""
        result = erstelle_budget.invoke({
            "quartal": 1,
            "jahr": 2099,
            "gesamtbudget": 10000.0,
        })
        assert "erfolgreich angelegt" in result
        assert "Q1/2099" in result
        assert "10000.00" in result

    def test_verhindert_doppeltes_budget(self):
        """Ein Budget für ein bestehendes Quartal sollte abgelehnt werden."""
        erstelle_budget.invoke({
            "quartal": 3,
            "jahr": 2099,
            "gesamtbudget": 5000.0,
        })
        result = erstelle_budget.invoke({
            "quartal": 3,
            "jahr": 2099,
            "gesamtbudget": 5000.0,
        })
        assert "existiert bereits" in result

    def test_validiert_quartal(self):
        """Ungültige Quartale (ausserhalb 1-4) sollten abgelehnt werden."""
        result = erstelle_budget.invoke({
            "quartal": 5,
            "jahr": 2099,
            "gesamtbudget": 5000.0,
        })
        assert "Fehler" in result
        assert "zwischen 1 und 4" in result

    def test_validiert_jahr(self):
        """Jahre außerhalb des unterstützten Bereichs werden abgelehnt."""
        result = erstelle_budget.invoke({
            "quartal": 1,
            "jahr": 1900,
            "gesamtbudget": 1000.0,
        })
        assert "Fehler" in result
        assert "Jahr" in result
