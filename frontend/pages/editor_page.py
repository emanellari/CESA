import streamlit as st
from utils.ui_helpers import require_login, show_http_error
from services.dataset_service import load_dataset_into_session
from components.editable_table import render_editable_table
from components.add_row_form import render_add_row_form
from components.analysis_panel import render_analysis_panel


def render_editor_page():
    require_login()

    # ===================== CHECK DATASET =====================
    if not st.session_state.get("dataset_id"):
        st.markdown("""
        <div class="page-hero">
            <div class="page-hero-title">Editor + Analysis</div>
            <div class="page-hero-subtitle">
                Edit records, manage structure, and move directly into analysis workflows.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="empty-state-card">
            <div class="empty-state-title">No dataset is currently open</div>
            <div class="empty-state-text">
                Go to <strong>Datasets</strong> and open or upload one to start editing and analysis.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    if st.session_state.get("df") is None:
        with st.spinner("Loading dataset..."):
            response = load_dataset_into_session(st.session_state.dataset_id)
        if not response.ok:
            show_http_error(response)
            return

    # ===================== PAGE HEADER =====================
    dataset_name = st.session_state.get("dataset_name") or st.session_state.get("dataset_id")

    st.markdown("""
    <div class="page-hero">
        <div class="page-hero-title">Editor + Analysis</div>
        <div class="page-hero-subtitle">
            Edit records, review structure, and continue directly into calculations, charts, and deeper analysis.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="dataset-pill">
        Active dataset: <strong>{dataset_name}</strong>
    </div>
    """, unsafe_allow_html=True)

    # ===================== MAIN TABS =====================
    tab_add_data, tab_analysis = st.tabs(["Data Editor", "Calculations & Charts"])

    # ---------- TAB 1: DATA EDITOR ----------
    with tab_add_data:

        col_form, col_table = st.columns([1, 1.5])

        with col_form:

            st.markdown('<div class="soft-card">', unsafe_allow_html=True)
            render_add_row_form()
            st.markdown('</div>', unsafe_allow_html=True)

        with col_table:

            st.markdown(
                """
                <style>
                .streamlit-table-container {
                    min-height: 640px;
                    max-height: 850px;
                    overflow-y: auto;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            st.markdown('<div class="soft-card table-card">', unsafe_allow_html=True)
            render_editable_table()
            st.markdown('</div>', unsafe_allow_html=True)

    # ---------- TAB 2: CALCULATIONS & CHARTS ----------
    with tab_analysis:
        st.markdown("""
        <div class="section-intro">
            Explore relationships, descriptive statistics, patterns, and visual insights from your dataset.
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="soft-card analysis-card">', unsafe_allow_html=True)
        render_analysis_panel()
        st.markdown('</div>', unsafe_allow_html=True)
    st.divider()