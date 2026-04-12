from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status, Request, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
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


from .models.models import User, Token, TokenData, LoginRequest, TokenResponse, RegisterRequest
from .db_service.gen_fake_data import gen_fake_data
from .db_service.database import DataBaseManager
from .auth_service.jwt import jwt_service
from .auth_service.middleware import AuthMiddleware

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

# Функция для получения БД
def get_db():
    """Зависимость для получения экземпляра БД"""
    db = DataBaseManager()
    try:
        yield db
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
    # TODO: добавить проверку роли когда она будет в БД
    return current_user

# Зависимость для админа (если понадобится)
def require_admin(request: Request):
    user = get_current_user(request)
    # Здесь можно добавить проверку роли
    return user

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
        
        # Создаем access token
        access_token = jwt_service.create_access_token(
            data={
                "sub": login_data.username,
                "user_id": str(employee_id),
                "full_name": full_name
            }
        )
        
        # Создаем refresh token (опционально)
        refresh_token = jwt_service.create_refresh_token(
            data={
                "sub": login_data.username,
                "user_id": str(employee_id)
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
                "full_name": f"{register_data.surname} {register_data.name}"
            }
        )

        # Создаем refresh token
        refresh_token = jwt_service.create_refresh_token(
            data={
                "sub": register_data.username,
                "user_id": str(employee_id)
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
                "full_name": payload.get("full_name", "")
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
    db: DataBaseManager = Depends(get_db)
):
    """
    Отправляет аудио на обработку в фоновом режиме (Celery).
    Возвращает task_id для отслеживания статуса.
    """
    from app.tasks.transcribe import transcribe_and_summarize_task
    
    print(f"llm_model: {llm_model}")
    print(f"transcribe_model: {transcribe_model}")
    
    try:
        # Чтение файла в байты
        file_bytes = await file.read()
        
        # Подготовка опций для задачи
        options = {
            "transcribe_model": transcribe_model or "v3_ctc",
            "diarization_model": diarization_model or "pyannote/speaker-diarization-community-1",
            "diarize_lib": diarize_lib or "pyannote",
            "transcribe_lib": transcribe_lib or "gigaam",
            "llm_model": llm_model or "gemini-2.5-flash",
            "noise_sup_bool": noise_sup_bool,
            "user_id": current_user["user_id"]
        }
        
        # Отправка задачи в Celery
        task = transcribe_and_summarize_task.delay(file_bytes, options)
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
    llm_model = Form("gemini-2.5-flash"), #HARD CODED
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
    db.insert_chat_message(transcript_id, "user", question)
    db.insert_chat_message(transcript_id, "assistant", response_data.get("answer", ""))

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
    messages = db.select_chat_messages_by_transcript_id(transcript_id)
    
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
            # Теперь используем прямое поле employee_id в Transcripts
            sql = text("""
                SELECT t.id, t.title, t.text, t.created_at, t.employee_id
                FROM "Transcripts" t
                WHERE t.employee_id = :user_id
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
                SELECT COUNT(t.id)
                FROM "Transcripts" t
                WHERE t.employee_id = :user_id
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
                "meeting_type": summary_data.get('meeting_type') if summary_data else "Не определено",
                "speakers": list(speakers),
                "duration": duration,
                "parts": parts or []
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
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить все транскрипции пользователя с пагинацией"""
    try:
        logger.info(f"Fetching transcripts for user: {current_user}")

        from sqlalchemy import text
        
        with db.session_scope() as session:
            user_id = current_user["user_id"]
            
            # Получаем транскрипции пользователя напрямую по employee_id
            sql = text("""
                SELECT t.id, t.title, t.text, t.created_at
                FROM "Transcripts" t
                WHERE t.employee_id = :user_id
                ORDER BY t.created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            
            result = session.execute(sql, {"user_id": user_id, "limit": limit, "offset": offset})
            rows = result.fetchall()
            
            # Получаем общее количество
            count_sql = text("""
                SELECT COUNT(t.id)
                FROM "Transcripts" t
                WHERE t.employee_id = :user_id
            """)
            count_result = session.execute(count_sql, {"user_id": user_id})
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
                "meeting_type": summary_data.get('meeting_type') if summary_data else "Не определено",
                "speakers": list(speakers),
                "duration": duration,
                "parts": parts or []
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
        
        parts = db.select_parts_transcription_by_transcript_id(transcript_uuid)
        
        summary_data = db.select_summaries_by_transcript_id(transcript_uuid)
        
        return {
            "transcript_id": transcript_id,
            "original_text": transcript_data.get('original_text') or '',
            "title": transcript_data.get('title') or f'Запись от {transcript_id[:8]}',
            "parts": parts,
            "summary": summary_data.get('text') if summary_data else None,
            "key_points": summary_data.get('key_points') if summary_data else None,
            "meeting_type": summary_data.get('meeting_type') if summary_data else "Не определено"
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
    """Удалить транскрипцию"""
    try:
        # Преобразуем строку в UUID
        try:
            transcript_uuid = UUID(transcript_id)
        except ValueError:
            raise HTTPException(400, "Некорректный формат ID транскрипции")

        success = db.delete_transcripts(transcript_uuid)

        if success:
            return {"status": "success", "message": "Транскрипция удалена"}
        else:
            raise HTTPException(404, "Транскрипция не найдена")

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
    current_user: Dict = Depends(get_current_user),
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

    def run_migrations():
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

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

    run_migrations()

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