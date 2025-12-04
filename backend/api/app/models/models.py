from pydantic import BaseModel
from typing import Optional, List
import uuid

class User(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    full_name: str
    role: str = "user" #УБРАТЬ ЗНАЧЕНИЕ ПО УМОЛЧАНИЮ, КОГДА В БД БУДУТ РОЛИ

class TokenData(BaseModel):
    username: str
    user_id: str
    role: str = "user" #УБРАТЬ ЗНАЧЕНИЕ ПО УМОЛЧАНИЮ, КОГДА В БД БУДУТ РОЛИ

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    full_name: str