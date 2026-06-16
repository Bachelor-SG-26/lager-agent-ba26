from langchain_core.tools import tool

from database.operations import create_budget
from database.queries import get_current_budget


def _format_currency(value):
    return f"{value:.2f} €"


@tool
def check_budget() -> str:
    """Zeigt das aktuelle Quartalsbudget mit Verbrauch und Restbetrag."""
    budget = get_current_budget()
    if not budget:
        return "Es ist noch kein Budget hinterlegt."

    return (
        f"Budget Q{budget['quartal']}/{budget['jahr']}:\n"
        f"- Gesamtbudget: {_format_currency(budget['gesamtbudget'])}\n"
        f"- Verbrauchtes Budget: {_format_currency(budget['verbrauchtes_budget'])}\n"
        f"- Freies Budget: {_format_currency(budget['freies_budget'])}\n"
        f"- Verbrauchsquote: {budget['verbrauchsquote'] * 100:.1f}%"
    )


@tool
def erstelle_budget(quartal: int, jahr: int, gesamtbudget: float) -> str:
    """Legt ein neues Budget für ein Quartal an."""
    result = create_budget(quartal, jahr, gesamtbudget)
    if not result["success"]:
        return f"Fehler: {result['message']}"

    return (
        f"Budget für Q{result['quarter']}/{result['year']} angelegt: "
        f"{_format_currency(result['total_budget'])}"
    )
