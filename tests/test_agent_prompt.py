"""Tests für Tool-Registry und System-Prompt des Agenten."""

from agent.prompt import SYSTEM_PROMPT
from agent.tools import TOOL_COUNT, TOOL_NAMES


EXPECTED_TOOL_NAMES = (
    "check_lagerbestand",
    "check_engpaesse",
    "check_budget",
    "erstelle_bestellung",
    "erstelle_bestellung_batch",
    "check_bestellhistorie",
    "erfasse_entnahme",
    "prognostiziere_bedarf",
    "prognostiziere_bedarf_batch",
    "vergleiche_lieferanten",
    "vergleiche_lieferanten_batch",
    "erstelle_produkt",
    "erstelle_lieferant",
    "erstelle_budget",
    "aktualisiere_produkt",
    "aktualisiere_lieferant",
)


def test_tool_registry_is_complete_and_unique():
    """Prüft Anzahl, Reihenfolge und Eindeutigkeit der registrierten Tools."""
    assert TOOL_COUNT == 16
    assert TOOL_NAMES == EXPECTED_TOOL_NAMES
    assert len(set(TOOL_NAMES)) == TOOL_COUNT


def test_system_prompt_contains_complete_tool_catalog():
    """Prüft, ob der Prompt Anzahl und Namen aus der Registry aufführt."""
    assert f"genau {TOOL_COUNT} Tools" in SYSTEM_PROMPT

    for tool_name in TOOL_NAMES:
        assert f"`{tool_name}`" in SYSTEM_PROMPT
