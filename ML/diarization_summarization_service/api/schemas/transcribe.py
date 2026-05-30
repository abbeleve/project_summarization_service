"""
Pydantic схемы для API запросов и ответов.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===== Схемы для транскрибации =====

class TranscribeRequest(BaseModel):
    """Запрос на транскрибацию."""
    transcribe_lib: str = Field(default="gigaam", description="Библиотека транскрибации")
    transcribe_model: str = Field(default="v3_ctc", description="Модель транскрибации")
    diarize_lib: str = Field(default="pyannote", description="Библиотека диаризации")
    diarization_model: str = Field(
        default="pyannote/speaker-diarization-community-1",
        description="Модель диаризации"
    )
    noise_suppression: bool = Field(default=False, description="Использовать шумоподавление")


class TranscribeSegment(BaseModel):
    """Сегмент транскрипции."""
    speaker: str = Field(..., description="Идентификатор спикера")
    start: float = Field(..., description="Время начала (сек)")
    stop: float = Field(..., description="Время окончания (сек)")
    text: str = Field(default="", description="Текст сегмента")


class TranscribeResponse(BaseModel):
    """Ответ транскрибации."""
    transcript: List[TranscribeSegment] = Field(..., description="Список сегментов")
    duration: float = Field(..., description="Длительность аудио (сек)")
    speakers_count: int = Field(..., description="Количество спикеров")


# ===== Схемы для суммаризации =====

class SummarizeRequest(BaseModel):
    """Запрос на суммаризацию."""
    input_text: str = Field(..., description="Текст для суммаризации")
    llm_model: str = Field(default="deepseek/deepseek-v4-flash", description="Модель LLM")
    include_title: bool = Field(default=True, description="Включить заголовок")
    include_key_points: bool = Field(default=True, description="Включить ключевые пункты")


class SummarizeResponse(BaseModel):
    """Ответ суммаризации."""
    title: Optional[str] = Field(None, description="Заголовок совещания")
    summary: str = Field(..., description="Краткое содержание")
    key_points: Optional[List[str]] = Field(None, description="Ключевые пункты")
    meeting_type: Optional[str] = Field(None, description="Тип совещания")


# ===== Схемы для классификации =====

class ClassifyRequest(BaseModel):
    """Запрос на классификацию типа совещания."""
    input_text: str = Field(..., description="Текст совещания")
    llm_model: str = Field(default="deepseek/deepseek-v4-flash", description="Модель LLM")
    use_fallback: bool = Field(default=True, description="Использовать fallback")


class ClassifyResponse(BaseModel):
    """Ответ классификации."""
    meeting_type: str = Field(..., description="Тип совещания")
    confidence: Optional[float] = Field(None, description="Уверенность классификации")
    method: Optional[str] = Field(None, description="Метод классификации (llm/fallback)")


# ===== Схемы для Q&A =====

class AskRequest(BaseModel):
    """Запрос вопроса по транскрипции."""
    text: str = Field(..., description="Текст совещания")
    question: str = Field(..., description="Вопрос пользователя")
    llm_model: str = Field(default="deepseek/deepseek-v4-flash", description="Модель LLM")
    include_context: bool = Field(default=False, description="Включить контекст")


class AskResponse(BaseModel):
    """Ответ на вопрос."""
    answer: str = Field(..., description="Ответ на вопрос")
    question: str = Field(..., description="Исходный вопрос")
    model: str = Field(..., description="Использованная модель")
    context_length: Optional[int] = Field(None, description="Длина контекста")


# ===== Схемы для LLM Pipeline =====

class LLMPipelineRequest(BaseModel):
    """Запрос на полный пайплайн LLM."""
    input_text: str = Field(..., description="Текст совещания")
    llm_model: str = Field(default="deepseek/deepseek-v4-flash", description="Модель LLM")
    summarization_usage: bool = Field(default=True, description="Использовать суммаризацию")
    classification_usage: bool = Field(default=True, description="Использовать классификацию")


class LLMPipelineResponse(BaseModel):
    """Ответ полного пайплайна LLM."""
    summary: Optional[Dict[str, Any]] = Field(None, description="Результат суммаризации")
    meeting_type: Optional[str] = Field(None, description="Тип совещания")


# ===== Общие схемы =====

class HealthResponse(BaseModel):
    """Ответ health check."""
    status: str = Field(..., description="Статус сервиса")
    version: str = Field(..., description="Версия сервиса")


class ErrorResponse(BaseModel):
    """Ответ с ошибкой."""
    detail: str = Field(..., description="Описание ошибки")
    status_code: Optional[int] = Field(None, description="Код ошибки")
