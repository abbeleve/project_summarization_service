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

model = None

app = FastAPI(title="Whisper Transcription Service", version="1.0")


@app.on_event("startup")
async def startup_event():
    """Загрузка модели при старте сервиса."""
    global model
    logger.info("Начало загрузки модели Whisper large-v3...")
    try:
        # Проверяем переменную окружения для пути к модели
        model_path = os.getenv("WHISPER_MODEL_PATH", "/app/models/faster-whisper-large-v3")
        
        if os.path.exists(model_path):
            logger.info(f"Загрузка модели из локального пути: {model_path}")
            model = WhisperModel(model_path, device="cuda", compute_type="float16")
        else:
            # Fallback: загрузка из кэша Hugging Face
            logger.warning(f"Локальная модель не найдена по пути {model_path}, загрузка из Hugging Face...")
            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
        
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

        # Транскрибация сегментов — каждый загружается отдельно через offset/duration
        # Никогда не загружаем весь файл в RAM.
        for index, timings in tqdm(enumerate(diarization_results)):
            start = timings["start"]
            stop = timings["stop"]
            duration = stop - start
            if duration <= 0:
                continue

            logger.debug(
                f"Сегмент {index + 1}/{len(diarization_results)} "
                f"[{start:.2f}s - {stop:.2f}s] (длит. {duration:.2f}s)"
            )

            # librosa загружает с ресемплингом в 16kHz, только нужный участок
            audio_chunk, _ = librosa.load(
                audio_path,
                sr=SAMPLE_RATE,
                mono=True,
                offset=start,
                duration=(stop - start),
            )

            # Передаём numpy array напрямую, без промежуточного WAV-файла
            segments, _ = model.transcribe(audio_chunk, beam_size=1, language="ru")
            transcribed_text = "".join(segment.text for segment in segments)
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