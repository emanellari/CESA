import streamlit as st
import pandas as pd
from api.dataset_api import list_datasets, get_dataset


def refresh_dataset_list():
    r = list_datasets()
    if r.ok:
        st.session_state.datasets = r.json()
    else:
        st.session_state.datasets = []


def load_dataset_into_session(dataset_id: int):
    r = get_dataset(dataset_id)
    if not r.ok:
        return r

    payload = r.json()
    st.session_state.dataset_id = payload["dataset_id"]
    st.session_state.dataset_name = payload.get("name")
    st.session_state.dataset_meta = payload.get("meta", {})
    st.session_state.df = pd.DataFrame(payload["data"])
    return r