"""
Pydantic схемы для суммаризации и Q&A.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ===== Задачи (action items) =====

class TaskItemModel(BaseModel):
    """Задача / action item, извлечённая из текста совещания (для CRM)."""
    description: str = Field(..., description="Описание задачи — что нужно сделать")
    assignee: str = Field(default="", description="Ответственный (если указан)")
    deadline: str = Field(default="", description="Срок / дедлайн (если указан)")


# ===== Схемы для суммаризации =====

class SummarizeRequest(BaseModel):
    """Запрос на суммаризацию."""
    input_text: str = Field(..., description="Текст для суммаризации", min_length=1)
    llm_model: str = Field(default="deepseek/deepseek-v4-flash", description="Модель LLM")


class SummarizeResponse(BaseModel):
    """Ответ суммаризации."""
    title: str = Field(..., description="Заголовок совещания")
    summary: str = Field(..., description="Краткое содержание")
    key_points: List[str] = Field(..., description="Ключевые пункты")
    tasks: List[TaskItemModel] = Field(default_factory=list, description="Задачи (action items) для CRM")
    meeting_type: Optional[str] = Field(None, description="Тип совещания")


# ===== Схемы для классификации =====

class ClassifyRequest(BaseModel):
    """Запрос на классификацию типа совещания."""
    input_text: str = Field(..., description="Текст совещания", min_length=1)
    llm_model: str = Field(default="deepseek/deepseek-v4-flash", description="Модель LLM")


class ClassifyResponse(BaseModel):
    """Ответ классификации."""
    meeting_type: str = Field(..., description="Тип совещания")


# ===== Схемы для Q&A =====

class AskRequest(BaseModel):
    """Запрос вопроса по транскрипции."""
    text: str = Field(..., description="Текст совещания", min_length=1)
    question: str = Field(..., description="Вопрос пользователя", min_length=1)
    llm_model: str = Field(default="deepseek/deepseek-v4-flash", description="Модель LLM")


class AskResponse(BaseModel):
    """Ответ на вопрос."""
    answer: str = Field(..., description="Ответ на вопрос")


# ===== Схемы для LLM Pipeline =====

class LLMPipelineRequest(BaseModel):
    """Запрос на полный пайплайн LLM."""
    input_text: str = Field(..., description="Текст совещания", min_length=1)
    llm_model: str = Field(default="deepseek/deepseek-v4-flash", description="Модель LLM")
    summarization_usage: bool = Field(default=True, description="Использовать суммаризацию")
    classification_usage: bool = Field(default=True, description="Использовать классификацию")


class LLMPipelineResponse(BaseModel):
    """Ответ полного пайплайна LLM."""
    summary: Dict[str, Any] = Field(..., description="Результат суммаризации")
    meeting_type: Optional[str] = Field(None, description="Тип совещания")
