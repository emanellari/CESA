import streamlit as st
from api.auth_api import login_user, signup_user
from utils.ui_helpers import show_http_error
from services.dataset_service import refresh_dataset_list

PAGE_DATASETS = "Datasets"


def render_login_page():
    st.divider()
    col1, col2 = st.columns([1.18, 1], vertical_alignment="top")

    with col1:
        left_panel_html = (
            '<div class="gradient-panel">'
            '<div class="gradient-badge">Intelligent data workspace</div>'
            '<div class="gradient-title">From raw datasets to usable workflows</div>'
            '<div class="gradient-subtitle">'
            'A streamlined environment for dataset ingestion, smart cleaning, '
            'automatic form generation, and structured analysis.'
            '</div>'
            '<div class="gradient-section">What this workspace does</div>'
            '<div class="gradient-feature">• Automatically clean and standardize raw datasets</div>'
            '<div class="gradient-feature">• Convert tabular data into dynamic forms for faster data entry</div>'
            '<div class="gradient-feature">• Reopen saved datasets and continue working without losing structure</div>'
            '<div class="gradient-feature">• Move directly from preparation to editing and analysis</div>'
            '<div class="gradient-section" style="margin-top:22px;">Designed for</div>'
            '<div class="gradient-feature">• More efficient dataset preparation</div>'
            '<div class="gradient-feature">• Reusable data collection workflows</div>'
            '<div class="gradient-feature">• Faster transition from messy data to analysis-ready data</div>'
            '</div>'
        )
        st.markdown(left_panel_html, unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="auth-wrapper">', unsafe_allow_html=True)
        st.markdown('<div class="card-header-text">Autenticación</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="auth-subtitle">Access your intelligent data workspace</div>',
            unsafe_allow_html=True
        )

        tab_login, tab_signup = st.tabs(["Login", "Create account"])

        with tab_login:
            login_email = st.text_input("Email", key="li_email", placeholder="you@example.com")
            login_password = st.text_input("Password", type="password", key="li_pwd")

            if st.button("Sign in", width="stretch", key="login_btn"):
                if not login_email.strip() or not login_password.strip():
                    st.warning("Please complete all fields.")
                else:
                    with st.spinner("Signing in..."):
                        response = login_user(login_email, login_password)
                        if response.ok:
                            st.session_state.token = response.json().get("access_token")
                            refresh_dataset_list()
                            st.session_state.page = PAGE_DATASETS
                            st.rerun()
                        else:
                            show_http_error(response)

        with tab_signup:
            signup_email = st.text_input("Email", key="su_email", placeholder="you@example.com")
            signup_password = st.text_input("Password", type="password", key="su_pwd")

            if st.button("Create account", width="stretch", key="signup_btn"):
                if not signup_email.strip() or not signup_password.strip():
                    st.warning("Please complete all fields.")
                else:
                    with st.spinner("Creating account..."):
                        response = signup_user(signup_email, signup_password)
                        if response.ok:
                            st.success("Account created successfully. You can now sign in.")
                        else:
                            show_http_error(response)

        st.markdown('</div>', unsafe_allow_html=True)