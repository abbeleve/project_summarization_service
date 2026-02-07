"""
RAG Service — микросервис для индексации и поиска по транскрипциям совещаний.
Поддерживает переключение между векторными БД через переменную окружения VECTOR_DB.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import time
import traceback

from embedder import Embedder
from vector_db import get_vector_db

# ===== ИНИЦИАЛИЗАЦИЯ =====
app = FastAPI(
    title="RAG Service",
    description="Индексация и поиск по транскрипциям совещаний",
    version="1.0.0"
)

# Настройки
VECTOR_DIM = 1024  # Размер вектора для multilingual-e5-large-instruct
COLLECTION_NAME = "meeting_chunks"

# Инициализация компонентов
embedder = Embedder()

_vector_db = None

def get_vector_db_lazy():
    global _vector_db
    if _vector_db is None:
        _vector_db = get_vector_db()
    return _vector_db

# ===== МОДЕЛИ ДАННЫХ =====
class Chunk(BaseModel):
    """Модель одного чанка (реплики спикера)"""
    text: str
    transcript_id: str
    speaker: Optional[str] = None
    start_time: float
    end_time: float
    meeting_type: Optional[str] = None
    title: Optional[str] = None


class IndexRequest(BaseModel):
    """Запрос на индексацию чанков"""
    chunks: List[Chunk]


class SearchRequest(BaseModel):
    """Запрос на поиск похожих чанков"""
    query: str
    exclude_transcript_id: Optional[str] = None  # Исключить текущее совещание
    limit: int = 5


# ===== HEALTH CHECK =====
@app.get("/health")
async def health_check():
    """Проверка готовности сервиса"""
    return {
        "status": "healthy",
        "vector_db": os.getenv("VECTOR_DB", "qdrant"),
        "collection": COLLECTION_NAME,
        "vector_dim": VECTOR_DIM
    }


# ===== ИНИЦИАЛИЗАЦИЯ ПРИ СТАРТЕ =====
@app.on_event("startup")
async def startup_event():
    global _vector_db
    print("🚀 Запуск RAG Service...")
    print(f"🔌 Выбрана векторная БД: {os.getenv('VECTOR_DB', 'qdrant')}")
    
    # Загружаем эмбеддер (если ещё не загружен)
    global embedder
    if embedder is None:
        embedder = Embedder()
        test_emb = embedder.encode(["тест"], normalize_embeddings=True)[0]
        print(f"✅ Эмбеддер загружен, размер вектора: {len(test_emb)}")
    
    # Инициализируем векторную БД с повторными попытками
    max_retries = 15
    retry_delay = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"⏳ Попытка инициализации векторной БД ({attempt}/{max_retries})...")
            _vector_db = get_vector_db()  # ← Теперь это НЕ подключается к серверу!
            _vector_db.init_collection(COLLECTION_NAME, VECTOR_DIM)  # ← Подключение происходит ЗДЕСЬ
            print(f"✅ Векторная БД готова")
            return
        except Exception as e:
            print(f"⚠️ Ошибка инициализации ({attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                print(f"💤 Ждём {retry_delay} секунд...")
                time.sleep(retry_delay)
            else:
                raise RuntimeError(f"Не удалось инициализировать векторную БД после {max_retries} попыток") from e


# ===== ЭНДПОИНТ: ИНДЕКСАЦИЯ =====
@app.post("/index")
async def index_chunks(req: IndexRequest):
    """
    Индексирует чанки транскрипции в векторную БД.
    
    Пример запроса:
    {
      "chunks": [
        {
          "text": "Дедлайн по модулю X — 25 января",
          "transcript_id": "uuid-123",
          "speaker": "SPEAKER_01",
          "start_time": 10.5,
          "end_time": 15.2,
          "meeting_type": "Оперативное совещание",
          "title": "Планирование Q1"
        }
      ]
    }
    """
    try:
        # Валидация входных данных
        if not req.chunks:
            raise HTTPException(status_code=400, detail="Список чанков пуст")
        
        # Логирование для отладки
        print(f"📥 Получено чанков: {len(req.chunks)}")
        for i, c in enumerate(req.chunks[:3]):  # Первые 3 для лога
            preview = c.text[:60] + "..." if len(c.text) > 60 else c.text
            print(f"   [{i+1}] transcript_id={c.transcript_id}, speaker={c.speaker}, text='{preview}'")
        
        # Фильтрация пустых текстов
        valid_chunks = [c for c in req.chunks if c.text.strip()]
        if len(valid_chunks) < len(req.chunks):
            print(f"⚠️ Пропущено {len(req.chunks) - len(valid_chunks)} пустых чанков")
        
        if not valid_chunks:
            return {"status": "success", "indexed": 0, "warning": "Все чанки были пустыми"}
        
        # Генерация эмбеддингов с префиксом для E5
        texts = [f"passage: {c.text.strip()}" for c in valid_chunks]
        embeddings = embedder.encode(texts, normalize_embeddings=True).tolist()
        
        # Преобразование в словари для векторной БД
        chunks_dict = [
            {
                "text": c.text,
                "transcript_id": c.transcript_id,
                "speaker": c.speaker or "UNKNOWN",
                "start_time": c.start_time,
                "end_time": c.end_time,
                "meeting_type": c.meeting_type or "",
                "title": c.title or ""
            }
            for c in valid_chunks
        ]
        
        # Индексация
        indexed_count = _vector_db.index_chunks(chunks_dict, embeddings)
        
        print(f"✅ Успешно проиндексировано {indexed_count} чанков")
        return {
            "status": "success",
            "indexed": indexed_count,
            "total_received": len(req.chunks),
            "valid_chunks": len(valid_chunks)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Ошибка в /index: {str(e)}"
        print("💥 " + error_msg)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)


# ===== ЭНДПОИНТ: ПОИСК =====
@app.post("/search")
async def search_similar(req: SearchRequest):
    """
    Ищет релевантные чанки из прошлых совещаний.
    
    Пример запроса:
    {
      "query": "какой дедлайн по модулю X?",
      "exclude_transcript_id": "uuid-текущего-совещания",
      "limit": 3
    }
    """
    try:
        # Валидация
        if not req.query.strip():
            raise HTTPException(status_code=400, detail="Запрос не может быть пустым")
        
        print(f"🔍 Поиск по запросу: '{req.query}' (исключая transcript_id={req.exclude_transcript_id})")
        
        # Генерация эмбеддинга запроса с префиксом для E5
        query_text = f"query: {req.query.strip()}"
        query_vector = embedder.encode([query_text], normalize_embeddings=True).tolist()[0]
        
        # Поиск в векторной БД
        results = _vector_db.search(
            query_vector=query_vector,
            limit=req.limit,
            exclude_transcript_id=req.exclude_transcript_id
        )
        
        print(f"✅ Найдено {len(results)} релевантных чанков")
        for i, res in enumerate(results[:3]):  # Первые 3 для лога
            payload = res["payload"]
            preview = payload["text"][:50] + "..." if len(payload["text"]) > 50 else payload["text"]
            print(f"   [{i+1}] score={res['score']:.4f}, title='{payload.get('title', '')}', text='{preview}'")
        
        return {
            "results": results,
            "query": req.query,
            "total_found": len(results)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Ошибка в /search: {str(e)}"
        print("💥 " + error_msg)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)


# ===== ОБРАБОТКА ОШИБОК =====
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"detail": "Эндпоинт не найден. Доступные: /index, /search, /health"}
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Внутренняя ошибка: {str(exc)}"}
    )