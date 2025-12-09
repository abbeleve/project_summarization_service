import requests
import streamlit as st
from config.settings import API_URL

class APIClient:
    """Клиент для работы с API"""
    
    BASE_URL = API_URL
    
    @staticmethod
    def _get_auth_headers() -> dict:
        """Получить заголовки авторизации из session_state"""
        access_token = st.session_state.get('access_token')
        if access_token:
            return {"Authorization": f"Bearer {access_token}"}
        return {}
    
    @staticmethod
    def _refresh_token() -> bool:
        """Обновить токен (используется внутри APIClient)"""
        try:
            refresh_token = st.session_state.get("refresh_token")
            
            if not refresh_token:
                return False
            
            response = requests.post(
                f"{APIClient.BASE_URL}/auth/refresh",
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
    
    @staticmethod
    def get_chat_history(transcript_id: str) -> list:
        """Получить историю чата по transcript_id"""
        response = APIClient._make_request(
            method="GET",
            endpoint=f"/chat/{transcript_id}",
            timeout=30
        )
        
        if not response:
            return []
        
        if response.status_code == 200:
            return response.json().get("messages", [])
        elif response.status_code == 204:
            return []
        else:
            st.warning("Не удалось загрузить историю чата")
            return []
        
    @staticmethod
    def _make_request(method: str, endpoint: str, **kwargs):
        """
        Универсальный метод для выполнения запросов с автоматическим обновлением токена
        """
        try:
            # Получаем заголовки авторизации
            headers = APIClient._get_auth_headers()
            
            # Добавляем пользовательские заголовки если есть
            if 'headers' in kwargs:
                headers.update(kwargs['headers'])
                del kwargs['headers']
            
            # Добавляем стандартные заголовки
            if 'headers' not in kwargs:
                kwargs['headers'] = headers
            if endpoint == "/process":
                print(">>> DEBUG REQUEST TO /process <<<")
                print("Метод:", method)
                print("URL:", f"{APIClient.BASE_URL}{endpoint}")
                print("Data:", kwargs.get("data", {}))
                print(">>> END DEBUG <<<")
            # Выполняем запрос
            response = requests.request(
                method=method,
                url=f"{APIClient.BASE_URL}{endpoint}",
                **kwargs
            )
            
            # Если токен истек (401), пробуем обновить и повторить запрос
            if response.status_code == 401:
                st.info("🔄 Сессия истекла, пытаемся обновить токен...")
                
                if APIClient._refresh_token():
                    # Обновляем заголовки с новым токеном
                    new_headers = APIClient._get_auth_headers()
                    kwargs['headers'] = new_headers
                    
                    # Повторяем запрос с новым токеном
                    response = requests.request(
                        method=method,
                        url=f"{APIClient.BASE_URL}{endpoint}",
                        **kwargs
                    )
                    
                    if response.status_code == 200:
                        st.success("✅ Сессия обновлена")
                    else:
                        st.error("❌ Не удалось обновить сессию")
                        # Очищаем сессию
                        keys_to_remove = ['access_token', 'refresh_token', 'user_id', 'username', 'full_name', 'token_type', 'user_role']
                        for key in keys_to_remove:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                else:
                    st.error("❌ Не удалось обновить токен. Пожалуйста, войдите снова.")
                    # Очищаем сессию
                    keys_to_remove = ['access_token', 'refresh_token', 'user_id', 'username', 'full_name', 'token_type', 'user_role']
                    for key in keys_to_remove:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
            
            return response
            
        except requests.exceptions.ConnectionError:
            st.error("🔌 Не удалось подключиться к серверу")
            return None
        except requests.exceptions.Timeout:
            st.error("⏰ Превышено время ожидания ответа от сервера")
            return None
        except Exception as e:
            st.error(f"⚠️ Неизвестная ошибка при выполнении запроса: {str(e)}")
            return None
    
    @staticmethod
    def process_audio(file, **kwargs) -> dict:
        """Отправить аудио на обработку"""
        try:
            # Подготавливаем файл
            files = {"file": (file.name, file.getvalue(), file.type)}
            
            # Подготавливаем данные формы
            data = {}
            if transcribe_model := kwargs.get('transcribe_model'):
                data['transcribe_model'] = transcribe_model
            if diarization_model := kwargs.get('diarization_model'):
                data['diarization_model'] = diarization_model
            if diarize_lib := kwargs.get('diarize_lib'):
                data['diarize_lib'] = diarize_lib
            if transcribe_lib := kwargs.get('transcribe_lib'):
                data['transcribe_lib'] = transcribe_lib
            if llm_model := kwargs.get('llm_model'):
                data['llm_model'] = llm_model

            noise_sup_bool = kwargs.get('noise_sup_bool', 'false')
            print(noise_sup_bool)
            data['noise_sup_bool'] = noise_sup_bool
            
            # Используем универсальный метод для запроса
            response = APIClient._make_request(
                method="POST",
                endpoint="/process",
                files=files,
                data=data,
                timeout=300
            )
            
            if not response:
                return None
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                error_detail = response.json().get("detail", "Некорректный запрос")
                st.error(f"❌ Ошибка запроса: {error_detail}")
                return None
            elif response.status_code == 413:
                st.error("❌ Файл слишком большой")
                return None
            elif response.status_code == 415:
                st.error("❌ Неподдерживаемый формат файла")
                return None
            elif response.status_code == 429:
                st.error("❌ Слишком много запросов. Попробуйте позже.")
                return None
            elif response.status_code == 500:
                st.error("❌ Внутренняя ошибка сервера")
                return None
            else:
                try:
                    error_detail = response.json().get("detail", response.text)
                except:
                    error_detail = response.text[:100] + "..." if len(response.text) > 100 else response.text
                st.error(f"❌ Ошибка анализа (код {response.status_code}): {error_detail}")
                return None
                
        except Exception as e:
            st.error(f"⚠️ Ошибка при обработке файла: {str(e)}")
            return None
    
    @staticmethod
    def get_transcripts() -> list:
        """Получить историю транскрипций пользователя"""
        response = APIClient._make_request(
            method="GET",
            endpoint="/transcripts",
            timeout=30
        )
        
        if not response:
            return []
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 204:
            return []  # Нет данных
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except:
                error_detail = response.text[:100] + "..." if len(response.text) > 100 else response.text
            st.error(f"❌ Ошибка получения истории (код {response.status_code}): {error_detail}")
            return []
    
    @staticmethod
    def get_transcript_by_id(transcript_id: str) -> dict:
        """Получить конкретную транскрипцию по ID"""
        if not transcript_id:
            st.error("❌ ID транскрипции не указан")
            return None
        
        response = APIClient._make_request(
            method="GET",
            endpoint=f"/transcripts/{transcript_id}",
            timeout=30
        )
        
        if not response:
            return None
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            st.error("❌ Транскрипция не найдена")
            return None
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except:
                error_detail = response.text[:100] + "..." if len(response.text) > 100 else response.text
            st.error(f"❌ Ошибка получения транскрипции (код {response.status_code}): {error_detail}")
            return None
    
    @staticmethod
    def delete_transcript(transcript_id: str) -> bool:
        """Удалить транскрипцию по ID"""
        if not transcript_id:
            st.error("❌ ID транскрипции не указан")
            return False
        
        response = APIClient._make_request(
            method="DELETE",
            endpoint=f"/transcripts/{transcript_id}",
            timeout=30
        )
        
        if not response:
            return False
        
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            st.error("❌ Транскрипция не найдена")
            return False
        elif response.status_code == 403:
            st.error("❌ Недостаточно прав для удаления")
            return False
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except:
                error_detail = response.text[:100] + "..." if len(response.text) > 100 else response.text
            st.error(f"❌ Ошибка удаления (код {response.status_code}): {error_detail}")
            return False
    
    @staticmethod
    def check_health() -> bool:
        """Проверить здоровье API"""
        try:
            response = requests.get(
                f"{APIClient.BASE_URL}/health",
                timeout=5
            )
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            return False
        except:
            return False
    
    @staticmethod
    def get_users() -> list:
        """Получить список пользователей (только для админа)"""
        response = APIClient._make_request(
            method="GET",
            endpoint="/admin/users",
            timeout=30
        )
        
        if not response:
            return []
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403:
            st.error("❌ Доступ запрещен")
            return []
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except:
                error_detail = response.text[:100] + "..." if len(response.text) > 100 else response.text
            st.error(f"❌ Ошибка получения пользователей (код {response.status_code}): {error_detail}")
            return []
    
    @staticmethod
    def get_current_user() -> dict:
        """Получить информацию о текущем пользователе"""
        response = APIClient._make_request(
            method="GET",
            endpoint="/auth/me",
            timeout=30
        )
        
        if not response:
            return {}
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.error("❌ Ошибка авторизации")
            # Очищаем сессию
            keys_to_remove = ['access_token', 'refresh_token', 'user_id', 'username', 'full_name', 'token_type', 'user_role']
            for key in keys_to_remove:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
            return {}
        else:
            return {}
        
    @staticmethod
    def ask_question(transcript_id: str, question: str) -> dict:
        """
        Отправить вопрос по транскрипции на LLM и получить ответ.
        """
        if not transcript_id or not question.strip():
            st.error("❌ ID транскрипции или вопрос не указаны")
            return {"answer": "Ошибка: пустой запрос"}

        try:
            response = APIClient._make_request(
                method="POST",
                endpoint="/ask",
                data={
                    "transcript_id": transcript_id,
                    "question": question.strip()
                },
                timeout=60
            )

            if not response:
                return {"answer": "Не удалось получить ответ от сервера"}

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                st.error("❌ Транскрипция не найдена")
                return {"answer": "Транскрипция не найдена"}
            elif response.status_code == 400:
                error_detail = response.json().get("detail", "Некорректный запрос")
                st.error(f"❌ Ошибка запроса: {error_detail}")
                return {"answer": error_detail}
            elif response.status_code == 401:
                # _make_request уже обработал 401, но на всякий случай
                st.error("❌ Требуется авторизация")
                return {"answer": "Требуется вход в систему"}
            elif response.status_code == 500:
                st.error("❌ Ошибка на сервере при генерации ответа")
                return {"answer": "Серверная ошибка"}
            else:
                try:
                    error_detail = response.json().get("detail", response.text)
                except:
                    error_detail = response.text[:100] + "..." if len(response.text) > 100 else response.text
                st.error(f"❌ Ошибка (код {response.status_code}): {error_detail}")
                return {"answer": error_detail}

        except Exception as e:
            st.error(f"⚠️ Неизвестная ошибка при запросе к LLM: {str(e)}")
            return {"answer": "Произошла ошибка"}