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
import torchaudio
import librosa
import soundfile as sf
import gigaam
import hydra
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
_preprocessor = None  # FeatureExtractor for ONNX alignment
_tokenizer = None     # tokenizer for word alignment

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

    # Prepare feature extractor and tokenizer for word alignment
    global _preprocessor, _tokenizer
    _preprocessor = hydra.utils.instantiate(_model_cfg.preprocessor)
    _tokenizer = hydra.utils.instantiate(_model_cfg.decoding).tokenizer
    logger.info("FeatureExtractor + tokenizer готовы для word alignment")


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
# Word-level alignment helpers (ONNX Runtime)
# ---------------------------------------------------------------------------


def _onnx_session_dtype(session):
    """Infer numpy float dtype from the first float input of an ONNX session."""
    type_map = {
        "tensor(float16)": np.dtype(np.float16),
        "tensor(float)": np.dtype(np.float32),
        "tensor(double)": np.dtype(np.float64),
    }
    for inp in session.get_inputs():
        if inp.type in type_map:
            return type_map[inp.type]
    return np.dtype(np.float32)


def _onnx_build_inputs(session, values):
    return {node.name: data for node, data in zip(session.get_inputs(), values)}


def _decode_rnnt_onnx(encoded, encoded_len, pred_sess, joint_sess, blank_id):
    """
    RNNT greedy decode with frame tracking via ONNX Runtime.

    Returns (token_ids, token_frames) for a single sample (B=1).
    Adapted from gigaam.onnx_utils._decode_rnnt_batch.
    """
    dtype = _onnx_session_dtype(pred_sess)
    pred_rnn_layers = _model_cfg.head.decoder.pred_rnn_layers
    pred_hidden = _model_cfg.head.decoder.pred_hidden
    max_symbols = _model_cfg.decoding.get("max_symbols_per_step", 10)

    enc_features = np.asarray(encoded, dtype=dtype, order="C")  # [1, D, T]
    B, _, T = enc_features.shape
    assert B == 1, "Single-sample only"

    token_ids: List[int] = []
    token_frames: List[int] = []
    last_label = None
    dec_state = None

    def emit_at(t: int, fresh: bool):
        nonlocal last_label, dec_state

        f = enc_features[:, :, t : t + 1]  # [1, D, 1]

        if fresh:
            labels = np.full((1, 1), blank_id, dtype=np.int64)
            h = np.zeros((pred_rnn_layers, 1, pred_hidden), dtype=dtype)
            c = np.zeros((pred_rnn_layers, 1, pred_hidden), dtype=dtype)
        else:
            labels = last_label  # [1, 1]
            h, c = dec_state

        pred_outputs = pred_sess.run(
            [node.name for node in pred_sess.get_outputs()],
            _onnx_build_inputs(pred_sess, [labels, h, c]),
        )
        # pred_outputs[0] = dec [1, 1, H]
        # pred_outputs[1] = ho [L, 1, H]
        # pred_outputs[2] = co [L, 1, H]

        joint_outputs = joint_sess.run(
            [node.name for node in joint_sess.get_outputs()],
            _onnx_build_inputs(
                joint_sess, [f, pred_outputs[0].swapaxes(1, 2)],
            ),
        )
        # joint_outputs[0] = [1, num_classes, 1, 1]
        k = int(joint_outputs[0][0, 0, 0, :].argmax())

        if k == blank_id:
            return None

        token_ids.append(k)
        token_frames.append(t)
        last_label = np.array([[k]], dtype=np.int64)
        dec_state = (pred_outputs[1], pred_outputs[2])
        return k

    enc_len = int(encoded_len[0])

    for t in range(T):
        if t >= enc_len:
            break

        for _ in range(max_symbols):
            fresh = dec_state is None
            emitted = emit_at(t, fresh)
            if emitted is None:
                break

    return token_ids, token_frames


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


def _extract_word_timestamps_onnx(audio_path: str):
    """
    Extract word-level timestamps via ONNX Runtime.

    Loads audio with torchaudio (consistent with infer_onnx), extracts
    features via the shared FeatureExtractor, runs ONNX encoder, then
    decodes with frame tracking using ONNX decoder+joint sessions.
    """
    global _preprocessor, _tokenizer, _sessions

    # 1. Load audio (torchaudio — same as infer_onnx / AudioDataset)
    wav, sr = torchaudio.load(audio_path)
    if wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)
    wav = wav.squeeze(0)
    if sr != SAMPLE_RATE:
        wav = torchaudio.functional.resample(wav, sr, SAMPLE_RATE)

    audio_length_samples = wav.shape[-1]

    # 2. Feature extraction
    wav_batch = wav.unsqueeze(0).float()
    wav_len = torch.tensor([audio_length_samples], dtype=torch.long)
    features, feature_lengths = _preprocessor(wav_batch, wav_len)

    # 3. ONNX encoder
    enc_sess = _sessions[0]
    dtype = _onnx_session_dtype(enc_sess)
    enc_outputs = enc_sess.run(
        [node.name for node in enc_sess.get_outputs()],
        _onnx_build_inputs(
            enc_sess,
            [
                features.contiguous().numpy().astype(dtype),
                feature_lengths.numpy().astype(np.int64),
            ],
        ),
    )
    encoded = enc_outputs[0]   # [1, D, T_enc]
    encoded_len = enc_outputs[1]  # [1]

    seq_len = int(encoded_len[0])
    frame_shift = audio_length_samples / SAMPLE_RATE / seq_len

    # 4. RNNT decode with frame tracking
    pred_sess, joint_sess = _sessions[1], _sessions[2]
    blank_id = len(_tokenizer)

    token_ids, token_frames = _decode_rnnt_onnx(
        encoded, encoded_len, pred_sess, joint_sess, blank_id,
    )

    # 5. Convert to words
    chars = [_tokenizer.id_to_str(i) for i in token_ids]
    words = _chars_to_words(chars, token_frames, frame_shift)

    logger.info(
        f"_extract_word_timestamps_onnx: seq_len={seq_len}, "
        f"token_ids={len(token_ids)}, words={len(words)}, "
        f"transcript='{_tokenizer.decode(token_ids).strip()[:80]}'"
    )

    return {
        "transcript": _tokenizer.decode(token_ids).strip(),
        "words": words,
        "frame_shift": frame_shift,
    }


# ---------------------------------------------------------------------------
# Word-level alignment endpoint
# ---------------------------------------------------------------------------

# GigaAM positional embedding limit → макс фреймов до 5000 на чанк.
# С hop_length=160, subsampling=4: 5000 * 160 * 4 / 16000 = 200 секунд.
# Но RNNT декодер через ONNX выдаёт blank на чанках >~100s (баг декодера).
# Используем 75s — проверено на transcribe_full, работает стабильно.
_GIGAAM_CHUNK_SEC = 25.0


def _align_chunked(audio_path: str):
    """
    Align long audio by splitting into chunks.
    Each chunk is aligned independently via ONNX, then words are merged
    with time offset.
    """
    duration = librosa.get_duration(path=audio_path)

    if duration <= _GIGAAM_CHUNK_SEC:
        return _extract_word_timestamps_onnx(audio_path)

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
        chunk_path = os.path.join(
            tempfile.gettempdir(), f"gigaam_word_align_{chunk_idx:04d}.wav"
        )
        sf.write(chunk_path, chunk_wave, SAMPLE_RATE)

        try:
            result = _extract_word_timestamps_onnx(chunk_path)
            n_words = len(result["words"])
            chunk_texts.append(result["transcript"])

            logger.info(
                f"  Chunk {chunk_idx}: [{offset:.0f}-{offset+seg_duration:.0f}]s "
                f"({seg_duration:.0f}s) → {n_words} words"
            )

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
    Uses GigaAM ONNX Runtime (encoder + decoder + joint).
    Long audio is automatically chunked.

    Returns:
        transcript: full transcription text
        words: list of {"word", "start", "end"}
    """
    global _preprocessor, _tokenizer, _sessions

    if _preprocessor is None or _tokenizer is None:
        raise HTTPException(status_code=503, detail="ONNX model not loaded yet")

    # Stream to temp file
    CHUNK_SIZE = 8_388_608
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_path = tmp.name
        while chunk := await audio.read(CHUNK_SIZE):
            tmp.write(chunk)

    try:
        result = _align_chunked(audio_path)
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
