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

# Silero VAD
from silero_vad import get_speech_timestamps as _vad_get_speech_ts
from silero_vad.utils_vad import OnnxWrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MAX_CHUNK_SECONDS = 300  # 5 минут — максимальная длина одного чанка

# Globals
model = None
vad_model = None

app = FastAPI(title="Qwen3 Forced Aligner Service", version="1.0")


@app.on_event("startup")
async def startup_event():
    global model, vad_model
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
        logger.error(f"Failed to load Qwen3 aligner: {e}")
        raise

    logger.info("Loading Silero VAD ...")
    try:
        silero_vad_path = os.getenv("SILERO_VAD_MODEL_PATH")
        if silero_vad_path and os.path.exists(silero_vad_path):
            logger.info(f"Loading Silero VAD from local path: {silero_vad_path}")
            vad_model = OnnxWrapper(silero_vad_path, force_onnx_cpu=True)
        else:
            logger.info("Loading Silero VAD from package data")
            from silero_vad import load_silero_vad
            vad_model = load_silero_vad(onnx=True)
        logger.info("Silero VAD loaded successfully!")
    except Exception as e:
        logger.warning(f"Failed to load Silero VAD: {e} — will use uniform chunking fallback")
        vad_model = None


@app.get("/health")
async def health_check():
    status = "ready" if model is not None else "loading"
    return {"status": status, "service": "forced-aligner"}


@app.post("/vad")
async def vad_endpoint(
    audio: UploadFile = File(...),
):
    """
    Pure VAD test endpoint. Returns speech segments without alignment.
    Useful for comparing VAD results between different runs.
    """
    global vad_model

    if vad_model is None:
        raise HTTPException(status_code=503, detail="VAD model not loaded")

    # Stream to temp file
    suffix = ".wav"
    if audio.filename:
        _, ext = os.path.splitext(audio.filename)
        if ext:
            suffix = ext

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        audio_path = tmp.name
        while chunk := await audio.read(8_388_608):
            tmp.write(chunk)

    try:
        audio_wave, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
        duration = len(audio_wave) / SAMPLE_RATE
        audio_tensor = torch.from_numpy(audio_wave).float()

        speech_ts = _vad_get_speech_ts(audio_tensor, vad_model, return_seconds=True)

        return {
            "duration_s": round(duration, 2),
            "speech_segments": [
                {"start": round(s["start"], 3), "end": round(s["end"], 3)}
                for s in speech_ts
            ],
            "num_segments": len(speech_ts),
            "total_speech_s": round(sum(s["end"] - s["start"] for s in speech_ts), 2),
        }
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)


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
            # VAD-нарезка: режем аудио по логическим сегментам (тишина между ними)
            logger.info(f"Audio duration {duration:.1f}s — splitting by VAD speech segments")
            all_segments = _align_by_vad(
                model=model,
                audio_wave=audio_wave,
                full_text=text,
                duration=duration,
            )

        logger.info(f"Alignment complete: {len(all_segments)} segments")
        return AlignResponse(segments=all_segments)

    except Exception as e:
        logger.error(f"Alignment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)
            logger.debug(f"Temp file removed: {audio_path}")


# ---------------------------------------------------------------------------
# VAD-based chunking
# ---------------------------------------------------------------------------


def _merge_vad_segments(
    segments: list[dict],
    max_gap_s: float = 2.0,
    max_duration_s: float = 300.0,
) -> list[dict]:
    """
    Merge VAD speech segments separated by gaps <= *max_gap_s* into
    utterance groups. Each group is capped at *max_duration_s*.

    Returns list of {'start': ..., 'end': ...} dicts.
    """
    if not segments:
        return []

    groups: list[dict] = [{'start': segments[0]['start'], 'end': segments[0]['end']}]

    for seg in segments[1:]:
        gap = seg['start'] - groups[-1]['end']
        would_duration = seg['end'] - groups[-1]['start']

        if gap <= max_gap_s and would_duration <= max_duration_s:
            # Merge into current group
            groups[-1]['end'] = seg['end']
        else:
            groups.append({'start': seg['start'], 'end': seg['end']})

    return groups


def _align_by_vad(
    model: Qwen3ForcedAligner,
    audio_wave,
    full_text: str,
    duration: float,
) -> List[Segment]:
    """
    Split audio by Silero VAD speech segments, then align each chunk
    independently. Text is distributed proportionally to speech duration
    (not total audio duration, so pauses don't skew the ratio).
    """
    all_segments: List[Segment] = []
    text_len = len(full_text)

    # 1. Check VAD is available
    if vad_model is None:
        logger.warning("VAD model not loaded — falling back to uniform chunking")
        return _align_uniform_chunks(model, audio_wave, full_text, duration)

    # 2. Convert numpy array to torch tensor for VAD
    audio_tensor = torch.from_numpy(audio_wave).float()

    # 3. Get VAD speech segments
    speech_segments = _vad_get_speech_ts(audio_tensor, vad_model, return_seconds=True)
    if not speech_segments:
        logger.warning("VAD returned no speech segments — falling back to uniform chunking")
        return _align_uniform_chunks(model, audio_wave, full_text, duration)

    # 2. Merge close segments into utterance groups
    groups = _merge_vad_segments(speech_segments, max_gap_s=2.0, max_duration_s=MAX_CHUNK_SECONDS)
    logger.info(f"VAD: {len(speech_segments)} speech segments → {len(groups)} utterance groups")

    # 3. Total speech duration (excludes silence)
    total_speech = sum(g['end'] - g['start'] for g in groups)
    chars_per_speech_sec = text_len / total_speech if total_speech > 0 else 0

    # 4. Align each group
    cum_speech = 0.0
    for idx, group in enumerate(groups):
        group_dur = group['end'] - group['start']
        if group_dur < 0.5:
            cum_speech += group_dur
            continue

        # Text slice for this group (proportional to speech time)
        char_start = int(cum_speech * chars_per_speech_sec)
        char_end = int((cum_speech + group_dur) * chars_per_speech_sec)
        cum_speech += group_dur

        chunk_text = full_text[char_start:char_end]
        if not chunk_text.strip():
            continue

        # Audio slice
        start_sample = int(group['start'] * SAMPLE_RATE)
        end_sample = int(group['end'] * SAMPLE_RATE)
        chunk_audio = audio_wave[start_sample:end_sample]

        # Save to temp wav
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            chunk_path = tmp.name
            sf.write(chunk_path, chunk_audio, SAMPLE_RATE)

        try:
            results = model.align(
                audio=chunk_path,
                text=chunk_text,
                language="Russian",
            )
            for seg in results[0]:
                all_segments.append(Segment(
                    text=seg.text,
                    start_time=seg.start_time + group['start'],
                    end_time=seg.end_time + group['start'],
                ))
            logger.info(
                f"  Group {idx + 1}/{len(groups)}: "
                f"[{group['start']:.1f}-{group['end']:.1f}]s, "
                f"{group_dur:.1f}s, {len(chunk_text)} chars, {len(results[0])} segments"
            )
        except Exception as e:
            logger.error(f"  Group {idx + 1}/{len(groups)} alignment failed: {e}")
        finally:
            if os.path.exists(chunk_path):
                os.unlink(chunk_path)

    return all_segments


def _align_uniform_chunks(
    model: Qwen3ForcedAligner,
    audio_wave,
    full_text: str,
    duration: float,
) -> List[Segment]:
    """
    Fallback: uniform 300s chunking (original behaviour).
    Used when VAD is unavailable or returns no segments.
    """
    all_segments: List[Segment] = []
    chunk_samples = MAX_CHUNK_SECONDS * SAMPLE_RATE
    text_len = len(full_text)
    chars_per_second = text_len / duration if duration > 0 else 0
    total_chunks = (len(audio_wave) + chunk_samples - 1) // chunk_samples

    for chunk_idx, offset in enumerate(range(0, len(audio_wave), chunk_samples)):
        chunk_audio = audio_wave[offset:offset + chunk_samples]
        chunk_dur = len(chunk_audio) / SAMPLE_RATE
        if chunk_dur < 0.5:
            continue

        chunk_start_time = offset / SAMPLE_RATE
        char_start = min(int(chunk_start_time * chars_per_second), text_len - 1)
        char_end = min(int((chunk_start_time + chunk_dur) * chars_per_second), text_len)
        chunk_text = full_text[char_start:char_end]

        if not chunk_text.strip():
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            chunk_path = tmp.name
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
                f"{chunk_dur:.1f}s, {len(chunk_text)} chars, "
                f"{len(chunk_results[0])} segments"
            )
        except Exception as e:
            logger.error(f"  Chunk {chunk_idx + 1}/{total_chunks} failed: {e}")
        finally:
            if os.path.exists(chunk_path):
                os.unlink(chunk_path)

    return all_segments
