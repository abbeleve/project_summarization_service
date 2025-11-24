import streamlit as st

def init_session_state():
    """Инициализация состояния сессии"""
    # Авторизация
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    
    # Временные данные для анализа
    if 'pending_analysis' not in st.session_state:
        st.session_state.pending_analysis = None
    if 'current_analysis' not in st.session_state:
        st.session_state.current_analysis = None

def clear_session():
    """Очистка сессии"""
    for key in ['token', 'user_role', 'username', 'pending_analysis', 'current_analysis']:
        if key in st.session_state:
            del st.session_state[key]