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

    # Centered container (card style)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            """
            <div style="
                background-color: #f9f9f9;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
                text-align: center;
            ">
                <h3 style="margin-bottom: 10px;">Sesión activa</h3>
                <p style="color: green; font-size: 18px;">✅ Conectado correctamente</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.write("")  # spacing

        # Logout button with emphasis
        if st.button("🔓 Cerrar sesión", use_container_width=True):
            clear_session_on_logout()
            st.rerun()