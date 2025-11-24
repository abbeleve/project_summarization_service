import streamlit as st
from auth.auth_service import login
from config.settings import DEMO_CREDENTIALS
from utils.navigation import navigate

def show_login_page():
    st.title("🔐 Вход в систему")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        show_login_form()
        show_demo_credentials()

def show_login_form():
    with st.form("login_form", clear_on_submit=True):
        st.subheader("Авторизация")
        
        username = st.text_input("👤 Имя пользователя", placeholder="Введите имя пользователя", autocomplete="username")
        password = st.text_input("🔒 Пароль", type="password", placeholder="Введите пароль", autocomplete="current-password")
        submitted = st.form_submit_button("Войти", type="primary")
        
        if submitted:
            if login(username, password):
                st.success("Успешный вход!")
                navigate("home")
            else:
                st.error("Неверный логин или пароль")

def show_demo_credentials():
    with st.expander("🧪 Тестовые учетные записи"):
        for user_type, creds in DEMO_CREDENTIALS.items():
            st.markdown(f"""
            **{creds['description']}:**
            - Логин: `{creds['username']}`
            - Пароль: `{creds['password']}`
            """)
