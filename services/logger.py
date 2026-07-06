import logging
import os

LOG_DIR = os.getenv("LAGER_AGENT_LOG_DIR", "logs")
LOG_FILE = os.getenv("LAGER_AGENT_LOG_FILE", os.path.join(LOG_DIR, "lager_agent.log"))


def get_logger(name):
    """Erstellt einen konfigurierten Logger mit Datei- und Konsolen-Handler."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    os.makedirs(LOG_DIR, exist_ok=True)

    # Datei-Handler: alles loggen
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    # Konsolen-Handler: nur Warnungen und Fehler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_format = logging.Formatter("%(levelname)s | %(name)s | %(message)s")
    console_handler.setFormatter(console_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
