from agent.tools.bestellungen import (
    aktualisiere_bestellstatus,
    check_bestellhistorie,
    erstelle_bestellung,
)
from agent.tools.budget import check_budget, erstelle_budget
from agent.tools.entnahme import erfasse_entnahme
from agent.tools.lieferanten import vergleiche_lieferanten
from agent.tools.lager import check_engpaesse, check_lagerbestand
from agent.tools.prognose import prognostiziere_bedarf, prognostiziere_bedarf_batch
from agent.tools.stammdaten import (
    aktualisiere_lieferant,
    aktualisiere_produkt,
    erstelle_lieferant,
    erstelle_produkt,
)


ALL_TOOLS = [
    check_lagerbestand,
    check_engpaesse,
    erfasse_entnahme,
    check_budget,
    erstelle_budget,
    vergleiche_lieferanten,
    prognostiziere_bedarf,
    prognostiziere_bedarf_batch,
    erstelle_bestellung,
    check_bestellhistorie,
    aktualisiere_bestellstatus,
    erstelle_lieferant,
    erstelle_produkt,
    aktualisiere_lieferant,
    aktualisiere_produkt,
]
