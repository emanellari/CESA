import streamlit as st
import pandas as pd
import io

from constants.navigation import PAGE_CREATE_DATASET, PAGE_EDITOR, PAGE_Cleaning
from api.dataset_api import delete_dataset, upload_dataset
from components.cleaning.column_editor import render_column_editor
from services.cleaning.transforms import (
    read_uploaded_dataset,
    handle_duplicate_columns,
    apply_user_config,
)
from services.cleaning.config_builder import (
    generate_form_options_from_config,
    build_default_config,
)
from services.cleaning.profiles import profile_dataset
from services.dataset_service import refresh_dataset_list, load_dataset_into_session
from utils.ui_helpers import require_login, show_http_error

def render_datasets_page():
    require_login()

    st.markdown("""
        <div class="page-hero">
            <div class="page-hero-title">Datasets</div>
            <div class="page-hero-subtitle">
                Manage existing datasets, upload raw files, clean them automatically,
                and transform them into structured analysis workflows.
            </div>
        </div>
    """, unsafe_allow_html=True)

    _, top_right = st.columns([4, 1])

    with top_right:
        if st.button("Refresh", use_container_width=True):
            refresh_dataset_list()

    if not st.session_state.get("datasets"):
        refresh_dataset_list()

    datasets = st.session_state.get("datasets", [])

    st.markdown("""
        <div class="soft-info-card">
            <strong>Workspace capabilities</strong><br>
            Upload raw datasets, standardize them, generate form-ready structures,
            and continue directly into editing and analysis.
        </div>
    """, unsafe_allow_html=True)

    st.markdown("## Existing datasets")
    st.caption("Open a saved dataset to continue working on it.")

    if datasets:
        dataset_options = {
            f"{d['name']} (ID: {d['dataset_id']})": d["dataset_id"]
            for d in datasets
        }

        selected_label = st.selectbox(
            "Select a dataset",
            list(dataset_options.keys()),
            key="dataset_selector"
        )
        selected_id = dataset_options[selected_label]

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Open workspace", use_container_width=True, key="open_dataset_btn"):
                with st.spinner("Loading dataset..."):
                    response = load_dataset_into_session(selected_id)

                if response.ok:
                    st.session_state.page = PAGE_EDITOR
                    st.rerun()
                else:
                    show_http_error(response)

        with c2:
            if st.button("Delete dataset", use_container_width=True, key="delete_dataset_btn"):
                with st.spinner("Deleting dataset..."):
                    response = delete_dataset(selected_id)

                if response.ok:
                    st.success("Dataset deleted successfully.")
                    refresh_dataset_list()
                    st.rerun()
                else:
                    show_http_error(response)

    else:
        st.markdown("""
            <div class="empty-state-card">
                <div class="empty-state-title">No datasets available yet</div>
                <div class="empty-state-text">
                    Upload a raw file or create a dataset from scratch to get started.
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.markdown("## Create or upload a new dataset")
    st.caption("Start from scratch or upload a file and prepare it automatically for analysis.")

    c1, c2 = st.columns([1.2, 2])

    with c1:
        if st.button("Create dataset from scratch", use_container_width=True, key="create_bottom_btn"):
            st.session_state.page = PAGE_CREATE_DATASET
            st.rerun()

    with c2:
        st.markdown("""
            <div class="upload-hint-card">
                Uploaded datasets can be reviewed, cleaned, standardized, and converted
                into form-ready structures before being saved.
            </div>
        """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload a dataset file",
        type=["xlsx", "xls", "csv", "tsv"],
        key="dataset_uploader",
        help="Supported formats: XLSX, XLS, CSV, TSV"
    )

    if uploaded is not None:
        try:
            df_uploaded = read_uploaded_dataset(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return

        df_uploaded = handle_duplicate_columns(df_uploaded)

        st.success("File loaded successfully. Review and configure it before uploading.")
        st.dataframe(df_uploaded.head(20), use_container_width=True)

        st.session_state.upload_preview_df = df_uploaded.copy()

        if (
            "upload_profiles" not in st.session_state
            or st.session_state.get("last_uploaded_name") != uploaded.name
        ):
            profiles = profile_dataset(df_uploaded)
            st.session_state.upload_profiles = profiles
            st.session_state.upload_config = build_default_config(df_uploaded, profiles)
            st.session_state.last_uploaded_name = uploaded.name

        profiles = st.session_state.upload_profiles
        config = st.session_state.upload_config

        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button("Upload and clean", use_container_width=True, key="go_to_cleaning_btn"):
                st.session_state.cleaning_df = df_uploaded.copy()
                st.session_state.cleaning_profiles = profiles
                st.session_state.cleaning_config = config
                st.session_state.cleaning_dataset_name = uploaded.name

                st.session_state.page = PAGE_Cleaning
                st.rerun()

        with action_col2:
            if st.button("Upload without cleaning", use_container_width=True, key="upload_raw_btn"):
                try:
                    raw_df = df_uploaded.copy()
                    form_options = generate_form_options_from_config(raw_df, config)

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        raw_df.to_excel(writer, index=False, sheet_name="Sheet1")
                    output.seek(0)
                    output.name = uploaded.name

                    with st.spinner("Uploading dataset..."):
                        response = upload_dataset(
                            output,
                            options=form_options,
                            columns=raw_df.columns.tolist()
                        )

                    if response.ok:
                        payload = response.json()

                        st.session_state.dataset_id = payload.get("dataset_id")
                        st.session_state.dataset_name = payload.get("dataset_name", uploaded.name)
                        st.session_state.df = raw_df.copy()

                        meta = payload.get("meta", {})
                        meta["options"] = form_options
                        meta["columns"] = raw_df.columns.tolist()

                        st.session_state.dataset_meta = meta
                        st.session_state.generated_form_schema = form_options

                        st.success("Dataset uploaded successfully.")
                        st.session_state.page = PAGE_EDITOR
                        st.rerun()
                    else:
                        show_http_error(response)

                except Exception as e:
                    st.error(f"Error while uploading dataset: {e}")
