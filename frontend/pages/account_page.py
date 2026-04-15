import streamlit as st
from utils.ui_helpers import require_login
from utils.session import clear_session_on_logout


def render_account_page():
    require_login()

    # Page title
    st.markdown(
        """
        <h1 style='text-align: center;'>👤 Account</h1>
        <hr style='margin-top: -10px; margin-bottom: 30px;'>
        """,
        unsafe_allow_html=True
    )

    # Centered container (card layout)
    _, center_col, _ = st.columns([1, 2, 1])

    with center_col:
        # Card UI
        st.markdown(
            """
            <div style="
                background-color: #f9fafb;
                padding: 28px;
                border-radius: 14px;
                box-shadow: 0 6px 18px rgba(0,0,0,0.06);
                text-align: center;
                border: 1px solid #e5e7eb;
            ">
                <h3 style="margin-bottom: 8px; color: #111827;">Active Session</h3>
                <p style="color: #16a34a; font-size: 16px; margin: 0;">
                    ✅ Successfully connected
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        # Logout button
        if st.button("🔓 Log out", use_container_width=True):
            clear_session_on_logout()
            st.rerun()