import streamlit as st
from components.sidebar import show_user_sidebar, show_admin_sidebar
from components.analysis_results import display_analysis_result
from utils.api_client import APIClient
from utils.navigation import navigate

def show_analysis_page(analysis_id: str):
    if st.session_state.user_role == "admin":
        show_admin_sidebar()
    else:
        show_user_sidebar()
    
    if not analysis_id:
        st.error("❌ ID анализа не указан")
        if st.button("← Назад", use_container_width=True):
            navigate("home")
        return

    current_analysis = st.session_state.get("current_analysis") or {}

    if current_analysis.get("is_new") and current_analysis.get("id") == analysis_id:
        show_new_analysis(current_analysis)
    else:
        show_historical_analysis(analysis_id)

def show_new_analysis(data: dict):
    result = data["data"]
    filename = data["filename"]

    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("📊 Результаты анализа")
        st.success("✅ Анализ завершён")
        st.caption(f"Файл: {filename}")
    with col2:
        if st.button("← Назад", use_container_width=True):
            navigate("home")

    st.markdown("---")
    display_analysis_result(result, filename)

def show_historical_analysis(analysis_id: str):
    data = APIClient.get_analysis_by_id(analysis_id)

    if not data:
        st.error("Анализ не найден")
        if st.button("← Назад", use_container_width=True):
            navigate("home")
        return
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header(f"📊 {data['title']}")
        st.caption(f"📅 {data['date']} | ⏱️ {data['duration']} | 👥 {data['speakers_count']}")
    with col2:
        if st.button("← Назад", use_container_width=True):
            navigate("home")

    st.markdown("---")
    display_analysis_result(data, data["file_name"])
