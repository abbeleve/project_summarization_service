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
from faster_whisper.audio import decode_audio
import soundfile as sf

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
    logger.info(f"Получен запрос на транскрибацию. Размер аудио: {len(await audio.read())} байт")
    
    # Перематываем файл обратно после чтения
    await audio.seek(0)
    
    if model is None:
        logger.error("Модель не загружена!")
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await audio.read())
        audio_path = tmp.name

    try:
        logger.info(f"Аудио сохранено во временный файл: {audio_path}")
        
        if not os.path.isfile(audio_path):
            logger.error(f"Файл не найден: {audio_path}")
            raise HTTPException(status_code=400, detail="Audio file not saved")
        if os.path.getsize(audio_path) == 0:
            logger.error(f"Файл пустой: {audio_path}")
            raise HTTPException(status_code=400, detail="Audio file is empty")

        logger.info("Декодирование аудио...")
        audio_waveform = decode_audio(audio_path)
        
        request_data = json.loads(request)
        diarization_results = request_data["diarization_results"]
        logger.info(f"Количество сегментов для транскрибации: {len(diarization_results)}")

        for index, timings in tqdm(enumerate(diarization_results)):
            start_sample = int(timings["start"] * SAMPLE_RATE)
            stop_sample = int(timings["stop"] * SAMPLE_RATE)
            audio_chunk = audio_waveform[start_sample:stop_sample]

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as chunk_file:
                sf.write(chunk_file.name, audio_chunk, SAMPLE_RATE)
                logger.debug(f"Обработка сегмента {index + 1}/{len(diarization_results)} [{timings['start']:.2f}s - {timings['stop']:.2f}s]")
                segments, _ = model.transcribe(chunk_file.name, beam_size=5, language="ru")
                transcribed_text = "".join(segment.text for segment in segments)
                diarization_results[index]["Text"] = transcribed_text
                os.unlink(chunk_file.name)

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