"""
API роуты для транскрибации аудио.
"""
import logging
import tempfile
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from config import settings
from core.audio_converter import AudioConverter
from core.diarization.pyannote import PyannoteDiarization
from core.transcription.gigaam import GigaamTranscription
from core.noise_suppression import NoiseSuppressionClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcribe", tags=["Транскрибация"])


@router.post("/")
async def transcribe(
    file: UploadFile = File(..., description="Аудиофайл для транскрибации"),
    transcribe_model: str = Form("v3_ctc", description="Модель транскрибации"),
    diarization_model: str = Form(
        "pyannote/speaker-diarization-community-1",
        description="Модель диаризации"
    ),
    diarize_lib: str = Form("pyannote", description="Библиотека диаризации"),
    transcribe_lib: str = Form("gigaam", description="Библиотека транскрибации"),
    noise_sup_bool: str = Form("false", description="Использовать шумоподавление")
):
    """
    Транскрибация аудиофайла с диаризацией.
    
    - **file**: Аудиофайл (mp3, wav, mp4, ogg)
    - **transcribe_model**: Модель для транскрибации
    - **diarization_model**: Модель для диаризации спикеров
    - **transcribe_lib**: Библиотека транскрибации (gigaam/whisper)
    - **diarize_lib**: Библиотека диаризации (pyannote)
    - **noise_sup_bool**: Использовать ли шумоподавление
    """
    # Валидация расширения файла
    converter = AudioConverter()
    converter.validate_extension(file.filename)
    
    # Парсинг флага шумоподавления
    use_noise_suppression = noise_sup_bool.lower() in ("true", "yes", "1", "on")
    
    # Временная директория для файлов
    temp_dir = None
    
    try:
        # Создание временной директории
        temp_dir = tempfile.mkdtemp()
        input_path = Path(temp_dir) / f"input{Path(file.filename).suffix}"
        
        # Сохранение загруженного файла
        with open(input_path, "wb") as f:
            f.write(await file.read())
        
        logger.info(f"Загружен файл: {input_path} ({len(await file.read()) if hasattr(await file.read(), '__len__') else 'unknown'} bytes)")
        
        # Конвертация в WAV если нужно
        audio_converter = AudioConverter()
        if input_path.suffix.lower() != '.wav':
            wav_path = Path(temp_dir) / "input.wav"
            audio_converter.convert_to_wav(str(input_path), str(wav_path))
            audio_path = str(wav_path)
        else:
            audio_path = str(input_path)
        
        # Применение шумоподавления если запрошено
        if use_noise_suppression:
            logger.info("Применение шумоподавления...")
            noise_client = NoiseSuppressionClient()
            clean_audio_path = noise_client.apply_noise_suppression(audio_path)
            
            # Конвертация очищенного аудио в нужный формат
            if clean_audio_path != audio_path:
                audio_path = clean_audio_path
        
        # Диаризация
        logger.info("Запуск диаризации...")
        diarizer = PyannoteDiarization()
        diarization_segments = diarizer.diarize(audio_path)
        
        # Транскрибация
        logger.info("Запуск транскрибации...")
        if transcribe_lib == "gigaam":
            transcriber = GigaamTranscription()
            transcribed_segments = transcriber.transcribe(
                segments=diarization_segments,
                audio_path=audio_path,
                model_name=transcribe_model
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
    model: str = Form("pyannote/speaker-diarization-community-1", description="Модель диаризации")
):
    """
    Только диаризация аудио (без транскрибации).
    """
    converter = AudioConverter()
    converter.validate_extension(file.filename)
    
    temp_dir = None
    
    try:
        temp_dir = tempfile.mkdtemp()
        input_path = Path(temp_dir) / f"input{Path(file.filename).suffix}"
        
        with open(input_path, "wb") as f:
            f.write(await file.read())
        
        # Конвертация в WAV
        audio_converter = AudioConverter()
        if input_path.suffix.lower() != '.wav':
            wav_path = Path(temp_dir) / "input.wav"
            audio_converter.convert_to_wav(str(input_path), str(wav_path))
            audio_path = str(wav_path)
        else:
            audio_path = str(input_path)
        
        # Диаризация
        diarizer = PyannoteDiarization(model_path=model)
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
