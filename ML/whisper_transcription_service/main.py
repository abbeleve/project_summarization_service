# main.py
import os
import tempfile
import json
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from faster_whisper import WhisperModel
from tqdm import tqdm
import librosa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
WHISPER_MAX_SAMPLES = 28_800_000  # 1800 секунд при 16кГц
WHISPER_OVERLAP = 32_000          # 2 секунды перекрытие

model = None

app = FastAPI(title="Whisper Transcription Service", version="1.0")


@app.on_event("startup")
async def startup_event():
    """Загрузка модели при старте сервиса."""
    global model
    logger.info("Начало загрузки модели Whisper large-v3...")
    try:
        # Проверяем переменную окружения для пути к модели
        model_path = os.getenv("WHISPER_MODEL_PATH", "/app/models/faster-distil-whisper-large-v3-ru-int8")

        if os.path.exists(model_path):
            logger.info(f"Загрузка модели из локального пути: {model_path}")
            model = WhisperModel(model_path, device="cuda")
        else:
            # Fallback: загрузка из кэша Hugging Face
            logger.warning(f"Локальная модель не найдена по пути {model_path}, загрузка из Hugging Face...")
            model = WhisperModel("large-v3", device="cuda")
        
        logger.info("Модель Whisper успешно загружена!")
    except Exception as e:
        logger.error(f"Ошибка загрузки модели: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    global model
    status = "ready" if model is not None else "loading"
    return {"status": status, "service": "whisper-transcription"}


class DiarizationItem(BaseModel):
    start: float
    stop: float
    speaker: str


class TranscribeRequest(BaseModel):
    diarization_results: List[Dict]

@app.post("/transcribe")
async def transcribe_endpoint(
    request: str = Form(...),
    audio: UploadFile = File(...)
):
    global model

    if model is None:
        logger.error("Модель не загружена!")
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    if audio.size:
        logger.info(f"Получен запрос на транскрибацию. Размер аудио: {audio.size} байт")
    else:
        logger.info("Получен запрос на транскрибацию. Размер аудио: неизвестен")

    # Стримим HTTP body в temp-файл чанками по 8MB — без загрузки всего в RAM
    CHUNK_SIZE = 8_388_608  # 8 MB
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_path = tmp.name
        while chunk := await audio.read(CHUNK_SIZE):
            tmp.write(chunk)

    try:
        logger.info(f"Аудио сохранено во временный файл: {audio_path} ({os.path.getsize(audio_path)} байт)")

        if not os.path.isfile(audio_path):
            logger.error(f"Файл не найден: {audio_path}")
            raise HTTPException(status_code=400, detail="Audio file not saved")
        if os.path.getsize(audio_path) == 0:
            logger.error(f"Файл пустой: {audio_path}")
            raise HTTPException(status_code=400, detail="Audio file is empty")

        request_data = json.loads(request)
        diarization_results = request_data["diarization_results"]
        logger.info(f"Количество сегментов для транскрибации: {len(diarization_results)}")

        # Транскрибация сегментов — каждый загружается отдельно через offset/duration.
        # Сегменты длиннее WHISPER_MAX_SAMPLES дробятся на чанки с перекрытием.
        # Загрузка в RAM — не более одного чанка за раз.
        for index, timings in tqdm(enumerate(diarization_results)):
            start = timings["start"]
            stop = timings["stop"]
            duration = stop - start
            if duration <= 0:
                continue

            chunk_duration = WHISPER_MAX_SAMPLES / SAMPLE_RATE  # 1800 с
            overlap_duration = WHISPER_OVERLAP / SAMPLE_RATE    # 2 с

            if duration <= chunk_duration:
                # Короткий сегмент — загружаем целиком
                audio_chunk, _ = librosa.load(
                    audio_path, sr=SAMPLE_RATE, mono=True,
                    offset=start, duration=duration,
                )
                segments, _ = model.transcribe(audio_chunk, beam_size=1, language="ru")
                transcribed_text = "".join(segment.text for segment in segments)
            else:
                # Длинный сегмент — грузим чанками по chunk_duration с перекрытием
                chunk_texts = []
                chunk_start = start
                while chunk_start < stop:
                    chunk_end = min(chunk_start + chunk_duration, stop)
                    chunk_len = chunk_end - chunk_start
                    audio_chunk, _ = librosa.load(
                        audio_path, sr=SAMPLE_RATE, mono=True,
                        offset=chunk_start, duration=chunk_len,
                    )
                    segments, _ = model.transcribe(audio_chunk, beam_size=1, language="ru")
                    chunk_texts.append("".join(seg.text for seg in segments))
                    if chunk_end >= stop:
                        break
                    chunk_start += chunk_duration - overlap_duration
                transcribed_text = " ".join(chunk_texts).strip()

            diarization_results[index]["Text"] = transcribed_text

        logger.info(f"Транскрибация завершена успешно. Обработано сегментов: {len(diarization_results)}")
        return JSONResponse(content=diarization_results)

    except Exception as e:
        logger.error(f"Ошибка при транскрибации: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)
            logger.debug(f"Временный файл удалён: {audio_path}")