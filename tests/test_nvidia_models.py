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


def test_teste_nvidia_modell_sendet_kurze_pruefanfrage(monkeypatch):
    """Der Verbindungstest verwendet Schlüssel und ausgewählte Modellkennung."""
    captured = {}

    class FakeChatNVIDIA:
        def __init__(self, **kwargs):
            captured["config"] = kwargs

        def invoke(self, prompt):
            captured["prompt"] = prompt

    monkeypatch.setattr(nvidia_models, "ChatNVIDIA", FakeChatNVIDIA)

    assert nvidia_models.teste_nvidia_modell("nvapi-test", "anbieter/modell") is True
    assert captured["config"]["api_key"] == "nvapi-test"
    assert captured["config"]["model"] == "anbieter/modell"
    assert captured["prompt"] == "Antworte nur mit: ok"
