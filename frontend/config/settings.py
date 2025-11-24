# Конфигурационные параметры приложения
API_URL = "http://api:8000"

# Тестовые учетные данные для демо
DEMO_CREDENTIALS = {
    "admin": {
        "username": "admin",
        "password": "admin123",
        "role": "admin",
        "description": "Администратор системы"
    },
    "user": {
        "username": "user",
        "password": "user123", 
        "role": "user",
        "description": "Обычный пользователь"
    }
}


SUPPORTED_FORMATS = ['wav', 'mp3', 'm4a', 'flac', 'ogg']