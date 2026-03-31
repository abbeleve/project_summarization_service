"""
Конфигурация Celery для фоновых задач.
"""
import os
from celery import Celery

# Получаем Redis URL из переменных окружения
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Создаём Celery приложение
celery_app = Celery(
    "meeting_analyzer",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.transcribe"]  # Модули с задачами
)

# Конфигурация Celery
celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Таймауты
    task_ack_late=True,  # Подтверждать задачу после начала выполнения
    task_acks_on_failure_or_timeout=True,
    
    # Retry логика
    task_autoretry_for=(Exception,),
    task_retry_backoff=60,  # Ждать 60 сек перед первой повторной попыткой
    task_retry_backoff_max=600,  # Максимум 10 минут между попытками
    task_max_retries=3,
    
    # Очереди
    task_default_queue="celery",
    task_default_exchange="celery",
    task_default_routing_key="celery",
    
    # Результаты
    result_expires=3600,  # Хранить результаты 1 час
    result_extended=True,  # Хранить дополнительную информацию
)


def get_celery_app():
    """Получить экземпляр Celery приложения."""
    return celery_app
