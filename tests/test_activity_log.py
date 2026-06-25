from database.database import init_db
from database.operations import (
    correct_stock,
    create_budget,
    create_order,
    record_withdrawal,
    update_order_status,
)
from database.queries import get_activity_log


def test_withdrawal_writes_activity_entry(test_database):
    init_db()

    record_withdrawal(product_id=1, amount=5, reason="Montage")
    activities = get_activity_log(limit=1)

    assert activities[0]["bereich"] == "Entnahme"
    assert "Sechskantschraube" in activities[0]["beschreibung"]
    assert activities[0]["referenz"] == "Montage"


def test_stock_correction_writes_activity_entry(test_database):
    init_db()

    correct_stock(product_id=1, new_stock=77, reason="Inventur")
    activities = get_activity_log(limit=1)

    assert activities[0]["bereich"] == "Lager"
    assert "korrigiert" in activities[0]["beschreibung"]
    assert activities[0]["referenz"] == "Inventur"


def test_order_writes_activity_entry(test_database):
    init_db()

    result = create_order(product_id=1, amount=10)
    activities = get_activity_log(limit=1)

    assert activities[0]["bereich"] == "Bestellung"
    assert activities[0]["referenz"] == result["order_number"]


def test_order_status_writes_activity_entry(test_database):
    init_db()

    result = create_order(product_id=1, amount=10)
    update_order_status(result["order_number"], "geliefert")
    activities = get_activity_log(limit=1)

    assert activities[0]["bereich"] == "Bestellung"
    assert activities[0]["referenz"] == result["order_number"]
    assert "geliefert" in activities[0]["beschreibung"]


def test_budget_writes_activity_entry(test_database):
    init_db()

    create_budget(4, 2099, 750)
    activities = get_activity_log(limit=1)

    assert activities[0]["bereich"] == "Budget"
    assert activities[0]["referenz"] == "Q4/2099"
