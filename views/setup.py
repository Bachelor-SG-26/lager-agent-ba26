import os
import streamlit as st
from pathlib import Path

# Im Docker: .env im DATA_DIR (Volume), sonst im Projektverzeichnis
_data_dir = os.getenv("DATA_DIR")
if _data_dir:
    ENV_PATH = Path(_data_dir) / ".env"
else:
    ENV_PATH = Path(__file__).parent.parent / ".env"


def _lade_env_werte():
    """Liest aktuelle Werte aus der .env Datei."""
    werte = {"NVIDIA_API_KEY": "", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}
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
        "# NVIDIA AI Endpoints – API-Schluessel für das LLM",
        "# Registrierung unter: https://build.nvidia.com/",
        f"NVIDIA_API_KEY={werte['NVIDIA_API_KEY']}",
        "",
        "# Telegram Bot – für Bestellbenachrichtigungen (optional)",
        "# Bot erstellen via @BotFather in Telegram",
        f"TELEGRAM_BOT_TOKEN={werte['TELEGRAM_BOT_TOKEN']}",
        f"TELEGRAM_CHAT_ID={werte['TELEGRAM_CHAT_ID']}",
    ]
    ENV_PATH.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def ist_konfiguriert():
    """Prüft ob die minimale Konfiguration vorhanden ist (NVIDIA_API_KEY)."""
    if not ENV_PATH.exists():
        return False
    werte = _lade_env_werte()
    return bool(werte.get("NVIDIA_API_KEY"))


def show_setup():
    """Zeigt den Einrichtungsdialog beim ersten Start."""
    st.title("Einrichtung")
    st.info(
        "Willkommen bei lager-agent. "
        "Bitte konfiguriere die Verbindungsdaten, damit der Agent funktioniert."
    )

    werte = _lade_env_werte()

    st.subheader("LLM-Verbindung (erforderlich)")
    st.caption("API-Schluessel von https://build.nvidia.com/")
    nvidia_key = st.text_input(
        "NVIDIA API Key",
        value=werte["NVIDIA_API_KEY"],
        type="password",
        placeholder="nvapi-...",
    )

    st.divider()
    st.subheader("Telegram-Benachrichtigungen (optional)")
    st.caption(
        "Für Bestellbenachrichtigungen per Telegram. "
        "Kann spaeter in der .env Datei ergänzt werden."
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
        if st.button("Speichern und starten", type="primary", width="stretch"):
            if not nvidia_key:
                st.error("Der NVIDIA API Key ist erforderlich.")
                return

            _speichere_env({
                "NVIDIA_API_KEY": nvidia_key,
                "TELEGRAM_BOT_TOKEN": telegram_token,
                "TELEGRAM_CHAT_ID": telegram_chat_id,
            })

            # Env-Variablen sofort setzen für die laufende Session
            os.environ["NVIDIA_API_KEY"] = nvidia_key
            if telegram_token:
                os.environ["TELEGRAM_BOT_TOKEN"] = telegram_token
            if telegram_chat_id:
                os.environ["TELEGRAM_CHAT_ID"] = telegram_chat_id

            st.session_state._setup_done = True
            st.rerun()

    with col2:
        if werte["NVIDIA_API_KEY"]:
            if st.button("Überspringen", width="stretch"):
                st.session_state._setup_done = True
                st.rerun()
