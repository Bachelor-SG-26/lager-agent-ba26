import uuid
from pathlib import Path
import streamlit as st
from views.setup import ist_konfiguriert, show_setup

st.set_page_config(
    page_title="Lager-Agent",
    page_icon=None,
    layout="wide",
)


STYLE_PATH = Path(__file__).resolve().parent / "views" / "styles.css"


def _apply_global_styles():
    """Globale UI-Styles für kompaktere, konsistentere Darstellung."""
    if not STYLE_PATH.exists():
        return
    css = STYLE_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


_apply_global_styles()

# Setup beim ersten Start
if not ist_konfiguriert() and not st.session_state.get("_setup_done"):
    show_setup()
    st.stop()

# Imports erst nach Setup, da agent.py die .env lädt
from database.database import init_db  # noqa: E402
from views.chat import show_chat  # noqa: E402
from views.dashboard import show_dashboard  # noqa: E402
from views.bestellhistorie import show_bestellhistorie  # noqa: E402
from views.analytics import show_analytics  # noqa: E402
from views.metriken import show_metriken  # noqa: E402
from views.manuell import show_manuell  # noqa: E402
from views.evaluation import (  # noqa: E402
    render_active_evaluation_task,
    restore_evaluation_context,
    show_evaluation,
)
from views.auswertung import show_auswertung  # noqa: E402
from views.sidebar import render_sidebar  # noqa: E402
from services.session import (  # noqa: E402
    erstelle_session,
    lade_letzte_session,
    lade_nachrichten,
)

# Datenbank initialisieren
if "_db_initialized" not in st.session_state:
    init_db()
    st.session_state._db_initialized = True

# Session State initialisieren
if "config" not in st.session_state:
    letzte = lade_letzte_session()
    if letzte:
        thread_id = letzte
    else:
        thread_id = str(uuid.uuid4())
        erstelle_session(thread_id)
    st.session_state.config = {"configurable": {"thread_id": thread_id}}

if "messages" not in st.session_state:
    st.session_state.messages = lade_nachrichten(
        st.session_state.config["configurable"]["thread_id"]
    )

if "warte_auf_bestaetigung" not in st.session_state:
    st.session_state.warte_auf_bestaetigung = False

if "pending_tool_calls" not in st.session_state:
    st.session_state.pending_tool_calls = []

if "agent_arbeitet" not in st.session_state:
    st.session_state.agent_arbeitet = False

if "seite" not in st.session_state:
    st.session_state.seite = "Agent"
elif st.session_state.seite == "Chat":
    # Migriert offene Sitzungen von der früheren Navigationsbezeichnung.
    st.session_state.seite = "Agent"


restore_evaluation_context()
render_sidebar()


seite = st.session_state.seite
render_active_evaluation_task()

if seite == "Agent":
    show_chat()
elif seite == "Dashboard":
    show_dashboard()
elif seite == "Manuell":
    show_manuell()
elif seite == "Evaluation":
    show_evaluation()
elif seite == "Bestellhistorie":
    show_bestellhistorie()
elif seite == "Analysen":
    show_analytics()
elif seite == "Metriken":
    show_metriken()
elif seite == "Auswertung":
    show_auswertung()
elif seite == "Einstellungen":
    show_setup()

# Letzte Seite merken für Seitenwechsel-Erkennung im Chat
st.session_state._letzte_seite = seite
