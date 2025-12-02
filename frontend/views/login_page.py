import streamlit as st
from auth.auth_service import login
from utils.navigation import navigate

def show_login_page():
    st.title("🔐 Вход в систему")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        show_login_form()

def show_login_form():
    with st.form("login_form", clear_on_submit=True):
        st.subheader("Авторизация")
        
        username = st.text_input("👤 Имя пользователя", placeholder="Введите имя пользователя", autocomplete="username")
        password = st.text_input("🔒 Пароль", type="password", placeholder="Введите пароль", autocomplete="current-password")
        submitted = st.form_submit_button("Войти", type="primary")
        
        if submitted:
            if login(username, password):
                navigate("home")
