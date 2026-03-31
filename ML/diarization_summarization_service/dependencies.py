"""
Dependency Injection для FastAPI приложения.
Централизованное управление зависимостями.
"""
from functools import lru_cache
from typing import Optional
from services.llm_client import LLMClient
from services.summarization import SummarizationService
from services.classification import ClassificationService
from services.qa import QAService
from core.diarization.pyannote import PyannoteDiarization
from core.transcription.gigaam import GigaamTranscription
from core.audio_converter import AudioConverter
from core.noise_suppression import NoiseSuppressionClient
from config import Settings, get_settings


# ===== Настройки =====

@lru_cache()
def get_settings_cached() -> Settings:
    """
    Кэшированные настройки приложения.
    Использует lru_cache для единого экземпляра.
    """
    return get_settings()


# ===== Singleton ML модели =====
# Создаются один раз при старте приложения и переиспользуются

_diarization_instance: Optional[PyannoteDiarization] = None
_transcription_instance: Optional[GigaamTranscription] = None
_audio_converter_instance: Optional[AudioConverter] = None


def get_diarization_singleton() -> PyannoteDiarization:
    """
    Singleton экземпляр диаризации.
    Создаётся один раз при первом вызове.
    """
    global _diarization_instance
    if _diarization_instance is None:
        settings = get_settings_cached()
        _diarization_instance = PyannoteDiarization(
            model_path=settings.pyannote_model_path,
            sample_rate=settings.sample_rate
        )
    return _diarization_instance


def get_transcription_singleton() -> GigaamTranscription:
    """
    Singleton экземпляр транскрибации.
    Создаётся один раз при первом вызове.
    """
    global _transcription_instance
    if _transcription_instance is None:
        settings = get_settings_cached()
        _transcription_instance = GigaamTranscription(
            sample_rate=settings.sample_rate,
            chunk_duration=settings.chunk_duration_sec
        )
    return _transcription_instance


def get_audio_converter_singleton() -> AudioConverter:
    """
    Singleton экземпляр аудио конвертера.
    """
    global _audio_converter_instance
    if _audio_converter_instance is None:
        settings = get_settings_cached()
        _audio_converter_instance = AudioConverter(sample_rate=settings.sample_rate)
    return _audio_converter_instance


# ===== Фабрики (для тестов или если нужны новые экземпляры) =====

def get_llm_client() -> LLMClient:
    """
    Фабрика LLM клиента.
    """
    settings = get_settings_cached()
    return LLMClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url
    )


# ===== Сервисы =====

def get_summarization_service() -> SummarizationService:
    """
    Фабрика сервиса суммаризации.
    """
    llm_client = get_llm_client()
    return SummarizationService(llm_client=llm_client)


def get_classification_service() -> ClassificationService:
    """
    Фабрика сервиса классификации.
    """
    llm_client = get_llm_client()
    return ClassificationService(llm_client=llm_client)


def get_qa_service() -> QAService:
    """
    Фабрика Q&A сервиса.
    """
    llm_client = get_llm_client()
    return QAService(llm_client=llm_client)


# ===== Core компоненты (фабрики для тестов) =====
# Для основного использования используйте singleton_* версии выше

def get_audio_converter_factory() -> AudioConverter:
    """
    Фабрика аудио конвертера (создаёт новый экземпляр).
    Используйте get_audio_converter_singleton() для переиспользования.
    """
    settings = get_settings_cached()
    return AudioConverter(sample_rate=settings.sample_rate)


def get_diarization_factory() -> PyannoteDiarization:
    """
    Фабрика диаризации (создаёт новый экземпляр).
    Используйте get_diarization_singleton() для переиспользования.
    """
    settings = get_settings_cached()
    return PyannoteDiarization(
        model_path=settings.pyannote_model_path,
        sample_rate=settings.sample_rate
    )


def get_transcription_factory() -> GigaamTranscription:
    """
    Фабрика транскрибации (создаёт новый экземпляр).
    Используйте get_transcription_singleton() для переиспользования.
    """
    settings = get_settings_cached()
    return GigaamTranscription(
        sample_rate=settings.sample_rate,
        chunk_duration=settings.chunk_duration_sec
    )


def get_noise_suppression_client() -> NoiseSuppressionClient:
    """
    Фабрика клиента шумоподавления.
    """
    settings = get_settings_cached()
    return NoiseSuppressionClient(
        service_url=settings.noise_suppression_url,
        timeout=settings.noise_suppression_timeout_sec
    )
