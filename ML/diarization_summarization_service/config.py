"""
Конфигурация приложения через Pydantic Settings.
Все настройки централизованы и типизированы.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Set
import os


class Settings(BaseSettings):
    """
    Настройки приложения.
    Загружаются из переменных окружения или используют значения по умолчанию.
    """
    
    # ===== ML Модели =====
    pyannote_model_path: str = Field(
        default="/app/models/pyannote",
        description="Путь к модели диаризации pyannote"
    )
    whisper_model_path: str = Field(
        default="/app/models/whisper",
        description="Путь к модели Whisper"
    )

    # ===== LLM Настройки =====
    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", ""),
        description="API ключ для LLM (Gemini/OpenAI)"
    )
    openai_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        description="Базовый URL для LLM API (Gemini по умолчанию)"
    )
    allowed_llm_models: Set[str] = Field(
        default={"deepseek/deepseek-v4-flash", "gemini-2.5-flash", "gemini-2.5-pro"},
        description="Разрешённые LLM модели"
    )

    # ===== Аудио параметры =====
    sample_rate: int = Field(
        default=16000,
        description="Частота дискретизации аудио (Hz)"
    )
    max_audio_size_mb: int = Field(
        default=200,
        description="Максимальный размер аудиофайла (MB)"
    )
    chunk_duration_sec: int = Field(
        default=23,
        description="Длительность чанка для транскрибации (сек)"
    )
    min_segment_duration_sec: float = Field(
        default=0.5,
        description="Минимальная длительность сегмента для диаризации (сек)"
    )

    # ===== Параметры диаризации Pyannote =====
    # Порог VAD/сегментации: ниже 0.5 = больше речи, выше = строже.
    # Для шумных записей повышать до 0.6–0.7, для чистых можно 0.4–0.5.
    pyannote_segmentation_threshold: float = Field(
        default=0.5,
        description="Порог VAD/сегментации Pyannote (0-1)"
    )
    # Минимальная длительность речевого сегмента внутри VAD (отсекает короткие всплески)
    pyannote_min_duration_on: float = Field(
        default=0.1,
        description="Минимальная длительность speech-сегмента VAD (сек)"
    )
    # Минимальная пауза — если тишина короче, соседние speech-отрезки сливаются
    pyannote_min_duration_off: float = Field(
        default=0.1,
        description="Минимальная длительность паузы для разрыва сегментов VAD (сек)"
    )
    # Порог кластеризации: ниже → меньше спикеров (склеивает),
    # выше → больше спикеров (дробит). Для встреч 2–5 чел: пробовать 0.5–0.7.
    pyannote_clustering_threshold: float = Field(
        default=0.5,
        description="Порог кластеризации спикеров Pyannote (0-1)"
    )
    # Явное ограничение количества спикеров (None = автоопределение)
    pyannote_min_speakers: int | None = Field(
        default=None,
        description="Минимальное число спикеров (None = авто)"
    )
    pyannote_max_speakers: int | None = Field(
        default=None,
        description="Максимальное число спикеров (None = авто)"
    )
    # Overlap-aware диаризация (pyannote 3.1+)
    pyannote_overlap: bool = Field(
        default=False,
        description="Использовать overlap-aware сегментацию"
    )
    # RMS-нормализация перед диаризацией — стабилизирует VAD
    pyannote_normalize_audio: bool = Field(
        default=False,
        description="Нормализация громкости перед диаризацией"
    )
    # Размер окна медианного фильтра для сглаживания переключений спикеров
    # 0 = отключено, 3–5 обычно достаточно
    pyannote_median_filter_window: int = Field(
        default=0,
        description="Размер окна медианного фильтра спикеров (0 = откл)"
    )
    
    # ===== Шумоподавление =====
    noise_suppression_url: str = Field(
        default="http://denoiser:8052/denoise",
        description="URL сервиса шумоподавления"
    )
    noise_suppression_timeout_sec: int = Field(
        default=300,
        description="Таймаут запроса шумоподавления (сек)"
    )
    
    # ===== LLM параметры по умолчанию =====
    default_llm_model: str = Field(
        default="deepseek/deepseek-v4-flash",
        description="Модель LLM по умолчанию"
    )
    llm_temperature: float = Field(
        default=0.01,
        description="Температура для LLM"
    )
    llm_max_tokens: int = Field(
        default=3000,
        description="Максимум токенов для LLM"
    )
    llm_timeout_sec: int = Field(
        default=180,
        description="Таймаут запроса к LLM (сек)"
    )
    
    # ===== Логирование =====
    log_level: str = Field(
        default="INFO",
        description="Уровень логирования"
    )
    
    # ===== GigaAM ONNX сервис =====
    gigaam_onnx_service_url: str = Field(
        default="http://onnx-gigaam:8056/transcribe",
        description="URL сервиса транскрибации GigaAM ONNX"
    )
    gigaam_onnx_timeout_sec: int = Field(
        default=1800,
        description="Таймаут запроса к GigaAM ONNX сервису (сек) — 30 мин для длинных аудио"
    )

    # ===== Whisper сервис =====
    whisper_service_url: str = Field(
        default="http://audio-ml-whisper:8054/transcribe",
        description="URL сервиса транскрибации Whisper"
    )
    whisper_timeout_sec: int = Field(
        default=1800,
        description="Таймаут запроса к Whisper сервису (сек) — 30 мин для длинных аудио"
    )

    # ===== Full-audio transcription (WhisperX-style) =====
    gigaam_onnx_full_url: str = Field(
        default="http://onnx-gigaam:8056/transcribe_full",
        description="URL полной транскрибации GigaAM ONNX (весь файл за 1 проход)"
    )
    whisper_full_url: str = Field(
        default="http://audio-ml-whisper:8054/transcribe_full",
        description="URL полной транскрибации Whisper (весь файл за 1 проход)"
    )
    forced_aligner_url: str = Field(
        default="http://forced-aligner:8057/align",
        description="URL сервиса forced alignment"
    )
    forced_aligner_timeout_sec: int = Field(
        default=1800,
        description="Таймаут запроса к forced-aligner (сек)"
    )
    gigaam_align_url: str = Field(
        default="http://onnx-gigaam:8056/align_words",
        description="URL word-level alignment от GigaAM"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Глобальный инстанс настроек
settings = Settings()


def get_settings() -> Settings:
    """Фабричная функция для получения настроек (для DI)."""
    return settings
