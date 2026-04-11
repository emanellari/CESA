import requests
import streamlit as st

from config import APP_TITLE, APP_LAYOUT, API_URL, HEALTHCHECK_TIMEOUT
from utils.session import init_session

from pages.login_page import render_login_page
from pages.datasets_page import render_datasets_page
from pages.editor_page import render_editor_page
from pages.create_dataset_page import render_create_dataset_page
from pages.account_page import render_account_page


# CSS
with open("frontend/styles.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(
    page_title=APP_TITLE,
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded",
)

st.set_option("client.showSidebarNavigation", False)

init_session()

if "page" not in st.session_state:
    st.session_state.page = "Login" if not st.session_state.get("token") else "Datasets"


def get_api_status():
    try:
        r = requests.get(f"{API_URL}/docs", timeout=HEALTHCHECK_TIMEOUT)
        return r.status_code == 200, r.status_code
    except Exception:
        return False, None


st.title(APP_TITLE)
st.caption("Streamlit UI + FastAPI backend")
st.divider()

with st.sidebar:
    st.header("Navigation")

    if not st.session_state.get("token"):
        st.session_state.page = "Login"
        st.write("Please sign in first.")
    else:
        pages = ["Datasets", "Editor & Analysis", "Account", "Create Dataset"]
        current_page = st.session_state.page if st.session_state.page in pages else "Datasets"
        st.session_state.page = st.radio("Go to:", pages, index=pages.index(current_page))

    st.divider()
    st.caption("API Status")

    api_ok, status_code = get_api_status()

    if api_ok:
        st.success("API OK ✅")
    else:
        if status_code is not None:
            st.error(f"API: {status_code}")
        else:
            st.error("API is not responding ❌")

page = st.session_state.page

if page == "Login":
    render_login_page()
elif page == "Datasets":
    render_datasets_page()
elif page == "Editor & Analysis":
    render_editor_page()
elif page == "Account":
    render_account_page()
elif page == "Create Dataset":
    render_create_dataset_page()
else:
    render_login_page()