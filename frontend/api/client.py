import requests
import streamlit as st
from config import API_URL, REQUEST_TIMEOUT


def auth_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(path: str, **kwargs):
    headers = {**auth_headers(), **kwargs.pop("headers", {})}
    return requests.get(f"{API_URL}{path}", headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)


def api_post(path: str, **kwargs):
    headers = {**auth_headers(), **kwargs.pop("headers", {})}
    return requests.post(f"{API_URL}{path}", headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)


def api_delete(path: str, **kwargs):
    headers = {**auth_headers(), **kwargs.pop("headers", {})}
    return requests.delete(f"{API_URL}{path}", headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)