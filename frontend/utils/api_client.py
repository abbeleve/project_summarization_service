import requests
import streamlit as st
from auth.auth_service import get_auth_headers, logout
from config.settings import API_URL

class APIClient:
    """Клиент для работы с API"""
    
    @staticmethod
    def process_audio(
        file, 
        transcribe_model=None,
        diarization_model=None,
        diarize_lib=None,
        transcribe_lib=None,
        llm_model=None
    ) -> dict:
        """Отправить аудио на обработку"""
        try:
            files = {"file": (file.name, file.getvalue(), file.type)}
            headers = get_auth_headers()
            
            # Подготавливаем данные формы
            data = {}
            if transcribe_model:
                data['transcribe_model'] = transcribe_model
            if diarization_model:
                data['diarization_model'] = diarization_model
            if diarize_lib:
                data['diarize_lib'] = diarize_lib
            if transcribe_lib:
                data['transcribe_lib'] = transcribe_lib
            if llm_model:
                data['llm_model'] = llm_model
            
            response = requests.post(
                f"{API_URL}/process", 
                files=files,
                data=data,  # Передаем данные формы
                headers=headers,
                timeout=300  # Увеличен таймаут для больших файлов
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации")
                logout()
                st.rerun()
            else:
                error_detail = response.json().get("detail", response.text)
                st.error(f"❌ Ошибка анализа: {error_detail}")
                return None
                
        except requests.exceptions.RequestException as e:
            st.error(f"🔌 Ошибка подключения: {str(e)}")
            return None
    
    @staticmethod
    def get_transcripts() -> list:
        """Получить историю транскрипций пользователя"""
        try:
            headers = get_auth_headers()
            response = requests.get(
                f"{API_URL}/transcripts",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации")
                logout()
                st.rerun()
                return []
            else:
                st.error(f"❌ Ошибка получения истории: {response.text}")
                return []
                
        except requests.exceptions.RequestException:
            return []  # Возвращаем пустой список при ошибке
    
    @staticmethod
    def get_transcript_by_id(transcript_id: str) -> dict:
        """Получить конкретную транскрипцию по ID"""
        try:
            headers = get_auth_headers()
            response = requests.get(
                f"{API_URL}/transcripts/{transcript_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                st.error("Транскрипция не найдена")
                return None
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации")
                logout()
                st.rerun()
                return None
            else:
                st.error(f"❌ Ошибка получения транскрипции: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            st.error(f"🔌 Ошибка подключения: {str(e)}")
            return None
    
    @staticmethod
    def check_health() -> bool:
        """Проверить здоровье API"""
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    @staticmethod
    def get_users() -> list:
        """Получить список пользователей (только для админа)"""
        try:
            headers = get_auth_headers()
            response = requests.get(
                f"{API_URL}/admin/users",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                st.error("Доступ запрещен")
                return []
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации")
                logout()
                st.rerun()
                return []
            else:
                st.error(f"❌ Ошибка получения пользователей: {response.text}")
                return []
                
        except requests.exceptions.RequestException:
            return []