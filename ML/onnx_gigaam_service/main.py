"""
GigaAM ONNX Transcription Service

Автономный микросервис для инференса GigaAM v3_e2e_rnnt / v3_e2e_ctc
через ONNX Runtime (gigaam.onnx_utils).

Запускается в отдельном контейнере, чтобы изолировать CUDA-контекст ONNX Runtime
от PyTorch (pyannote) в основном audio-ml сервисе.
"""
import os
import gc
import json
import logging
import tempfile
from typing import List, Dict, Any

import numpy as np
import librosa
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gigaam-onnx-service")

SAMPLE_RATE = 16000
# Уменьшенный размер чанка для снижения пикового потребления памяти.
# pos_emb_max_len=5000 при hop_length=160 и subsampling=4 даёт макс ~200 с.
# 75 с — безопасный запас, при котором каждый infer_onnx аллоцирует меньше памяти.
RNNT_MAX_SAMPLES = 1_200_000
RNNT_OVERLAP = 16_000

_model_cfg = None
_sessions = None
_model_version = None

app = FastAPI(title="GigaAM ONNX Transcription Service", version="1.0")


@app.on_event("startup")
async def startup_event():
    global _model_cfg, _sessions, _model_version

    model_dir = os.getenv("GIGAAM_MODEL_PATH", "/app/models/gigaam_v3_e2e_rnnt")
    model_version = os.getenv("GIGAAM_MODEL_VERSION", "v3_e2e_rnnt")
    _model_version = model_version

    logger.info(f"Загрузка ONNX модели {model_version} из {model_dir}...")

    from gigaam.onnx_utils import load_onnx

    _sessions, _model_cfg = load_onnx(
        model_dir, model_version, provider="CUDAExecutionProvider"
    )

    logger.info(f"ONNX модель {model_version} загружена успешно")


@app.get("/health")
async def health_check():
    status = "ready" if _sessions is not None else "loading"
    return {
        "status": status,
        "service": "gigaam-onnx-transcription",
        "model": _model_version,
    }


@app.post("/transcribe")
async def transcribe_endpoint(
    request: str = Form(...),
    audio: UploadFile = File(...),
):
    global _model_cfg, _sessions

    if _sessions is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    logger.info(
        f"Получен запрос. Аудио: {audio.filename}, размер: {audio.size} байт"
    )

    # Стримим HTTP body в temp-файл чанками — без загрузки всего в RAM
    CHUNK_SIZE = 8_388_608  # 8 MB
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_path = tmp.name
        while chunk := await audio.read(CHUNK_SIZE):
            tmp.write(chunk)

    try:
        request_data: Dict[str, Any] = json.loads(request)
        diarization_results: List[Dict[str, Any]] = request_data["diarization_results"]
        logger.info(f"Сегментов: {len(diarization_results)}")

        # Собираем все чанки с индексом сегмента.
        # Каждый сегмент загружаем отдельно через librosa(offset=, duration=),
        # без полной загрузки всего аудио в RAM.
        chunk_list: List[Dict[str, Any]] = []  # {"seg_idx": int, "samples": np.ndarray}

        for seg_idx, seg in enumerate(diarization_results):
            start_sec = seg["start"]
            duration_sec = seg["stop"] - seg["start"]
            if duration_sec <= 0:
                continue

            # Загружаем только этот сегмент
            segment, _ = librosa.load(
                audio_path, sr=SAMPLE_RATE, mono=True,
                offset=start_sec, duration=duration_sec,
            )

            # Сегменты длиннее лимита — дробим с перекрытием
            if len(segment) > RNNT_MAX_SAMPLES:
                s = 0
                while s < len(segment):
                    e = min(s + RNNT_MAX_SAMPLES, len(segment))
                    chunk_list.append({"seg_idx": seg_idx, "samples": segment[s:e]})
                    if e == len(segment):
                        break
                    s += RNNT_MAX_SAMPLES - RNNT_OVERLAP
            else:
                chunk_list.append({"seg_idx": seg_idx, "samples": segment})

        if not chunk_list:
            return JSONResponse(content=diarization_results)

        # Инференс — по одному чанку, как в рабочем примере
        # (batched infer_onnx жрёт ~10 GB GPU памяти на 30 чанках)
        from gigaam.onnx_utils import infer_onnx
        import soundfile as sf

        seg_texts: Dict[int, List[str]] = {}
        logger.info(f"Инференс {len(chunk_list)} чанк(ов) по одному...")

        # Импортируем torch для очистки кэша CUDA после каждого чанка.
        # torch не импортирован в этом модуле напрямую, но gigaam.onnx_utils
        # и FeatureExtractor внутри infer_onnx используют torch,
        # поэтому torch уже загружен в процесс.
        import torch

        for i, item in enumerate(chunk_list):
            seg_idx = item["seg_idx"]
            chunk = item["samples"]

            # Сохраняем во временный WAV (infer_onnx с filepath — как в примере)
            chunk_path = os.path.join(tempfile.gettempdir(), f"gigaam_chunk_{i:04d}.wav")
            sf.write(chunk_path, chunk, SAMPLE_RATE)

            try:
                result = infer_onnx([chunk_path], _model_cfg, _sessions, progress=False)
                seg_texts.setdefault(seg_idx, []).append(result[0])
            finally:
                if os.path.exists(chunk_path):
                    os.unlink(chunk_path)

            # Принудительная сборка мусора после каждого чанка,
            # чтобы ONNX Runtime / PyTorch не копили аллокации.
            gc.collect()
            torch.cuda.empty_cache()

            if (i + 1) % 10 == 0:
                logger.info(f"Прогресс: {i + 1}/{len(chunk_list)} чанков")

        for seg_idx, seg in enumerate(diarization_results):
            if seg_idx in seg_texts:
                seg["Text"] = " ".join(seg_texts[seg_idx]).strip()
            else:
                seg["Text"] = ""

        logger.info(f"Транскрибация завершена. Сегментов: {len(diarization_results)}")
        return JSONResponse(content=diarization_results)

    except Exception as e:
        logger.error(f"Ошибка транскрибации: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)


@app.post("/transcribe_full")
async def transcribe_full_endpoint(
    audio: UploadFile = File(...),
):
    """
    Transcribe the ENTIRE audio file in one pass.

    Reads the audio in offset-based chunks (RNNT_MAX_SAMPLES at a time)
    via librosa.load(offset=, duration=) — never loads the full file into RAM.
    Returns the concatenated full text.

    Returns: {"text": "full transcription text"}
    """
    global _model_cfg, _sessions

    if _sessions is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    logger.info(f"Full transcription request: {audio.filename}, size: {audio.size} bytes")

    # Stream upload to temp file — no full-RAM buffering
    CHUNK_SIZE = 8_388_608
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_path = tmp.name
        while chunk := await audio.read(CHUNK_SIZE):
            tmp.write(chunk)

    try:
        if os.path.getsize(audio_path) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")

        # Get total duration without loading audio into RAM
        import soundfile as sf_info
        info = sf_info.SoundFile(audio_path)
        total_duration = info.frames / info.samplerate
        info.close()
        logger.info(f"Audio duration: {total_duration:.1f}s")

        chunk_duration = RNNT_MAX_SAMPLES / SAMPLE_RATE  # ~75 s
        overlap_duration = RNNT_OVERLAP / SAMPLE_RATE     # 1 s

        from gigaam.onnx_utils import infer_onnx
        import torch
        import soundfile as sf

        chunk_texts = []
        offset = 0.0
        chunk_idx = 0

        while offset < total_duration:
            seg_duration = min(chunk_duration, total_duration - offset)

            # Load only this chunk — no full-file RAM usage
            chunk_wave, _ = librosa.load(
                audio_path, sr=SAMPLE_RATE, mono=True,
                offset=offset, duration=seg_duration,
            )

            if len(chunk_wave) == 0:
                break

            # Save to temp wav and infer
            chunk_path = os.path.join(
                tempfile.gettempdir(), f"gigaam_full_chunk_{chunk_idx:04d}.wav"
            )
            sf.write(chunk_path, chunk_wave, SAMPLE_RATE)
            try:
                result = infer_onnx([chunk_path], _model_cfg, _sessions, progress=False)
                chunk_texts.append(result[0])
            finally:
                if os.path.exists(chunk_path):
                    os.unlink(chunk_path)

            # Free GPU memory after every chunk
            del chunk_wave
            gc.collect()
            torch.cuda.empty_cache()

            if offset + seg_duration >= total_duration:
                break
            offset += chunk_duration - overlap_duration
            chunk_idx += 1

            if chunk_idx % 10 == 0:
                logger.info(f"Full transcribe progress: {chunk_idx} chunks")

        full_text = " ".join(chunk_texts).strip()
        logger.info(f"Full transcription complete: {len(full_text)} chars")
        return {"text": full_text}

    except Exception as e:
        logger.error(f"Full transcription error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)
