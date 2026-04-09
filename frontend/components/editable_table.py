import streamlit as st
from api.dataset_api import update_dataset, export_dataset, get_dataset
from utils.ui_helpers import show_http_error
import pandas as pd


def render_editable_table():
    st.markdown("### Data Table Editor")

    df = st.session_state.df.copy()

    # ===================== CONTROLS =====================
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1, 1, 2, 2])

    with ctrl1:
        show_index = st.checkbox("Show index", value=False)

    with ctrl2:
        height = st.number_input("Table height", min_value=300, max_value=800, value=500, step=50)

    with ctrl3:
        search_term = st.text_input("Search")

    with ctrl4:
        filter_col = st.selectbox("Filter column", [""] + list(df.columns))

    # ===================== SEARCH =====================
    if search_term:
        df = df[
            df.astype(str)
            .apply(lambda row: row.str.contains(search_term, case=False).any(), axis=1)
        ]

    # ===================== FILTER =====================
    if filter_col:
        unique_vals = df[filter_col].dropna().astype(str).unique()
        selected_val = st.selectbox("Filter value", [""] + sorted(unique_vals.tolist()))
        if selected_val:
            df = df[df[filter_col].astype(str) == selected_val]

    st.markdown("---")

    # ===================== DATA EDITOR =====================
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=not show_index,
        height=height,
        key="advanced_editor_clean"
    )

    st.session_state.df = edited_df

    st.markdown("---")

    # ===================== ACTIONS =====================
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Save changes", use_container_width=True):
            rows = edited_df.fillna("").to_dict(orient="records")
            r = update_dataset(st.session_state.dataset_id, rows)
            if r.ok:
                st.success("Changes saved successfully")
            else:
                show_http_error(r)

    with col2:
        if st.button("Download Excel", use_container_width=True):
            r = export_dataset(st.session_state.dataset_id)
            if r.ok:
                st.download_button(
                    label="Download file",
                    data=r.content,
                    file_name="export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                show_http_error(r)

    with col3:
        if st.button("Reload data", use_container_width=True):
            r = get_dataset(st.session_state.dataset_id)
            if r.ok:
                payload = r.json()
                st.session_state.df = pd.DataFrame(payload["data"])
                st.success("Data reloaded")
                st.rerun()
            else:
                show_http_error(r)