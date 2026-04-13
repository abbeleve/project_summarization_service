from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid

class User(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = "user" #УБРАТЬ ЗНАЧЕНИЕ ПО УМОЛЧАНИЮ, КОГДА В БД БУДУТ РОЛИ

class LoginRequest(BaseModel):
    username: str = Field(..., description="Логин пользователя")
    password: str = Field(..., description="Пароль пользователя")

class RegisterRequest(BaseModel):
    username: str = Field(..., description="Логин пользователя")
    password: str = Field(..., description="Пароль пользователя")
    surname: str = Field(..., description="Фамилия")
    name: str = Field(..., description="Имя")
    patronymic: Optional[str] = Field(None, description="Отчество")
    email: str = Field(..., description="Email")

class TokenResponse(Token):
    refresh_token: Optional[str] = None
    user_id: str
    full_name: str


# === Meeting Bot Models ===

class MeetingModelSettings(BaseModel):
    """Настройки моделей для ML пайплайна."""
    transcribe_model: Optional[str] = Field("v3_ctc", description="Модель транскрибации")
    diarization_model: Optional[str] = Field("pyannote/speaker-diarization-community-1", description="Модель диаризации")
    diarize_lib: Optional[str] = Field("pyannote", description="Библиотека диаризации")
    transcribe_lib: Optional[str] = Field("gigaam", description="Библиотека транскрибации")
    llm_model: Optional[str] = Field("gemini-2.5-flash", description="Модель LLM для суммаризации")
    noise_suppression: Optional[bool] = Field(False, description="Шумоподавление")


class JoinMeetingRequest(MeetingModelSettings):
    """Запрос на немедленное подключение к совещанию."""
    meeting_url: str
    provider: str = Field(..., description="Платформа: google, microsoft, zoom")
    bot_name: Optional[str] = Field("Meeting Notetaker", description="Имя бота в совещании")


class ScheduleMeetingRequest(MeetingModelSettings):
    """Запрос на планирование совещания."""
    meeting_url: str
    provider: str = Field(..., description="Платформа: google, microsoft, zoom")
    scheduled_at: str = Field(..., description="Время начала в ISO 8601, например: 2026-04-13T15:00:00")
    bot_name: Optional[str] = Field("Meeting Notetaker", description="Имя бота в совещании")


class MeetingBotWebhookPayload(BaseModel):
    """Payload для webhook от meeting-bot (уведомление о завершении записи)."""
    recordingId: str
    meetingLink: str
    status: str = Field(..., description="completed, failed")
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None
    blobUrl: Optional[str] = None