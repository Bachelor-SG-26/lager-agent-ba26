from agent.tools.entnahme import erfasse_entnahme
from agent.tools.lager import check_engpaesse, check_lagerbestand


ALL_TOOLS = [
    check_lagerbestand,
    check_engpaesse,
    erfasse_entnahme,
]
