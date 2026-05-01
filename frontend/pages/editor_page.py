import streamlit as st

from utils.ui_helpers import require_login, show_http_error
from services.dataset_service import load_dataset_into_session
from components.editable_table import render_editable_table
from components.add_row_form import render_add_row_form
from components.analysis_panel import render_analysis_panel


def render_editor_page():
    require_login()

    # ===================== CUSTOM PAGE CSS =====================
    st.markdown(
        """
        <style>
        .dataset-pill {
            display: inline-block;
            margin-bottom: 1rem;
            padding: 0.45rem 0.75rem;
            border-radius: 999px;
            background: #eff6ff;
            border: 1px solid #dbeafe;
            color: #1e3a8a;
            font-size: 0.9rem;
        }

        .section-intro {
            margin-bottom: 1rem;
            padding: 0.9rem 1rem;
            border-radius: 14px;
            background: linear-gradient(90deg, #eff6ff 0%, #f8fafc 100%);
            border: 1px solid #dbeafe;
            color: #334155;
            line-height: 1.6;
        }

        .soft-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 1rem 1rem 0.9rem 1rem;
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
            margin-bottom: 1rem;
        }

        .analysis-card {
            margin-top: 0.4rem;
        }

        .tab-helper-text {
            color: #64748b;
            font-size: 0.94rem;
            line-height: 1.55;
            margin-bottom: 1rem;
        }

        div[data-testid="stDataEditor"] {
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
            background: #ffffff;
        }

        div[data-testid="stDataEditor"] [data-testid="stElementToolbar"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ===================== CHECK DATASET =====================
    if not st.session_state.get("dataset_id"):
        st.markdown(
            """
            <div class="page-hero">
                <div class="page-hero-title">Editor + Analysis</div>
                <div class="page-hero-subtitle">
                    Edit records, manage structure, and move directly into analysis workflows.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="empty-state-card">
                <div class="empty-state-title">No dataset is currently open</div>
                <div class="empty-state-text">
                    Go to <strong>Datasets</strong> and open or upload one to start editing and analysis.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # ===================== LOAD DATASET =====================
    if st.session_state.get("df") is None:
        with st.spinner("Loading dataset..."):
            response = load_dataset_into_session(st.session_state.dataset_id)

        if not response.ok:
            show_http_error(response)
            return

    # ===================== PAGE HEADER =====================
    dataset_name = (
        st.session_state.get("dataset_name")
        or st.session_state.get("dataset_id")
    )

    st.markdown(
        """
        <div class="page-hero">
            <div class="page-hero-title">Editor + Analysis</div>
            <div class="page-hero-subtitle">
                Add new records, edit your dataset, and continue directly into calculations,
                charts, and deeper analysis.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="dataset-pill">
            Active dataset: <strong>{dataset_name}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===================== MAIN TABS =====================
    tab_form, tab_table, tab_analysis = st.tabs(
        [
            "Add Record",
            "Data Table",
            "Calculations & Charts",
        ]
    )

    # ---------- TAB 1: ADD RECORD FORM ----------
    with tab_form:
        st.markdown(
            """
            <div class="section-intro">
                Add a new row to your active dataset. Fill in the fields below and save it
                before reviewing the updated table.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        render_add_row_form()
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- TAB 2: EDITABLE TABLE ----------
    with tab_table:
        st.markdown(
            """
            <div class="section-intro">
                Review, edit, and manage the records in your dataset. Changes here affect
                the active working dataset.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Important:
        # Do NOT wrap this in a custom HTML div.
        # Streamlit components like st.data_editor do not behave well inside raw HTML wrappers.
        render_editable_table()

    # ---------- TAB 3: CALCULATIONS & CHARTS ----------
    with tab_analysis:
        st.markdown(
            """
            <div class="section-intro">
                Explore relationships, descriptive statistics, patterns, and visual insights
                from your dataset.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="soft-card analysis-card">', unsafe_allow_html=True)
        render_analysis_panel()
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()