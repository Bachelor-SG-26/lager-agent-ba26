"""Tests für NVIDIA-Modellkatalog und sichere Fehlermeldungen."""

from types import SimpleNamespace

from services import nvidia_models


def test_lade_nvidia_modelle_filtert_und_sortiert(monkeypatch):
    """Aktive Tool-Modelle stehen vor aktiven Modellen ohne Tool-Flag."""
    katalog = [
        SimpleNamespace(id="anbieter/ohne-tools", supports_tools=False, deprecated=False),
        SimpleNamespace(id="anbieter/veraltet", supports_tools=True, deprecated=True),
        SimpleNamespace(id="anbieter/mit-tools", supports_tools=True, deprecated=False),
    ]
    captured = {}

    def fake_get_available_models(**kwargs):
        captured.update(kwargs)
        return katalog

    monkeypatch.setattr(
        nvidia_models.ChatNVIDIA,
        "get_available_models",
        fake_get_available_models,
    )

    modelle = nvidia_models.lade_nvidia_modelle("nvapi-test")

    assert captured["api_key"] == "nvapi-test"
    assert [modell.id for modell in modelle] == [
        "anbieter/mit-tools",
        "anbieter/ohne-tools",
    ]


def test_formatiere_modellfehler_entfernt_interne_accountdaten():
    """Technische Accountkennungen werden nicht an die Oberfläche durchgereicht."""
    fehler = Exception("[404] Function abc: Not found for account geheime-kennung")

    meldung = nvidia_models.formatiere_modellfehler(fehler)

    assert "API-Schlüssel" in meldung
    assert "geheime-kennung" not in meldung


def test_teste_nvidia_modell_misst_und_empfiehlt_schnelles_tool_modell(monkeypatch):
    """Ein schnelles Tool-Modell erhält eine positive Empfehlung."""
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    zeiten = iter((100.0, 103.5))
    monkeypatch.setattr(nvidia_models.requests, "post", fake_post)
    monkeypatch.setattr(nvidia_models, "perf_counter", lambda: next(zeiten))

    ergebnis = nvidia_models.teste_nvidia_modell(
        "nvapi-test",
        "anbieter/modell",
        supports_tools=True,
    )

    assert ergebnis.empfohlen is True
    assert ergebnis.bewertung == "Empfohlen"
    assert ergebnis.dauer_sekunden == 3.5
    assert captured["url"] == nvidia_models.NVIDIA_CHAT_COMPLETIONS_URL
    assert captured["headers"]["Authorization"] == "Bearer nvapi-test"
    assert captured["json"]["model"] == "anbieter/modell"
    assert captured["timeout"] == (5, nvidia_models.MODELLTEST_TIMEOUT_SEKUNDEN)


def test_bewerte_nvidia_modell_lehnt_lange_antwort_ab():
    """Eine sehr lange Kurzantwort ist trotz Tool-Unterstützung ungeeignet."""
    ergebnis = nvidia_models.bewerte_nvidia_modell(16.0, supports_tools=True)

    assert ergebnis.empfohlen is False
    assert ergebnis.bewertung == "Nicht empfohlen"


def test_bewerte_nvidia_modell_lehnt_modell_ohne_tools_ab():
    """Fehlende Tool-Unterstützung verhindert eine positive Empfehlung."""
    ergebnis = nvidia_models.bewerte_nvidia_modell(2.0, supports_tools=False)

    assert ergebnis.empfohlen is False
    assert ergebnis.bewertung == "Nicht empfohlen"


def test_formatiere_modellfehler_benennt_timeout_als_nicht_empfohlen():
    """Ein Zeitlimit wird als verständliche Empfehlung ausgegeben."""
    fehler = nvidia_models.requests.Timeout("read timed out")

    meldung = nvidia_models.formatiere_modellfehler(fehler)

    assert "20 Sekunden" in meldung
    assert "nicht empfohlen" in meldung
