import streamlit as st
import requests

import re

def sanitize_column_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\s+", "_", name)  # espacios → _
    name = re.sub(r"[^a-z0-9_]", "", name)  # quitar símbolos
    return name

def build_prediction_formula(model) -> str:
    terms = []

    for var, coef in model.params.items():
        if var == "const":
            terms.append(f"{coef:.3f}")
        else:
            terms.append(f"({coef:.3f} × {var})")

    formula = " + ".join(terms)
    return f"y = {formula}"

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