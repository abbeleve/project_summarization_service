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
import httpx
import tempfile
import logging

from .models.models import User, Token, TokenData
from .database import get_db
from .database import init_db
from .database import DataBaseManager

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        user_id: int = payload.get("user_id")
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
        "user_id": user_info[0],
        "username": current_user.username,
        "full_name": f"{user_info[1]} {user_info[2]} {user_info[3] or ''}".strip(),
        "email": user_info[4]
    }


@app.post("/process")
async def process_audio(
    file: UploadFile = File(...),
    transcribe_model: Optional[str] = None,
    diarization_model: Optional[str] = None,
    diarize_lib: Optional[str] = None,
    transcribe_lib: Optional[str] = None,
    llm_model: Optional[str] = None,
    current_user: TokenData = Depends(get_current_active_user),
    db: DataBaseManager = Depends(get_db)
):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Подготовка данных для отправки
            files = {
                'file': (file.filename, open(tmp_file_path, 'rb'), file.content_type)
            }
            
            data = {
                'transcribe_model': transcribe_model or "v3_ctc",
                'diarization_model': diarization_model or "pyannote/speaker-diarization-community-1",
                'diarize_lib': diarize_lib or "pyannote",
                'transcribe_lib': transcribe_lib or "gigasm"
            }
            
            # Отправка запроса к внешнему сервису транскрибации
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    "http://audio-ml:8053/transcribe",
                    files=files,
                    data=data
                )
            
            if response.status_code != 200:
                try:
                    error_detail = response.json().get("detail", response.text)
                except:
                    error_detail = response.text
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Transcription service error: {error_detail}"
                )
            
            result = response.json()
            
            # Получаем транскрипцию
            original_text = result.get("text", "")
            clean_text = result.get("cleaned_text", original_text)
            
            # Вставляем транскрипцию в базу
            db.insert_transcripts(original_text, clean_text)
            
            # Получаем ID созданной транскрипции
            transcripts = db.select_transcripts()
            transcript_id = transcripts[-1][0] if transcripts else None
            
            # Сохраняем части транскрипции
            segments = result.get("segments", [])
            
            for segment in segments:
                speaker = segment.get("speaker", "UNKNOWN")
                text = segment.get("text", "")
                start = segment.get("start", 0.0)
                end = segment.get("end", 0.0)
                
                db.insert_parts_transcription(
                    employee_id=current_user.user_id,
                    transcript_id=transcript_id,
                    text=f"{speaker}: {text}",
                    start_time=int(start * 1000),
                    end_time=int(end * 1000)
                )
            
            summary = ""
            if clean_text:
                try:
                    # Подготавливаем данные для суммаризации
                    summarize_data = {
                        "text": clean_text,
                        "llm_model": llm_model or "openai/gpt-oss-20b",
                        "base_url": ""
                    }
                    
                    # Отправляем запрос на суммаризацию
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        summarize_response = await client.post(
                            "http://audio-ml:8053/summarize",
                            data=summarize_data
                        )
                    
                    if summarize_response.status_code == 200:
                        summary_result = summarize_response.json()
                        summary = summary_result.get("summary", "")
                    else:
                        print(f"Summarization service error: {summarize_response.status_code}")
                        summary = ""
                        
                except Exception as e:
                    print(f"Error during summarization: {str(e)}")
                    summary = ""
            
            # Сохраняем суммаризацию в базу
            if summary:
                db.insert_summaries(transcript_id, summary)
            
            # Формируем ответ
            return {
                "status": "success",
                "transcript_id": transcript_id,
                "original_text": original_text,
                "clean_text": clean_text,
                "segments": segments,
                "summary": summary,
                "speakers": result.get("speakers", []),
                "duration": result.get("duration", 0),
                "language": result.get("language", "ru"),
                "processing_time": result.get("processing_time", 0),
                "used_models": {
                    "transcribe_model": transcribe_model,
                    "diarization_model": diarization_model,
                    "transcribe_lib": transcribe_lib,
                    "diarize_lib": diarize_lib
                }
            }
            
        finally:
            # Удаляем временный файл
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Transcription service timeout. Try again with a smaller file or different model."
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Transcription service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Transcription error: {str(e)}"
        )


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
    """Инициализация базы данных при запуске приложения с повторными попытками"""
    max_retries = 5
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            init_db()
            logger.info("✅ Таблицы базы данных инициализированы успешно")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries}: "
                              f"Не удалось инициализировать БД: {e}. Повтор через {retry_delay} сек...")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ Не удалось инициализировать БД после {max_retries} попыток: {e}")
                # Не падаем, а продолжаем работу - БД может быть доступна позже

@app.get("/health")
async def health_check():
    """Проверка здоровья приложения"""
    try:
        # Пробуем подключиться к БД
        db = DataBaseManager(
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password'),
            host=os.getenv('DB_HOST', 'postgres'),
            port=os.getenv('DB_PORT', '5432'),
            dbname=os.getenv('DB_NAME', 'meeting_analyzer'),
            max_retries=1,
            retry_delay=1
        )
        db.execute_query("SELECT 1")
        db.disconnect_db()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        logger.warning(f"⚠️ База данных недоступна: {e}")
    
    return {
        "status": "healthy",
        "service": "meeting-analyzer-api",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)