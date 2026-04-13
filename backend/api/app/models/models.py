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

class JoinMeetingRequest(BaseModel):
    """Запрос на немедленное подключение к совещанию."""
    meeting_url: str
    provider: str = Field(..., description="Платформа: google, microsoft, zoom")
    bot_name: Optional[str] = Field("Meeting Notetaker", description="Имя бота в совещании")


class ScheduleMeetingRequest(BaseModel):
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