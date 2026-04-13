"""
Celery задачи для подключения к совещаниям через meeting-bot.
"""
import io
import json
import logging
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from uuid import UUID

from app.celery_app import celery_app
from app.db_service.database import DataBaseManager

logger = logging.getLogger(__name__)

# URL meeting-bot сервиса
MEETING_BOT_URL = os.getenv("MEETING_BOT_URL", "http://meeting-bot:3000")
# URL backend API для webhook callback
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://api:8000")


def update_task_status(task_id: str, status: str, progress: Dict[str, Any] = None):
    """Обновляет статус задачи в PostgreSQL."""
    db = DataBaseManager()
    db.update_celery_task_status(task_id, status, progress)


@celery_app.task(bind=True, max_retries=1)
def process_due_scheduled_meetings(self):
    """
    Периодическая задача: проверяет все due scheduled meetings и запускает их.
    Вызывается Celery Beat каждую минуту.
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Проверка запланированных совещаний...")

    db = DataBaseManager()

    try:
        # Получаем все совещания, которые должны начаться в течение 2 минут
        due_meetings = db.select_due_scheduled_meetings(grace_period_minutes=2)

        if not due_meetings:
            logger.info(f"[{task_id}] Нет совещаний для запуска")
            return {"processed": 0}

        logger.info(f"[{task_id}] Найдено {len(due_meetings)} совещаний для запуска")

        processed_count = 0
        for meeting in due_meetings:
            meeting_id = meeting['id']
            logger.info(f"[{task_id}] Запуск совещания {meeting_id} ({meeting['meeting_url']})")

            # Обновляем статус на processing
            db.update_scheduled_meeting(meeting_id, status="processing")

            # Создаём задачу Celery для подключения
            join_task = join_meeting_immediate.apply_async(
                args=[meeting_id, meeting['meeting_url'], meeting['provider'], meeting['user_id']],
                kwargs={"bot_name": meeting.get('bot_name', 'Meeting Notetaker')}
            )

            # Сохраняем ID задачи
            db.update_scheduled_meeting(meeting_id, meeting_bot_task_id=str(join_task.id))

            processed_count += 1

        logger.info(f"[{task_id}] Запущено {processed_count} совещаний")
        return {"processed": processed_count}

    except Exception as exc:
        logger.error(f"[{task_id}] Ошибка проверки scheduled meetings: {exc}")
        # Не делаем retry — следующая итерация beat снова проверит
        return {"processed": 0, "error": str(exc)}


@celery_app.task(bind=True, max_retries=2)
def join_meeting_immediate(
    self,
    meeting_id: str,
    meeting_url: str,
    provider: str,
    user_id: str,
    bot_name: str = "Meeting Notetaker"
):
    """
    Немедленное подключение к совещанию через meeting-bot.
    Вызывается напрямую или из process_due_scheduled_meetings.

    Args:
        meeting_id: UUID записи в scheduled_meetings
        meeting_url: Ссылка на совещание
        provider: google, microsoft, zoom
        user_id: ID пользователя
        bot_name: Имя бота в совещании
    """
    task_id = self.request.id
    db = DataBaseManager()

    logger.info(f"[{task_id}] Подключение к совещанию {meeting_id}: {meeting_url}")

    try:
        # Обновляем статус
        db.update_scheduled_meeting(meeting_id, status="processing")
        update_task_status(task_id, "processing", {"step": "joining", "percent": 10})

        # Формируем запрос к meeting-bot
        bot_endpoint = f"/{provider}/join"
        full_url = f"{MEETING_BOT_URL}{bot_endpoint}"

        payload = {
            "url": meeting_url,
            "name": bot_name,
            "teamId": f"user_{user_id}",
            "timezone": "UTC",
            "userId": str(user_id),
            "botId": str(meeting_id),
            "bearerToken": os.getenv("MEETING_BOT_AUTH_TOKEN", "")  # Если нужна аутентификация
        }

        logger.info(f"[{task_id}] POST {full_url} with payload: {json.dumps(payload, ensure_ascii=False)}")

        response = requests.post(
            full_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code not in (200, 202):
            raise RuntimeError(f"Meeting-bot returned status {response.status_code}: {response.text}")

        bot_response = response.json()
        logger.info(f"[{task_id}] Meeting-bot response: {bot_response}")

        update_task_status(task_id, "processing", {"step": "recording", "percent": 30})

        # Совещание запущено, теперь ждём webhook от meeting-bot
        # webhook обработится отдельно в meeting_bot_webhook_handler
        return {
            "status": "recording",
            "meeting_id": meeting_id,
            "message": "Meeting bot joined successfully, waiting for recording completion"
        }

    except Exception as exc:
        logger.error(f"[{task_id}] Ошибка подключения к совещанию: {exc}")

        db.update_scheduled_meeting(meeting_id, status="failed", error=str(exc))
        update_task_status(task_id, "failed", {"step": "failed", "error": str(exc)})

        # Retry через 30 секунд
        raise self.retry(exc, countdown=30 * (2 ** (self.request.retries or 0)))


@celery_app.task(bind=True, max_retries=3)
def process_recording_callback(
    self,
    meeting_id: str,
    recording_url: str,
    user_id: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Обработка callback от meeting-bot когда запись готова.
    Скачивает запись и запускает ML-пайплайн.

    Args:
        meeting_id: UUID записи в scheduled_meetings
        recording_url: URL записи из S3/MinIO
        user_id: ID пользователя
        metadata: Дополнительные данные от meeting-bot
    """
    task_id = self.request.id
    db = DataBaseManager()

    logger.info(f"[{task_id}] Обработка записи для совещания {meeting_id}")

    try:
        # Обновляем статус
        db.update_scheduled_meeting(meeting_id, status="recording", recording_url=recording_url)
        update_task_status(task_id, "processing", {"step": "downloading", "percent": 40})

        # Скачиваем запись
        logger.info(f"[{task_id}] Скачивание записи из {recording_url}")
        response = requests.get(recording_url, timeout=600)  # 10 минут на скачивание

        if response.status_code != 200:
            raise RuntimeError(f"Failed to download recording: {response.status_code}")

        file_bytes = response.content
        logger.info(f"[{task_id}] Запись скачана: {len(file_bytes)} bytes")

        update_task_status(task_id, "processing", {"step": "transcription", "percent": 50})

        # Запускаем ML-пайплайн (переиспользуем существующую задачу)
        from app.tasks.transcribe import transcribe_and_summarize_task

        ml_options = {
            "transcribe_model": "v3_ctc",
            "diarization_model": "pyannote/speaker-diarization-community-1",
            "diarize_lib": "pyannote",
            "transcribe_lib": "gigaam",
            "llm_model": "gemini-2.5-flash",
            "noise_sup_bool": "false",
            "user_id": user_id
        }

        ml_task = transcribe_and_summarize_task.delay(file_bytes, ml_options)
        ml_task_id = str(ml_task.id)

        logger.info(f"[{task_id}] ML-пайплайн запущен: {ml_task_id}")
        update_task_status(task_id, "processing", {"step": "ml_processing", "percent": 60})

        # Ждём завершения ML-пайплайна (с таймаутом)
        ml_result = ml_task.get(timeout=1800)  # 30 минут максимум

        if ml_result.get("status") != "completed":
            raise RuntimeError(f"ML pipeline failed: {ml_result}")

        transcript_id = ml_result.get("transcript_id")

        # Обновляем запись
        db.update_scheduled_meeting(
            meeting_id,
            status="completed",
            result_transcript_id=UUID(transcript_id)
        )
        update_task_status(task_id, "completed", {
            "step": "completed",
            "percent": 100,
            "transcript_id": transcript_id
        })

        logger.info(f"[{task_id}] Совещание обработано: transcript_id={transcript_id}")

        return {
            "status": "completed",
            "meeting_id": meeting_id,
            "transcript_id": transcript_id
        }

    except Exception as exc:
        logger.error(f"[{task_id}] Ошибка обработки записи: {exc}")

        db.update_scheduled_meeting(meeting_id, status="failed", error=str(exc))
        update_task_status(task_id, "failed", {"step": "failed", "error": str(exc)})

        raise self.retry(exc, countdown=60 * (2 ** (self.request.retries or 0)))
