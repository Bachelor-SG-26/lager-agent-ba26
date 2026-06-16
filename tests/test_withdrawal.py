from agent.tools.entnahme import erfasse_entnahme
from database.database import db_connection, init_db
from database.operations import record_withdrawal
from database.queries import get_withdrawal_history


def test_record_withdrawal_reduces_stock(test_database):
    init_db()

    result = record_withdrawal(product_id=1, amount=5, reason="Montage")

    assert result["success"] is True
    assert result["new_stock"] == result["old_stock"] - 5


def test_record_withdrawal_writes_consumption_entry(test_database):
    init_db()

    record_withdrawal(product_id=1, amount=5, reason="Montage")
    history = get_withdrawal_history(limit=1)

    assert history[0]["produkt"] == "Sechskantschraube M8x40 verzinkt"
    assert history[0]["menge"] == 5
    assert history[0]["grund"] == "Montage"


def test_record_withdrawal_rejects_missing_stock(test_database):
    init_db()

    result = record_withdrawal(product_id=2, amount=999, reason="Montage")

    assert result["success"] is False
    assert "Nicht genug Bestand" in result["message"]


def test_record_withdrawal_marks_low_stock(test_database):
    init_db()

    result = record_withdrawal(product_id=1, amount=50, reason="Montage")

    assert result["success"] is True
    assert result["is_low_stock"] is True


def test_erfasse_entnahme_tool_returns_summary(test_database):
    init_db()

    result = erfasse_entnahme.invoke({
        "produkt_id": 1,
        "menge": 50,
        "grund": "Montage",
    })

    assert "Entnahme erfasst" in result
    assert "Warnung" in result


def test_failed_withdrawal_does_not_change_stock(test_database):
    init_db()

    with db_connection() as (_, cursor):
        cursor.execute("SELECT bestand FROM produkte WHERE id = 2")
        stock_before = cursor.fetchone()["bestand"]

    record_withdrawal(product_id=2, amount=999, reason="Montage")

    with db_connection() as (_, cursor):
        cursor.execute("SELECT bestand FROM produkte WHERE id = 2")
        stock_after = cursor.fetchone()["bestand"]

    assert stock_after == stock_before
