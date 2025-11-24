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

    params = st.query_params

    current_page = params.get("page", "home")
    analysis_id = params.get("id")

    # Проверка авторизации
    if not st.session_state.get("token"):
        if current_page != "login":
            navigate("login")
        show_login_page()
        return

    # Маршрутизация
    if current_page == "home":
        show_home_page()

    elif current_page == "analysis" and analysis_id:
        show_analysis_page(analysis_id)

    elif current_page == "login":
        show_login_page()

    else:
        navigate("home")

if __name__ == "__main__":
    main()
