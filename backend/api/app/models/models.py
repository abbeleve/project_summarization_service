from pydantic import BaseModel, Field
from typing import Optional, List
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