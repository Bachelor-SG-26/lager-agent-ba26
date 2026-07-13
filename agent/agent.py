from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
from agent.tools import ALL_TOOLS
from agent.prompt import SYSTEM_PROMPT
from config import CHECKPOINT_DB, DATA_DIR
import sqlite3
import os

# .env aus DATA_DIR laden (Docker), dann Projektverzeichnis als Fallback
load_dotenv(DATA_DIR / ".env")
load_dotenv()

llm = ChatNVIDIA(
    model="moonshotai/kimi-k2.6",
    api_key=os.getenv("NVIDIA_API_KEY"),
    max_completion_tokens=4096,
)

_checkpoint_conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
checkpointer = SqliteSaver(_checkpoint_conn)

agent = create_react_agent(
    model=llm,
    tools=ALL_TOOLS,
    prompt=SYSTEM_PROMPT,
    interrupt_before=["tools"],
    checkpointer=checkpointer,
    name="lager_agent",
)
