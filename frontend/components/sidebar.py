import streamlit as st
from auth.auth_service import logout
from utils.api_client import APIClient
from utils.navigation import navigate

def show_user_sidebar():
    with st.sidebar:
        st.info(f"Роль: **{st.session_state.user_role}**")

        if st.query_params.get("page") != "home":
            if st.button("🏠 На главную", use_container_width=True):
                navigate("home")

        st.markdown("---")
        show_system_info()

        if st.button("🚪 Выйти", use_container_width=True):
            logout()
            navigate("login")

def show_admin_sidebar():
    with st.sidebar:
        st.success(f"👑 Администратор: **{st.session_state.username}**")

        if st.query_params.get("page") != "home":
            if st.button("🏠 На главную", use_container_width=True):
                navigate("home")

        if st.button("БД", use_container_width=True):
            navigate("control_db")

        st.markdown("---")
        show_system_info()

        if st.button("🚪 Выйти", use_container_width=True):
            logout()
            navigate("login")

def show_system_info():
    with st.expander("ℹ️ О сервисе"):
        st.markdown("""
        **Анализатор встреч**
        - 📝 Автоматическая транскрипция
        - 👥 Определение спикеров
        - 📊 Суммаризация
        - 💾 Экспорт
        - 📋 История
        """)
