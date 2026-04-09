import streamlit as st
from utils.ui_helpers import require_login, show_http_error
from services.dataset_service import load_dataset_into_session
from components.editable_table import render_editable_table
from components.add_row_form import render_add_row_form
from components.analysis_panel import render_analysis_panel

def render_editor_page():
    require_login()

    # ===================== PAGE HEADER =====================
    st.header("Editor + Analysis")

    # ===================== CHECK DATASET =====================
    if not st.session_state.get("dataset_id"):
        st.info("Go to 'Datasets' and open or upload one.")
        return

    if st.session_state.get("df") is None:
        r = load_dataset_into_session(st.session_state.dataset_id)
        if not r.ok:
            show_http_error(r)
            return

    # ===================== DATASET INFO =====================
    dataset_name = st.session_state.get("dataset_name") or st.session_state.get("dataset_id")
    st.subheader(f"Dataset: {dataset_name}")

    # ===================== MAIN TABS =====================
    tab_add_data, tab_analysis = st.tabs(["Add More Data", "Calculations & Charts"])

    # ---------- TAB 1: ADD MORE DATA ----------
    with tab_add_data:

        # Krijojmë 2 kolona: form-i në të majtë, tabela në të djathtë
        col_form, col_table = st.columns([3, 4])  # tabela e gjërë më shumë se form-i

        with col_form:
            render_add_row_form()

        with col_table:
            # Vendosim një container me lartësi minimale për të mos qenë e shkurter
            st.markdown(
                """
                <style>
                .streamlit-table-container {
                    min-height: 600px;  /* ndrysho sipas nevojës */
                    max-height: 800px;
                    overflow-y: auto;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            render_editable_table()

    # ---------- TAB 2: CALCULATIONS & CHARTS ----------
    with tab_analysis:
        st.markdown("### Calculations & Charts")
        render_analysis_panel()