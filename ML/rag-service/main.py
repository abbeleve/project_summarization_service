"""
RAG Service — микросервис для индексации и поиска по транскрипциям совещаний.
Поддерживает переключение между векторными БД через переменную окружения VECTOR_DB.

Qdrant: гибридный поиск (dense semantic + sparse BM25) с RRF fusion.
Milvus: только dense search.
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
from sentence_splitter import split_sentences, chunk_sentences

# ===== ИНИЦИАЛИЗАЦИЯ =====
app = FastAPI(
    title="RAG Service",
    description="Индексация и поиск по транскрипциям совещаний",
    version="2.0.0"
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
    """Модель одного чанка (реплики спикера) — то, что приходит от бэкенда."""
    text: str
    transcript_id: str
    employee_id: str
    speaker: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    meeting_type: Optional[str] = None
    title: Optional[str] = None
    created_at: Optional[str] = None  # ISO date string для фильтрации по дате


class IndexRequest(BaseModel):
    """Запрос на индексацию чанков (приходят от бэкенда)."""
    chunks: List[Chunk]


class SearchFilters(BaseModel):
    """Фильтры для поиска."""
    meeting_type: Optional[str] = None
    speaker: Optional[str] = None
    title: Optional[str] = None
    date_from: Optional[str] = None  # ISO date string
    date_to: Optional[str] = None    # ISO date string


class SearchRequest(BaseModel):
    """Запрос на поиск похожих чанков."""
    query: str
    employee_id: str
    exclude_transcript_id: Optional[str] = None
    limit: int = 10
    filters: Optional[SearchFilters] = None


# ===== HEALTH CHECK =====
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "vector_db": os.getenv("VECTOR_DB", "qdrant"),
        "collection": COLLECTION_NAME,
        "vector_dim": VECTOR_DIM,
        "version": "2.0.0 (hybrid dense+sparse, sentence-aware chunking)"
    }


# ===== ИНИЦИАЛИЗАЦИЯ ПРИ СТАРТЕ =====
@app.on_event("startup")
async def startup_event():
    global _vector_db
    global embedder
    print("🚀 Запуск RAG Service v2...")
    print(f"🔌 Выбрана векторная БД: {os.getenv('VECTOR_DB', 'qdrant')}")

    if embedder is None:
        embedder = Embedder()
        test_emb = embedder.encode(["тест"], normalize_embeddings=True)[0]
        print(f"✅ Эмбеддер загружен, размер вектора: {len(test_emb)}")

    max_retries = 15
    retry_delay = 3

    for attempt in range(1, max_retries + 1):
        try:
            print(f"⏳ Попытка инициализации векторной БД ({attempt}/{max_retries})...")
            _vector_db = get_vector_db()
            _vector_db.init_collection(COLLECTION_NAME, VECTOR_DIM)
            print(f"✅ Векторная БД готова")
            return
        except Exception as e:
            print(f"⚠️ Ошибка инициализации ({attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                print(f"💤 Ждём {retry_delay} секунд...")
                time.sleep(retry_delay)
            else:
                raise RuntimeError(f"Не удалось инициализировать векторную БД после {max_retries} попыток") from e


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def _sentence_chunk(parts: List[Chunk]) -> List[dict]:
    """
    Sentence-aware чанкинг с перекрытием в 1 предложение.
    Берёт сырые части от бэкенда, нарезает на чанки по предложениям.
    """
    result = []

    for part in parts:
        text = part.text.strip()
        if not text:
            continue

        sentences = split_sentences(text)
        if not sentences:
            # Fallback: весь текст как один чанк
            result.append({
                "text": text,
                "transcript_id": part.transcript_id,
                "employee_id": part.employee_id,
                "speaker": part.speaker or "UNKNOWN",
                "start_time": part.start_time,
                "end_time": part.end_time,
                "meeting_type": part.meeting_type or "",
                "title": part.title or "",
                "created_at": part.created_at or "",
            })
            continue

        # Группируем предложения в чанки с перекрытием
        chunks = chunk_sentences(sentences, max_chars=400, min_chars=150, overlap=1)

        for chunk_text in chunks:
            result.append({
                "text": chunk_text,
                "transcript_id": part.transcript_id,
                "employee_id": part.employee_id,
                "speaker": part.speaker or "UNKNOWN",
                "start_time": part.start_time,
                "end_time": part.end_time,
                "meeting_type": part.meeting_type or "",
                "title": part.title or "",
                "created_at": part.created_at or "",
            })

    return result


# ===== ЭНДПОИНТ: ИНДЕКСАЦИЯ =====
@app.post("/index")
async def index_chunks(req: IndexRequest):
    """
    Индексирует чанки транскрипции в векторную БД.
    Внутри делает sentence-aware чанкинг, dense + sparse эмбеддинги.

    Пример запроса:
    {
      "chunks": [
        {
          "text": "Дедлайн по модулю X — 25 января",
          "transcript_id": "uuid-123",
          "employee_id": "uuid-user",
          "speaker": "SPEAKER_01",
          "start_time": 10.5,
          "end_time": 15.2,
          "meeting_type": "Оперативное совещание",
          "title": "Планирование Q1",
          "created_at": "2026-06-24T10:00:00Z"
        }
      ]
    }
    """
    try:
        if not req.chunks:
            raise HTTPException(status_code=400, detail="Список чанков пуст")

        print(f"📥 Получено сырых частей: {len(req.chunks)}")

        # Sentence-aware чанкинг
        sentence_chunks = _sentence_chunk(req.chunks)
        print(f"🔪 После sentence-чанкинга: {len(sentence_chunks)} чанков")

        if not sentence_chunks:
            return {"status": "success", "indexed": 0, "warning": "Нечего индексировать"}

        # Фильтрация пустых
        valid = [c for c in sentence_chunks if c["text"].strip()]
        print(f"✅ Валидных чанков: {len(valid)}")

        if not valid:
            return {"status": "success", "indexed": 0, "warning": "Все чанки пусты"}

        # Генерация dense-эмбеддингов
        texts = [f"passage: {c['text']}" for c in valid]
        embeddings = embedder.encode(texts, normalize_embeddings=True).tolist()

        # Индексация
        indexed_count = _vector_db.index_chunks(valid, embeddings)

        print(f"✅ Проиндексировано {indexed_count} чанков "
              f"(из {len(req.chunks)} сырых частей → {len(sentence_chunks)} предложенческих чанков)")
        return {
            "status": "success",
            "indexed": indexed_count,
            "raw_parts": len(req.chunks),
            "sentence_chunks": len(sentence_chunks),
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
    Гибридный поиск: dense (semantic) + sparse (BM25) с RRF fusion.
    Поддерживает фильтры: meeting_type, speaker, title, date_from, date_to.

    Пример запроса:
    {
      "query": "какой дедлайн по модулю X?",
      "employee_id": "uuid-user",
      "exclude_transcript_id": "uuid-текущего",
      "limit": 10,
      "filters": {
        "meeting_type": "sprint-planning",
        "date_from": "2026-06-01",
        "date_to": "2026-06-30"
      }
    }
    """
    try:
        if not req.query.strip():
            raise HTTPException(status_code=400, detail="Запрос не может быть пустым")
        if not req.employee_id:
            raise HTTPException(status_code=400, detail="employee_id обязателен")

        print(f"🔍 Поиск: '{req.query}' (user={req.employee_id}, "
              f"limit={req.limit}, filters={req.filters})")

        # Dense эмбеддинг запроса
        query_text = f"query: {req.query.strip()}"
        query_vector = embedder.encode([query_text], normalize_embeddings=True).tolist()[0]

        # Фильтры в словарь
        filters_dict = None
        if req.filters:
            filters_dict = req.filters.model_dump(exclude_none=True)
            if not filters_dict:
                filters_dict = None

        # Поиск
        results = _vector_db.search(
            query_vector=query_vector,
            limit=req.limit,
            employee_id=req.employee_id,
            exclude_transcript_id=req.exclude_transcript_id,
            query_text=req.query.strip(),
            filters=filters_dict,
        )

        print(f"✅ Найдено {len(results)} чанков")
        return {
            "results": results,
            "query": req.query,
            "total_found": len(results),
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
