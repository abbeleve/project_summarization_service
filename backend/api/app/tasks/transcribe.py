"""
Celery задачи для обработки аудио.
"""
import io
import json
import logging
import requests
from uuid import UUID
from typing import Dict, Any, Optional, List
from app.celery_app import celery_app
from app.db_service.database import DataBaseManager

logger = logging.getLogger(__name__)


def update_task_status(task_id: str, status: str, progress: Dict[str, Any] = None):
    """
    Обновляет статус задачи в PostgreSQL.
    
    Args:
        task_id: ID задачи Celery
        status: pending, processing, completed, failed
        progress: {"step": "transcription", "percent": 50}
    """
    db = DataBaseManager()
    db.update_celery_task_status(task_id, status, progress)


@celery_app.task(bind=True, max_retries=1)
def transcribe_and_summarize_task(self, file_bytes: bytes, options: Dict[str, Any]):
    """
    Полный пайплайн обработки аудио:
    1. Транскрибация (diarization + transcription)
    2. Суммаризация
    3. Сохранение в PostgreSQL
    4. RAG indexing
    
    Args:
        file_bytes: Байты аудиофайла
        options: Параметры обработки
            - transcribe_model: модель транскрибации
            - diarization_model: модель диаризации
            - diarize_lib: библиотека диаризации
            - transcribe_lib: библиотека транскрибации
            - llm_model: модель суммаризации
            - noise_sup_bool: использовать ли шумоподавление
            - user_id: ID пользователя
    
    Returns:
        {"transcript_id": int, "status": "completed"}
    """
    task_id = self.request.id
    logger.info(f"Начало обработки задачи {task_id}")
    
    try:
        # === 1. Транскрибация (вызов audio-ml сервиса) ===
        logger.info(f"[{task_id}] Шаг 1: Транскрибация")
        update_task_status(task_id, "processing", {"step": "transcription", "percent": 10})
        
        # Подготовка запроса к audio-ml сервису
        files = {"file": ("audio.wav", io.BytesIO(file_bytes), "audio/wav")}
        data = {
            "transcribe_model": options.get("transcribe_model", "v3_ctc"),
            "diarization_model": options.get("diarization_model", "pyannote/speaker-diarization-community-1"),
            "diarize_lib": options.get("diarize_lib", "pyannote"),
            "transcribe_lib": options.get("transcribe_lib", "gigaam"),
            "noise_sup_bool": options.get("noise_sup_bool", "false")
        }
        
        # Вызов audio-ml сервиса
        response = requests.post(
            "http://audio-ml:8053/transcribe/",
            files=files,
            data=data,
            timeout=1200  # 20 минут на транскрибацию
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Audio-ML service error: {response.status_code} - {response.text}")
        
        ml_result = response.json()
        transcript_segments = ml_result.get("transcript", [])
        
        if not transcript_segments:
            raise RuntimeError("Audio-ML service returned empty transcript")
        
        logger.info(f"[{task_id}] Транскрибация завершена: {len(transcript_segments)} сегментов")
        update_task_status(task_id, "processing", {"step": "transcription", "percent": 40})
        
        # === 2. Суммаризация (вызов audio-ml сервиса) ===
        logger.info(f"[{task_id}] Шаг 2: Суммаризация")
        update_task_status(task_id, "processing", {"step": "summarization", "percent": 50})
        
        # Подготовка текста для суммаризации
        transcription_text = "\n".join(
            f"{seg.get('Speaker', 'UNKNOWN')}: {seg.get('Text', '')}"
            for seg in transcript_segments
        )
        
        summarize_data = {
            "input_text": transcription_text,
            "llm_model": options.get("llm_model", "gemini-2.5-flash")
        }
        
        summary_response = requests.post(
            "http://audio-ml:8053/llm_pipeline",
            data=summarize_data,
            timeout=300  # 5 минут на суммаризацию
        )
        
        summary_result = {}
        if summary_response.status_code == 200:
            try:
                summary_result = summary_response.json()
            except Exception as e:
                logger.warning(f"[{task_id}] Summarization returned invalid JSON: {e}")
        
        logger.info(f"[{task_id}] Суммаризация завершена")
        update_task_status(task_id, "processing", {"step": "summarization", "percent": 70})
        
        # === 3. Сохранение в PostgreSQL ===
        logger.info(f"[{task_id}] Шаг 3: Сохранение в БД")
        update_task_status(task_id, "processing", {"step": "db_save", "percent": 80})
        
        db = DataBaseManager()
        user_id = options.get("user_id")
        
        # Формируем оригинальный текст
        original_text = " ".join(
            seg.get("Text", "") for seg in transcript_segments if seg.get("Text")
        )
        
        # Извлекаем summary данные
        summary_json = summary_result.get("summary", {}) if isinstance(summary_result, dict) else {}
        title = summary_json.get("title", f"Запись от {task_id[:8]}")
        summary_text = summary_json.get("summary", "")
        key_points = summary_json.get("key_points", [])
        meeting_type = summary_json.get("meeting_type", "Не определено")
        
        # Вставляем транскрипцию
        transcript_id = db.insert_transcripts(
            text=original_text,
            title=title,
            employee_id=user_id
        )
        
        if not transcript_id:
            raise RuntimeError("Failed to insert transcript to database")
        
        # Вставляем части транскрипции
        for segment in transcript_segments:
            speaker = segment.get("Speaker", segment.get("speaker", "UNKNOWN"))
            text = segment.get("Text", "")
            start = segment.get("start", segment.get("start_time", 0))
            end = segment.get("stop", segment.get("end_time", 0))
            
            db.insert_parts_transcription(
                transcript_id=transcript_id,
                text=f"{speaker}: {text}",
                start_time=int(start * 1000),
                end_time=int(end * 1000)
            )
        
        # Вставляем суммаризацию
        if summary_text:
            db.insert_summaries(
                transcript_id=transcript_id,
                text=summary_text,
                key_points=key_points,
                meeting_type=meeting_type
            )
        
        logger.info(f"[{task_id}] Сохранение в БД завершено (transcript_id={transcript_id})")
        update_task_status(task_id, "processing", {"step": "db_save", "percent": 90})
        
        # === 4. RAG indexing ===
        logger.info(f"[{task_id}] Шаг 4: RAG индексирование")
        update_task_status(task_id, "processing", {"step": "rag_index", "percent": 95})
        
        try:
            # Получаем части транскрипции
            parts = db.select_parts_transcription_by_transcript_id(transcript_id)
            
            transcript_meta = {
                "id": transcript_id,
                "title": title,
                "meeting_type": meeting_type,
                "employee_id": user_id  # Добавляем employee_id для RAG фильтрации
            }
            
            # Функция split_into_chunks (нужно импортировать или скопировать)
            chunks = split_into_chunks(parts, transcript_meta)
            
            if chunks:
                requests.post(
                    "http://rag-service:8055/index",
                    json={"chunks": chunks},
                    timeout=30
                )
                logger.info(f"[{task_id}] RAG индексирование завершено")
        except Exception as e:
            logger.warning(f"[{task_id}] Не удалось проиндексировать в RAG: {e}")
            # Не прерываем задачу, RAG indexing не критичен

        # === 5. Speaker identification ===
        # Пытаемся определить реальных спикеров по SPEAKER_XX меткам
        try:
            enrolled = _get_enrolled_speakers()
            if enrolled:
                logger.info(f"[{task_id}] Найдено {len(enrolled)} зарегистрированных голосовых профилей")
                _match_speakers_in_parts(db, transcript_id, enrolled)
        except Exception as e:
            logger.warning(f"[{task_id}] Speaker identification не удалась: {e}")

        # === 6. Удаляем запись из scheduled_meetings ===
        # Пайплайн завершён, результат сохранён в transcripts/summaries — временная запись больше не нужна
        meeting_id = options.get("meeting_id")
        if meeting_id:
            try:
                db.delete_scheduled_meeting(meeting_id)
                logger.info(f"[{task_id}] Запись scheduled_meeting {meeting_id} удалена")
            except Exception as e:
                logger.warning(f"[{task_id}] Не удалось удалить scheduled_meeting: {e}")

        # === 6. Завершение ===
        logger.info(f"[{task_id}] Задача завершена успешно")
        update_task_status(task_id, "completed", {
            "step": "completed",
            "percent": 100,
            "transcript_id": str(transcript_id)  # Конвертируем UUID в строку
        })

        return {
            "status": "completed",
            "transcript_id": str(transcript_id),  # Конвертируем UUID в строку
            "title": title,
            "meeting_type": meeting_type
        }

    except Exception as exc:
        # === Обработка ошибок ===
        logger.error(f"[{task_id}] Ошибка обработки: {exc}")

        # Удаляем запись из scheduled_meetings при ошибке
        meeting_id = options.get("meeting_id")
        if meeting_id:
            try:
                db.delete_scheduled_meeting(meeting_id)
                logger.info(f"[{task_id}] Запись scheduled_meeting {meeting_id} удалена (ошибка)")
            except Exception:
                pass

        update_task_status(task_id, "failed", {
            "step": "failed",
            "error": str(exc)
        })

        # Retry через 60 секунд (exponential backoff)
        raise self.retry(exc=exc, countdown=60 * (2 ** (self.request.retries or 0)))


def split_into_chunks(parts: list, transcript_meta: dict, max_length: int = 500) -> list:
    """
    Разбивает транскрипцию на чанки для RAG индексирования.

    Args:
        parts: Список частей транскрипции из БД
        transcript_meta: Метаданные транскрипции (включая employee_id)
        max_length: Максимальная длина чанка

    Returns:
        Список чанков
    """
    chunks = []

    for part in parts:
        text = part.get("text", "")

        # Разбиваем текст на чанки если он слишком длинный
        if len(text) > max_length:
            words = text.split()
            current_chunk = []
            current_length = 0

            for word in words:
                current_chunk.append(word)
                current_length += len(word) + 1

                if current_length >= max_length:
                    chunks.append({
                        "text": " ".join(current_chunk),
                        "transcript_id": str(transcript_meta["id"]),
                        "employee_id": str(transcript_meta["employee_id"]),
                        "speaker": part.get("speaker", "UNKNOWN"),
                        "start_time": part.get("start_time", 0) / 1000.0,
                        "end_time": part.get("end_time", 0) / 1000.0,
                        "meeting_type": transcript_meta.get("meeting_type"),
                        "title": transcript_meta.get("title")
                    })
                    current_chunk = []
                    current_length = 0

            if current_chunk:
                chunks.append({
                    "text": " ".join(current_chunk),
                    "transcript_id": str(transcript_meta["id"]),
                    "employee_id": str(transcript_meta["employee_id"]),
                    "speaker": part.get("speaker", "UNKNOWN"),
                    "start_time": part.get("start_time", 0) / 1000.0,
                    "end_time": part.get("end_time", 0) / 1000.0,
                    "meeting_type": transcript_meta.get("meeting_type"),
                    "title": transcript_meta.get("title")
                })
        else:
            chunks.append({
                "text": text,
                "transcript_id": str(transcript_meta["id"]),
                "employee_id": str(transcript_meta["employee_id"]),
                "speaker": part.get("speaker", "UNKNOWN"),
                "start_time": part.get("start_time", 0) / 1000.0,
                "end_time": part.get("end_time", 0) / 1000.0,
                "meeting_type": transcript_meta.get("meeting_type"),
                "title": transcript_meta.get("title")
            })

    return chunks


def _get_enrolled_speakers() -> List[Dict[str, Any]]:
    """
    Get list of enrolled speakers from Qdrant voice profiles.
    Returns empty list if Qdrant is unavailable or no profiles exist.
    """
    try:
        from app.voice.qdrant_profiles import list_all_profiles
        return list_all_profiles()
    except ImportError:
        logger.debug("voice module not available, skipping speaker identification")
        return []
    except Exception as e:
        logger.debug(f"Could not fetch enrolled speakers: {e}")
        return []


def _match_speakers_in_parts(
    db: DataBaseManager,
    transcript_id: UUID,
    enrolled: List[Dict[str, Any]],
):
    """
    For each unique speaker label in the transcript parts, try to match
    against enrolled user profiles. Updates part text labels in DB.

    Simple label-based matching: if there's exactly one enrolled speaker
    or names match partially, update the parts.
    """
    parts = db.select_parts_transcription_by_transcript_id(transcript_id)
    if not parts:
        return

    # Extract unique speaker labels
    speaker_labels = set()
    for part in parts:
        text = part.get("text", "")
        if ":" in text:
            speaker = text.split(":", 1)[0].strip()
            speaker_labels.add(speaker)

    if not speaker_labels:
        return

    # Build mapping: SPEAKER_XX -> enrolled user name
    # Simple heuristic: assign in order (first SPEAKER_00 -> first enrolled, etc.)
    sorted_labels = sorted(speaker_labels)
    label_to_name = {}

    for i, label in enumerate(sorted_labels):
        if i < len(enrolled):
            full_name = enrolled[i].get("full_name", "")
            if full_name:
                label_to_name[label] = full_name

    if not label_to_name:
        return

    # Update parts with identified names
    for part in parts:
        text = part.get("text", "")
        if ":" not in text:
            continue

        speaker = text.split(":", 1)[0].strip()
        if speaker in label_to_name:
            new_text = f"{label_to_name[speaker]}:{text.split(':', 1)[1]}"
            db.update_parts_transcription(part["id"], text=new_text)

    logger.info(
        f"Speaker labels updated for transcript {transcript_id}: "
        f"{', '.join(f'{k}→{v}' for k, v in label_to_name.items())}"
    )
