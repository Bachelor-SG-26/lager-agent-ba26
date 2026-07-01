from agent.tools.prognose import prognostiziere_bedarf, prognostiziere_bedarf_batch
from database.database import init_db
from database.operations import create_product
from database.queries import (
    forecast_product_demand,
    get_consumption_by_product,
    get_consumption_by_reason,
    get_consumption_timeline,
    get_forecast_overview,
)


def test_consumption_summary_uses_withdrawal_history(test_database):
    init_db()

    consumption = get_consumption_by_product(history_days=90)

    assert consumption
    assert consumption[0]["produkt"] == "Sechskantschraube M8x40 verzinkt"
    assert consumption[0]["verbrauch"] == 60


def test_consumption_by_reason_groups_withdrawals(test_database):
    init_db()

    consumption = get_consumption_by_reason(history_days=90)

    assert consumption
    assert consumption[0]["grund"] == "Montage"
    assert consumption[0]["verbrauch"] == 100
    assert consumption[0]["buchungen"] == 2


def test_consumption_timeline_groups_withdrawals_by_day(test_database):
    init_db()

    timeline = get_consumption_timeline(history_days=90)

    assert len(timeline) == 4
    assert sum(row["verbrauch"] for row in timeline) == 111
    assert timeline[0]["datum"] < timeline[-1]["datum"]
    assert all(row["buchungen"] == 1 for row in timeline)


def test_forecast_product_demand_returns_recommendation(test_database):
    init_db()

    forecast = forecast_product_demand(product_id=2, days_ahead=30)

    assert forecast["product_name"] == "Unterlegscheibe M8 Edelstahl"
    assert forecast["forecast_amount"] > 0
    assert forecast["recommended_order"] > 0


def test_forecast_handles_product_without_consumption(test_database):
    init_db()
    create_product(
        name="Distanzhülse 12 mm",
        stock=20,
        minimum_stock=10,
        unit_price=1.20,
        supplier_id=1,
    )

    forecast = forecast_product_demand(product_id=9, days_ahead=30)

    assert forecast["total_consumption"] == 0
    assert forecast["coverage_days"] is None
    assert forecast["recommended_order"] == 0


def test_forecast_overview_sorts_recommendations(test_database):
    init_db()

    forecasts = get_forecast_overview(days_ahead=30)

    assert forecasts
    assert forecasts[0]["recommended_order"] >= forecasts[-1]["recommended_order"]


def test_prognostiziere_bedarf_tool_returns_summary(test_database):
    init_db()

    result = prognostiziere_bedarf.invoke({
        "produkt_id": 2,
        "tage_voraus": 30,
    })

    assert "Prognose für Unterlegscheibe M8 Edelstahl" in result
    assert "Empfohlene Bestellung" in result


def test_prognostiziere_bedarf_batch_tool_returns_multiple_items(test_database):
    init_db()

    result = prognostiziere_bedarf_batch.invoke({
        "produkt_ids": [1, 2],
        "tage_voraus": 30,
    })

    assert "Bedarfsprognose" in result
    assert "Sechskantschraube M8x40 verzinkt" in result
