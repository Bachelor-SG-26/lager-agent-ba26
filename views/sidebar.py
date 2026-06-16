import streamlit as st


def render_sidebar(project_name, pages):
    st.sidebar.title(project_name)

    for page in pages:
        if st.sidebar.button(page, use_container_width=True, key=f"nav_{page}"):
            st.session_state.seite = page

    st.sidebar.divider()
    st.sidebar.caption("Lokale Lagerverwaltung")
