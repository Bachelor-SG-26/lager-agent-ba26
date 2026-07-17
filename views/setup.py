import hashlib
import os
import streamlit as st
from pathlib import Path

from services.nvidia_models import (
    DEFAULT_NVIDIA_MODEL,
    formatiere_modellfehler,
    lade_nvidia_modelle,
    teste_nvidia_modell,
)

# Im Docker: .env im DATA_DIR (Volume), sonst im Projektverzeichnis
_data_dir = os.getenv("DATA_DIR")
if _data_dir:
    ENV_PATH = Path(_data_dir) / ".env"
else:
    ENV_PATH = Path(__file__).parent.parent / ".env"

MODEL_CACHE_KEY = "_nvidia_model_catalog"
MODEL_TEST_KEY = "_nvidia_model_test"


def _lade_env_werte():
    """Liest aktuelle Werte aus der .env Datei."""
    werte = {
        "NVIDIA_API_KEY": "",
        "NVIDIA_MODEL": DEFAULT_NVIDIA_MODEL,
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
    }
    if ENV_PATH.exists():
        for zeile in ENV_PATH.read_text(encoding="utf-8").splitlines():
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#"):
                continue
            if "=" in zeile:
                key, val = zeile.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key in werte:
                    werte[key] = val
    return werte


def _speichere_env(werte):
    """Schreibt die Werte in die .env Datei."""
    zeilen = [
        "# NVIDIA AI Endpoints – API-Schlüssel und Modell",
        "# Registrierung unter: https://build.nvidia.com/",
        f"NVIDIA_API_KEY={werte['NVIDIA_API_KEY']}",
        f"NVIDIA_MODEL={werte['NVIDIA_MODEL']}",
        "",
        "# Telegram Bot – für Bestellbenachrichtigungen (optional)",
        "# Bot erstellen via @BotFather in Telegram",
        f"TELEGRAM_BOT_TOKEN={werte['TELEGRAM_BOT_TOKEN']}",
        f"TELEGRAM_CHAT_ID={werte['TELEGRAM_CHAT_ID']}",
    ]
    ENV_PATH.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def _setze_laufzeit_env(werte):
    """Übernimmt gespeicherte Werte sofort in die laufende Anwendung."""
    for key, value in werte.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


def _modell_fingerprint(api_key):
    """Erzeugt eine nicht rückrechenbare Kennung für den Modell-Cache."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _lade_modellkatalog(api_key, abrufen=False, force=False):
    """Lädt oder verwendet den pro Schlüssel gecachten NVIDIA-Modellkatalog."""
    if not api_key:
        return (), None

    fingerprint = _modell_fingerprint(api_key)
    cache = st.session_state.get(MODEL_CACHE_KEY)
    if cache and cache.get("fingerprint") == fingerprint and not force:
        return cache["modelle"], None
    if not abrufen:
        return (), None

    try:
        modelle = lade_nvidia_modelle(api_key)
    except Exception as error:
        st.session_state.pop(MODEL_CACHE_KEY, None)
        return (), formatiere_modellfehler(error)

    st.session_state[MODEL_CACHE_KEY] = {
        "fingerprint": fingerprint,
        "modelle": modelle,
    }
    return modelle, None


def ist_konfiguriert():
    """Prüft ob die minimale Konfiguration vorhanden ist (NVIDIA_API_KEY)."""
    if not ENV_PATH.exists():
        return False
    werte = _lade_env_werte()
    return bool(werte.get("NVIDIA_API_KEY"))


def show_setup():
    """Zeigt Einrichtung und spätere Verbindungs- sowie Modellauswahl."""
    werte = _lade_env_werte()
    ist_ersteinrichtung = not bool(werte["NVIDIA_API_KEY"])

    st.title("Einrichtung" if ist_ersteinrichtung else "Einstellungen")
    if ist_ersteinrichtung:
        st.info(
            "Willkommen bei lager-agent. "
            "Bitte konfiguriere die Verbindungsdaten, damit der Agent funktioniert."
        )

    st.subheader("LLM-Verbindung (erforderlich)")
    st.caption("API-Schlüssel von https://build.nvidia.com/")
    nvidia_key = st.text_input(
        "NVIDIA API Key",
        value=werte["NVIDIA_API_KEY"],
        type="password",
        placeholder="nvapi-...",
    )

    modelle_neu_laden = st.button(
        "Modelle neu laden",
        disabled=not bool(nvidia_key),
        width="content",
    )
    if modelle_neu_laden:
        st.session_state.pop(MODEL_TEST_KEY, None)
    gespeicherter_key = bool(
        nvidia_key and nvidia_key == werte["NVIDIA_API_KEY"]
    )
    soll_abrufen = gespeicherter_key or modelle_neu_laden
    if soll_abrufen:
        with st.spinner("Modelle werden geladen..."):
            modelle, modellfehler = _lade_modellkatalog(
                nvidia_key,
                abrufen=True,
                force=modelle_neu_laden,
            )
    else:
        modelle, modellfehler = _lade_modellkatalog(nvidia_key)

    modell_metadaten = {modell.id: modell for modell in modelle}
    modell_ids = [modell.id for modell in modelle]
    konfiguriertes_modell = werte["NVIDIA_MODEL"] or DEFAULT_NVIDIA_MODEL
    if konfiguriertes_modell not in modell_ids:
        modell_ids.insert(0, konfiguriertes_modell)

    def _modell_label(modell_id):
        """Ergänzt die Modellkennung um den gemeldeten Tool-Status."""
        modell = modell_metadaten.get(modell_id)
        if modell is None:
            return f"{modell_id} (aktuell konfiguriert)"
        if modell.supports_tools:
            return f"{modell_id} (Tools)"
        return f"{modell_id} (Tool-Unterstützung nicht bestätigt)"

    nvidia_model = st.selectbox(
        "KI-Modell",
        options=modell_ids,
        index=modell_ids.index(konfiguriertes_modell),
        format_func=_modell_label,
    )

    if modellfehler:
        st.warning(modellfehler)
    elif modelle:
        tool_modelle = sum(modell.supports_tools for modell in modelle)
        st.caption(
            f"{len(modelle)} aktive Modelle geladen, "
            f"davon {tool_modelle} mit bestätigter Tool-Unterstützung."
        )

    ausgewaehltes_modell = modell_metadaten.get(nvidia_model)
    if modelle and ausgewaehltes_modell is None:
        st.warning(
            "Das aktuell ausgewählte Modell ist nicht mehr in der aktiven "
            "NVIDIA-Modellliste enthalten."
        )
    elif ausgewaehltes_modell and not ausgewaehltes_modell.supports_tools:
        st.warning(
            "Dieses Modell meldet keine bestätigte Tool-Unterstützung. "
            "Lagerabfragen und Aktionen können damit fehlschlagen."
        )

    if st.button(
        "Auswahl testen",
        disabled=not bool(nvidia_key and nvidia_model),
        width="content",
    ):
        try:
            with st.spinner("Modellverbindung wird geprüft..."):
                modelltest = teste_nvidia_modell(
                    nvidia_key,
                    nvidia_model,
                    supports_tools=(
                        ausgewaehltes_modell.supports_tools
                        if ausgewaehltes_modell
                        else None
                    ),
                )
        except Exception as error:
            st.session_state.pop(MODEL_TEST_KEY, None)
            st.error(formatiere_modellfehler(error))
        else:
            st.session_state[MODEL_TEST_KEY] = {
                "fingerprint": _modell_fingerprint(nvidia_key),
                "modell_id": nvidia_model,
                "ergebnis": modelltest,
            }

    gespeicherter_modelltest = st.session_state.get(MODEL_TEST_KEY)
    if (
        gespeicherter_modelltest
        and gespeicherter_modelltest["fingerprint"]
        == _modell_fingerprint(nvidia_key)
        and gespeicherter_modelltest["modell_id"] == nvidia_model
    ):
        modelltest = gespeicherter_modelltest["ergebnis"]
        testmeldung = (
            f"{modelltest.bewertung}: {modelltest.dauer_sekunden:.1f} Sekunden. "
            f"{modelltest.begruendung}"
        )
        if modelltest.empfohlen:
            st.success(testmeldung)
        else:
            st.warning(testmeldung)
        st.caption(
            "Die Messung ist eine Momentaufnahme der vollständigen Kurzantwort. "
            "Netzwerk und Auslastung können das Ergebnis verändern."
        )

    st.divider()
    st.subheader("Telegram-Benachrichtigungen (optional)")
    st.caption(
        "Für Bestellbenachrichtigungen per Telegram. "
        "Kann später in den Einstellungen ergänzt werden."
    )
    telegram_token = st.text_input(
        "Bot Token",
        value=werte["TELEGRAM_BOT_TOKEN"],
        type="password",
        placeholder="123456:ABC-...",
    )
    telegram_chat_id = st.text_input(
        "Chat ID",
        value=werte["TELEGRAM_CHAT_ID"],
        placeholder="7180404617",
    )

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        speichern_label = "Speichern und starten" if ist_ersteinrichtung else "Speichern"
        if st.button(speichern_label, type="primary", width="stretch"):
            if not nvidia_key:
                st.error("Der NVIDIA API Key ist erforderlich.")
                return
            if not nvidia_model:
                st.error("Ein KI-Modell ist erforderlich.")
                return

            neue_werte = {
                "NVIDIA_API_KEY": nvidia_key,
                "NVIDIA_MODEL": nvidia_model,
                "TELEGRAM_BOT_TOKEN": telegram_token,
                "TELEGRAM_CHAT_ID": telegram_chat_id,
            }
            _speichere_env(neue_werte)
            _setze_laufzeit_env(neue_werte)

            # Der nächste Agent-Aufruf verwendet sofort das ausgewählte Modell.
            from agent.agent import build_agent

            build_agent.cache_clear()

            st.session_state._setup_done = True
            st.rerun()

    with col2:
        if werte["NVIDIA_API_KEY"]:
            if st.button("Zurück zum Chat", width="stretch"):
                st.session_state._setup_done = True
                st.session_state.seite = "Chat"
                st.rerun()
