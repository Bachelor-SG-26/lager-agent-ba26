import os
from pathlib import Path


PROJECT_NAME = "lager-agent"

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DB_NAME = DATA_DIR / "lager.db"
CHECKPOINT_DB = DATA_DIR / "checkpoints.db"
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))

APP_PAGES = (
    "Dashboard",
    "Lager",
    "Entnahme",
    "Bestellungen",
    "Agent",
    "Auswertung",
)
