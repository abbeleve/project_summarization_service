from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue
from embedder import Embedder
import uvicorn
import os
import uuid

app = FastAPI(title="RAG Service")

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = "meeting_chunks"

embedder = Embedder()
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Инициализация коллекции при старте
@app.on_event("startup")
def init_collection():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE)  # размер для multilingual-e5-large-instruct
        )

class Chunk(BaseModel):
    text: str
    transcript_id: str
    speaker: Optional[str] = None
    start_time: float
    end_time: float
    meeting_type: Optional[str] = None
    title: Optional[str] = None

class IndexRequest(BaseModel):
    chunks: List[Chunk]

class SearchRequest(BaseModel):
    query: str
    exclude_transcript_id: Optional[str] = None  # чтобы не возвращать текущее совещание
    limit: int = 5

@app.post("/index")
async def index_chunks(req: IndexRequest):
    try:
        print(f"📥 Получено чанков: {len(req.chunks)}")
        for i, c in enumerate(req.chunks[:2]):
            print(f"   [{i}] text='{c.text[:50]}...', transcript_id={c.transcript_id}")
            if not c.text.strip():
                print("   ⚠️ ПУСТОЙ ТЕКСТ!")
        embeddings = embedder.encode([c.text for c in req.chunks])
        points = []
        for i, chunk in enumerate(req.chunks):
            payload = {
                "text": chunk.text,
                "transcript_id": chunk.transcript_id,
                "speaker": chunk.speaker,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "meeting_type": chunk.meeting_type,
                "title": chunk.title
            }
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embeddings[i],
                    payload=payload
                )
            )
        print(f"Размер первого вектора: {len(embeddings[0])}")
        client.upsert(collection_name=COLLECTION_NAME, wait=True, points=points)
        return {"status": "success", "indexed": len(points)}
    except Exception as e:
        import traceback
        print("💥 ОШИБКА В /index:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@app.post("/search")
async def search_similar(req: SearchRequest):
    try:
        # Формируем запрос с префиксом для E5
        query_text = f"query: {req.query}"
        query_vector = embedder.encode([query_text], normalize_embeddings=True)[0].tolist()

        # Подготовка фильтра
        query_filter = None
        if req.exclude_transcript_id:
            query_filter = Filter(
                must_not=[
                    FieldCondition(
                        key="transcript_id",
                        match=MatchValue(value=req.exclude_transcript_id)
                    )
                ]
            )

        # Выполняем поиск
        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=req.limit,
            with_payload=True
        )

        return {
            "results": [
                {
                    "score": point.score,
                    "payload": point.payload
                }
                for point in search_result.points
            ]
        }

    except Exception as e:
        import traceback
        print("💥 ОШИБКА В /search:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")