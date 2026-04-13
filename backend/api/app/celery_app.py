"""
Конфигурация Celery для фоновых задач.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Получаем Redis URL из переменных окружения
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Создаём Celery приложение
celery_app = Celery(
    "meeting_analyzer",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.transcribe",
        "app.tasks.meetings"
    ]  # Модули с задачами
)

# Конфигурация Celery
celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Таймауты
    task_ack_late=True,
    task_acks_on_failure_or_timeout=True,

    # Retry логика
    task_autoretry_for=(Exception,),
    task_retry_backoff=60,
    task_retry_backoff_max=600,
    task_max_retries=3,

    # Результаты
    result_expires=3600,
    result_extended=True,

    # === Маршрутизация задач по очередям ===
    task_create_missing_queues=True,
    task_default_queue="default",
    task_routes={
        # Транскрибация/суммаризация — тяжёлые ML задачи (GPU)
        "app.tasks.transcribe.transcribe_and_summarize_task": {"queue": "default"},

        # Meeting bot задачи — лёгкие HTTP вызовы
        "app.tasks.meetings.join_meeting_immediate": {"queue": "meetings"},
        "app.tasks.meetings.process_recording_callback": {"queue": "meetings"},

        # Beat задача — лёгкая проверка БД
        "app.tasks.meetings.process_due_scheduled_meetings": {"queue": "meetings"},
    },

    # === Celery Beat (периодические задачи) ===
    beat_schedule={
        'check-scheduled-meetings': {
            'task': 'app.tasks.meetings.process_due_scheduled_meetings',
            'schedule': 60.0,  # Каждую минуту
        },
    },
    beat_scheduler="celery.beat:PersistentScheduler",
)


def get_celery_app():
    """Получить экземпляр Celery приложения."""
    return celery_app
