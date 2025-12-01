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
from .database import get_db
from .database import init_db
from .database import DataBaseManager

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
ACCESS_TOKEN_EXPIRE_MINUTES = 30

#Для продакшена:
# SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# if not SECRET_KEY:
#     raise ValueError("JWT_SECRET_KEY environment variable is required!")

security = HTTPBearer()

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

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DataBaseManager = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")  # Добавляем user_id
        if username is None or user_id is None:
            raise credentials_exception
        token_data = TokenData(username=username, user_id=user_id)
    except jwt.PyJWTError:
        raise credentials_exception
    
    # Проверяем существование пользователя в БД
    user_data = db.select_staff_by_login(username)
    if not user_data:
        raise credentials_exception
    
    return token_data

async def get_current_active_user(current_user: TokenData = Depends(get_current_user)):
    return current_user

# пока разделения на роли в бд нет
def require_admin(current_user: TokenData = Depends(get_current_active_user)):
    return current_user

# Эндпоинты аутентификации
@app.post("/auth/login", response_model=Token)
async def login(user: User, db: DataBaseManager = Depends(get_db)):
    # Аутентификация через базу данных
    employee_id = db.authentication(user.username, user.password)
    
    if not employee_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль"
        )
    
    # Получаем данные пользователя для токена
    user_data = db.select_staff_by_id(employee_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Данные пользователя не найдены"
        )
    
    user_info = user_data[0]  # Первая запись
    full_name = f"{user_info[1]} {user_info[2]}"  # Фамилия + Имя
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username, 
            "user_id": employee_id,
            "full_name": full_name
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": employee_id,
        "full_name": full_name
    }

@app.get("/auth/me")
async def read_users_me(
    current_user: TokenData = Depends(get_current_active_user),
    db: DataBaseManager = Depends(get_db)
):
    user_data = db.select_staff_by_login(current_user.username)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    user_info = user_data[0]
    return {
        "user_id": user_info[0],  # ID
        "username": current_user.username,
        "full_name": f"{user_info[1]} {user_info[2]} {user_info[3] or ''}".strip(),  # ФИО
        "email": user_info[4]
    }

# Эндпоинты для пользователей
@app.post("/process")
async def process_audio(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_active_user),
    db: DataBaseManager = Depends(get_db)
):
    try:
        # Читаем файл
        file_content = await file.read()
        file_size = len(file_content)
        
        # Здесь будет логика обработки аудио
        # Пока используем заглушку
        
        # Сохраняем транскрипцию в базу данных
        original_text = "Оригинальный текст транскрипции..."
        clean_text = "Очищенный текст транскрипции..."
        
        # Вставляем транскрипцию
        db.insert_transcripts(original_text, clean_text)
        
        # Получаем ID созданной транскрипции (последняя вставленная запись)
        transcripts = db.select_transcripts()
        transcript_id = transcripts[-1][0] if transcripts else None
        
        # Сохраняем части транскрипции
        transcription_parts = [
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
        ]
        
        for part in transcription_parts:
            db.insert_parts_transcription(
                employee_id=current_user.user_id,
                transcript_id=transcript_id,
                text=part["text"],
                start_time=int(part["start"] * 1000),  # Конвертируем в миллисекунды
                end_time=int(part["end"] * 1000)
            )
        
        # Сохраняем суммаризацию
        summary_text = "Суммаризированный текст совещания: Обсудили основные вопросы проекта, приняли решение о следующих шагах и назначили ответственных за выполнение задач."
        db.insert_summaries(transcript_id, summary_text)
        
        result = {
            "status": "success",
            "filename": file.filename,
            "file_size": file_size,
            "processed_by": current_user.username,
            "user_id": current_user.user_id,
            "transcript_id": transcript_id,
            "summary": summary_text,
            "transcription": transcription_parts,
            "speakers_count": 2,
            "meeting_duration": "25.7 секунд"
        }
        
        return JSONResponse(content=result)
        
    except Exception as e:
        raise HTTPException(500, f"Processing error: {str(e)}")

@app.get("/transcripts")
async def get_user_transcripts(
    current_user: TokenData = Depends(get_current_active_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить все транскрипции пользователя"""
    try:
        # Получаем части транскрипций, созданные пользователем
        user_parts = db.select_parts_transcription_by_employee_id(current_user.user_id)
        
        # Группируем по transcript_id
        transcripts_map = {}
        for part in user_parts:
            transcript_id = part[2]  # TranscriptID
            if transcript_id not in transcripts_map:
                # Получаем основную информацию о транскрипции
                transcript_data = db.select_transcripts_by_id(transcript_id)
                if transcript_data:
                    transcripts_map[transcript_id] = {
                        "transcript_id": transcript_id,
                        "original_text": transcript_data[0][1],
                        "clean_text": transcript_data[0][2],
                        "parts": []
                    }
            
            transcripts_map[transcript_id]["parts"].append({
                "part_id": part[0],
                "text": part[3],
                "start_time": part[4],
                "end_time": part[5]
            })
        
        return list(transcripts_map.values())
        
    except Exception as e:
        raise HTTPException(500, f"Error fetching transcripts: {str(e)}")

@app.get("/transcripts/{transcript_id}")
async def get_transcript(
    transcript_id: int,
    current_user: TokenData = Depends(get_current_active_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить конкретную транскрипцию"""
    try:
        transcript_data = db.select_transcripts_by_id(transcript_id)
        if not transcript_data:
            raise HTTPException(404, "Транскрипция не найдена")
        
        parts = db.select_parts_transcription_by_transcript_id(transcript_id)
        summary_data = db.select_summaries_by_transcript_id(transcript_id)
        
        return {
            "transcript_id": transcript_id,
            "original_text": transcript_data[0][1],
            "clean_text": transcript_data[0][2],
            "parts": [
                {
                    "part_id": part[0],
                    "employee_id": part[1],
                    "text": part[3],
                    "start_time": part[4],
                    "end_time": part[5]
                } for part in parts
            ],
            "summary": summary_data[0][2] if summary_data else None
        }
        
    except Exception as e:
        raise HTTPException(500, f"Error fetching transcript: {str(e)}")

@app.get("/admin/users")
async def get_all_users(
    current_user: TokenData = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    try:
        users = db.select_staff()
        return [
            {
                "user_id": user[0],
                "surname": user[1],
                "name": user[2],
                "patronymic": user[3],
                "email": user[4],
                "login": user[5]
            }
            for user in users
        ]
    except Exception as e:
        raise HTTPException(500, f"Error fetching users: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Инициализация базы данных при запуске приложения"""
    try:
        init_db()
        print("✅ Database tables initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

@app.get("/health")
async def health_check(db: DataBaseManager = Depends(get_db)):
    try:
        db.execute_query("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy",
        "service": "meeting-analyzer-api",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)