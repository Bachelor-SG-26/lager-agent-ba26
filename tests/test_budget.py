from agent.tools.budget import check_budget, erstelle_budget
from database.database import init_db
from database.operations import create_budget
from database.queries import get_budget_history, get_budget_trend, get_current_budget


def test_current_budget_returns_seeded_quarter(test_database):
    init_db()

    budget = get_current_budget()

    assert budget["gesamtbudget"] == 5000.00
    assert budget["freies_budget"] > 0
    assert 0 < budget["verbrauchsquote"] < 1


def test_create_budget_adds_new_quarter(test_database):
    init_db()

    result = create_budget(quarter=4, year=2099, total_budget=7500.00)

    assert result["success"] is True
    assert result["quarter"] == 4
    assert result["total_budget"] == 7500.00


def test_create_budget_rejects_duplicate_quarter(test_database):
    init_db()

    create_budget(quarter=4, year=2099, total_budget=7500.00)
    result = create_budget(quarter=4, year=2099, total_budget=7500.00)

    assert result["success"] is False
    assert "bereits ein Budget vorhanden" in result["message"]


def test_budget_history_orders_latest_quarter_first(test_database):
    init_db()

    create_budget(quarter=4, year=2099, total_budget=7500.00)
    create_budget(quarter=1, year=2100, total_budget=8200.00)
    history = get_budget_history(limit=2)

    assert history[0]["jahr"] == 2100
    assert history[0]["quartal"] == 1
    assert history[0]["freies_budget"] == 8200.00


def test_budget_trend_orders_chronologically(test_database):
    init_db()

    create_budget(quarter=4, year=2099, total_budget=7500.00)
    create_budget(quarter=1, year=2100, total_budget=8200.00)
    trend = get_budget_trend(limit=2)

    assert trend[0]["jahr"] == 2099
    assert trend[0]["quartal"] == 4
    assert trend[-1]["jahr"] == 2100
    assert trend[-1]["quartal"] == 1


def test_create_budget_validates_input(test_database):
    init_db()

    result = create_budget(quarter=5, year=2099, total_budget=7500.00)

    assert result["success"] is False
    assert "Quartal" in result["message"]


def test_check_budget_tool_returns_overview(test_database):
    init_db()

    result = check_budget.invoke({})

    assert "Gesamtbudget" in result
    assert "Freies Budget" in result


def test_erstelle_budget_tool_returns_confirmation(test_database):
    init_db()

    result = erstelle_budget.invoke({
        "quartal": 3,
        "jahr": 2099,
        "gesamtbudget": 6200.00,
    })

    assert "Budget für Q3/2099 angelegt" in result
