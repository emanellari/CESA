import streamlit as st

def init_session():
    if "token" not in st.session_state:
        st.session_state.token = None

    if "datasets" not in st.session_state:
        st.session_state.datasets = []

    if "page" not in st.session_state:
        st.session_state.page = "Login"


def go(page_name: str):
    st.session_state.page = page_name
    st.rerun()