from pydantic import BaseModel
from typing import Optional, List
import uuid

class User(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    full_name: str
    role: str = "user" #УБРАТЬ ЗНАЧЕНИЕ ПО УМОЛЧАНИЮ, КОГДА В БД БУДУТ РОЛИ

class TokenData(BaseModel):
    username: str
    user_id: int
    role: str = "user" #УБРАТЬ ЗНАЧЕНИЕ ПО УМОЛЧАНИЮ, КОГДА В БД БУДУТ РОЛИ

class AudioUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_size: int
    status: str

class TranscriptionRequest(BaseModel):
    file_id: str
    language: Optional[str] = "ru"

class TranscriptionResponse(BaseModel):
    transcription_id: int
    file_id: str
    status: str
    segments: List[dict]

class SummarizationRequest(BaseModel):
    transcription_id: int
    summary_type: Optional[str] = "brief"  # brief, detailed, action_items

class SummarizationResponse(BaseModel):
    summary_id: int
    transcription_id: int
    summary_text: str
    status: str