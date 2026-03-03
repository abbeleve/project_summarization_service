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


# ===== LLM Клиент =====

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


# ===== Core компоненты =====

def get_audio_converter() -> AudioConverter:
    """
    Фабрика аудио конвертера.
    """
    settings = get_settings_cached()
    return AudioConverter(sample_rate=settings.sample_rate)


def get_diarization() -> PyannoteDiarization:
    """
    Фабрика диаризации.
    """
    settings = get_settings_cached()
    return PyannoteDiarization(
        model_path=settings.pyannote_model_path,
        sample_rate=settings.sample_rate
    )


def get_transcription() -> GigaamTranscription:
    """
    Фабрика транскрибации.
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
