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
            "llm_model": options.get("llm_model", "deepseek/deepseek-v4-flash")
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
        
        # Сохраняем recording_url если передан (для плеера на фронтенде)
        recording_url = options.get("recording_url")
        if recording_url:
            db.update_transcripts(transcript_id, recording_url=recording_url)
            logger.info(f"[{task_id}] recording_url сохранён: {recording_url}")

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

        # === 5. Speaker identification (by voice embeddings) ===
        try:
            enrolled = _get_enrolled_speakers()
            if enrolled:
                logger.info(f"[{task_id}] Найдено {len(enrolled)} зарегистрированных голосовых профилей")
                _identify_speakers_by_embedding(
                    db, transcript_id, file_bytes, transcript_segments, enrolled
                )
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


def _identify_speakers_by_embedding(
    db: DataBaseManager,
    transcript_id: UUID,
    file_bytes: bytes,
    transcript_segments: List[Dict[str, Any]],
    enrolled: List[Dict[str, Any]],
):
    """
    Identify speakers by comparing voice embeddings against Qdrant profiles.

    Для каждого уникального SPEAKER_XX:
      1. Вырезать до 30 секунд его аудио по таймингам из оригинального файла
      2. Извлечь ECAPA-TDNN эмбеддинг
      3. Найти ближайший profile в Qdrant (cosine similarity, threshold 0.6)
      4. Если найден — обновить все части транскрипции с этим спикером
    """
    from collections import defaultdict

    # Группируем тайминги по спикеру
    speaker_timestamps = defaultdict(list)
    for seg in transcript_segments:
        speaker = seg.get("Speaker", seg.get("speaker", "UNKNOWN"))
        start = seg.get("start", seg.get("start_time", 0))
        end = seg.get("stop", seg.get("end_time", 0))
        if float(end) > float(start):
            speaker_timestamps[speaker].append((float(start), float(end)))

    if not speaker_timestamps:
        return

    # Загружаем оригинальное аудио через pydub (WebM/MP3 и т.д. — ffmpeg в контейнере есть)
    try:
        from pydub import AudioSegment
        import io as io_module
        with io_module.BytesIO(file_bytes) as buf:
            full_audio = AudioSegment.from_file(buf)
    except Exception as e:
        logger.warning(f"Cannot load audio for speaker identification: {e}")
        return

    # Импортируем voice-модули (могут отсутствовать в тестовом окружении)
    try:
        from app.voice.speaker_identification import extract_embedding_from_wav_bytes
        from app.voice.qdrant_profiles import search_speaker
    except ImportError as e:
        logger.warning(f"Voice modules not available: {e}")
        return

    MAX_SECONDS = 30
    label_to_name = {}

    for speaker_label, timestamps in speaker_timestamps.items():
        # Склеиваем сегменты этого спикера, но не дольше MAX_SECONDS
        speaker_audio = None
        total_ms = 0
        max_ms = MAX_SECONDS * 1000

        for start_sec, end_sec in timestamps:
            if total_ms >= max_ms:
                break
            start_ms = int(start_sec * 1000)
            end_ms = int(end_sec * 1000)
            seg = full_audio[start_ms:end_ms]
            if speaker_audio is None:
                speaker_audio = seg
            else:
                speaker_audio = speaker_audio + seg
            total_ms += len(seg)

        if speaker_audio is None or len(speaker_audio) < 1000:
            logger.debug(f"{speaker_label}: too short ({len(speaker_audio)//1000}s), skip")
            continue

        # Экспортируем в WAV bytes
        with io_module.BytesIO() as buf:
            speaker_audio.export(buf, format="wav")
            wav_bytes = buf.getvalue()

        # Извлекаем эмбеддинг
        embedding = extract_embedding_from_wav_bytes(wav_bytes)
        if embedding is None:
            logger.debug(f"{speaker_label}: embedding extraction failed, skip")
            continue

        # Ищем в Qdrant
        result = search_speaker(embedding=embedding, threshold=0.6)
        if result:
            user_id, full_name, score = result
            label_to_name[speaker_label] = full_name
            logger.info(f"{speaker_label} → {full_name} (score: {score:.4f})")

    if not label_to_name:
        logger.info(f"No speakers identified for transcript {transcript_id}")
        return

    # Обновляем части транскрипции в БД
    parts = db.select_parts_transcription_by_transcript_id(transcript_id)
    updated = 0
    for part in parts:
        text = part.get("text", "")
        if ":" not in text:
            continue
        speaker = text.split(":", 1)[0].strip()
        if speaker in label_to_name:
            new_text = f"{label_to_name[speaker]}:{text.split(':', 1)[1]}"
            db.update_parts_transcription(part["id"], text=new_text)
            updated += 1

    logger.info(
        f"Speaker identification for {transcript_id}: "
        f"{len(label_to_name)}/{len(speaker_timestamps)} speakers matched, "
        f"{updated} parts updated"
    )
