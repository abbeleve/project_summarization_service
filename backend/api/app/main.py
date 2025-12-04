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
import time
import os
import httpx
import tempfile
import logging
from uuid import UUID, uuid4

from .models.models import User, Token, TokenData, LoginRequest, TokenResponse
from .gen_fake_data import gen_fake_data
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

# Функция для получения БД
def get_db():
    """Зависимость для получения экземпляра БД"""
    db = DataBaseManager()
    try:
        yield db
    finally:
        # SQLAlchemy сам управляет соединениями через сессии
        pass

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
        user_id: str = payload.get("user_id")
        if username is None or user_id is None:
            raise credentials_exception

        token_data = TokenData(username=username, user_id=user_id)
    except jwt.PyJWTError:
        raise credentials_exception
    
    # Проверяем существование пользователя в БД
    users = db.select_staff_by_various_parameters(login=username)
    if not users or len(users) == 0:
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
    
    full_name = f"{user_data['surname']} {user_data['name']}"
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username, 
            "user_id": str(employee_id),
            "full_name": full_name
        },
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=str(employee_id),  # UUID как строка
        full_name=full_name
    )

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
                'transcribe_lib': transcribe_lib or "gigaam"
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
            transcript_id = db.insert_transcripts(original_text, clean_text)
            
            if not transcript_id:
                raise HTTPException(500, "Failed to save transcript to database")
            
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
            if segments:
                try:
                    # Подготавливаем данные для суммаризации
                    summarize_data = {
                        "text": segments,
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

            print(db.select_transcripts_by_id("521890b8-b81f-464f-8c2d-e94dfe2f7e25"))

            speakers = []
            for segment in segments:
                speaker = segment.get("speaker", "UNKNOWN")
                if speaker not in speakers:
                    speakers.append(speaker)
            
            duration = 0.0
            for segment in segments:
                end_time = segment.get("end", 0.0)
                if end_time > duration:
                    duration = end_time

            parts = db.select_parts_transcription_by_transcript_id(transcript_id)
        
            # Формируем ответ
            return {
                "status": "success",
                "transcript_id": str(transcript_id),
                "original_text": original_text,
                "clean_text": clean_text,
                "segments": segments,
                "summary": summary,
                "speakers": speakers,
                "duration": duration,
                "parts": parts,
                "used_models": {
                    "transcribe_model": transcribe_model or "v3_ctc",
                    "diarization_model": diarization_model or "pyannote/speaker-diarization-community-1",
                    "transcribe_lib": transcribe_lib or "gigaam",
                    "diarize_lib": diarize_lib or "pyannote"
                }
            }
            
        finally:
            # Закрываем файл и удаляем временный файл
            if os.path.exists(tmp_file_path):
                try:
                    if 'files' in locals() and files.get('file'):
                        files['file'][1].close()
                except:
                    pass
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
            transcript_id_str = part['transcript_id']
            
            if transcript_id_str not in transcripts_map:
                # Получаем основную информацию о транскрипции
                try:
                    transcript_uuid = UUID(transcript_id_str)
                except ValueError:
                    continue
                    
                transcript_data = db.select_transcripts_by_id(transcript_uuid)
                if not transcript_data:
                    continue
                    
                # Получаем суммаризацию
                summary_data = db.select_summaries_by_transcript_id(transcript_uuid)
                
                transcripts_map[transcript_id_str] = {
                    "transcript_id": transcript_id_str,
                    "original_text": transcript_data.get('original_text', ''),
                    "clean_text": transcript_data.get('clean_text', ''),
                    "summary": summary_data.get('text') if summary_data else None,
                    "parts": []  # Инициализируем пустой список
                }
            
            # Добавляем часть в список
            transcripts_map[transcript_id_str]["parts"].append(part)
        
        # Преобразуем в список
        return list(transcripts_map.values())
        
    except Exception as e:
        logger.error(f"Error fetching user transcripts: {str(e)}")
        raise HTTPException(500, f"Error fetching transcripts: {str(e)}")

@app.get("/transcripts/{transcript_id}")
async def get_transcript(
    transcript_id: str,
    current_user: TokenData = Depends(get_current_active_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить конкретную транскрипцию"""
    try:

        try:
            transcript_uuid = UUID(transcript_id)
        except ValueError:
            raise HTTPException(400, "Некорректный формат ID транскрипции")
        
        transcript_data = db.select_transcripts_by_id(transcript_uuid)

        if not transcript_data:
            raise HTTPException(404, "Транскрипция не найдена")
        
        parts = db.select_parts_transcription_by_transcript_id(transcript_uuid)
        
        summary_data = db.select_summaries_by_transcript_id(transcript_uuid)
        
        return {
            "transcript_id": transcript_id,
            "original_text": transcript_data.get('original_text', ''),
            "clean_text": transcript_data.get('clean_text', ''),
            "parts": parts,
            "summary": summary_data.get('text') if summary_data else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching transcript: {str(e)}")
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
    max_retries = 10
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Попытка инициализации БД {attempt + 1}/{max_retries}...")
            db = DataBaseManager()
            
            # Создаем тестового пользователя, если нет пользователей
            users = db.select_staff()
            print(f"📊 Найдено пользователей в БД: {len(users)}")
            
            if not users:
                print("👤 Создаем тестового пользователя...")
                try:
                    db.insert_staff(
                        surname="Иванов",
                        name="Иван",
                        patronymic="Иванович",
                        email="test@example.com",
                        login="test",
                        password="test"
                    )
                    print("✅ Создан тестовый пользователь: test/test")
                    
                    # Генерируем тестовые данные только если БД была пустой
                    try:
                        gen_fake_data(db)
                        print("✅ Тестовые данные сгенерированы")
                    except Exception as e:
                        print(f"⚠️ Не удалось сгенерировать тестовые данные: {e}")
                        
                except Exception as e:
                    # Ошибка уникальности - пользователь уже существует
                    if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                        print("ℹ️ Тестовый пользователь уже существует")
                    else:
                        print(f"⚠️ Ошибка при создании пользователя: {e}")
            else:
                print("ℹ️ В базе уже есть пользователи, пропускаем создание тестовых")

            print("✅ База данных инициализирована успешно")
            
            return
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Попытка {attempt + 1}/{max_retries}: "
                      f"Не удалось инициализировать БД: {e}. Повтор через {retry_delay} сек...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Не удалось инициализировать БД после {max_retries} попыток: {e}")
                # Не падаем, а продолжаем работу - БД может быть доступна позже

@app.get("/health")
async def health_check():
    """Проверка здоровья приложения"""
    try:
        db = DataBaseManager()
        users = db.select_staff()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        logger.warning(f"⚠️ База данных недоступна: {e}")
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "meeting-analyzer-api",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)