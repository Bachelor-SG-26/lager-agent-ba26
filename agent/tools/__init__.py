from agent.tools.lager import check_lagerbestand, check_engpaesse
from agent.tools.bestellungen import (
    erstelle_bestellung,
    erstelle_bestellung_batch,
    check_bestellhistorie,
)
from agent.tools.budget import check_budget, erstelle_budget
from agent.tools.entnahme import erfasse_entnahme
from agent.tools.prognose import prognostiziere_bedarf, prognostiziere_bedarf_batch
from agent.tools.lieferanten import (
    check_lieferanten,
    vergleiche_lieferanten,
    vergleiche_lieferanten_batch,
    erstelle_lieferant,
)
from agent.tools.produkte import erstelle_produkt
from agent.tools.update import aktualisiere_produkt, aktualisiere_lieferant

ALL_TOOLS = [
    check_lagerbestand,
    check_engpaesse,
    check_budget,
    erstelle_bestellung,
    erstelle_bestellung_batch,
    check_bestellhistorie,
    erfasse_entnahme,
    prognostiziere_bedarf,
    prognostiziere_bedarf_batch,
    check_lieferanten,
    vergleiche_lieferanten,
    vergleiche_lieferanten_batch,
    erstelle_produkt,
    erstelle_lieferant,
    erstelle_budget,
    aktualisiere_produkt,
    aktualisiere_lieferant,
]

TOOL_NAMES = tuple(tool.name for tool in ALL_TOOLS)
TOOL_COUNT = len(TOOL_NAMES)
