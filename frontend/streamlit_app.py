import requests
import streamlit as st

from config import APP_TITLE, APP_LAYOUT, API_URL, HEALTHCHECK_TIMEOUT
from utils.session import init_session

from pages.login_page import render_login_page
from pages.datasets_page import render_datasets_page
from pages.editor_page import render_editor_page
from pages.create_dataset_page import render_create_dataset_page
from pages.account_page import render_account_page

from costants.navigation import PAGE_CREATE_DATASET,PAGE_DATASETS,PAGE_EDITOR,PAGE_ACCOUNT,PAGE_LOGIN

def get_api_status():
    try:
        response = requests.get(f"{API_URL}/docs", timeout=HEALTHCHECK_TIMEOUT)
        return response.status_code == 200, response.status_code
    except Exception:
        return False, None


st.set_page_config(
    page_title=APP_TITLE,
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded",
)

st.set_option("client.showSidebarNavigation", False)

with open("frontend/styles.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

init_session()

if "page" not in st.session_state:
    st.session_state.page = PAGE_LOGIN if not st.session_state.get("token") else PAGE_DATASETS

st.markdown(f"""
<div class="uv-header">
    <div class="uv-title">{APP_TITLE}</div>
    <div class="uv-subtitle">Streamlit UI + FastAPI backend</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Navigation")

    if not st.session_state.get("token"):
        st.session_state.page = PAGE_LOGIN
        st.write("Please sign in first.")
    else:
        pages = [
            PAGE_DATASETS,
            PAGE_EDITOR,
            PAGE_ACCOUNT,
            PAGE_CREATE_DATASET,
        ]

        current_page = st.session_state.page if st.session_state.page in pages else PAGE_DATASETS
        selected_page = st.radio("", pages, index=pages.index(current_page), label_visibility="collapsed")
        st.session_state.page = selected_page

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

page = st.session_state.page

if page == PAGE_LOGIN:
    render_login_page()
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