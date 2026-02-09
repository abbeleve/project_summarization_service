import streamlit as st
import requests
import jwt
from datetime import datetime
from config.settings import API_URL

class AuthService:
    def __init__(self):
        self.API_URL = API_URL
        
    def login(self, username: str, password: str) -> bool:
        """Аутентификация пользователя"""
        try:
            response = requests.post(
                f"{self.API_URL}/auth/login",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Сохраняем токены и данные пользователя в session_state
                st.session_state.access_token = data["access_token"]
                st.session_state.refresh_token = data.get("refresh_token")
                st.session_state.user_id = data["user_id"]
                st.session_state.username = username
                st.session_state.full_name = data.get("full_name", "")
                st.session_state.token_type = data["token_type"]
                
                # Устанавливаем role = user по умолчанию
                st.session_state.user_role = "user"
                
                # Для админов можно добавить проверку по имени пользователя
                if username.lower() == "admin" or username.endswith("_admin"):
                    st.session_state.user_role = "admin"
                
                st.success(f"✅ Добро пожаловать, {st.session_state.full_name or username}!")
                return True
                
            else:
                try:
                    error_detail = response.json().get("detail", "Неверные учетные данные")
                except:
                    error_detail = response.text[:100] if response.text else "Неизвестная ошибка"
                
                st.error(f"❌ Ошибка авторизации: {error_detail}")
                return False
                
        except requests.exceptions.ConnectionError:
            st.error("🔌 Не удалось подключиться к серверу")
            return False
        except Exception as e:
            st.error(f"⚠️ Ошибка: {str(e)}")
            return False
    
    def refresh_token(self) -> bool:
        """Обновить access токен"""
        refresh_token = st.session_state.get("refresh_token")
        
        if not refresh_token:
            return False
        
        try:
            # Прямой запрос без использования APIClient (чтобы избежать циклического импорта)
            response = requests.post(
                f"{self.API_URL}/auth/refresh",
                json={"refresh_token": refresh_token},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                st.session_state.access_token = data["access_token"]
                return True
            else:
                return False
                
        except:
            return False
    
    def logout(self):
        """Выход из системы"""
        keys_to_remove = [
            'access_token', 'refresh_token', 'user_id',
            'username', 'full_name', 'token_type', 'user_role'
        ]
        
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
        
        st.success("✅ Вы успешно вышли из системы")
    
    def is_token_expired(self, token: str) -> bool:
        """Проверить истек ли токен"""
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get('exp')
            if exp:
                # Добавляем буфер в 60 секунд для предварительного обновления
                return datetime.now().timestamp() > (exp - 60)
            return True
        except:
            return True
    
    def check_auth(self) -> bool:
        """Проверить авторизацию пользователя и обновить токен при необходимости"""
        access_token = st.session_state.get('access_token')
        
        if not access_token:
            return False
        
        # Проверяем, не истек ли токен
        if self.is_token_expired(access_token):
            # Пробуем обновить токен
            if self.refresh_token():
                return True
            else:
                st.warning("⏰ Сессия истекла. Пожалуйста, войдите снова.")
                self.logout()
                st.rerun()
                return False
        
        return True
    
    def get_auth_headers(self) -> dict:
        """Получить заголовки авторизации"""
        access_token = st.session_state.get('access_token')
        if access_token:
            return {"Authorization": f"Bearer {access_token}"}
        return {}
    
    def get_user_info(self) -> dict:
        """Получить информацию о текущем пользователе"""
        return {
            "user_id": st.session_state.get("user_id"),
            "username": st.session_state.get("username"),
            "full_name": st.session_state.get("full_name", ""),
            "role": st.session_state.get("user_role", "user")
        }
    
    def is_admin(self) -> bool:
        """Проверить, является ли пользователь админом"""
        return st.session_state.get("user_role") == "admin"

# Создаем глобальный экземпляр
auth_service = AuthService()

# Функции для удобства (для обратной совместимости)
def login(username: str, password: str) -> bool:
    return auth_service.login(username, password)

def logout():
    auth_service.logout()

def check_auth() -> bool:
    return auth_service.check_auth()

def get_auth_headers() -> dict:
    return auth_service.get_auth_headers()

def get_user_role() -> str:
    """Получить роль пользователя (по умолчанию 'user')"""
    return st.session_state.get("user_role", "user")

def is_admin() -> bool:
    """Проверить, является ли пользователь админом"""
    return get_user_role() == "admin"