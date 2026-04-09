import streamlit as st
from api.auth_api import login_user, signup_user
from utils.ui_helpers import show_http_error
from utils.session import go
from services.dataset_service import refresh_dataset_list



def render_login_page():

    col1, col2 = st.columns([1.15, 1], vertical_alignment="top")

    with col1:
        st.markdown("""
        <div class="gradient-panel">
            <div class="gradient-title">Data Analysis Workspace</div>
            <div class="gradient-subtitle">
                A focused environment for dataset management, structured exploration and analysis workflows.
            </div>
            <div class="gradient-section">Core workflow</div>
            <div class="gradient-feature">• Upload and organize Excel datasets</div>
            <div class="gradient-feature">• Create new datasets from zero and automate data entry through customized forms</div>
            <div class="gradient-feature">• Reopen saved files and continue your work</div>
            <div class="gradient-feature">• Move directly into editing and analysis</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="auth-wrapper">', unsafe_allow_html=True)
        st.markdown('<div class="card-header-text">Autentificación</div>', unsafe_allow_html=True)

        tab_login, tab_signup = st.tabs(["Login", "Create account"])

        with tab_login:
            st.markdown('<div class="auth-box">', unsafe_allow_html=True)
            st.text("Access your workspace")
            email = st.text_input("Email", key="li_email", placeholder="you@example.com")
            password = st.text_input("Password", type="password", key="li_pwd")

            if st.button("Sign in", use_container_width=True, key="login_btn"):
                if not email.strip() or not password.strip():
                    st.warning("Please complete all fields.")
                else:
                    with st.spinner("Signing in..."):
                        response = login_user(email, password)
                        if response.ok:
                            st.session_state.token = response.json().get("access_token")
                            refresh_dataset_list()
                            go("Datasets")
                        else:
                            show_http_error(response)
            st.markdown('</div>', unsafe_allow_html=True)

        with tab_signup:
            st.markdown('<div class="auth-box">', unsafe_allow_html=True)
            st.text("Create account")
            email = st.text_input("Email", key="su_email", placeholder="you@example.com")
            password = st.text_input("Password", type="password", key="su_pwd")

            if st.button("Create account", use_container_width=True, key="signup_btn"):
                if not email.strip() or not password.strip():
                    st.warning("Please complete all fields.")
                else:
                    with st.spinner("Creating account..."):
                        response = signup_user(email, password)
                        if response.ok:
                            st.success("Account created successfully. You can now sign in.")
                        else:
                            show_http_error(response)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)