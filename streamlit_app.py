import streamlit as st

from config import APP_PAGES, PROJECT_NAME
from database.database import init_db
from views.agent import show_agent
from views.auswertung import show_auswertung
from views.bestellungen import show_bestellungen
from views.dashboard import show_dashboard
from views.entnahme import show_entnahme
from views.lager import show_lager
from views.placeholder import show_placeholder
from views.sidebar import render_sidebar
from views.stammdaten import show_stammdaten


st.set_page_config(
    page_title="lager-agent",
    page_icon=None,
    layout="wide",
)


def main():
    if "_db_initialized" not in st.session_state:
        init_db()
        st.session_state._db_initialized = True

    if "seite" not in st.session_state:
        st.session_state.seite = APP_PAGES[0]

    render_sidebar(PROJECT_NAME, APP_PAGES)

    page = st.session_state.seite
    if page == "Dashboard":
        show_dashboard()
    elif page == "Lager":
        show_lager()
    elif page == "Entnahme":
        show_entnahme()
    elif page == "Bestellungen":
        show_bestellungen()
    elif page == "Stammdaten":
        show_stammdaten()
    elif page == "Agent":
        show_agent()
    elif page == "Auswertung":
        show_auswertung()
    else:
        show_placeholder(page)


if __name__ == "__main__":
    main()
