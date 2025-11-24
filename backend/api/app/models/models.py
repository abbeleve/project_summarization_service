from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class User(BaseModel):
    username: str
    password: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    username: str
    role: str