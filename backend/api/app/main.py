from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status, Request, Form, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import io
import time
import os
import json
import httpx
import tempfile
import logging
from uuid import UUID, uuid4
from datetime import timedelta, datetime
import json

from alembic.config import Config
from alembic import command


from .models.models import (
    User, Token, TokenData, LoginRequest, TokenResponse, RegisterRequest,
    JoinMeetingRequest, ScheduleMeetingRequest, MeetingBotWebhookPayload,
    AdminCreateUserRequest, AdminUpdateRoleRequest
)
from .db_service.gen_fake_data import gen_fake_data
from .db_service.database import DataBaseManager
from .db_service.minio_client import MinioClient
from .auth_service.jwt import jwt_service
from .auth_service.middleware import AuthMiddleware
from .voice.router import router as voice_router
from .crm.router import router as crm_router
from .audio_utils import normalize_audio, guess_format

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Meeting Analyzer API", version="1.0.0")

# Создаем middleware список
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_middleware = AuthMiddleware(jwt_service)

@app.middleware("http")
async def auth_middleware_wrapper(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    return await auth_middleware(request, call_next)

# Include routers
app.include_router(voice_router)
app.include_router(crm_router)

# Функция для получения БД
def get_db():
    """Зависимость для получения экземпляра БД"""
    db = DataBaseManager()
    try:
        yield db
    finally:
        pass

# Зависимость для получения MinIO клиента
def get_minio():
    """Зависимость для получения экземпляра MinIO клиента"""
    client = MinioClient()
    try:
        yield client
    finally:
        pass

# Зависимость для получения текущего пользователя из request.state
async def get_current_user(request: Request) -> Dict:
    """Получить текущего пользователя из request.state"""
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    user = request.state.user
    if not user or not user.get("user_id"):
        logger.error(f"Invalid user in request.state: {user}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user data in token"
        )
    return user

# Для обратной совместимости с некоторыми эндпоинтами:
async def get_current_active_user(current_user: Dict = Depends(get_current_user)):
    return current_user

def require_admin(current_user: Dict = Depends(get_current_user)):
    """Проверка, что пользователь является администратором."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    return current_user

# Эндпоинты аутентификации
@app.post("/auth/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: DataBaseManager = Depends(get_db)
):
    """Аутентификация пользователя"""
    try:
        # Аутентификация через базу данных
        employee_id = db.authentication(login_data.username, login_data.password)
        
        if not employee_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль"
            )
        
        # Получаем данные пользователя
        user_data = db.select_staff_by_id(employee_id)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Данные пользователя не найдены"
            )
        
        full_name = f"{user_data['surname']} {user_data['name']}"
        user_role = user_data.get('role', 'user')

        # Создаем access token
        access_token = jwt_service.create_access_token(
            data={
                "sub": login_data.username,
                "user_id": str(employee_id),
                "full_name": full_name,
                "role": user_role
            }
        )

        # Создаем refresh token (опционально)
        refresh_token = jwt_service.create_refresh_token(
            data={
                "sub": login_data.username,
                "user_id": str(employee_id),
                "role": user_role
            }
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user_id=str(employee_id),
            full_name=full_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post("/auth/register", response_model=TokenResponse)
async def register(
    register_data: RegisterRequest,
    db: DataBaseManager = Depends(get_db)
):
    """Регистрация нового пользователя"""
    try:
        # Проверяем существует ли уже пользователь с таким логином
        existing_users = db.select_staff()
        if any(user['login'] == register_data.username for user in existing_users):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким именем уже существует"
            )

        # Проверяем email
        if any(user['email'] == register_data.email for user in existing_users):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )

        # Создаем нового пользователя
        employee_id = db.insert_staff(
            surname=register_data.surname,
            name=register_data.name,
            patronymic=register_data.patronymic,
            email=register_data.email,
            login=register_data.username,
            password=register_data.password
        )

        if not employee_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при создании пользователя"
            )

        # Создаем access token
        access_token = jwt_service.create_access_token(
            data={
                "sub": register_data.username,
                "user_id": str(employee_id),
                "full_name": f"{register_data.surname} {register_data.name}",
                "role": "user"
            }
        )

        # Создаем refresh token
        refresh_token = jwt_service.create_refresh_token(
            data={
                "sub": register_data.username,
                "user_id": str(employee_id),
                "role": "user"
            }
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user_id=str(employee_id),
            full_name=f"{register_data.surname} {register_data.name}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post("/auth/refresh")
async def refresh_token(
    refresh_token_data: Dict[str, str]
):
    """Обновить access token с помощью refresh token"""
    try:
        refresh_token = refresh_token_data.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token is required"
            )
        
        # Проверяем refresh token
        payload = jwt_service.verify_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        # Создаем новый access token
        access_token = jwt_service.create_access_token(
            data={
                "sub": payload.get("sub"),
                "user_id": payload.get("user_id"),
                "full_name": payload.get("full_name", ""),
                "role": payload.get("role", "user")
            }
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Refresh token error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get("/auth/me")
async def read_users_me(
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить информацию о текущем пользователе"""
    try:
        user_data = db.select_staff_by_login(current_user["username"])
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        user_info = user_data[0]
        return {
            "user_id": user_info[0],
            "username": current_user["username"],
            "full_name": f"{user_info[1]} {user_info[2]} {user_info[3] or ''}".strip(),
            "email": user_info[4]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ----- Users / Profile Endpoints -----

class UpdateProfileRequest(BaseModel):
    surname: Optional[str] = None
    name: Optional[str] = None
    patronymic: Optional[str] = None
    email: Optional[str] = None


@app.get("/users/me")
async def get_current_user_profile(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db),
):
    """Получить полный профиль текущего пользователя."""
    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["user_id"])
    user_data = db.select_staff_by_id(user_id)

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    # Если есть аватарка — возвращаем ссылку на публичный эндпоинт
    avatar_url = None
    if user_data.get("avatar_key"):
        avatar_url = f"{request.base_url}users/me/avatar?user_id={current_user['user_id']}"

    return {
        "user_id": user_data["id"],
        "username": user_data["login"],
        "surname": user_data["surname"],
        "name": user_data["name"],
        "patronymic": user_data.get("patronymic", ""),
        "full_name": f"{user_data['surname']} {user_data['name']}".strip(),
        "email": user_data["email"],
        "avatar_url": avatar_url,
    }


@app.put("/users/me")
async def update_current_user_profile(
    request: Request,
    profile_data: UpdateProfileRequest,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db),
):
    """Обновить профиль текущего пользователя."""
    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["user_id"])

    update_kwargs = {}
    if profile_data.surname is not None:
        update_kwargs["surname"] = profile_data.surname
    if profile_data.name is not None:
        update_kwargs["name"] = profile_data.name
    if profile_data.patronymic is not None:
        update_kwargs["patronymic"] = profile_data.patronymic
    if profile_data.email is not None:
        update_kwargs["email"] = profile_data.email

    if not update_kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    success = db.update_staff(user_id, **update_kwargs)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update profile")

    user_data = db.select_staff_by_id(user_id)
    avatar_url = f"{request.base_url}users/me/avatar?user_id={current_user['user_id']}" if user_data.get("avatar_key") else None

    return {
        "user_id": user_data["id"],
        "username": user_data["login"],
        "surname": user_data["surname"],
        "name": user_data["name"],
        "patronymic": user_data.get("patronymic", ""),
        "full_name": f"{user_data['surname']} {user_data['name']}".strip(),
        "email": user_data["email"],
        "avatar_url": avatar_url,
    }


# ----- Avatar Endpoints -----

MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@app.post("/users/me/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db),
    minio: MinioClient = Depends(get_minio),
):
    """Загрузить или заменить аватарку."""
    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["user_id"])

    # Валидация типа файла
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат. Разрешены: {', '.join(ALLOWED_AVATAR_TYPES)}"
        )

    # Валидация размера
    data = await file.read()
    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум 5 МБ."
        )

    # Загружаем в MinIO
    avatar_key = minio.upload_avatar(user_id, data, file.content_type)

    # Сохраняем ключ в БД
    db.update_staff(user_id, avatar_key=avatar_key)

    return {
        "avatar_url": f"{request.base_url}users/me/avatar?user_id={current_user['user_id']}",
        "message": "Аватарка загружена"
    }


@app.delete("/users/me/avatar")
async def delete_avatar(
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db),
    minio: MinioClient = Depends(get_minio),
):
    """Удалить аватарку."""
    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["user_id"])

    # Удаляем из MinIO
    minio.delete_avatar(user_id)

    # Очищаем ключ в БД
    db.update_staff(user_id, avatar_key=None)

    return {"message": "Аватарка удалена"}


@app.get("/users/me/avatar")
async def get_avatar(
    user_id: str = Query(..., description="UUID пользователя"),
    minio: MinioClient = Depends(get_minio),
):
    """Получить файл аватарки пользователя.

    Публичный эндпоинт (без JWT) — для прямого использования в <img>.
    """
    from uuid import UUID as UUIDType
    uid = UUIDType(user_id)

    result = minio.get_avatar_data(uid)
    if not result:
        raise HTTPException(status_code=404, detail="Аватарка не найдена")

    data, content_type = result
    return Response(content=data, media_type=content_type)


@app.post("/process")
async def process_audio(
    file: UploadFile = File(...),
    transcribe_model: Optional[str] = Form(None),
    diarization_model: Optional[str] = Form(None),
    diarize_lib: Optional[str] = Form(None),
    transcribe_lib: Optional[str] = Form(None),
    llm_model: Optional[str] = Form(None),
    noise_sup_bool: str = Form("false"),
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db),
    minio: MinioClient = Depends(get_minio)
):
    """
    Отправляет аудио на обработку в фоновом режиме (Celery).
    Сохраняет аудиофайл в MinIO для последующего воспроизведения.
    Возвращает task_id для отслеживания статуса.
    """
    from app.tasks.transcribe import transcribe_and_summarize_task

    print(f"llm_model: {llm_model}")
    print(f"transcribe_model: {transcribe_model}")

    try:
        task_id_for_key = str(uuid4())
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        original_filename = file.filename or f"audio_{task_id_for_key[:8]}.webm"
        base = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename

        # === Шаг 1: MP3 для плеера на фронтенде ===
        fmt = guess_format(file_bytes)
        if fmt == 'mp3':
            mp3_bytes = file_bytes  # уже MP3 — без перекодировки
            logger.debug("MP3 original — сохранён как есть")
        else:
            # Конвертируем в MP3 16kHz через pydub
            from pydub import AudioSegment
            with io.BytesIO(file_bytes) as buf:
                audio = AudioSegment.from_file(buf, format=fmt or 'webm')
            audio = audio.set_frame_rate(16000).set_channels(1)
            with io.BytesIO() as out:
                audio.export(out, format='mp3', bitrate='64k')
                mp3_bytes = out.getvalue()
            del audio  # освободить RAM

        mp3_key = f"uploads/{current_user['user_id']}/{task_id_for_key}/{base}.mp3"
        minio.upload_audio(mp3_key, mp3_bytes, content_type="audio/mpeg")
        recording_url = minio.get_audio_public_url(mp3_key)
        del mp3_bytes  # освободить RAM

        # === Шаг 2: WAV 16kHz для ML-пайплайна ===
        wav_bytes = normalize_audio(file_bytes, original_filename)
        wav_key = f"uploads/{current_user['user_id']}/{task_id_for_key}/{base}.wav"
        minio.upload_audio(wav_key, wav_bytes, content_type="audio/wav")
        del wav_bytes  # освободить RAM

        logger.info(f"MP3 + WAV загружены в MinIO: {recording_url}")

        # Подготовка опций для задачи
        options = {
            "transcribe_model": transcribe_model or "v3_e2e_rnnt",
            "diarization_model": diarization_model or "pyannote/speaker-diarization-community-1",
            "diarize_lib": diarize_lib or "pyannote",
            "transcribe_lib": transcribe_lib or "gigaam",
            "llm_model": llm_model or "deepseek/deepseek-v4-flash",
            "noise_sup_bool": noise_sup_bool,
            "user_id": current_user["user_id"],
            "recording_url": recording_url,  # MP3 URL для плеера
            "audio_key": wav_key,            # WAV ключ для ML-пайплайна
        }

        # Отправка задачи в Celery
        task = transcribe_and_summarize_task.delay(options)
        task_id = str(task.id)

        # Сохранение задачи в БД
        db.insert_celery_task(
            task_id=task_id,
            user_id=current_user["user_id"],
            status="pending"
        )

        logger.info(f"Задача {task_id} отправлена в обработку для пользователя {current_user['user_id']}")

        # Мгновенный ответ (202 Accepted)
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Задача принята в обработку",
            "poll_url": f"/tasks/{task_id}"
        }

    except Exception as e:
        logger.error(f"Ошибка при отправке задачи в Celery: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue task: {str(e)}"
        )


@app.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """
    Получение статуса задачи обработки аудио.
    """

    try:
        # Получение задачи из БД
        task = db.get_celery_task(task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задача не найдена"
            )
        
        # Проверка прав доступа (пользователь может видеть только свои задачи)
        if task.get("user_id") != current_user["user_id"]:
            # Проверка на админа
            if current_user.get("role") != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет доступа к этой задаче"
                )
        
        # Формирование ответа
        response = {
            "task_id": task_id,
            "status": task["status"],
            "step": task.get("step"),
            "progress": task.get("progress"),
            "result": task.get("result"),
            "error": task.get("error"),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at")
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении статуса задачи: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


@app.get("/tasks")
async def get_user_tasks(
    limit: int = 50,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """
    Получение списка задач пользователя.
    """
    try:
        from uuid import UUID as UUID_obj
        user_id = UUID_obj(current_user["user_id"])
        
        tasks = db.get_user_celery_tasks(user_id, limit)
        
        return {
            "tasks": tasks,
            "count": len(tasks)
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка задач: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tasks: {str(e)}"
        )

def split_into_chunks(parts: List[Dict], transcript_meta: Dict) -> List[Dict]:
    chunks = []
    for part in parts:
        # part['text'] имеет формат "SPEAKER_01: текст"
        if ":" in part["text"]:
            speaker, text = part["text"].split(":", 1)
            speaker = speaker.strip()
            text = text.strip()
        else:
            speaker, text = "UNKNOWN", part["text"].strip()

        if not text:
            continue

        chunks.append({
            "text": text,
            "transcript_id": str(transcript_meta["id"]),
            "speaker": speaker,
            "start_time": part["start_time"] / 1000.0,
            "end_time": part["end_time"] / 1000.0,
            "meeting_type": transcript_meta.get("meeting_type"),
            "title": transcript_meta.get("title")
        })
    return chunks

@app.post("/ask")
async def proxy_ask_question(
    transcript_id: str = Form(...),
    question: str = Form(...),
    current_user: dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db),
    llm_model = Form("deepseek/deepseek-v4-flash"), #HARD CODED
):
    """
    Проксирует запрос к LLM в audio-ml сервис и сохраняет историю в БД.
    """
    AUDIO_ML_URL = "http://audio-ml:8053"
    # Проверяем, существует ли транскрипция и принадлежит ли она пользователю
    print(transcript_id)
    # transcript = db.select_transcripts_by_id(transcript_id)
    # if not transcript:
    #     raise HTTPException(status_code=404, detail="Транскрипция не найдена")
    
    parts = db.select_parts_transcription_by_transcript_id(transcript_id)
    if not parts:
        raise HTTPException(status_code=404, detail="Транскрипция не найдена")
    
    meeting_text = "\n".join([p["text"] for p in parts])
    # meeting_text = "\n".join(
    #     part.get("text", "") for part in parts
    # )
    retrieved_context = ""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client_rag:
            rag_resp = await client_rag.post(
                "http://rag-service:8055/search",
                json={
                    "query": question,
                    "employee_id": current_user["user_id"],  # Фильтрация по пользователю
                    "exclude_transcript_id": transcript_id,  # Исключаем текущее совещание
                    "limit": 3  # HARD CODED LIMIT
                }
            )
            if rag_resp.status_code == 200:
                results = rag_resp.json().get("results", [])
                if results:
                    context_lines = []
                    for i, res in enumerate(results, 1):
                        payload = res["payload"]
                        title = "Название совещания: " + '"' + payload.get("title") or "Без названия" + '"'
                        meeting_type_raw = payload.get("meeting_type")
                        meeting_type = f"Тема совещания: {meeting_type_raw}" if meeting_type_raw else ""
                        meeting_type = '"' + meeting_type + '"'
                        speaker = payload.get("speaker") or "Неизвестный"
                        text = payload["text"]
                        line = f"[{i}] ({title}), ({meeting_type}): \"{text}\" (сказал: {speaker})"
                        context_lines.append(line)
                    retrieved_context = "\n".join(context_lines)
    except Exception as e:
        logger.warning(f"Ошибка при RAG-поиске: {e}")
    print("ORIGINAL TEXT" * 10)
    print(meeting_text)
    if retrieved_context:
        final_text = (
            f"ТЕКУЩАЯ ВСТРЕЧА:\n{meeting_text}\n\n"
            f"РЕЛЕВАНТНЫЙ КОНТЕКСТ ИЗ ПРОШЛЫХ ВСТРЕЧ:\n{retrieved_context}"
        )
    else:
        final_text = meeting_text
    print("WITH RAG"*10)
    print(final_text)
    # Подготавливаем данные для отправки в audio-ml
    payload = {
        "question": question,
        "text": final_text,
        "llm_model": llm_model,
    }

    # Отправляем запрос в audio-ml
    try:
        async with httpx.AsyncClient(timeout=160.0) as client:
            ml_response = await client.post(
                f"{AUDIO_ML_URL}/ask",
                json=payload  # Отправляем как JSON
            )
            ml_response.raise_for_status()
            response_data = ml_response.json()

    except httpx.HTTPStatusError as e:
        # Пробрасываем ошибку от ML-сервиса
        detail = ml_response.json().get("detail", str(e)) if ml_response else str(e)
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка подключения к ML-сервису: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка: {str(e)}")

    # 5. Сохраняем историю в БД (ваша новая таблица ChatMessages)
    db.insert_chat_message(transcript_id, current_user["user_id"], "user", question)
    db.insert_chat_message(transcript_id, current_user["user_id"], "assistant", response_data.get("answer", ""))

    # 6. Возвращаем ответ фронтенду
    return JSONResponse(content=response_data)

@app.post("/apply-noise-suppression")
async def apply_noise_suppression(file: UploadFile = File(...)):
    async with httpx.AsyncClient(timeout=1000.0) as client:
        try:
            file_content = await file.read()
            files = {"file": (file.filename, file_content, file.content_type)}

            resp = await client.post("http://denoiser:8052/denoise", files=files)
            resp.raise_for_status()

            return Response(
                content=resp.content,
                media_type=resp.headers.get("content-type", "audio/wav"),
                headers={
                    "Content-Disposition": resp.headers.get("content-disposition", 'attachment; filename="clean.wav"')
                }
            )

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

@app.get("/chat/{transcript_id}")
async def get_chat_history(
    transcript_id: str,
    current_user: dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    # Проверка: существует ли транскрипция и доступна ли пользователю
    transcript = db.select_transcripts_by_id(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Транскрипция не найдена")

    # Загружаем сообщения
    messages = db.select_chat_messages_by_transcript_id(transcript_id, current_user["user_id"])

    return {
        "transcript_id": transcript_id,
        "messages": [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]
    }



@app.get("/transcripts/search")
async def search_transcripts(
    query: Optional[str] = None,
    search_type: str = "exact",  # "exact" или "fuzzy" (для будущего расширения)
    limit: int = 50,
    offset: int = 0,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """
    Поиск транскрипций по названию.
    
    Параметры:
    - query: поисковый запрос (если пустой - возвращается пустой список)
    - search_type: тип поиска ("exact" - точное совпадение, "fuzzy" - нечёткий поиск)
    - limit: максимальное количество результатов
    - offset: смещение для пагинации
    """
    try:
        # Если запрос пустой - возвращаем пустой результат
        if not query or not query.strip():
            return {
                "items": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "query": query or "",
                "search_type": search_type
            }
        
        logger.info(f"Search transcripts for user {current_user['user_id']}: query='{query}', type='{search_type}'")

        # Ищем транскрипции пользователя по названию через SQL LIKE
        from sqlalchemy import text
        
        with db.session_scope() as session:
            user_id = current_user["user_id"]
            query_lower = f"%{query.lower()}%"
            
            # SQL запрос с поиском по названию (case-insensitive)
            # Теперь ищем только через таблицу доступа, так как employee_id удален из Transcripts
            sql = text("""
                SELECT DISTINCT t.id, t.title, t.text, t.created_at, t.recording_url
                FROM "Transcripts" t
                JOIN "TranscriptAccess" ta ON t.id = ta.transcript_id
                WHERE ta.employee_id = :user_id
                  AND LOWER(t.title) LIKE :query
                ORDER BY t.created_at DESC
                LIMIT :limit OFFSET :offset
            """)

            result = session.execute(
                sql,
                {"user_id": user_id, "query": query_lower, "limit": limit, "offset": offset}
            )
            rows = result.fetchall()

            # Получаем общее количество для пагинации
            count_sql = text("""
                SELECT COUNT(DISTINCT t.id)
                FROM "Transcripts" t
                JOIN "TranscriptAccess" ta ON t.id = ta.transcript_id
                WHERE ta.employee_id = :user_id
                  AND LOWER(t.title) LIKE :query
            """)
            count_result = session.execute(count_sql, {"user_id": user_id, "query": query_lower})
            total = count_result.scalar() or 0

        transcripts_list = []
        for row in rows:
            transcript_uuid = row[0]
            
            # Получаем части транскрипции
            parts = db.select_parts_transcription_by_transcript_id(transcript_uuid)
            
            # Получаем суммаризацию
            summary_data = db.select_summaries_by_transcript_id(transcript_uuid)
            
            # Количество уникальных спикеров
            speakers = set()
            duration = 0
            if parts:
                for part in parts:
                    text_part = part.get("text", "")
                    if ":" in text_part:
                        speaker = text_part.split(":")[0].strip()
                        speakers.add(speaker)
                
                min_start = min(p.get("start_time", 0) for p in parts)
                max_end = max(p.get("end_time", 0) for p in parts)
                duration = (max_end - min_start) / 1000.0 / 60.0

            transcript_obj = {
                "transcript_id": str(transcript_uuid),
                "original_text": row[2] or '',
                "title": row[1] or f'Запись от {str(transcript_uuid)[:8]}',
                "created_at": row[3].isoformat() if row[3] else None,
                "summary": summary_data.get('text') if summary_data else None,
                "key_points": summary_data.get('key_points') if summary_data else None,
                "tasks": summary_data.get('tasks') if summary_data else None,
                "meeting_type": summary_data.get('meeting_type') if summary_data else "Не определено",
                "speakers": list(speakers),
                "duration": duration,
                "parts": parts or [],
                "audio_url": row[4] if len(row) > 4 else None
            }
            transcripts_list.append(transcript_obj)

        return {
            "items": transcripts_list,
            "total": total,
            "limit": limit,
            "offset": offset,
            "query": query,
            "search_type": search_type
        }

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Error searching transcripts: {str(e)}")
        logger.error(f"Traceback: {error_traceback}")
        raise HTTPException(500, f"Error searching transcripts: {str(e)}")


@app.get("/transcripts")
async def get_user_transcripts(
    limit: int = 10,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить все транскрипции пользователя с пагинацией"""
    try:
        logger.info(f"Fetching transcripts for user: {current_user}")

        # Парсим даты если они предоставлены
        parsed_start_date = None
        parsed_end_date = None
        try:
            if start_date:
                parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

        # Используем новый метод для получения всех доступных транскрипций (своих и расшаренных)
        all_transcripts = db.select_transcripts_for_employee(
            current_user["user_id"], 
            start_date=parsed_start_date, 
            end_date=parsed_end_date
        )

        # Пагинация на уровне Python
        total = len(all_transcripts)
        rows = all_transcripts[offset : offset + limit]
        transcripts_list = []
        for transcript_data in rows:
            transcript_uuid = UUID(transcript_data['id'])

            # Получаем части транскрипции
            parts = db.select_parts_transcription_by_transcript_id(transcript_uuid)

            # Получаем суммаризацию
            summary_data = db.select_summaries_by_transcript_id(transcript_uuid)

            # Количество уникальных спикеров
            speakers = set()
            duration = 0
            if parts:
                for part in parts:
                    text_part = part.get("text", "")
                    if ":" in text_part:
                        speaker = text_part.split(":")[0].strip()
                        speakers.add(speaker)

                min_start = min(p.get("start_time", 0) for p in parts)
                max_end = max(p.get("end_time", 0) for p in parts)
                duration = (max_end - min_start) / 1000.0 / 60.0

            transcript_obj = {
                "transcript_id": str(transcript_uuid),
                "original_text": transcript_data.get('text') or '',
                "title": transcript_data.get('title') or f'Запись от {str(transcript_uuid)[:8]}',
                "created_at": transcript_data.get('created_at'),
                "summary": summary_data.get('text') if summary_data else None,
                "key_points": summary_data.get('key_points') if summary_data else None,
                "tasks": summary_data.get('tasks') if summary_data else None,
                "meeting_type": summary_data.get('meeting_type') if summary_data else "Не определено",
                "speakers": list(speakers),
                "duration": duration,
                "parts": parts or [],
                "audio_url": transcript_data.get('recording_url')
            }
            transcripts_list.append(transcript_obj)

        return {
            "items": transcripts_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Error fetching transcripts: {str(e)}")
        logger.error(f"Traceback: {error_traceback}")
        raise HTTPException(500, f"Error fetching transcripts: {str(e)}")

@app.get("/transcripts/{transcript_id}")
async def get_transcript(
    transcript_id: str,
    current_user: Dict = Depends(get_current_user),
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

        user_id = current_user.get('user_id')
        # Проверяем доступ через новую систему (владелец или расшарено)
        if not db.check_transcript_access(transcript_uuid, user_id):
            # Вариант Б: Автоматически предоставляем доступ при посещении ссылки
            db.insert_transcript_access(transcript_uuid, user_id)

        parts = db.select_parts_transcription_by_transcript_id(transcript_uuid)

        summary_data = db.select_summaries_by_transcript_id(transcript_uuid)

        # Формируем audio_url из recording_url
        audio_url = transcript_data.get('recording_url')

        return {
            "transcript_id": transcript_id,
            "original_text": transcript_data.get('original_text') or '',
            "title": transcript_data.get('title') or f'Запись от {transcript_id[:8]}',
            "parts": parts,
            "summary": summary_data.get('text') if summary_data else None,
            "key_points": summary_data.get('key_points') if summary_data else None,
            "tasks": summary_data.get('tasks') if summary_data else None,
            "meeting_type": summary_data.get('meeting_type') if summary_data else "Не определено",
            "audio_url": audio_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching transcript: {str(e)}")
        raise HTTPException(500, f"Error fetching transcript: {str(e)}")

@app.delete("/transcripts/{transcript_id}")
async def delete_transcript(
    transcript_id: str,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Удалить транскрипцию из списка пользователя (отмена доступа)"""
    try:
        # Преобразуем строку в UUID
        try:
            transcript_uuid = UUID(transcript_id)
        except ValueError:
            raise HTTPException(400, "Некорректный формат ID транскрипции")

        # Просто удаляем запись о доступе текущего пользователя к этой транскрипции
        success = db.remove_transcript_access(transcript_uuid, current_user["user_id"])

        if success:
            return {"status": "success", "message": "Транскрипция удалена из вашего списка"}
        else:
            raise HTTPException(404, "Запись о доступе не найдена или транскрипция не существует")

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка при удалении: {str(e)}")
        logger.error(f"Error deleting transcript: {str(e)}")
        raise HTTPException(500, f"Ошибка при удалении транскрипции: {str(e)}")


@app.put("/transcripts/{transcript_id}/rename")
async def rename_transcript(
    transcript_id: str,
    rename_data: Dict[str, str],
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Переименовать транскрипцию"""
    try:
        # Преобразуем строку в UUID
        try:
            transcript_uuid = UUID(transcript_id)
        except ValueError:
            raise HTTPException(400, "Некорректный формат ID транскрипции")

        # Проверяем новое название
        new_title = rename_data.get("title", "").strip()
        if not new_title:
            raise HTTPException(400, "Название не может быть пустым")
        if len(new_title) > 500:
            raise HTTPException(400, "Название слишком длинное (макс. 500 символов)")

        # Проверяем, существует ли транскрипция и принадлежит ли пользователю
        transcript_data = db.select_transcripts_by_id(transcript_uuid)
        if not transcript_data:
            raise HTTPException(404, "Транскрипция не найдена")

        # Обновляем название
        success = db.update_transcripts(transcript_uuid, title=new_title)

        if success:
            return {"status": "success", "message": "Транскрипция переименована", "title": new_title}
        else:
            raise HTTPException(500, "Ошибка при обновлении названия")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming transcript: {str(e)}")
        raise HTTPException(500, f"Ошибка при переименовании транскрипции: {str(e)}")


# ===== Annotations API =====

@app.post("/annotations")
async def create_annotation(
    annotation_data: Dict[str, Any],
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Создать аннотацию (подчёркивание)"""
    try:
        from uuid import UUID
        
        part_id = annotation_data.get("part_id")
        start_char = annotation_data.get("start_char")
        end_char = annotation_data.get("end_char")
        color = annotation_data.get("color")
        note = annotation_data.get("note")

        # Валидация
        if not part_id or start_char is None or end_char is None:
            raise HTTPException(400, "part_id, start_char и end_char обязательны")
        if end_char <= start_char:
            raise HTTPException(400, "end_char должен быть больше start_char")

        # Проверяем, существует ли часть транскрипции
        part = db.select_parts_transcription_by_id(UUID(part_id))
        if not part:
            raise HTTPException(404, "Часть транскрипции не найдена")

        # Проверяем, нет ли уже аннотации с такими же параметрами (защита от дублирования)
        existing_annotations = db.select_annotations_by_part_id(UUID(part_id))
        for existing in existing_annotations:
            if existing["employee_id"] != current_user["user_id"]:
                continue
            
            # Проверка на пересечение диапазонов
            if (start_char < existing["end_char"] and end_char > existing["start_char"]):
                # Аннотация пересекается с существующей - не создаём
                raise HTTPException(
                    409, 
                    "Аннотация уже существует для этого участка текста. Удалите существующую перед созданием новой."
                )

        # Создаём аннотацию
        annotation_id = db.insert_annotation(
            part_id=UUID(part_id),
            employee_id=UUID(current_user["user_id"]),
            start_char=start_char,
            end_char=end_char,
            color=color,
            note=note
        )

        if not annotation_id:
            raise HTTPException(500, "Ошибка при создании аннотации")

        return {
            "id": str(annotation_id),
            "part_id": part_id,
            "start_char": start_char,
            "end_char": end_char,
            "color": color,
            "note": note
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating annotation: {str(e)}")
        raise HTTPException(500, f"Ошибка при создании аннотации: {str(e)}")


@app.get("/transcripts/{transcript_id}/annotations")
async def get_transcript_annotations(
    transcript_id: str,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить все аннотации транскрипции для текущего пользователя"""
    try:
        from uuid import UUID
        
        transcript_uuid = UUID(transcript_id)
        
        # Проверяем, существует ли транскрипция
        transcript = db.select_transcripts_by_id(transcript_uuid)
        if not transcript:
            raise HTTPException(404, "Транскрипция не найдена")

        # Один запрос в БД — все аннотации пользователя для этой транскрипции
        annotations = db.select_annotations_by_transcript_and_employee(
            transcript_uuid,
            UUID(current_user["user_id"])
        )

        return {"annotations": annotations, "count": len(annotations)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting annotations: {str(e)}")
        raise HTTPException(500, f"Ошибка при получении аннотаций: {str(e)}")


@app.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: str,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Удалить аннотацию"""
    try:
        from uuid import UUID
        
        annotation_uuid = UUID(annotation_id)
        
        # Проверяем, существует ли аннотация и принадлежит ли пользователю
        # Получаем аннотацию через прямой запрос к БД
        # (нужно добавить метод select_annotation_by_id)
        success = db.delete_annotation(annotation_uuid)

        if success:
            return {"status": "success", "message": "Аннотация удалена"}
        else:
            raise HTTPException(404, "Аннотация не найдена")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting annotation: {str(e)}")
        raise HTTPException(500, f"Ошибка при удалении аннотации: {str(e)}")


@app.get("/admin/users")
async def get_all_users(
    _admin: Dict = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    """Получить список всех пользователей (только для админа)"""
    try:
        users = db.select_staff()
        return [
            {
                "user_id": user["id"],
                "username": user["login"],
                "surname": user["surname"],
                "name": user["name"],
                "patronymic": user.get("patronymic", ""),
                "email": user["email"],
                "login": user["login"],
                "role": user.get("role", "user"),
                "full_name": f"{user['surname']} {user['name']}".strip()
            }
            for user in users
        ]
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(500, f"Error fetching users: {str(e)}")


@app.post("/admin/users")
async def admin_create_user(
    user_data: AdminCreateUserRequest,
    _admin: Dict = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    """Создать пользователя (только для админа)"""
    try:
        existing_users = db.select_staff()
        if any(u['login'] == user_data.username for u in existing_users):
            raise HTTPException(400, "Пользователь с таким логином уже существует")
        if any(u['email'] == user_data.email for u in existing_users):
            raise HTTPException(400, "Пользователь с таким email уже существует")

        employee_id = db.insert_staff(
            surname=user_data.surname,
            name=user_data.name,
            patronymic=user_data.patronymic,
            email=user_data.email,
            login=user_data.username,
            password=user_data.password,
            role=user_data.role
        )

        if not employee_id:
            raise HTTPException(500, "Ошибка при создании пользователя")

        return {
            "status": "success",
            "message": "Пользователь создан",
            "user_id": str(employee_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(500, f"Ошибка при создании пользователя: {str(e)}")


@app.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    _admin: Dict = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    """Удалить пользователя (только для админа)"""
    try:
        from uuid import UUID
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise HTTPException(400, "Некорректный формат ID пользователя")

        user_data = db.select_staff_by_id(user_uuid)
        if not user_data:
            raise HTTPException(404, "Пользователь не найден")

        success = db.delete_staff(user_uuid)
        if not success:
            raise HTTPException(500, "Ошибка при удалении пользователя")

        return {"status": "success", "message": "Пользователь удалён"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(500, f"Ошибка при удалении пользователя: {str(e)}")


@app.patch("/admin/users/{user_id}/role")
async def admin_update_user_role(
    user_id: str,
    role_data: AdminUpdateRoleRequest,
    _admin: Dict = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    """Изменить роль пользователя (только для админа)"""
    try:
        from uuid import UUID
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise HTTPException(400, "Некорректный формат ID пользователя")

        user_data = db.select_staff_by_id(user_uuid)
        if not user_data:
            raise HTTPException(404, "Пользователь не найден")

        success = db.update_staff(user_uuid, role=role_data.role)
        if not success:
            raise HTTPException(500, "Ошибка при обновлении роли")

        return {"status": "success", "message": "Роль обновлена"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role: {str(e)}")
        raise HTTPException(500, f"Ошибка при обновлении роли: {str(e)}")


@app.get("/admin/stats")
async def admin_get_stats(
    _admin: Dict = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    """Получить статистику (только для админа)"""
    try:
        users = db.select_staff()
        transcripts = db.select_transcripts()

        total_duration = 0.0
        for t in transcripts:
            parts = db.select_parts_transcription_by_transcript_id(UUID(t['id']))
            if parts:
                min_start = min(p.get("start_time", 0) for p in parts)
                max_end = max(p.get("end_time", 0) for p in parts)
                total_duration += (max_end - min_start) / 1000.0

        return {
            "total_users": len(users),
            "total_transcripts": len(transcripts),
            "total_duration": round(total_duration, 2)
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        raise HTTPException(500, f"Ошибка получения статистики: {str(e)}")


@app.get("/admin/analytics")
async def admin_get_analytics(
    _admin: Dict = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    """Получить расширенную аналитику сервиса (только для админа)"""
    try:
        analytics = db.get_analytics()
        return analytics
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        raise HTTPException(500, f"Ошибка получения аналитики: {str(e)}")


@app.get("/admin/users/{user_id}/transcripts")
async def admin_get_user_transcripts(
    user_id: str,
    limit: int = 10,
    offset: int = 0,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    _admin: Dict = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    """Получить транскрипции конкретного пользователя (только для админа)"""
    try:
        from uuid import UUID
        from datetime import datetime

        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise HTTPException(400, "Некорректный формат ID пользователя")

        user_data = db.select_staff_by_id(user_uuid)
        if not user_data:
            raise HTTPException(404, "Пользователь не найден")

        # Парсим даты фильтрации если переданы
        parsed_start_date = None
        parsed_end_date = None
        try:
            if start_date:
                parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

        # Используем существующий метод получения транскрипций сотрудника
        all_transcripts = db.select_transcripts_for_employee(
            user_uuid,
            start_date=parsed_start_date,
            end_date=parsed_end_date
        )

        # Фильтр по поиску на стороне Python
        if search:
            search_lower = search.lower()
            all_transcripts = [
                t for t in all_transcripts
                if (t.get('title') or '').lower().find(search_lower) != -1
            ]

        total = len(all_transcripts)
        rows = all_transcripts[offset : offset + limit]

        transcripts_list = []
        for transcript_data in rows:
            transcript_uuid = UUID(transcript_data['id'])
            parts = db.select_parts_transcription_by_transcript_id(transcript_uuid)
            summary_data = db.select_summaries_by_transcript_id(transcript_uuid)

            speakers = set()
            duration = 0
            if parts:
                for part in parts:
                    text_part = part.get("text", "")
                    if ":" in text_part:
                        speaker = text_part.split(":")[0].strip()
                        speakers.add(speaker)
                min_start = min(p.get("start_time", 0) for p in parts)
                max_end = max(p.get("end_time", 0) for p in parts)
                duration = (max_end - min_start) / 1000.0 / 60.0

            transcripts_list.append({
                "transcript_id": str(transcript_uuid),
                "title": transcript_data.get('title') or f'Запись от {str(transcript_uuid)[:8]}',
                "original_text": transcript_data.get('text', ''),
                "created_at": transcript_data.get('created_at'),
                "summary": summary_data.get('text') if summary_data else None,
                "speakers": list(speakers),
                "duration": round(duration, 2),
                "parts_count": len(parts) if parts else 0
            })

        return {
            "items": transcripts_list,
            "total": total,
            "user": {
                "user_id": user_id,
                "full_name": f"{user_data['surname']} {user_data['name']}".strip(),
                "login": user_data['login'],
                "email": user_data['email']
            },
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user transcripts: {str(e)}")
        raise HTTPException(500, f"Ошибка получения транскрипций: {str(e)}")


@app.delete("/admin/transcripts/{transcript_id}")
async def admin_delete_transcript(
    transcript_id: str,
    _admin: Dict = Depends(require_admin),
    db: DataBaseManager = Depends(get_db)
):
    """Жёстко удалить транскрипцию (только для админа)"""
    try:
        from uuid import UUID
        try:
            transcript_uuid = UUID(transcript_id)
        except ValueError:
            raise HTTPException(400, "Некорректный формат ID транскрипции")

        transcript_data = db.select_transcripts_by_id(transcript_uuid)
        if not transcript_data:
            raise HTTPException(404, "Транскрипция не найдена")

        success = db.delete_transcripts(transcript_uuid)
        if not success:
            raise HTTPException(500, "Ошибка при удалении транскрипции")

        return {"status": "success", "message": "Транскрипция удалена"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting transcript: {str(e)}")
        raise HTTPException(500, f"Ошибка при удалении транскрипции: {str(e)}")


# ============================================================================
# === MEETING BOT ENDPOINTS ===
# ============================================================================

@app.post("/meetings/join")
async def join_meeting_now(
    request: JoinMeetingRequest,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """
    Немедленное подключение к совещанию.
    Бот подключится к совещанию сразу после вызова.
    """
    from app.tasks.meetings import join_meeting_immediate

    # Валидация provider
    valid_providers = ["google", "microsoft", "zoom"]
    if request.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {request.provider}. Must be one of: {valid_providers}"
        )

    # Создаём запись в БД (для трекинга)
    now = datetime.utcnow()
    scheduled_id = db.insert_scheduled_meeting(
        user_id=current_user["user_id"],
        meeting_url=request.meeting_url,
        provider=request.provider,
        scheduled_at=now,
        title=request.title,
        bot_name=request.bot_name,
        transcribe_model=request.transcribe_model,
        diarization_model=request.diarization_model,
        diarize_lib=request.diarize_lib,
        transcribe_lib=request.transcribe_lib,
        llm_model=request.llm_model,
        noise_suppression=request.noise_suppression
    )

    if not scheduled_id:
        raise HTTPException(status_code=500, detail="Failed to create meeting record")

    # Запускаем задачу немедленно
    task = join_meeting_immediate.apply_async(
        args=[str(scheduled_id), request.meeting_url, request.provider, current_user["user_id"]],
        kwargs={"bot_name": request.bot_name}
    )

    # Сохраняем ID задачи
    db.update_scheduled_meeting(scheduled_id, meeting_bot_task_id=str(task.id))

    logger.info(f"Meeting join requested: {scheduled_id}, user: {current_user['user_id']}")

    return {
        "success": True,
        "meeting_id": str(scheduled_id),
        "task_id": str(task.id),
        "status": "processing",
        "message": "Meeting bot is joining the meeting now"
    }


@app.post("/meetings/schedule")
async def schedule_meeting(
    request: ScheduleMeetingRequest,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """
    Запланировать подключение к совещанию.
    Бот подключится в указанное время.
    """
    # Валидация provider
    valid_providers = ["google", "microsoft", "zoom"]
    if request.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {request.provider}. Must be one of: {valid_providers}"
        )

    # Парсим время
    try:
        scheduled_at = datetime.fromisoformat(request.scheduled_at.replace("Z", "+00:00"))
        # Убираем timezone info для сравнения с БД (БД хранит UTC)
        scheduled_at = scheduled_at.replace(tzinfo=None)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid scheduled_at format. Use ISO 8601, e.g.: 2026-04-13T15:00:00"
        )

    # Проверяем что время в будущем
    if scheduled_at <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="scheduled_at must be in the future"
        )

    # Создаём запись в БД
    scheduled_id = db.insert_scheduled_meeting(
        user_id=current_user["user_id"],
        meeting_url=request.meeting_url,
        provider=request.provider,
        scheduled_at=scheduled_at,
        title=request.title,
        bot_name=request.bot_name,
        transcribe_model=request.transcribe_model,
        diarization_model=request.diarization_model,
        diarize_lib=request.diarize_lib,
        transcribe_lib=request.transcribe_lib,
        llm_model=request.llm_model,
        noise_suppression=request.noise_suppression
    )

    if not scheduled_id:
        raise HTTPException(status_code=500, detail="Failed to create meeting record")

    logger.info(f"Meeting scheduled: {scheduled_id}, at: {scheduled_at}, user: {current_user['user_id']}")

    return {
        "success": True,
        "meeting_id": str(scheduled_id),
        "status": "scheduled",
        "scheduled_at": scheduled_at.isoformat(),
        "message": "Meeting has been scheduled. Bot will join at the scheduled time."
    }


@app.get("/meetings")
async def get_user_meetings(
    limit: int = 50,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить список запланированных совещаний пользователя."""
    from uuid import UUID as UUID_obj

    user_id = UUID_obj(current_user["user_id"])
    meetings = db.select_user_scheduled_meetings(user_id, limit)

    return {
        "meetings": meetings,
        "count": len(meetings)
    }


@app.get("/meetings/{meeting_id}")
async def get_meeting_status(
    meeting_id: str,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить статус конкретного запланированного совещания."""
    from uuid import UUID as UUID_obj

    meeting = db.select_scheduled_meeting(UUID_obj(meeting_id))

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Проверка прав доступа
    if meeting["user_id"] != current_user["user_id"]:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="No access to this meeting")

    return meeting


@app.delete("/meetings/{meeting_id}")
async def cancel_meeting(
    meeting_id: str,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Отменить запланированное совещание или отозвать бота из конференции."""
    from uuid import UUID as UUID_obj

    meeting = db.select_scheduled_meeting(UUID_obj(meeting_id))

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting["user_id"] != current_user["user_id"]:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="No access to this meeting")

    # completed нельзя отменить — он уже завершён
    if meeting["status"] == "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel meeting with status: {meeting['status']}"
        )

    db.update_scheduled_meeting(UUID_obj(meeting_id), status="cancelled")

    return {
        "success": True,
        "meeting_id": meeting_id,
        "status": "cancelled"
    }


@app.delete("/meetings/{meeting_id}/permanent")
async def delete_meeting_permanently(
    meeting_id: str,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Полностью удалить запись о совещании из БД. Только для completed/cancelled/failed."""
    from uuid import UUID as UUID_obj

    meeting = db.select_scheduled_meeting(UUID_obj(meeting_id))

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting["user_id"] != current_user["user_id"]:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="No access to this meeting")

    # Удалять можно только завершённые, отменённые или с ошибкой
    if meeting["status"] in ("pending", "processing", "recording"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete active meeting with status: {meeting['status']}"
        )

    db.delete_scheduled_meeting(UUID_obj(meeting_id))

    return {
        "success": True,
        "meeting_id": meeting_id,
        "message": "Meeting deleted"
    }


@app.post("/meetings/webhook")
async def meeting_bot_webhook(payload: MeetingBotWebhookPayload):
    """
    Webhook от meeting-bot. Вызывается когда запись совещания готова.
    Этот эндпоинт НЕ требует аутентификации (meeting-bot не имеет JWT).
    """
    from app.tasks.meetings import process_recording_callback
    from uuid import UUID

    logger.info(f"Webhook received: recordingId={payload.recordingId}, status={payload.status}")

    if payload.status == "failed":
        # Запись не удалась, обновляем статус
        # meeting_id в botId или recordingId
        meeting_id = payload.recordingId  # Может потребоваться адаптация
        db = DataBaseManager()
        db.update_scheduled_meeting(
            UUID(meeting_id),
            status="failed",
            error="Recording failed"
        )
        return {"status": "recorded", "message": "Failure recorded"}

    # Запись готова, запускаем обработку
    # meeting_id может быть в metadata.botId или recordingId
    meeting_id = payload.metadata.get("botId") if payload.metadata else None
    if not meeting_id:
        meeting_id = payload.recordingId

    user_id = payload.metadata.get("userId") if payload.metadata else None
    if not user_id:
        logger.warning(f"Webhook received without userId in metadata")
        return {"status": "error", "message": "userId not found in metadata"}

    recording_url = payload.blobUrl
    if not recording_url:
        logger.warning(f"Webhook received without blobUrl")
        return {"status": "error", "message": "blobUrl not found"}

    # Конвертируем внутренний MinIO URL (minio:9000) в публичный (localhost:9000)
    recording_url = recording_url.replace("minio:9000", "localhost:9000")

    # Проверяем, не отменено ли совещание
    if meeting_id:
        try:
            meeting = db.select_scheduled_meeting(UUID(meeting_id))
            if meeting and meeting.get("status") == "cancelled":
                logger.info(f"Meeting {meeting_id} was cancelled — skipping ML pipeline, ignoring recording")
                return {"status": "ignored", "message": "Meeting was cancelled, recording discarded"}
        except Exception as e:
            logger.warning(f"Could not check meeting status: {e}")

    # Запускаем Celery задачу для обработки
    task = process_recording_callback.apply_async(
        args=[meeting_id, recording_url, user_id],
        kwargs={"metadata": payload.metadata}
    )

    logger.info(f"Processing callback task: {task.id}")

    return {
        "status": "accepted",
        "message": "Recording processing started",
        "task_id": str(task.id)
    }


@app.post("/meetings/{meeting_id}/process-now")
async def process_meeting_recording_now(
    meeting_id: str,
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """
    Вручную запустить обработку записи для совещания.
    Полезно если webhook не сработал и нужно перезапустить обработку.
    """
    from app.tasks.meetings import process_recording_callback
    from uuid import UUID as UUID_obj

    meeting = db.select_scheduled_meeting(UUID_obj(meeting_id))

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting["user_id"] != current_user["user_id"]:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="No access to this meeting")

    if not meeting.get("recording_url"):
        raise HTTPException(status_code=400, detail="Recording URL not available yet")

    # Запускаем обработку
    task = process_recording_callback.apply_async(
        args=[meeting_id, meeting["recording_url"], meeting["user_id"]]
    )

    db.update_scheduled_meeting(UUID_obj(meeting_id), status="processing")

    return {
        "success": True,
        "task_id": str(task.id),
        "message": "Processing started"
    }


@app.on_event("startup")
async def startup_event():
    """Инициализация базы данных при запуске приложения с повторными попытками"""
    max_retries = 10
    retry_delay = 10

    def run_migrations():
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

    # Сначала применяем миграции (Alembic — единственный источник правды для схемы)
    # Если БД недоступна, миграции упадут, и ретрай-луп ниже их перезапустит
    for attempt in range(max_retries):
        try:
            print(f"🔄 Попытка применения миграций {attempt + 1}/{max_retries}...")
            run_migrations()
            print("✅ Миграции БД успешно применены")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Миграции не применились: {e}. Повтор через {retry_delay} сек...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Не удалось применить миграции после {max_retries} попыток: {e}")
                # Не падаем — возможно БД поднимется позже
    else:
        # Цикл ни разу не выполнил break (все попытки миграций провалились)
        print("⚠️ Пропускаем инициализацию БД — PostgreSQL недоступен")

    # После миграций — инициализация данных (тестовые пользователи, create_all для таблиц
    # не покрытых миграциями, если такие есть)
    for attempt in range(max_retries):
        try:
            print(f"🔄 Попытка инициализации данных {attempt + 1}/{max_retries}...")
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
                      f"Не удалось инициализировать данные: {e}. Повтор через {retry_delay} сек...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Не удалось инициализировать данные после {max_retries} попыток: {e}")
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