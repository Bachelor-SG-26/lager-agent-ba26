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
    "check_lieferanten",
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
    assert TOOL_COUNT == 17
    assert TOOL_NAMES == EXPECTED_TOOL_NAMES
    assert len(set(TOOL_NAMES)) == TOOL_COUNT


def test_system_prompt_contains_complete_tool_catalog():
    """Prüft, ob der Prompt Anzahl und Namen aus der Registry aufführt."""
    assert f"genau {TOOL_COUNT} Tools" in SYSTEM_PROMPT

    for tool_name in TOOL_NAMES:
        assert f"`{tool_name}`" in SYSTEM_PROMPT


def test_system_prompt_resolves_product_names_before_follow_up_tools():
    """Prüft die gezielte Namensauflösung für nachfolgende Produkt-Tools."""
    assert "`check_lagerbestand` mit `suchbegriff`" in SYSTEM_PROMPT
    assert "gefundene Produkt-ID für weitere Tools" in SYSTEM_PROMPT


def test_system_prompt_avoids_redundant_supplier_confirmation():
    """Prüft die direkte Fortsetzung bei bereits genanntem Auswahlkriterium."""
    assert "weder ein Lieferant noch ein Auswahlkriterium genannt" in SYSTEM_PROMPT
    assert "nicht erneut nach einem Kriterium fragen" in SYSTEM_PROMPT
    assert "die passende `lieferant_id`" in SYSTEM_PROMPT


def test_system_prompt_forbids_placeholder_ids_in_dependent_steps():
    """Prüft, ob Folgeschritte nur mit realen Ergebnissen geplant werden."""
    assert "jedes Tool-Ergebnis abwarten" in SYSTEM_PROMPT
    assert "niemals Platzhalter oder erfundene IDs" in SYSTEM_PROMPT
    assert "empfohlen oder ohne nähere Gewichtung = bestes Verhältnis" in SYSTEM_PROMPT
