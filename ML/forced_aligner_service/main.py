import os
import tempfile
import logging
from typing import List

import torch
import librosa
import soundfile as sf
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from pydantic import BaseModel

from qwen_asr import Qwen3ForcedAligner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MAX_CHUNK_SECONDS = 300  # 5 минут

model = None

app = FastAPI(title="Qwen3 Forced Aligner Service", version="1.0")


@app.on_event("startup")
async def startup_event():
    global model
    logger.info("Loading Qwen3-ForcedAligner-0.6B ...")
    try:
        model_path = os.getenv(
            "FORCED_ALIGNER_MODEL_PATH",
            "Qwen/Qwen3-ForcedAligner-0.6B",
        )

        if os.path.exists(model_path):
            logger.info(f"Loading model from local path: {model_path}")
            model = Qwen3ForcedAligner.from_pretrained(
                model_path,
                dtype=torch.bfloat16,
                device_map="cuda:0",
            )
        else:
            logger.info(f"Local path not found, loading from HuggingFace: {model_path}")
            model = Qwen3ForcedAligner.from_pretrained(
                model_path,
                dtype=torch.bfloat16,
                device_map="cuda:0",
            )

        logger.info("Qwen3-ForcedAligner-0.6B loaded successfully!")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


@app.get("/health")
async def health_check():
    status = "ready" if model is not None else "loading"
    return {"status": status, "service": "forced-aligner"}


class Segment(BaseModel):
    text: str
    start_time: float
    end_time: float


class AlignResponse(BaseModel):
    segments: List[Segment]


@app.post("/align", response_model=AlignResponse)
async def align_endpoint(
    audio: UploadFile = File(...),
    text: str = Form(...),
):
    global model


    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty")

    # Stream upload to temp file — no full-RAM buffering
    CHUNK_SIZE = 8_388_608  # 8 MB
    suffix = ".wav"
    if audio.filename:
        _, ext = os.path.splitext(audio.filename)
        if ext:
            suffix = ext

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        audio_path = tmp.name
        while chunk := await audio.read(CHUNK_SIZE):
            tmp.write(chunk)

    logger.info(
        f"Received alignment request: "
        f"audio={audio.filename} ({os.path.getsize(audio_path)} bytes), "
        f"text length={len(text)} chars"
    )

    try:
        if os.path.getsize(audio_path) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")

        # Load audio to check duration
        audio_wave, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
        duration = len(audio_wave) / SAMPLE_RATE
        all_segments: List[Segment] = []

        if duration <= MAX_CHUNK_SECONDS:
            logger.info(f"Audio duration {duration:.1f}s — aligning directly")
            results = model.align(
                audio=audio_path,
                text=text,
                language="Russian",
            )
            for seg in results[0]:
                all_segments.append(Segment(
                    text=seg.text,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                ))
        else:
            # Длинное аудио — режем на 5-минутные чанки
            logger.info(f"Audio duration {duration:.1f}s — splitting into {MAX_CHUNK_SECONDS}s chunks")
            chunk_samples = MAX_CHUNK_SECONDS * SAMPLE_RATE
            text_chars = len(text)
            chars_per_second = text_chars / duration
            total_chunks = (len(audio_wave) + chunk_samples - 1) // chunk_samples

            for chunk_idx, offset in enumerate(range(0, len(audio_wave), chunk_samples)):
                chunk_audio = audio_wave[offset:offset + chunk_samples]
                chunk_duration = len(chunk_audio) / SAMPLE_RATE
                if chunk_duration < 0.5:
                    continue

                chunk_start_time = offset / SAMPLE_RATE
                chunk_start_char = min(int(chunk_start_time * chars_per_second), text_chars - 1)
                chunk_end_char = min(int((chunk_start_time + chunk_duration) * chars_per_second), text_chars)
                chunk_text = text[chunk_start_char:chunk_end_char]

                if not chunk_text.strip():
                    continue

                # Save chunk to temp wav
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as chunk_tmp:
                    chunk_path = chunk_tmp.name
                    sf.write(chunk_path, chunk_audio, SAMPLE_RATE)

                try:
                    chunk_results = model.align(
                        audio=chunk_path,
                        text=chunk_text,
                        language="Russian",
                    )
                    for seg in chunk_results[0]:
                        all_segments.append(Segment(
                            text=seg.text,
                            start_time=seg.start_time + chunk_start_time,
                            end_time=seg.end_time + chunk_start_time,
                        ))
                    logger.info(
                        f"  Chunk {chunk_idx + 1}/{total_chunks}: "
                        f"{chunk_duration:.1f}s, {len(chunk_text)} chars, "
                        f"{len(chunk_results[0])} segments"
                    )
                finally:
                    if os.path.exists(chunk_path):
                        os.unlink(chunk_path)

        logger.info(f"Alignment complete: {len(all_segments)} segments")
        return AlignResponse(segments=all_segments)

    except Exception as e:
        logger.error(f"Alignment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)
            logger.debug(f"Temp file removed: {audio_path}")
