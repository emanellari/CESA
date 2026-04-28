import requests
import streamlit as st
import time

from config import APP_TITLE, APP_LAYOUT, API_URL, HEALTHCHECK_TIMEOUT
from utils.session import init_session

from pages.login_page import render_login_page
from pages.datasets_page import render_datasets_page
from pages.editor_page import render_editor_page
from pages.create_dataset_page import render_create_dataset_page
from pages.account_page import render_account_page
from pages.cleaning_page import render_cleaning_page

from constants.navigation import (
    PAGE_CREATE_DATASET,
    PAGE_DATASETS,
    PAGE_EDITOR,
    PAGE_ACCOUNT,
    PAGE_LOGIN,
    PAGE_Cleaning
)

# ===================== PAGE STATE KEYS =====================
PAGE_STATE_KEYS = {
    PAGE_CREATE_DATASET: [
        "undo_stack_create",
        "redo_stack_create",
        "new_vars",
        "new_ops",
        "current_var_type",
        "current_var_options",
        "reset_form",
        "input_key"
    ],
    PAGE_EDITOR: [],
    PAGE_Cleaning: [],
    PAGE_DATASETS: [],
    PAGE_ACCOUNT: [],
}
def clear_page_state(page):
    if page in PAGE_STATE_KEYS:
        for key in PAGE_STATE_KEYS[page]:
            if key in st.session_state:
                del st.session_state[key]


def scroll_to_top():
    st.markdown(
        """
        <script>
            window.parent.document.querySelector('.main').scrollTo(0, 0);
        </script>
        """,
        unsafe_allow_html=True
    )
def get_api_status():
    if "api_last_check" not in st.session_state:
        st.session_state.api_last_check = 0
        st.session_state.api_status = None
        st.session_state.api_status_code = None

    current_time = time.time()

    if current_time - st.session_state.api_last_check > 10:
        try:
            response = requests.get(f"{API_URL}/health", timeout=HEALTHCHECK_TIMEOUT)
            st.session_state.api_status = response.status_code == 200
            st.session_state.api_status_code = response.status_code
        except Exception:
            st.session_state.api_status = False
            st.session_state.api_status_code = None

        st.session_state.api_last_check = current_time

    return st.session_state.api_status, st.session_state.api_status_code


# ===================== CONFIG =====================
st.set_page_config(
    page_title=APP_TITLE,
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded",
)

st.set_option("client.showSidebarNavigation", False)

with open("frontend/styles.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

init_session()

# ===================== PAGE INIT =====================
if "page" not in st.session_state:
    st.session_state.page = PAGE_LOGIN if not st.session_state.get("token") else PAGE_DATASETS

if "prev_page" not in st.session_state:
    st.session_state.prev_page = st.session_state.page


# ===================== HEADER =====================
st.markdown(f"""
<div class="uv-header">
    <div class="uv-title">{APP_TITLE}</div>
    <div class="uv-subtitle">Streamlit UI + FastAPI backend</div>
</div>
""", unsafe_allow_html=True)


# ===================== SIDEBAR =====================
with st.sidebar:
    st.header("Navigation")

    if not st.session_state.get("token"):
        st.session_state.page = PAGE_LOGIN
        st.write("Please sign in first.")
    else:
        pages = [
            PAGE_DATASETS,
            PAGE_Cleaning,
            PAGE_EDITOR,
            PAGE_ACCOUNT,
            PAGE_CREATE_DATASET,
        ]

        current_page = (
            st.session_state.page
            if st.session_state.page in pages
            else PAGE_DATASETS
        )

        selected_page = st.radio(
            "",
            pages,
            index=pages.index(current_page),
            label_visibility="collapsed"
        )

        # ===================== PAGE CHANGE HANDLER =====================
        if selected_page != st.session_state.page:
            clear_page_state(st.session_state.page)
            st.session_state.prev_page = st.session_state.page
            st.session_state.page = selected_page

            scroll_to_top()
            st.rerun()

    st.divider()
    st.caption("API Status")

    api_ok, status_code = get_api_status()

    if api_ok:
        st.success("API OK")
    else:
        if status_code is not None:
            st.error(f"API: {status_code}")
        else:
            st.error("API is not responding")


# ===================== RENDER PAGE =====================
page = st.session_state.page

# Forzar scroll arriba también en el primer render tras cambio
if st.session_state.prev_page != page:
    scroll_to_top()
    st.session_state.prev_page = page

if page == PAGE_LOGIN:
    render_login_page()

elif page == PAGE_Cleaning:
    render_cleaning_page()

elif page == PAGE_DATASETS:
    render_datasets_page()

elif page == PAGE_EDITOR:
    render_editor_page()

elif page == PAGE_CREATE_DATASET:
    render_create_dataset_page()

elif page == PAGE_ACCOUNT:
    render_account_page()

else:
    st.session_state.page = PAGE_DATASETS
    st.rerun()