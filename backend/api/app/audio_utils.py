"""
Утилиты для нормализации аудиофайлов.

Приводит любой аудиофайл к единому формату: WAV, 16kHz, моно, 16-bit PCM.
"""
import io
import logging
import wave
from typing import IO, Optional

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2  # 16-bit PCM


def guess_format(data: bytes) -> Optional[str]:
    """Определить формат аудио по magic-bytes."""
    if data.startswith(b'RIFF') and data[8:12] == b'WAVE':
        return 'wav'
    if data.startswith(b'\xff\xfb') or data.startswith(b'\xff\xf3') or data.startswith(b'\xff\xf2'):
        return 'mp3'
    if data.startswith(b'fLaC'):
        return 'flac'
    if data.startswith(b'OggS'):
        return 'ogg'
    if data.startswith(b'\x1aE\xdf\xa3'):
        return 'webm'
    if data.startswith(b'ftyp'):
        return 'mp4'
    return None


def _wav_sample_rate(data: bytes) -> int:
    """Прочитать sample rate из заголовка WAV без загрузки сэмплов."""
    with io.BytesIO(data) as buf:
        with wave.open(buf, 'rb') as w:
            return w.getframerate()


def is_wav_16khz_mono(source: IO[bytes]) -> bool:
    """Быстрая проверка: является ли файл уже WAV 16kHz моно.

    Читает только заголовок WAV (~44 байта), не загружает сэмплы.
    После вызова позиция в source возвращается в начало (seek(0)).
    """
    try:
        header = source.read(100)
        source.seek(0)
        if header[:4] != b'RIFF' or header[8:12] != b'WAVE':
            return False
        with wave.open(io.BytesIO(header), 'rb') as w:
            return w.getframerate() == TARGET_SAMPLE_RATE and w.getnchannels() == TARGET_CHANNELS
    except Exception:
        source.seek(0)
        return False


def normalize_audio(file_bytes: bytes, original_filename: str = "audio") -> bytes:
    """
    Привести аудио к единому формату: WAV 16kHz моно 16-bit PCM.

    - Не-WAV → конвертация через pydub
    - WAV, но sample rate ≠ 16000 → ресемплинг
    - Уже валидный WAV → без изменений

    Args:
        file_bytes: Сырые байты аудиофайла.
        original_filename: Оригинальное имя файла (для fallback определения формата).

    Returns:
        Нормализованные байты WAV 16kHz моно 16-bit PCM.

    Raises:
        ValueError: Пустой файл.
        RuntimeError: Ошибка конвертации (pydub/ffmpeg не установлены).
    """
    if not file_bytes:
        raise ValueError("Empty audio file")

    fmt = guess_format(file_bytes)
    if fmt is None:
        raise ValueError(f"Cannot detect audio format: {original_filename}")

    # Уже WAV — проверим sample rate
    if fmt == 'wav':
        try:
            sr = _wav_sample_rate(file_bytes)
            if sr == TARGET_SAMPLE_RATE:
                logger.debug("Audio already WAV %dHz — returning as-is", sr)
                return file_bytes
            logger.info("WAV sample rate %dHz → resampling to %dHz", sr, TARGET_SAMPLE_RATE)
        except Exception as e:
            logger.warning("Could not read WAV header, will convert via pydub: %s", e)

    # Конвертация через pydub
    try:
        from pydub import AudioSegment

        with io.BytesIO(file_bytes) as buf:
            audio = AudioSegment.from_file(buf, format=fmt)

        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(TARGET_CHANNELS)

        with io.BytesIO() as out:
            audio.export(out, format='wav')
            return out.getvalue()

    except ImportError:
        raise RuntimeError("pydub is required. Install: pip install pydub")
    except Exception as e:
        msg = str(e).lower()
        if 'ffmpeg' in msg or 'avconv' in msg:
            raise RuntimeError(
                "ffmpeg is required for audio conversion. "
                "Install: sudo apt-get install ffmpeg"
            ) from e
        raise RuntimeError(f"Audio conversion failed (format={fmt}): {e}") from e


def wav_to_mp3(wav_bytes: bytes, bitrate: str = "64k") -> bytes:
    """Конвертировать WAV bytes в MP3 bytes."""
    from pydub import AudioSegment

    with io.BytesIO(wav_bytes) as buf:
        audio = AudioSegment.from_file(buf, format='wav')
    with io.BytesIO() as out:
        audio.export(out, format='mp3', bitrate=bitrate)
        return out.getvalue()


def normalize_audio_from_file(file_obj: IO[bytes], fmt: str = "wav") -> bytes:
    """Прочитать аудио из file-like объекта и вернуть WAV 16kHz моно 16-bit PCM.

    Args:
        file_obj: File-like объект (например, UploadFile.file / SpooledTemporaryFile).
        fmt: Формат входного аудио (pydub-совместимый, напр. 'wav', 'mp3', 'webm').

    Returns:
        Нормализованные байты WAV 16kHz моно 16-bit PCM.
    """
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(file_obj, format=fmt)
        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(TARGET_CHANNELS)

        with io.BytesIO() as out:
            audio.export(out, format='wav')
            return out.getvalue()

    except ImportError:
        raise RuntimeError("pydub is required. Install: pip install pydub")
    except Exception as e:
        msg = str(e).lower()
        if 'ffmpeg' in msg or 'avconv' in msg:
            raise RuntimeError(
                "ffmpeg is required for audio conversion. "
                "Install: sudo apt-get install ffmpeg"
            ) from e
        raise RuntimeError(f"Audio conversion failed (format={fmt}): {e}") from e
