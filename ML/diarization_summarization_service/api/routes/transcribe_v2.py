"""
WhisperX-style transcription pipeline (v2).

Flow:
  1. Download audio (file or file_url) + convert to WAV
  2. DIARIZATION — pyannote identifies speaker segments
  3. FULL TRANSCRIBE — entire audio in one pass → full text
  4. FORCED ALIGN — align full text to audio → word-level timestamps
  5. MERGE — assign each word to a speaker via timestamp overlap
"""
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import httpx
import requests
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends

from config import settings
from core.audio_converter import AudioConverter
from core.diarization.pyannote import PyannoteDiarization
from core.diarization.base import DiarizationSegment
from core.transcription.full_transcriber import FullTranscriber
from core.merge import merge, AlignedWord, FinalSegment
from dependencies import (
    get_audio_converter_singleton,
    get_diarization_singleton,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcribe_v2", tags=["Транскрибация v2 (WhisperX)"])

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}


def _extract_audio_with_ffmpeg(input_path: Path, output_path: Path, sample_rate: int) -> str:
    """Extract audio track from video via ffmpeg."""
    import subprocess
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        str(output_path),
        "-y",
        "-loglevel", "error",
    ]
    logger.info(f"ffmpeg: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    logger.info(f"Audio extracted: {output_path}")
    return str(output_path)


@router.post("/")
async def transcribe_v2(
    file: Optional[UploadFile] = File(None, description="Аудиофайл"),
    file_url: Optional[str] = Form(None, description="URL аудио в MinIO"),
    transcribe_model: str = Form("v3_e2e_rnnt", description="Модель транскрибации"),
    diarization_model: str = Form(
        "pyannote/speaker-diarization-community-1",
        description="Модель диаризации",
    ),
    diarize_lib: str = Form("pyannote", description="Библиотека диаризации"),
    transcribe_lib: str = Form("gigaam", description="Библиотека транскрибации"),
    audio_converter: AudioConverter = Depends(get_audio_converter_singleton),
    diarizer: PyannoteDiarization = Depends(get_diarization_singleton),
):
    """
    WhisperX-style transcription: diarize → full transcribe → forced align → merge.

    Параметры — те же, что и у v1:
      - file / file_url (один обязателен)
      - transcribe_lib: gigaam | whisper
      - diarize_lib: pyannote (только pyannote)
    """
    if not file and not file_url:
        raise HTTPException(400, "Необходимо передать file или file_url")

    temp_dir = None
    audio_path: Optional[str] = None

    try:
        temp_dir = tempfile.mkdtemp()

        # === 1. Download & convert to WAV ===
        if file_url:
            filename = file_url.rstrip("/").split("/")[-1] or "audio.webm"
            input_path = Path(temp_dir) / filename
            logger.info(f"Downloading audio from {file_url}")
            resp = requests.get(file_url, stream=True, timeout=300)
            resp.raise_for_status()
            with open(input_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8_388_608):
                    if chunk:
                        f.write(chunk)
        else:
            audio_converter.validate_extension(file.filename)
            input_path = Path(temp_dir) / f"input{Path(file.filename).suffix}"
            with open(input_path, "wb") as f:
                while chunk := await file.read(8_388_608):
                    f.write(chunk)

        logger.info(f"Input file: {input_path} ({input_path.stat().st_size} bytes)")

        # Convert to WAV 16kHz mono
        if input_path.suffix.lower() in VIDEO_EXTENSIONS:
            wav_path = Path(temp_dir) / "input.wav"
            audio_path = _extract_audio_with_ffmpeg(input_path, wav_path, audio_converter.sample_rate)
        elif input_path.suffix.lower() != ".wav":
            wav_path = Path(temp_dir) / "input.wav"
            audio_converter.convert_to_wav(str(input_path), str(wav_path))
            audio_path = str(wav_path)
        else:
            import wave
            try:
                with wave.open(str(input_path), "rb") as wf:
                    wav_sr = wf.getframerate()
                if wav_sr != audio_converter.sample_rate:
                    logger.info(f"WAV sr={wav_sr}Hz != target — resampling")
                    wav_path = Path(temp_dir) / "input_resampled.wav"
                    audio_converter.convert_to_wav(str(input_path), str(wav_path))
                    audio_path = str(wav_path)
                else:
                    audio_path = str(input_path)
            except Exception:
                wav_path = Path(temp_dir) / "input_resampled.wav"
                audio_converter.convert_to_wav(str(input_path), str(wav_path))
                audio_path = str(wav_path)

        # === 2. Diarization ===
        logger.info("=== Step 1/4: Diarization ===")
        diarization_segments = diarizer.diarize(audio_path)
        logger.info(f"Diarization: {len(diarization_segments)} segments, "
                     f"{len(set(s.speaker for s in diarization_segments))} speakers")
        print(diarization_segments)
        # === 3. Full-audio transcription ===
        logger.info("=== Step 2/4: Full transcription ===")
        transcriber = FullTranscriber()
        full_text = transcriber.transcribe_full(
            audio_path=audio_path,
            transcribe_lib=transcribe_lib,
        )
        logger.info(f"Full transcription: {len(full_text)} chars")
        print(full_text)
        if not full_text.strip():
            raise RuntimeError("Full transcription returned empty text")

        # === 4. Forced alignment ===
        logger.info("=== Step 3/4: Forced alignment ===")
        aligned_words = await _align_text(
            audio_path=audio_path,
            text=full_text,
        )
        print(aligned_words)
        logger.info(f"Forced alignment: {len(aligned_words)} words")

        # === 5. Merge ===
        logger.info("=== Step 4/4: Merge ===")
        final_segments = merge(diarization_segments, aligned_words)
        logger.info(f"Merge complete: {len(final_segments)} final segments")
        print(final_segments)
        # Format response (same schema as v1)
        segments_dicts = [
            {
                "Speaker": seg.speaker,
                "start": seg.start,
                "stop": seg.stop,
                "Text": seg.text,
            }
            for seg in final_segments
        ]
        print(segments_dicts)
        duration = max((seg.stop for seg in final_segments), default=0)
        speakers = set(seg.speaker for seg in final_segments)

        return {
            "transcript": segments_dicts,
            "duration": duration,
            "speakers_count": len(speakers),
            "pipeline": "whisperx",
        }

    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        logger.error(f"Pipeline error: {e}")
        raise HTTPException(500, str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Processing failed: {str(e)}")
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


async def _align_text(audio_path: str, text: str) -> list[AlignedWord]:
    """
    Send audio + full text to the forced-aligner microservice via httpx (async).
    Returns the list of word-level aligned timestamps.
    """
    url = settings.forced_aligner_url
    timeout = settings.forced_aligner_timeout_sec

    async with httpx.AsyncClient(timeout=timeout) as client:
        with open(audio_path, "rb") as f:
            files = {"audio": (audio_path, f, "audio/wav")}
            resp = await client.post(url, files=files, data={"text": text})

    if resp.status_code != 200:
        raise RuntimeError(
            f"Forced aligner error {resp.status_code}: {resp.text}"
        )

    result = resp.json()
    raw_segments = result.get("segments", [])

    return [
        AlignedWord(
            text=seg["text"],
            start=seg["start_time"],
            end=seg["end_time"],
        )
        for seg in raw_segments
        if seg.get("text", "").strip()
    ]
