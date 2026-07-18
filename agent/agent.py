from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
from functools import lru_cache
from agent.tools import ALL_TOOLS
from agent.prompt import SYSTEM_PROMPT
from config import CHECKPOINT_DB, DATA_DIR
from services.nvidia_models import DEFAULT_NVIDIA_MODEL
import sqlite3
import os

# .env aus DATA_DIR laden (Docker), dann Projektverzeichnis als Fallback
load_dotenv(DATA_DIR / ".env")
load_dotenv()

_checkpoint_conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
checkpointer = SqliteSaver(_checkpoint_conn)


@lru_cache(maxsize=1)
def build_agent(api_key=None, model_name=None):
    """Erstellt den Agenten für die aktuell gespeicherte NVIDIA-Konfiguration."""
    resolved_key = api_key or os.getenv("NVIDIA_API_KEY")
    resolved_model = model_name or os.getenv("NVIDIA_MODEL") or DEFAULT_NVIDIA_MODEL

    if not resolved_key:
        raise RuntimeError("Der NVIDIA API Key fehlt in den Einstellungen.")

    llm = ChatNVIDIA(
        model=resolved_model,
        api_key=resolved_key,
        max_completion_tokens=4096,
        temperature=0,
    )
    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT,
        interrupt_before=["tools"],
        checkpointer=checkpointer,
        name="lager_agent",
    )
