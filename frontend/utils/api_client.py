import requests
import streamlit as st
from auth.auth_service import get_auth_headers, logout
from config.settings import API_URL
from datetime import datetime, timedelta
import random

class APIClient:
    """Клиент для работы с API"""
    
    @staticmethod
    def process_audio(file) -> dict:
        """Отправить аудио на обработку"""
        try:
            files = {"file": (file.name, file.getvalue(), file.type)}
            headers = get_auth_headers()
            
            response = requests.post(
                f"{API_URL}/process", 
                files=files,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                st.error("❌ Ошибка авторизации")
                logout()
                st.rerun()
            else:
                st.error(f"❌ Ошибка анализа: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            st.error(f"🔌 Ошибка подключения: {str(e)}")
            return None
    
    @staticmethod
    def get_analysis_history(search_query: str = "") -> list:
        """Получить историю анализов (заглушка)"""
        # Заглушка с тестовыми данными
        base_meetings = [
            {
                "id": "1",
                "title": "Еженедельное совещание отдела",
                "date": (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y %H:%M"),
                "duration": "25:17",
                "speakers_count": 3,
                "summary_preview": "Обсудили текущие задачи проекта и распределили роли...",
                "file_name": "meeting_2024_01_15.wav"
            },
            {
                "id": "2", 
                "title": "Планирование квартала",
                "date": (datetime.now() - timedelta(days=3)).strftime("%d.%m.%Y %H:%M"),
                "duration": "42:05",
                "speakers_count": 5,
                "summary_preview": "Определили цели на следующий квартал и ключевые метрики...",
                "file_name": "quarter_planning.mp3"
            },
            {
                "id": "3",
                "title": "Обсуждение дизайна",
                "date": (datetime.now() - timedelta(days=5)).strftime("%d.%m.%Y %H:%M"),
                "duration": "18:33", 
                "speakers_count": 2,
                "summary_preview": "Рассмотрели новые макеты интерфейса и внесли правки...",
                "file_name": "design_review.m4a"
            },
            {
                "id": "4",
                "title": "Техническое совещание",
                "date": (datetime.now() - timedelta(days=7)).strftime("%d.%m.%Y %H:%M"),
                "duration": "35:44",
                "speakers_count": 4,
                "summary_preview": "Обсудили архитектурные решения и технические детали...",
                "file_name": "tech_meeting.wav"
            }
        ]
        
        # Фильтрация по поисковому запросу
        if search_query:
            search_lower = search_query.lower()
            filtered_meetings = [
                meeting for meeting in base_meetings
                if (search_lower in meeting["title"].lower() or 
                    search_lower in meeting["summary_preview"].lower())
            ]
            return filtered_meetings
        else:
            return base_meetings
    
    @staticmethod
    def get_analysis_by_id(analysis_id: str) -> dict:
        """Получить детальный анализ по ID"""
        
        base = {
            "1": {
                "id": "1",
                "title": "Еженедельное совещание отдела",
                "date": (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y %H:%M"),
                "duration": "25:17",
                "speakers_count": 3,
                "summary": "Суммаризированный текст совещания...",
                "transcription": [
                    {
                        "speaker": "SPEAKER_01",
                        "start": 0.0,
                        "end": 5.2,
                        "text": "Добрый день, коллеги..."
                    }
                ],
                "file_name": "meeting_2024_01_15.wav",
                "file_size": 15482901
            },
            "2": {
                "id": "2",
                "title": "Планирование квартала",
                "date": (datetime.now() - timedelta(days=3)).strftime("%d.%m.%Y %H:%M"),
                "duration": "42:05",
                "speakers_count": 5,
                "summary": "Суммаризированный текст совещания...",
                "transcription": [
                    {
                        "speaker": "SPEAKER_01",
                        "start": 0.0,
                        "end": 8.1,
                        "text": "Переходим к планированию..."
                    }
                ],
                "file_name": "quarter_planning.mp3",
                "file_size": 25430145
            }
        }

        result = base.get(analysis_id)
        if not result:
            return None
        
        result["processed_by"] = st.session_state.get("username", "user")
        return result

    
    @staticmethod
    def save_analysis_result(file_name: str, result: dict) -> str:
        """Сохранить результат анализа и вернуть ID"""
        # В реальном приложении здесь был бы вызов API для сохранения
        # Создаем уникальный ID для нового анализа
        new_id = str(random.randint(1000, 9999))
        
        # Добавляем метаданные к результату
        result['saved_id'] = new_id
        result['saved_at'] = datetime.now().strftime("%d.%m.%Y %H:%M")
        result['saved_title'] = f"Анализ от {result['saved_at']}"
        
        return new_id

    @staticmethod
    def check_health() -> bool:
        """Проверить здоровье API"""
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            return response.status_code == 200
        except:
            return False