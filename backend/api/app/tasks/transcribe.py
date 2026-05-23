"""
Celery задачи для обработки аудио.
"""
import json
import logging
import os
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
def transcribe_and_summarize_task(self, options: Dict[str, Any]):
    """
    Полный пайплайн обработки аудио:
    1. Транскрибация (diarization + transcription)
    2. Суммаризация
    3. Сохранение в PostgreSQL
    4. RAG indexing

    Args:
        options: Параметры обработки
            - recording_url: URL аудиофайла в MinIO (воркер скачивает сам)
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

        # Определяем internal URL для audio-ml (внутри Docker)
        audio_key = options.get("audio_key")
        if not audio_key:
            raise RuntimeError("audio_key is missing in options")
        minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        audio_bucket = os.getenv("AUDIO_BUCKET_NAME", "meeting-recordings")
        internal_url = f"http://{minio_endpoint}/{audio_bucket}/{audio_key}"

        # Передаём URL в audio-ml — он сам скачает файл из MinIO
        data = {
            "file_url": internal_url,
            "transcribe_model": options.get("transcribe_model", "v3_ctc"),
            "diarization_model": options.get("diarization_model", "pyannote/speaker-diarization-community-1"),
            "diarize_lib": options.get("diarize_lib", "pyannote"),
            "transcribe_lib": options.get("transcribe_lib", "gigaam"),
            "noise_sup_bool": options.get("noise_sup_bool", "false")
        }

        # Вызов audio-ml сервиса
        response = requests.post(
            "http://audio-ml:8053/transcribe/",
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

        # === 2. Speaker identification (by voice embeddings) ===
        # Определяем реальных спикеров ДО суммаризации, чтобы LLM получила имена
        speaker_label_map: Dict[str, str] = {}  # SPEAKER_XX -> real_name
        try:
            enrolled = _get_enrolled_speakers()
            if enrolled:
                logger.info(f"[{task_id}] Найдено {len(enrolled)} зарегистрированных голосовых профилей")

                # Скачиваем аудио из MinIO для speaker identification
                resp = requests.get(internal_url, timeout=300)
                resp.raise_for_status()
                audio_bytes = resp.content

                speaker_label_map = _identify_speakers_by_embedding(
                    None,  # db не нужен в dry_run
                    None,  # transcript_id ещё не существует
                    audio_bytes,
                    transcript_segments,
                    enrolled,
                    dry_run=True,  # только возвращает маппинг, не трогает БД
                )
        except Exception as e:
            logger.warning(f"[{task_id}] Speaker identification не удалась (продолжаем): {e}")

        # Применяем идентифицированные имена к тексту для суммаризации
        def _map_speaker(label: str) -> str:
            return speaker_label_map.get(label, label)

        # === 3. Суммаризация (вызов audio-ml сервиса) ===
        logger.info(f"[{task_id}] Шаг 3: Суммаризация")
        update_task_status(task_id, "processing", {"step": "summarization", "percent": 50})

        # Подготовка текста для суммаризации — уже с реальными именами
        transcription_text = "\n".join(
            f"{_map_speaker(seg.get('Speaker', seg.get('speaker', 'UNKNOWN')))}: {seg.get('Text', '')}"
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

        # === 4. Сохранение в PostgreSQL ===
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
        
        # === 5. RAG indexing ===
        logger.info(f"[{task_id}] Шаг 5: RAG индексирование")
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

        # === 6. Apply speaker labels to DB parts ===
        # Обновляем части транскрипции: проставляем реальные имена и employee_id
        if speaker_label_map:
            try:
                _apply_speaker_labels_to_parts(db, transcript_id, speaker_label_map)
            except Exception as e:
                logger.warning(f"[{task_id}] Не удалось обновить employee_id в частях: {e}")

        # === 7. Удаляем запись из scheduled_meetings ===
        # Пайплайн завершён, результат сохранён в transcripts/summaries — временная запись больше не нужна
        meeting_id = options.get("meeting_id")
        if meeting_id:
            try:
                db.delete_scheduled_meeting(meeting_id)
                logger.info(f"[{task_id}] Запись scheduled_meeting {meeting_id} удалена")
            except Exception as e:
                logger.warning(f"[{task_id}] Не удалось удалить scheduled_meeting: {e}")

        # === 8. Завершение ===
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


def _apply_speaker_labels_to_parts(
    db: DataBaseManager,
    transcript_id: UUID,
    label_map: Dict[str, str],
):
    """
    Обновляет части транскрипции в БД: заменяет SPEAKER_XX на реальное имя
    и проставляет employee_id (NULL — для неопознанных).
    """
    # Загружаем enrolled speakers для поиска user_id по имени
    enrolled = _get_enrolled_speakers()
    name_to_user_id = {s["full_name"].lower(): s["user_id"] for s in enrolled if s.get("full_name")}

    parts = db.select_parts_transcription_by_transcript_id(transcript_id)
    updated = 0
    for part in parts:
        text = part.get("text", "")
        if ":" not in text:
            continue
        speaker = text.split(":", 1)[0].strip()
        if speaker in label_map:
            real_name = label_map[speaker]
            new_text = f"{real_name}:{text.split(':', 1)[1]}"
            uid = name_to_user_id.get(real_name.lower())
            db.update_parts_transcription(
                part["id"],
                text=new_text,
                employee_id=uid,
            )
            updated += 1

    if updated:
        logger.info(f"Applied speaker labels to {updated} parts for {transcript_id}")


def _identify_speakers_by_embedding(
    db: DataBaseManager,
    transcript_id: UUID,
    file_bytes: bytes,
    transcript_segments: List[Dict[str, Any]],
    enrolled: List[Dict[str, Any]],
    dry_run: bool = False,
) -> Dict[str, str]:
    """
    Identify speakers by comparing voice embeddings against Qdrant profiles.

    Для каждого уникального SPEAKER_XX:
      1. Вырезать до 30 секунд его аудио по таймингам из оригинального файла
      2. Извлечь ECAPA-TDNN эмбеддинг
      3. Найти ближайший profile в Qdrant (cosine similarity, threshold 0.6)
      4. Если найден — обновить все части транскрипции с этим спикером

    Если dry_run=True — только возвращает маппинг SPEAKER_XX → полное имя,
    не трогает БД.
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
        return {}

    # Загружаем оригинальное аудио через pydub (WebM/MP3 и т.д. — ffmpeg в контейнере есть)
    try:
        from pydub import AudioSegment
        import io as io_module
        with io_module.BytesIO(file_bytes) as buf:
            full_audio = AudioSegment.from_file(buf)
    except Exception as e:
        logger.warning(f"Cannot load audio for speaker identification: {e}")
        return {}

    # Импортируем voice-модули (могут отсутствовать в тестовом окружении)
    try:
        from app.voice.speaker_identification import extract_embedding_from_wav_bytes
        from app.voice.qdrant_profiles import search_speaker
    except ImportError as e:
        logger.warning(f"Voice modules not available: {e}")
        return {}

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
            label_to_name[speaker_label] = {"name": full_name, "user_id": user_id}
            logger.info(f"{speaker_label} → {full_name} (score: {score:.4f})")

    # Строим плоский маппинг SPEAKER_XX → полное имя
    name_map: Dict[str, str] = {}
    for label, info in label_to_name.items():
        name_map[label] = info["name"]

    if not name_map:
        logger.info(f"No speakers identified for transcript {transcript_id}")
        return name_map

    if dry_run:
        logger.info(
            f"Speakers identified (dry_run) for {transcript_id}: "
            f"{', '.join(f'{k}→{v}' for k, v in name_map.items())}"
        )
        return name_map

    # Обновляем части транскрипции в БД
    parts = db.select_parts_transcription_by_transcript_id(transcript_id)
    updated = 0
    for part in parts:
        text = part.get("text", "")
        if ":" not in text:
            continue
        speaker = text.split(":", 1)[0].strip()
        if speaker in label_to_name:
            info = label_to_name[speaker]
            new_text = f"{info['name']}:{text.split(':', 1)[1]}"
            db.update_parts_transcription(
                part["id"],
                text=new_text,
                employee_id=info["user_id"],
            )
            updated += 1

    logger.info(
        f"Speaker identification for {transcript_id}: "
        f"{len(label_to_name)}/{len(speaker_timestamps)} speakers matched, "
        f"{updated} parts updated"
    )
    return name_map
