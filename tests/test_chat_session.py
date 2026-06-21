from database.database import init_db
from services.chat_session import (
    create_chat_session,
    get_latest_chat_session,
    list_chat_sessions,
    load_chat_messages,
    save_chat_message,
    update_chat_title_from_message,
)


def test_create_chat_session_returns_thread_id(test_database):
    init_db()

    thread_id = create_chat_session("thread-1")
    latest = get_latest_chat_session()

    assert thread_id == "thread-1"
    assert latest["thread_id"] == "thread-1"


def test_save_and_load_chat_messages(test_database):
    init_db()
    create_chat_session("thread-1")

    save_chat_message("thread-1", "user", "Zeige mir Engpässe")
    save_chat_message("thread-1", "assistant", "Es gibt zwei Engpässe.")
    messages = load_chat_messages("thread-1")

    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Zeige mir Engpässe"


def test_update_chat_title_from_first_message(test_database):
    init_db()
    create_chat_session("thread-1")

    update_chat_title_from_message("thread-1", "Welche Produkte sind kritisch?")
    latest = get_latest_chat_session()

    assert latest["titel"] == "Welche Produkte sind kritisch?"


def test_list_chat_sessions_orders_latest_first(test_database):
    init_db()
    create_chat_session("thread-1")
    create_chat_session("thread-2")

    sessions = list_chat_sessions()

    assert sessions[0]["thread_id"] == "thread-2"
