from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict
import jwt
from datetime import datetime, timedelta
import secrets
import json
import os
from .models.models import User, Token, TokenData

app = FastAPI(title="Meeting Analyzer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://frontend:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация
SECRET_KEY = secrets.token_urlsafe(32)
print(f"Dev SECRET_KEY: {SECRET_KEY}")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 5

#Для продакшена:
# SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# if not SECRET_KEY:
#     raise ValueError("JWT_SECRET_KEY environment variable is required!")

security = HTTPBearer()

# Заглушка базы данных пользователей
users_db = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "full_name": "Администратор Системы"
    },
    "user": {
        "password": "user123", 
        "role": "user",
        "full_name": "Обычный Пользователь"
    }
}

# Функции для работы с JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except jwt.PyJWTError:
        raise credentials_exception
    
    if username not in users_db:
        raise credentials_exception
    
    return token_data

async def get_current_active_user(current_user: TokenData = Depends(get_current_user)):
    return current_user

def require_admin(current_user: TokenData = Depends(get_current_active_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения операции"
        )
    return current_user

# Эндпоинты аутентификации
@app.post("/auth/login", response_model=Token)
async def login(user: User):
    if user.username not in users_db or users_db[user.username]["password"] != user.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": users_db[user.username]["role"]},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": users_db[user.username]["role"]
    }

@app.get("/auth/me")
async def read_users_me(current_user: TokenData = Depends(get_current_active_user)):
    return {
        "username": current_user.username,
        "role": current_user.role,
        "full_name": users_db[current_user.username]["full_name"]
    }

# Эндпоинты для пользователей
@app.post("/process")
async def process_audio(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_active_user)
):
    try:
        file_size = len(await file.read())
        
        result = {
            "status": "success",
            "filename": file.filename,
            "file_size": file_size,
            "processed_by": current_user.username,
            "user_role": current_user.role,
            "summary": "Суммаризированный текст совещания: Обсудили основные вопросы проекта, приняли решение о следующих шагах и назначили ответственных за выполнение задач.",
            "transcription": [
                {
                    "speaker": "SPEAKER_01",
                    "start": 0.0,
                    "end": 5.2,
                    "text": "Добрый день, коллеги. Давайте начнем наше совещание."
                },
                {
                    "speaker": "SPEAKER_02", 
                    "start": 5.3,
                    "end": 12.1,
                    "text": "Согласен. Первый вопрос по текущему статусу проекта."
                }
            ],
            "speakers_count": 2,
            "meeting_duration": "25.7 секунд"
        }
        
        return JSONResponse(content=result)
        
    except Exception as e:
        raise HTTPException(500, f"Processing error: {str(e)}")

@app.get("/admin/users")
async def get_all_users(current_user: TokenData = Depends(require_admin)):
    users_list = []
    for username, user_data in users_db.items():
        users_list.append({
            "username": username,
            "role": user_data["role"],
            "full_name": user_data["full_name"]
        })
    return users_list

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "meeting-analyzer-api",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)