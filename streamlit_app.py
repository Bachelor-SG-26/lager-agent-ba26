import streamlit as st

from config import APP_PAGES, PROJECT_NAME
from views.dashboard import show_dashboard
from views.placeholder import show_placeholder
from views.sidebar import render_sidebar


st.set_page_config(
    page_title="lager-agent",
    page_icon=None,
    layout="wide",
)


def main():
    if "seite" not in st.session_state:
        st.session_state.seite = APP_PAGES[0]

    render_sidebar(PROJECT_NAME, APP_PAGES)

    page = st.session_state.seite
    if page == "Dashboard":
        show_dashboard()
    else:
        show_placeholder(page)


if __name__ == "__main__":
    main()
