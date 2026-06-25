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
import torch
import librosa
import soundfile as sf
import gigaam
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
_gigaam_model = None  # for word-level alignment

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

    logger.info(f"Загрузка GigaAM Python API для word alignment...")
    try:
        global _gigaam_model
        # load_model скачает .ckpt в ~/.cache/gigaam/ при первом запуске
        _gigaam_model = gigaam.load_model(
            model_version,
            device="cuda",
        )
        logger.info("GigaAM Python API загружена успешно")
    except Exception as e:
        logger.warning(f"GigaAM Python API не загружена: {e} — /align_words недоступен")
        _gigaam_model = None


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
                print(result)
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


# ---------------------------------------------------------------------------
# Word-level alignment helpers
# ---------------------------------------------------------------------------


@torch.inference_mode()
def _decode_rnnt(head, encoded_seq, seq_len, blank_id, max_symbols=3):
    """RNNT decoder loop with frame tracking."""
    token_ids, token_frames = [], []
    dec_state, last_label = None, None

    for t in range(seq_len):
        encoder_step = encoded_seq[t, :, :].unsqueeze(1)
        not_blank = True
        emitted = 0

        while not_blank and emitted < max_symbols:
            decoder_step, hidden = head.decoder.predict(last_label, dec_state)
            joint = head.joint.joint(encoder_step, decoder_step)[0, 0, 0, :]
            k = int(torch.argmax(joint).item())

            if k == blank_id:
                not_blank = False
                continue

            token_ids.append(k)
            token_frames.append(t)
            last_label = torch.tensor([[k]], dtype=torch.long, device=encoded_seq.device)
            dec_state = hidden
            emitted += 1

    return token_ids, token_frames


@torch.inference_mode()
def _decode_ctc(head, encoded, seq_len, blank_id):
    """CTC argmax decoding with frame tracking."""
    log_probs = head(encoder_output=encoded)
    frame_labels = log_probs.argmax(dim=-1)[0, :seq_len].cpu().tolist()

    token_ids, token_frames = [], []
    prev = blank_id

    for t, lbl in enumerate(frame_labels):
        if lbl != blank_id and (lbl != prev or prev == blank_id):
            token_ids.append(lbl)
            token_frames.append(t)
        prev = lbl

    return token_ids, token_frames


def _get_token_str(tokenizer, token_id: int) -> str:
    """Decode a single token ID to its string representation."""
    if hasattr(tokenizer, "charwise") and tokenizer.charwise:
        return tokenizer.vocab[token_id]
    return tokenizer.model.IdToPiece(token_id)


def _chars_to_words(chars, frames, frame_shift):
    """Group character-level tokens into words with start/end times."""
    words, cur_chars, cur_frames = [], [], []

    def flush():
        if not cur_chars:
            return
        text = "".join(cur_chars).strip()
        if text:
            words.append({
                "word": text,
                "start": round(cur_frames[0] * frame_shift, 3),
                "end": round((cur_frames[-1] + 1) * frame_shift, 3),
            })
        cur_chars.clear()
        cur_frames.clear()

    for c, f in zip(chars, frames):
        if c == " " or c.startswith("▁"):
            flush()
            c = c.lstrip("▁")
            if c:
                cur_chars.append(c)
                cur_frames.append(f)
            continue
        cur_chars.append(c)
        cur_frames.append(f)

    flush()
    return words


@torch.inference_mode()
def _extract_word_timestamps(model, audio_path: str):
    """
    Extract word-level timestamps from GigaAM model.

    Uses model.prepare_wav() + model.forward() to get frame-level
    encoder outputs, then decodes with frame tracking.
    """
    wav, length = model.prepare_wav(audio_path)
    encoded, encoded_len = model.forward(wav, length)

    seq_len = int(encoded_len[0].item())
    frame_shift = float(length[0].item()) / SAMPLE_RATE / seq_len

    blank_id = model.decoding.blank_id
    tokenizer = model.decoding.tokenizer
    head = model.head

    is_rnnt = hasattr(head, "decoder") and hasattr(head, "joint")

    if is_rnnt:
        encoded_seq = encoded.transpose(1, 2)[0, :, :].unsqueeze(1)
        token_ids, token_frames = _decode_rnnt(head, encoded_seq, seq_len, blank_id)
    else:
        token_ids, token_frames = _decode_ctc(head, encoded, seq_len, blank_id)

    chars = [_get_token_str(tokenizer, i) for i in token_ids]
    words = _chars_to_words(chars, token_frames, frame_shift)

    return {
        "transcript": tokenizer.decode(token_ids).strip(),
        "words": words,
        "frame_shift": frame_shift,
    }


# ---------------------------------------------------------------------------
# Word-level alignment endpoint
# ---------------------------------------------------------------------------

# GigaAM positional embedding limit → макс фреймов до 5000 на чанк.
# С hop_length=200, subsampling=4: 5000 * 200 * 4 / 16000 = 250 секунд.
# Берём 140s для запаса.
_GIGAAM_CHUNK_SEC = 140.0


def _align_chunked(model, audio_path: str):
    """
    Align long audio by splitting into chunks.
    Each chunk is aligned independently, then words are merged with offset.
    """
    duration = librosa.get_duration(path=audio_path)

    if duration <= _GIGAAM_CHUNK_SEC:
        return _extract_word_timestamps(model, audio_path)

    logger.info(f"Long audio ({duration:.1f}s) — chunking at {_GIGAAM_CHUNK_SEC}s")

    all_words = []
    chunk_texts = []
    offset = 0.0
    chunk_idx = 0

    while offset < duration:
        seg_duration = min(_GIGAAM_CHUNK_SEC, duration - offset)

        # load only this chunk
        chunk_wave, _ = librosa.load(
            audio_path, sr=SAMPLE_RATE, mono=True,
            offset=offset, duration=seg_duration,
        )
        if len(chunk_wave) == 0:
            break

        # save to temp wav
        chunk_path = os.path.join(tempfile.gettempdir(), f"gigaam_word_align_{chunk_idx:04d}.wav")
        sf.write(chunk_path, chunk_wave, SAMPLE_RATE)

        try:
            result = _extract_word_timestamps(model, chunk_path)
            chunk_texts.append(result["transcript"])

            for w in result["words"]:
                all_words.append({
                    "word": w["word"],
                    "start": round(w["start"] + offset, 3),
                    "end": round(w["end"] + offset, 3),
                })
        finally:
            if os.path.exists(chunk_path):
                os.unlink(chunk_path)

        gc.collect()
        torch.cuda.empty_cache()

        offset += seg_duration
        chunk_idx += 1

    return {
        "transcript": " ".join(chunk_texts).strip(),
        "words": all_words,
    }


@app.post("/align_words")
async def align_words_endpoint(
    audio: UploadFile = File(...),
):
    """
    Transcribe audio and return word-level timestamps.
    Uses GigaAM's internal frame-level alignment.
    Long audio is automatically chunked.

    Returns:
        transcript: full transcription text
        words: list of {"word", "start", "end"}
    """
    global _gigaam_model

    if _gigaam_model is None:
        raise HTTPException(status_code=503, detail="GigaAM model not loaded")

    # Stream to temp file
    CHUNK_SIZE = 8_388_608
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_path = tmp.name
        while chunk := await audio.read(CHUNK_SIZE):
            tmp.write(chunk)

    try:
        result = _align_chunked(_gigaam_model, audio_path)
        logger.info(
            f"Word alignment: {len(result['words'])} words, "
            f"{len(result['transcript'])} chars"
        )
        return result
    except Exception as e:
        logger.error(f"Word alignment failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)
