import streamlit as st
from auth.auth_service import check_auth, logout
from utils.session_manager import init_session_state
from views.login_page import show_login_page
from views.home_page import show_home_page
from views.analysis_page import show_analysis_page

def navigate(page: str, **params):
    """Обновляет URL и делает переход на страницу"""
    qp = {"page": page}
    if params:
        qp.update(params)
    st.query_params.clear()
    st.query_params.update(qp)
    st.rerun()

def main():
    init_session_state()

    st.set_page_config(
        page_title="Meeting Analyzer", 
        page_icon="🎙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    query_params = st.query_params
    page = query_params.get("page", "home")

    # Проверка авторизации
    if page not in ["login"] and not check_auth():
        navigate("login")
        return

    # Маршрутизация
    if page == "login":
        show_login_page()
    elif page == "home":
        show_home_page()
    elif page == "analysis":
        transcript_id = query_params.get("id")
        show_analysis_page(transcript_id)
    else:
        st.error(f"Страница '{page}' не найдена")
        navigate("home")

if __name__ == "__main__":
    main()
