import streamlit as st
import requests


def require_login():
    if not st.session_state.get("token"):
        st.warning("🔐 Inicia sesión para usar la app.")
        st.stop()


def show_http_error(r: requests.Response):
    try:
        detail = r.json().get("detail", r.text)
    except Exception:
        detail = r.text
    st.error(f"Error {r.status_code}: {detail}")