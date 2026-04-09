import requests
import streamlit as st

from config import APP_TITLE, APP_LAYOUT, API_URL, HEALTHCHECK_TIMEOUT
from utils.session import init_session

from pages.login_page import render_login_page
from pages.datasets_page import render_datasets_page
from pages.editor_page import render_editor_page
from pages.create_dataset_page import render_create_dataset_page
from pages.account_page import render_account_page

with open("frontend/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
st.markdown("""
<button id="sidebarToggle" style="
    position: fixed;
    top: 16px;
    left: 16px;
    z-index: 100;
    background: #2563eb;
    border: none;
    color: white;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
">☰ Menu</button>

<script>
const btn = document.getElementById('sidebarToggle');
const sidebar = document.querySelector('section[data-testid="stSidebar"]');

btn.onclick = () => {
    sidebar.classList.toggle('open');
};
</script>
""", unsafe_allow_html=True)
st.set_page_config(page_title=APP_TITLE, layout=APP_LAYOUT)

init_session()

st.title(APP_TITLE)
st.caption("Streamlit UI + FastAPI backend")
st.divider()

with st.sidebar:
    st.header("Navegación")

    if not st.session_state.token:
        st.session_state.page = "Login"
        st.write("Primero inicia sesión.")
    else:
        pages = ["Datasets", "Editor + Análisis", "Cuenta", "Crear desde 0"]
        current_page = st.session_state.page if st.session_state.page in pages else "Datasets"
        st.session_state.page = st.radio("Ir a:", pages, index=pages.index(current_page))

    st.divider()
    st.caption("🔌 Estado API")

    try:
        r = requests.get(f"{API_URL}/docs", timeout=HEALTHCHECK_TIMEOUT)
        st.success("API OK ✅" if r.status_code == 200 else f"API: {r.status_code}")
    except Exception:
        st.error("API no responde ❌")

page = st.session_state.page

if page == "Login":
    render_login_page()
elif page == "Datasets":
    render_datasets_page()
elif page == "Editor + Análisis":
    render_editor_page()
elif page == "Cuenta":
    render_account_page()
elif page == "Crear desde 0":
    render_create_dataset_page()
else:
    render_login_page()