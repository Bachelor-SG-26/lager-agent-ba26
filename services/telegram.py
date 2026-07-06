import requests
import os
from dotenv import load_dotenv
from services.logger import get_logger
from config import DATA_DIR

load_dotenv(DATA_DIR / ".env")
load_dotenv()

logger = get_logger("services.telegram")


def send_telegram(text: str) -> bool:
    """Sendet eine Benachrichtigung über Telegram."""
    # .env vor jedem Versand neu laden, falls Werte zur Laufzeit aktualisiert wurden.
    load_dotenv(DATA_DIR / ".env", override=True)
    load_dotenv(override=True)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.debug("Telegram nicht konfiguriert (Token oder Chat-ID fehlt)")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            logger.info("Telegram-Nachricht gesendet")
        else:
            logger.warning(
                "Telegram-Fehler: Status %d, Antwort: %s",
                response.status_code,
                response.text[:500],
            )
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error("Telegram-Verbindungsfehler: %s", e)
        return False
