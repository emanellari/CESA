import streamlit as st
from api.dataset_api import update_dataset, export_dataset, get_dataset
from utils.ui_helpers import show_http_error
import pandas as pd


def render_editable_table():
    st.markdown("### Data Table Editor")

    base_df = st.session_state.df.copy()

    if base_df is None or base_df.empty:
        st.info("No data available to display.")
        return

    # ===================== CONTROLS CARD =====================
    with st.expander("TABLE CONTROLS", expanded=False):
        st.markdown("""
        <div class="table-card-title">Table Controls</div>
        <div class="table-card-subtitle">
            Configure the table view, search across records, and apply a focused filter.
        </div>
        """, unsafe_allow_html=True)

        ctrl1, ctrl2 = st.columns([1, 1])
        ctrl3, ctrl4 = st.columns([1.4, 1.2])

        with ctrl1:
            show_index = st.toggle("Show index", value=False)

        with ctrl2:
            height = st.slider(
                "Table height",
                min_value=350,
                max_value=2000,
                value=800,
                step=50
            )

        with ctrl3:
            search_term = st.text_input(
                "Search across all columns",
                placeholder="Type a keyword or value..."
            )

        with ctrl4:
            filter_col = st.selectbox(
                "Filter column",
                [""] + list(base_df.columns),
                index=0
            )

        filtered_df = base_df.copy()

        # ---------------- SEARCH ----------------
        if search_term:
            filtered_df = filtered_df[
                filtered_df.astype(str)
                .apply(lambda row: row.str.contains(search_term, case=False, na=False).any(), axis=1)
            ]

        # ---------------- FILTER ----------------
        selected_val = ""
        if filter_col:
            unique_vals = (
                filtered_df[filter_col]
                .dropna()
                .astype(str)
                .sort_values()
                .unique()
                .tolist()
            )

            selected_val = st.selectbox(
                "Filter value",
                [""] + unique_vals,
                index=0
            )

            if selected_val:
                filtered_df = filtered_df[filtered_df[filter_col].astype(str) == selected_val]

        metric1, metric2, metric3 = st.columns(3)

        with metric1:
            st.markdown(
                f"""
                <div class="table-mini-metric">
                    <div class="table-mini-metric-label">Rows displayed</div>
                    <div class="table-mini-metric-value">{len(filtered_df)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with metric2:
            st.markdown(
                f"""
                <div class="table-mini-metric">
                    <div class="table-mini-metric-label">Columns</div>
                    <div class="table-mini-metric-value">{len(filtered_df.columns)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with metric3:
            st.markdown(
                f"""
                <div class="table-mini-metric">
                    <div class="table-mini-metric-label">Original rows</div>
                    <div class="table-mini-metric-value">{len(base_df)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ===================== TABLE CARD =====================
    st.markdown(' <div class="card-scope""> ', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("""
        <div class="table-card-title">Editable Dataset View</div>
        <div class="table-card-subtitle">
            Edit values directly in the grid below. Save changes when you are ready.
        </div>
        """, unsafe_allow_html=True)

        edited_df = st.data_editor(
            filtered_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=not show_index,
            height=height,
            key="advanced_editor_clean"
        )
    st.markdown(' </div> ', unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ===================== ACTIONS CARD =====================
    with st.container(border=True):
        st.markdown("""
        <div class="table-card-title">Actions</div>
        <div class="table-card-subtitle">
            Save the current view, export the dataset, or reload the original version from the backend.
        </div>
        """, unsafe_allow_html=True)

        action1, action2, action3 = st.columns(3)

        with action1:
            if st.button("Save Changes", width="stretch"):
                rows = edited_df.fillna("").to_dict(orient="records")
                response = update_dataset(st.session_state.dataset_id, rows)

                if response.ok:
                    st.session_state.df = edited_df.copy()
                    st.success("Changes saved successfully.")
                else:
                    show_http_error(response)

        with action2:
            response_export = export_dataset(st.session_state.dataset_id)
            if response_export.ok:
                st.download_button(
                    label="Download Excel File",
                    data=response_export.content,
                    file_name="export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    key="download_excel_btn"
                )
            else:
                st.button("Download Excel File", width="stretch", disabled=True)

        with action3:
            if st.button("Reload Data", width="stretch"):
                response = get_dataset(st.session_state.dataset_id)

                if response.ok:
                    payload = response.json()
                    st.session_state.df = pd.DataFrame(payload["data"])
                    st.success("Dataset reloaded successfully.")
                    st.rerun()
                else:
                    show_http_error(response)