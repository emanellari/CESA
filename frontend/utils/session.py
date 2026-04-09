import streamlit as st


def init_session():
    defaults = {
        "token": None,
        "page": "Login",
        "dataset_id": None,
        "df": None,
        "dataset_name": None,
        "dataset_meta": {},
        "datasets": [],
        "new_vars": [],
        "new_ops": {},
        "undo_stack_create": [],
        "redo_stack_create": [],
        "new_dataset_name": "mi_dataset",
        "reset_create_inputs": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go(page: str):
    st.session_state.page = page
    st.rerun()


def clear_session_on_logout():
    st.session_state.token = None
    st.session_state.page = "Login"
    st.session_state.dataset_id = None
    st.session_state.df = None
    st.session_state.dataset_name = None
    st.session_state.dataset_meta = {}
    st.session_state.datasets = []