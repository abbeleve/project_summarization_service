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


from .models.models import User, Token, TokenData, LoginRequest, TokenResponse
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
    allow_origins=["http://localhost:8501", "http://frontend:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_middleware = AuthMiddleware(jwt_service)

@app.middleware("http")
async def auth_middleware_wrapper(request: Request, call_next):
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
    return request.state.user

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
    print(llm_model)
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
                'transcribe_lib': transcribe_lib or "gigaam",
                'noise_sup_bool': noise_sup_bool
            }
            
            # Отправка запроса к внешнему сервису транскрибации
            async with httpx.AsyncClient(timeout=1300.0) as client:
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

            ml_response = response.json()
            
            segments = ml_response.get("transcript", [])

            if not segments:
                raise HTTPException(500, "ML service returned empty transcript")

            segments_texts = []
            for segment in segments:
                text = segment.get("Text", "")
                if text:
                    segments_texts.append(text)
            original_text = " ".join(segments_texts)
            
            summary = ""
            try:
                # Подготавливаем данные для суммаризации и определения темы
                transcription_text = "\n".join(
                    f"{segment.get('Speaker', 'UNKNOWN')}: {segment.get('Text', '')}"
                    for segment in segments
                )
                                    
                summarize_data = {
                    "input_text": transcription_text,
                    "llm_model": llm_model or "arcee-ai/trinity-mini:free",
                }
                
                # Отправляем запрос на суммаризацию и определение темы 
                async with httpx.AsyncClient(timeout=300.0) as client:
                    summarize_response = await client.post(
                        "http://audio-ml:8053/llm_pipeline",
                        data=summarize_data
                    )
                
                if summarize_response.status_code == 200:
                    try:
                        summary_result = summarize_response.json()
                        summary_json = summary_result.get("summary", "")
                        title = summary_json.get("title", "no title")
                        summary = summary_json.get("summary", "no summary")
                        key_points = summary_json.get("key_points", ["no_keypoints"])
                        meeting_type = summary_json.get("meeting_type", "Не определено")
                        print(meeting_type)
                    except Exception as e:
                        print(f"Summarization returned wrong JSON format, fallback to default: {e}")
                else:
                    print(f"Summarization service error: {summarize_response.status_code}")
                    summary = ""
                    key_points = ["no_keypoints"]
                    meeting_type = "Не определено"
                    
            except Exception as e:
                print(f"Error during summarization: {str(e)}")
                summary = ""
                key_points = ["no_keypoints"]
                meeting_type = "Не определено"

            # Вставляем транскрипцию в базу
            transcript_id = db.insert_transcripts(
                text=original_text,
                title=title or f"Запись от {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            if not transcript_id:
                raise HTTPException(500, "Failed to save transcript to database")
            
            for segment in segments:
                speaker = segment.get("Speaker", "UNKNOWN")
                text = segment.get("Text", "")
                start = segment.get("start", 0.0)
                end = segment.get("stop", 0.0)
                
                db.insert_parts_transcription(
                    employee_id=current_user["user_id"],
                    transcript_id=transcript_id,
                    text=f"{speaker}: {text}",
                    start_time=int(start * 1000),
                    end_time=int(end * 1000)
                )
            print(meeting_type)
            # Сохраняем суммаризацию в базу
            if summary:
                db.insert_summaries(
                    transcript_id=transcript_id,
                    text=summary,
                    key_points=key_points,
                    meeting_type=meeting_type
                )
                
            speakers = []
            for segment in segments:
                speaker = segment.get("speaker", "UNKNOWN")
                if speaker not in speakers:
                    speakers.append(speaker)
            
            duration = 0.0
            for segment in segments:
                end_time = segment.get("stop", 0.0)
                if end_time > duration:
                    duration = end_time

            parts = db.select_parts_transcription_by_transcript_id(transcript_id)
            
            # Формируем ответ
            return {
                "status": "success",
                "transcript_id": str(transcript_id),
                "title": title,
                "original_text": original_text,
                "segments": segments,
                "summary": summary,
                "key_points": key_points,
                "meeting_type": meeting_type,
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
            detail=f"Transcription or summarization error: {str(e)}"
        ) from e

@app.post("/ask")
async def proxy_ask_question(
    transcript_id: str = Form(...),
    question: str = Form(...),
    current_user: dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """
    Проксирует запрос к LLM в audio-ml сервис и сохраняет историю в БД.
    """
    AUDIO_ML_URL = "http://audio-ml:8053"
    # Проверяем, существует ли транскрипция и принадлежит ли она пользователю
    print(transcript_id)
    transcript = db.select_transcripts_by_id(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Транскрипция не найдена")
    
    parts = db.select_parts_transcription_by_transcript_id(transcript_id)
    meeting_text = "\n".join(
        part.get("text", "") for part in parts
    )
    llm_model = "arcee-ai/trinity-mini:free" # ! HARD CODED
    # Подготавливаем данные для отправки в audio-ml
    payload = {
        "question": question,
        "text": meeting_text,
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
                    "Content-Disposition": resp.headers.get(" content-disposition", 'attachment; filename="clean.wav"')
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



@app.get("/transcripts")
async def get_user_transcripts(
    current_user: Dict = Depends(get_current_user),
    db: DataBaseManager = Depends(get_db)
):
    """Получить все транскрипции пользователя"""
    try:
        # Получаем части транскрипций, созданные пользователем
        user_parts = db.select_parts_transcription_by_employee_id(current_user["user_id"])

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
                    "title": transcript_data.get('title', ''),
                    "created_at": transcript_data.get('created_at'),
                    "summary": summary_data.get('text') if summary_data else None,
                    "key_points": summary_data.get('key_points') if summary_data else None,
                    "meeting_type": summary_data.get('meeting_type', "Не определено"),
                    "parts": []
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
            "original_text": transcript_data.get('original_text', ''),
            "title": transcript_data.get('title', ''),
            "parts": parts,
            "summary": summary_data.get('text') if summary_data else None,
            "key_points": summary_data.get('key_points') if summary_data else None,
            "meeting_type": summary_data.get('meeting_type', "Не определено")
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