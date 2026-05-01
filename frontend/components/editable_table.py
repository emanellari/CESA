import streamlit as st
import pandas as pd

from api.dataset_api import update_dataset, export_dataset, get_dataset
from utils.ui_helpers import show_http_error


def _get_dynamic_table_height(df: pd.DataFrame, mode: str) -> int:
    """
    Returns a professional-looking dynamic table height.
    Prevents the large empty white block when the dataset has few rows.
    """
    row_count = len(df)

    if mode == "Compact":
        min_height, max_height, row_height = 180, 360, 35
    elif mode == "Comfortable":
        min_height, max_height, row_height = 220, 520, 38
    else:
        min_height, max_height, row_height = 260, 720, 40

    return min(max_height, max(min_height, (row_count + 1) * row_height))


def _apply_search_and_filter(
    df: pd.DataFrame,
    search_term: str,
    filter_col: str,
    selected_val: str,
) -> pd.DataFrame:
    filtered_df = df.copy()

    if search_term:
        search_mask = (
            filtered_df.astype(str)
            .apply(
                lambda row: row.str.contains(
                    search_term,
                    case=False,
                    na=False,
                    regex=False,
                ).any(),
                axis=1,
            )
        )
        filtered_df = filtered_df[search_mask]

    if filter_col and selected_val:
        filtered_df = filtered_df[
            filtered_df[filter_col].astype(str) == selected_val
        ]

    return filtered_df


def _render_metric_card(label: str, value: int | str) -> None:
    st.markdown(
        f"""
        <div class="table-mini-metric">
            <div class="table-mini-metric-label">{label}</div>
            <div class="table-mini-metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_editable_table():
    # ===================== SAFETY CHECK =====================
    if "df" not in st.session_state or st.session_state.df is None:
        st.info("No data available to display.")
        return

    base_df = st.session_state.df.copy()

    if base_df.empty:
        st.info("No data available to display.")
        return

    dataset_id = st.session_state.get("dataset_id")

    # ===================== HEADER =====================
    st.markdown(
        """
        <div class="table-section-header">
            <div class="table-section-title">Data Table Editor</div>
            <div class="table-section-subtitle">
                Review, filter, edit, save, export, or reload your dataset from one place.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===================== CONTROLS =====================
    with st.expander("Table controls", expanded=True):
        ctrl1, ctrl2, ctrl3 = st.columns([1, 1.2, 2])

        with ctrl1:
            show_index = st.toggle(
                "Show index",
                value=False,
                help="Show or hide the dataframe index.",
            )

        with ctrl2:
            density = st.selectbox(
                "Table density",
                ["Compact", "Comfortable", "Spacious"],
                index=1,
                help="Controls the table height without creating large empty space.",
            )

        with ctrl3:
            search_term = st.text_input(
                "Search across all columns",
                placeholder="Type a keyword or value...",
            )

        filter_col = st.selectbox(
            "Filter column",
            [""] + list(base_df.columns),
            index=0,
            help="Optionally filter the table by a specific column.",
        )

        selected_val = ""
        if filter_col:
            values_source = base_df.copy()

            if search_term:
                values_source = _apply_search_and_filter(
                    values_source,
                    search_term=search_term,
                    filter_col="",
                    selected_val="",
                )

            unique_vals = (
                values_source[filter_col]
                .dropna()
                .astype(str)
                .sort_values()
                .unique()
                .tolist()
            )

            selected_val = st.selectbox(
                "Filter value",
                [""] + unique_vals,
                index=0,
                help="Choose one value from the selected column.",
            )

        filtered_df = _apply_search_and_filter(
            base_df,
            search_term=search_term,
            filter_col=filter_col,
            selected_val=selected_val,
        )

        metric1, metric2, metric3 = st.columns(3)

        with metric1:
            _render_metric_card("Rows displayed", len(filtered_df))

        with metric2:
            _render_metric_card("Columns", len(filtered_df.columns))

        with metric3:
            _render_metric_card("Original rows", len(base_df))

    # ===================== TABLE =====================
    st.markdown(
        """
        <div class="table-card-title">Editable Dataset View</div>
        <div class="table-card-subtitle">
            Edit values directly in the grid below. Save changes when you are ready.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filtered_df.empty:
        st.warning("No rows match the current search or filter.")
        edited_df = filtered_df.copy()
    else:
        table_height = _get_dynamic_table_height(filtered_df, density)

        edited_df = st.data_editor(
            filtered_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=not show_index,
            height=table_height,
            key="advanced_editor_clean",
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ===================== ACTIONS =====================
    with st.container(border=True):
        st.markdown(
            """
            <div class="table-card-title">Actions</div>
            <div class="table-card-subtitle">
                Save changes, export the dataset, or reload the latest version from the backend.
            </div>
            """,
            unsafe_allow_html=True,
        )

        action1, action2, action3 = st.columns(3)

        with action1:
            save_clicked = st.button(
                "Save Changes",
                use_container_width=True,
                type="primary",
            )

        with action2:
            response_export = export_dataset(dataset_id)

            if response_export.ok:
                st.download_button(
                    label="Download Excel File",
                    data=response_export.content,
                    file_name="export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="download_excel_btn",
                )
            else:
                st.button(
                    "Download Excel File",
                    use_container_width=True,
                    disabled=True,
                )

        with action3:
            reload_clicked = st.button(
                "Reload Data",
                use_container_width=True,
            )

    # ===================== SAVE LOGIC =====================
    if save_clicked:
        if filtered_df.empty:
            st.warning("There are no rows to save in the current filtered view.")
            return

        rows = edited_df.fillna("").to_dict(orient="records")
        response = update_dataset(dataset_id, rows)

        if response.ok:
            st.session_state.df = edited_df.copy()
            st.success("Changes saved successfully.")
        else:
            show_http_error(response)

    # ===================== RELOAD LOGIC =====================
    if reload_clicked:
        response = get_dataset(dataset_id)

        if response.ok:
            payload = response.json()
            st.session_state.df = pd.DataFrame(payload["data"])
            st.success("Dataset reloaded successfully.")
            st.rerun()
        else:
            show_http_error(response)