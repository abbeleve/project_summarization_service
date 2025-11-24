import streamlit as st
import requests
import jwt
from datetime import datetime
from config.settings import API_URL

def login(username: str, password: str) -> bool:
    """Аутентификация пользователя"""
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={"username": username, "password": password, "role": ""}
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.user_role = data["role"]
            st.session_state.username = username
            return True
        else:
            st.error("Неверное имя пользователя или пароль")
            return False
    except Exception as e:
        st.error(f"Ошибка подключения: {str(e)}")
        return False

def logout():
    """Выход из системы"""
    st.session_state.token = None
    st.session_state.user_role = None
    st.session_state.username = None

def is_token_expired(token: str) -> bool:
    """Проверить истек ли токен"""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get('exp')
        if exp:
            return datetime.now().timestamp() > exp
        return True
    except:
        return True

def check_auth() -> bool:
    """Проверить авторизацию пользователя"""
    token = st.session_state.get('token')
    if not token:
        return False
    
    if is_token_expired(token):
        st.warning("Сессия истекла. Пожалуйста, войдите снова.")
        logout()
        return False
    
    return True

def get_auth_headers() -> dict:
    """Получить заголовки авторизации"""
    token = st.session_state.get('token')
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}