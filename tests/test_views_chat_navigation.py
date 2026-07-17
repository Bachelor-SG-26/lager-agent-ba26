"""Tests für den Browser-Reload beim Wechsel auf die Agent-Seite."""

from types import SimpleNamespace
from unittest.mock import Mock

import views.chat as chat_view


class SessionState(dict):
    """Bildet den für den Test benötigten Attributzugriff auf Session State ab."""

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def _fake_streamlit(letzte_seite):
    """Erzeugt einen minimalen Streamlit-Ersatz für den Reload-Test."""
    return SimpleNamespace(
        session_state=SessionState({"_letzte_seite": letzte_seite}),
        stop=Mock(),
    )


def test_keine_browseraktualisierung_beim_nachrichten_rerun(monkeypatch):
    """Ein Rerun auf der Agent-Seite darf keinen Browser-Reload auslösen."""
    fake_st = _fake_streamlit("Agent")
    html = Mock()
    monkeypatch.setattr(chat_view, "st", fake_st)
    monkeypatch.setattr(chat_view.components, "html", html)

    chat_view._reload_bei_seitenwechsel()

    html.assert_not_called()
    fake_st.stop.assert_not_called()


def test_browseraktualisierung_nur_nach_echtem_seitenwechsel(monkeypatch):
    """Beim Wechsel von einer anderen Seite bleibt der bestehende Reload erhalten."""
    fake_st = _fake_streamlit("Manuell")
    html = Mock()
    monkeypatch.setattr(chat_view, "st", fake_st)
    monkeypatch.setattr(chat_view.components, "html", html)

    chat_view._reload_bei_seitenwechsel()

    assert fake_st.session_state["_letzte_seite"] == "Agent"
    html.assert_called_once()
    fake_st.stop.assert_called_once()


def test_evaluationsaufgabe_verhindert_zusaetzlichen_browser_reload(monkeypatch):
    """Der Chat darf den persistenten Evaluationskontext nicht selbst neu laden."""
    fake_st = _fake_streamlit("Evaluation")
    fake_st.session_state["_evaluation_task_id"] = 12
    html = Mock()
    monkeypatch.setattr(chat_view, "st", fake_st)
    monkeypatch.setattr(chat_view.components, "html", html)

    chat_view._reload_bei_seitenwechsel()

    html.assert_not_called()
    fake_st.stop.assert_not_called()
