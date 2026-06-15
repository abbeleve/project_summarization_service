"""
API роуты для транскрибации аудио.
"""
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional
import requests
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from config import settings
from core.audio_converter import AudioConverter
from core.diarization.pyannote import PyannoteDiarization
from core.transcription.gigaam import GigaamTranscription
from core.transcription.whisper import WhisperTranscription
from core.noise_suppression import NoiseSuppressionClient
from dependencies import (
    get_audio_converter_singleton,
    get_diarization_singleton,
    get_transcription_singleton
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcribe", tags=["Транскрибация"])

# Форматы, требующие извлечения аудиодорожки через ffmpeg
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}


def _extract_audio_with_ffmpeg(input_path: Path, output_path: Path, sample_rate: int) -> str:
    """
    Извлекает аудиодорожку из видеофайла через ffmpeg.
    Параллельно делает ресемплинг, конвертацию в моно и WAV.
    Результат — готовый к использованию WAV файл.
    """
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-vn",                              # без видео
        "-acodec", "pcm_s16le",             # 16-bit PCM
        "-ar", str(sample_rate),            # ресемплинг
        "-ac", "1",                         # моно
        str(output_path),
        "-y",                               # перезаписать
        "-loglevel", "error"
    ]
    logger.info(f"ffmpeg: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    logger.info(f"Аудио извлечено: {output_path}")
    return str(output_path)


@router.post("/")
async def transcribe(
    file: Optional[UploadFile] = File(None, description="Аудиофайл для транскрибации"),
    file_url: Optional[str] = Form(None, description="URL аудиофайла в MinIO (альтернатива file)"),
    transcribe_model: str = Form("v3_e2e_rnnt", description="Модель транскрибации"),
    diarization_model: str = Form(
        "pyannote/speaker-diarization-community-1",
        description="Модель диаризации"
    ),
    diarize_lib: str = Form("pyannote", description="Библиотека диаризации"),
    transcribe_lib: str = Form("gigaam", description="Библиотека транскрибации"),
    noise_sup_bool: str = Form("false", description="Использовать шумоподавление"),
    audio_converter: AudioConverter = Depends(get_audio_converter_singleton),
    diarizer: PyannoteDiarization = Depends(get_diarization_singleton),
    transcriber_gigaam: GigaamTranscription = Depends(get_transcription_singleton)
):
    """
    Транскрибация аудиофайла с диаризацией.

    Принимает либо **file** (прямая загрузка), либо **file_url** (URL в MinIO).
    Один из двух параметров обязателен.

    - **file**: Аудиофайл (mp3, wav, mp4, ogg)
    - **file_url**: URL аудиофайла в MinIO (audio-ml сам скачает)
    - **transcribe_model**: Модель для транскрибации
    - **diarization_model**: Модель для диаризации спикеров
    - **transcribe_lib**: Библиотека транскрибации (gigaam/whisper)
    - **diarize_lib**: Библиотека диаризации (pyannote)
    - **noise_sup_bool**: Использовать ли шумоподавление
    """
    if not file and not file_url:
        raise HTTPException(400, "Необходимо передать file или file_url")

    # Временная директория для файлов
    temp_dir = None

    try:
        # Создание временной директории
        temp_dir = tempfile.mkdtemp()

        # Определяем имя файла и скачиваем
        if file_url:
            # Скачиваем по URL (streaming, без resp.content)
            filename = file_url.rstrip("/").split("/")[-1] or "audio.webm"
            input_path = Path(temp_dir) / filename
            logger.info(f"Скачивание аудио из {file_url}")
            resp = requests.get(file_url, stream=True, timeout=300)
            resp.raise_for_status()
            with open(input_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8_388_608):  # 8MB чанки
                    if chunk:
                        f.write(chunk)
            file_size = input_path.stat().st_size
            logger.info(f"Файл скачан: {input_path} ({file_size} байт)")
        else:
            # Прямая загрузка файла (чанками, без await file.read())
            audio_converter.validate_extension(file.filename)
            input_path = Path(temp_dir) / f"input{Path(file.filename).suffix}"
            with open(input_path, "wb") as f:
                while chunk := await file.read(8_388_608):
                    f.write(chunk)
            logger.info(f"Загружен файл: {input_path}")

        # Для видеофайлов — извлекаем только аудиодорожку через ffmpeg
        # Это превращает 600MB MP4 → ~50MB WAV, снимая нагрузку с torchaudio
        if input_path.suffix.lower() in VIDEO_EXTENSIONS:
            wav_path = Path(temp_dir) / "input.wav"
            audio_path = _extract_audio_with_ffmpeg(input_path, wav_path, audio_converter.sample_rate)
        elif input_path.suffix.lower() != '.wav':
            wav_path = Path(temp_dir) / "input.wav"
            audio_converter.convert_to_wav(str(input_path), str(wav_path))
            audio_path = str(wav_path)
        else:
            audio_path = str(input_path)

        # Диаризация (используем singleton экземпляр)
        logger.info("Запуск диаризации...")
        diarization_segments = diarizer.diarize(audio_path)

        # Транскрибация
        logger.info("Запуск транскрибации...")
        if transcribe_lib == "gigaam":
            # Используем singleton экземпляр с кэшем моделей
            transcribed_segments = transcriber_gigaam.transcribe(
                segments=diarization_segments,
                audio_path=audio_path,
                model_name=transcribe_model
            )
        elif transcribe_lib == "whisper":
            # Whisper сервис — создаём новый экземпляр (легковесный HTTP клиент)
            logger.info(f"Использование Whisper сервиса: {settings.whisper_service_url}")
            transcriber = WhisperTranscription(
                service_url=settings.whisper_service_url,
                timeout=settings.whisper_timeout_sec
            )
            logger.info(f"Сегменты диаризации: {len(diarization_segments)}")
            transcribed_segments = transcriber.transcribe(
                segments=diarization_segments,
                audio_path=audio_path
            )
        else:
            raise HTTPException(400, f"Unsupported transcribe_lib: {transcribe_lib}")
        
        # Формирование ответа
        segments_dicts = [seg.to_dict() for seg in transcribed_segments]
        
        # Подсчёт спикеров
        speakers = set(seg.speaker for seg in transcribed_segments)
        
        # Длительность
        duration = max((seg.stop for seg in transcribed_segments), default=0)
        
        return {
            "transcript": segments_dicts,
            "duration": duration,
            "speakers_count": len(speakers)
        }
        
    except FileNotFoundError as e:
        logger.error(f"Файл не найден: {e}")
        raise HTTPException(400, str(e))
    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        logger.error(f"Ошибка обработки: {e}")
        raise HTTPException(500, str(e))
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Processing failed: {str(e)}")
    finally:
        # Очистка временных файлов
        if temp_dir and shutil:
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/diarize")
async def diarize_only(
    file: UploadFile = File(..., description="Аудиофайл для диаризации"),
    model: str = Form("pyannote/speaker-diarization-community-1", description="Модель диаризации"),
    audio_converter: AudioConverter = Depends(get_audio_converter_singleton),
    diarizer: PyannoteDiarization = Depends(get_diarization_singleton)
):
    """
    Только диаризация аудио (без транскрибации).
    """
    audio_converter.validate_extension(file.filename)

    temp_dir = None

    try:
        temp_dir = tempfile.mkdtemp()
        input_path = Path(temp_dir) / f"input{Path(file.filename).suffix}"

        with open(input_path, "wb") as f:
            while chunk := await file.read(8_388_608):
                f.write(chunk)

        # Конвертация в WAV
        if input_path.suffix.lower() != '.wav':
            wav_path = Path(temp_dir) / "input.wav"
            audio_converter.convert_to_wav(str(input_path), str(wav_path))
            audio_path = str(wav_path)
        else:
            audio_path = str(input_path)

        # Диаризация (используем singleton экземпляр)
        segments = diarizer.diarize(audio_path)

        return {
            "segments": [seg.to_dict() for seg in segments],
            "speakers_count": len(set(seg.speaker for seg in segments))
        }

    except Exception as e:
        logger.error(f"Ошибка диаризации: {e}")
        raise HTTPException(500, f"Diarization failed: {str(e)}")
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
