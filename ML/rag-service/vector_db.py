"""
Универсальный клиент для работы с векторными БД.
Поддерживает Qdrant и Milvus через переменную окружения VECTOR_DB.
Qdrant: dense (1024d) + sparse (BM25) векторы.
Milvus: только dense (1024d).
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import os
import uuid
import time
import math
import re
from collections import Counter

from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility
from pymilvus import connections as milvus_connections

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams, SparseIndexParams,
    PointStruct, SparseVector,
    Filter, FieldCondition, MatchValue, Range, MatchText, Modifier,
    Prefetch, Fusion,
)


# ─── Sparse vector extractor ─────────────────────────────────────────────────

# Simple English + Russian tokenizer for BM25 sparse vectors
_TOKEN_RE = re.compile(r"[а-яёa-z]+|[0-9]+", re.IGNORECASE)

_STOP_WORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со",
    "как", "а", "то", "все", "она", "так", "его", "но", "да",
    "ты", "к", "у", "же", "вы", "за", "бы", "по", "из", "им",
    "от", "о", "об", "для", "или", "это", "обо", "до",
    "the", "a", "an", "in", "on", "at", "to", "for", "of",
    "and", "or", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "with", "from", "by", "as",
}


def extract_sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """
    Extract a sparse vector from text.
    Returns (indices, values) where indices are token hash -> dim ids.
    Simple bag-of-words with sublinear scaling (log(1+freq)).
    """
    tokens = _TOKEN_RE.findall(text.lower())
    tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]
    if not tokens:
        # Fallback: use the original text hashed
        tokens = [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1]
    if not tokens:
        return [], []

    freq = Counter(tokens)

    # Deterministic hashing to 30k dimension space
    # Use dict to merge duplicate dims (hash collisions)
    dims: dict[int, float] = {}
    for token, count in freq.items():
        dim = (abs(hash(token)) % 30000) + 1  # 1..30000
        value = 1.0 + math.log(1.0 + count)  # sublinear scaling
        dims[dim] = dims.get(dim, 0.0) + value  # merge collisions

    indices = sorted(dims.keys())
    values = [dims[d] for d in indices]

    # Ensure at least one non-zero dimension (Qdrant requires non-empty sparse vectors)
    if not indices:
        indices = [0]
        values = [0.0]

    return indices, values


def extract_sparse_vector_from_text(text: str) -> SparseVector:
    """Return a qdrant SparseVector from text."""
    indices, values = extract_sparse_vector(text)
    return SparseVector(indices=indices, values=values)


def _build_filter_dict(
    employee_id: str,
    exclude_transcript_id: Optional[str] = None,
    filters: Optional[Dict] = None,
) -> Optional[dict]:
    """Build Qdrant REST filter dict from parameters."""
    must_conditions = []

    # Employee ID is mandatory
    must_conditions.append({
        "key": "employee_id",
        "match": {"value": employee_id},
    })

    if exclude_transcript_id:
        must_conditions.append({
            "key": "transcript_id",
            "match": {"value": exclude_transcript_id},
        })

    if filters:
        meeting_type = filters.get("meeting_type")
        if meeting_type:
            must_conditions.append({
                "key": "meeting_type",
                "match": {"value": meeting_type},
            })

        speaker = filters.get("speaker")
        if speaker:
            must_conditions.append({
                "key": "speaker",
                "match": {"value": speaker},
            })

        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        if date_from or date_to:
            range_kw = {}
            if date_from:
                range_kw["gte"] = date_from
            if date_to:
                range_kw["lte"] = date_to
            must_conditions.append({
                "key": "created_at",
                "range": range_kw,
            })

        title_query = filters.get("title")
        if title_query:
            must_conditions.append({
                "key": "title",
                "match": {"text": title_query},
            })

    if not must_conditions:
        return None

    result = {"must": must_conditions}

    # Exclude transcript_id goes into must_not
    if exclude_transcript_id:
        result["must_not"] = [
            {"key": "transcript_id", "match": {"value": exclude_transcript_id}}
        ]
        # Remove from must
        result["must"] = [
            c for c in result["must"]
            if not (c.get("key") == "transcript_id")
        ]

    return result if result["must"] or result.get("must_not") else None


# ─── Abstract interface ─────────────────────────────────────────────────────

class VectorDB(ABC):
    """Абстрактный интерфейс векторной БД"""
    @abstractmethod
    def init_collection(self, collection_name: str, vector_dim: int):
        pass

    @abstractmethod
    def index_chunks(self, chunks: List[Dict], embeddings: List[List[float]]):
        pass

    @abstractmethod
    def search(self, query_vector: List[float], limit: int, employee_id: str,
               exclude_transcript_id: Optional[str] = None,
               query_text: Optional[str] = None,
               filters: Optional[Dict] = None):
        pass


# ─── Qdrant implementation (dense + sparse) ─────────────────────────────────

class QdrantVectorDB(VectorDB):
    """Реализация для Qdrant с поддержкой dense + sparse векторов."""

    def __init__(self):
        self.client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "qdrant"),
            port=int(os.getenv("QDRANT_PORT", 6333))
        )
        self.collection_name = None
        self.distance = Distance.COSINE

    def init_collection(self, collection_name: str, vector_dim: int):
        self.collection_name = collection_name

        # Always recreate to ensure correct config (dense + sparse).
        # Existing data is incompatible with the new schema anyway.
        if self.client.collection_exists(collection_name):
            print(f"🗑️ Удаление старой коллекции '{collection_name}' для пересоздания...")
            self.client.delete_collection(collection_name)

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(size=vector_dim, distance=self.distance, on_disk=True),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=True),
                    modifier=Modifier.IDF,
                ),
            },
        )
        print(f"✅ Qdrant коллекция '{collection_name}' создана (dense + sparse)")

    def index_chunks(self, chunks: List[Dict], embeddings: List[List[float]]):
        points = []
        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            sparse_vec = extract_sparse_vector_from_text(text) if text.strip() else SparseVector(indices=[0], values=[0.0])
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        "dense": embeddings[i],
                        "sparse": sparse_vec,
                    },
                    payload=chunk,
                )
            )

        self.client.upsert(collection_name=self.collection_name, wait=True, points=points)
        return len(points)

    def _build_filter(self, employee_id: str,
                      exclude_transcript_id: Optional[str] = None,
                      filters: Optional[Dict] = None) -> Optional[Filter]:
        """Build Qdrant filter from parameters."""
        must_conditions = [
            FieldCondition(key="employee_id", match=MatchValue(value=employee_id))
        ]

        if exclude_transcript_id:
            # Must NOT = use "must_not" negation
            must_conditions.append(
                FieldCondition(key="transcript_id", match=MatchValue(value=exclude_transcript_id))
            )

        # Additional filters
        if filters:
            # Meeting type filter
            meeting_type = filters.get("meeting_type")
            if meeting_type:
                must_conditions.append(
                    FieldCondition(key="meeting_type", match=MatchValue(value=meeting_type))
                )

            # Speaker filter
            speaker = filters.get("speaker")
            if speaker:
                must_conditions.append(
                    FieldCondition(key="speaker", match=MatchValue(value=speaker))
                )

            # Date range filter
            date_from = filters.get("date_from")
            date_to = filters.get("date_to")
            if date_from or date_to:
                range_kw = {}
                if date_from:
                    range_kw["gte"] = date_from
                if date_to:
                    range_kw["lte"] = date_to
                must_conditions.append(
                    FieldCondition(key="created_at", range=Range(**range_kw))
                )

            # Title keyword search
            title_query = filters.get("title")
            if title_query:
                must_conditions.append(
                    FieldCondition(key="title", match=MatchText(text=title_query))
                )

        # If there's an exclude_transcript_id, wrap in must_not
        if exclude_transcript_id:
            qfilter = Filter(
                must=[c for c in must_conditions if c.key != "transcript_id"],
                must_not=[
                    FieldCondition(key="transcript_id", match=MatchValue(value=exclude_transcript_id))
                ]
            )
        else:
            qfilter = Filter(must=must_conditions) if must_conditions else None

        return qfilter

    def search(self, query_vector: List[float], limit: int, employee_id: str,
               exclude_transcript_id: Optional[str] = None,
               query_text: Optional[str] = None,
               filters: Optional[Dict] = None):
        """
        Гибридный поиск: dense (semantic) + sparse (BM25) с RRF fusion.
        Если query_text не передан — только dense search.
        """
        qfilter = self._build_filter(employee_id, exclude_transcript_id, filters)

        if query_text:
            # Hybrid search with RRF
            sparse_vec = extract_sparse_vector_from_text(query_text)
            # If sparse is empty, fallback to dense-only
            if not sparse_vec.indices or not sparse_vec.values:
                results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=qfilter,
                    limit=limit,
                    with_payload=True,
                    using="dense",
                )
            else:
                # Qdrant v1.13 requires {"fusion": "rrf"} in the query field (not raw string)
                import requests as _requests

                # Build the REST request body for hybrid search
                rest_body = {
                    "prefetch": [
                        {"query": query_vector, "using": "dense", "limit": limit * 2},
                        {"query": {
                            "indices": sparse_vec.indices,
                            "values": sparse_vec.values,
                        }, "using": "sparse", "limit": limit * 2},
                    ],
                    "query": {"fusion": "rrf"},
                    "limit": limit,
                    "with_payload": True,
                }

                # Add filter directly as dict
                rest_filter = _build_filter_dict(employee_id, exclude_transcript_id, filters)
                if rest_filter:
                    rest_body["filter"] = rest_filter

                host = os.getenv("QDRANT_HOST", "qdrant")
                port = int(os.getenv("QDRANT_PORT", 6333))
                rest_url = f"http://{host}:{port}/collections/{self.collection_name}/points/query"

                rest_resp = _requests.post(rest_url, json=rest_body, timeout=30)
                if rest_resp.status_code != 200:
                    print(f"⚠️ RRF hybrid search failed: {rest_resp.text[:200]}")
                    # Fallback to dense-only
                    results = self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        query_filter=qfilter,
                        limit=limit,
                        with_payload=True,
                        using="dense",
                    )
                else:
                    data = rest_resp.json()
                    points = data.get("result", {}).get("points", [])
                    results = type('_Q', (), {'points': [
                        type('_P', (), {
                            'score': p.get('score', 0),
                            'payload': p.get('payload', {}),
                        })() for p in points
                    ]})()
        else:
            # Dense-only fallback
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=qfilter,
                limit=limit,
                with_payload=True,
                using="dense",
            )

        return [{"score": p.score, "payload": p.payload} for p in results.points]


# ─── Milvus implementation (dense only) ─────────────────────────────────────

class MilvusVectorDB(VectorDB):
    """Реализация для Milvus с ленивым подключением (dense only)."""

    def __init__(self):
        self.host = os.getenv("MILVUS_HOST", "milvus-standalone")
        self.port = int(os.getenv("MILVUS_PORT", "19530"))
        self.collection = None
        self.collection_name = None

    def _ensure_connection(self):
        from pymilvus import connections, utility
        try:
            if utility.get_server_version():
                return
        except:
            pass

        max_retries = 10
        retry_delay = 2
        for attempt in range(1, max_retries + 1):
            try:
                milvus_connections.connect(
                    alias="default",
                    host=self.host,
                    port=self.port,
                    timeout=5
                )
                version = utility.get_server_version()
                print(f"   ✅ Подключено к Milvus {version} ({self.host}:{self.port})")
                return
            except Exception as e:
                if attempt < max_retries:
                    print(f"   ⚠️ Milvus недоступен: {e}")
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(f"Не удалось подключиться к Milvus после {max_retries} попыток: {e}")

    def init_collection(self, collection_name: str, vector_dim: int):
        self._ensure_connection()
        from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility

        self.collection_name = collection_name
        if not utility.has_collection(collection_name):
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=36),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=vector_dim),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4000),
                FieldSchema(name="transcript_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(name="employee_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(name="speaker", dtype=DataType.VARCHAR, max_length=100, default_value="UNKNOWN"),
                FieldSchema(name="start_time", dtype=DataType.FLOAT),
                FieldSchema(name="end_time", dtype=DataType.FLOAT),
                FieldSchema(name="meeting_type", dtype=DataType.VARCHAR, max_length=200, default_value=""),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500, default_value=""),
                FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=50, default_value=""),
            ]
            schema = CollectionSchema(fields, description="Чанки совещаний")
            self.collection = Collection(name=collection_name, schema=schema)
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            self.collection.create_index(field_name="vector", index_params=index_params)
            self.collection.load()
            print(f"✅ Milvus коллекция '{collection_name}' создана и загружена")
        else:
            self.collection = Collection(collection_name)
            self.collection.load()
            print(f"✅ Milvus коллекция '{collection_name}' загружена")

    def index_chunks(self, chunks: List[Dict], embeddings: List[List[float]]):
        if self.collection is None:
            raise RuntimeError("Коллекция не инициализирована.")

        entities = {
            "id": [str(uuid.uuid4()) for _ in chunks],
            "vector": embeddings,
            "text": [c["text"] for c in chunks],
            "transcript_id": [c["transcript_id"] for c in chunks],
            "employee_id": [c.get("employee_id", "") for c in chunks],
            "speaker": [c.get("speaker") or "UNKNOWN" for c in chunks],
            "start_time": [c["start_time"] for c in chunks],
            "end_time": [c["end_time"] for c in chunks],
            "meeting_type": [c.get("meeting_type") or "" for c in chunks],
            "title": [c.get("title") or "" for c in chunks],
            "created_at": [c.get("created_at") or "" for c in chunks],
        }
        self.collection.insert(entities)
        self.collection.flush()
        return len(chunks)

    def search(self, query_vector: List[float], limit: int, employee_id: str,
               exclude_transcript_id: Optional[str] = None,
               query_text: Optional[str] = None,
               filters: Optional[Dict] = None):
        if self.collection is None:
            raise RuntimeError("Коллекция не инициализирована.")

        expr = f'employee_id == "{employee_id}"'
        if exclude_transcript_id:
            expr += f' and transcript_id != "{exclude_transcript_id}"'

        if filters:
            meeting_type = filters.get("meeting_type")
            if meeting_type:
                expr += f' and meeting_type == "{meeting_type}"'
            speaker = filters.get("speaker")
            if speaker:
                expr += f' and speaker == "{speaker}"'

        results = self.collection.search(
            data=[query_vector],
            anns_field="vector",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=limit,
            expr=expr,
            output_fields=["text", "transcript_id", "employee_id", "speaker",
                          "start_time", "end_time", "meeting_type", "title", "created_at"]
        )

        return [
            {
                "score": hit.distance,
                "payload": {
                    "text": hit.entity.get("text"),
                    "transcript_id": hit.entity.get("transcript_id"),
                    "employee_id": hit.entity.get("employee_id"),
                    "speaker": hit.entity.get("speaker"),
                    "start_time": hit.entity.get("start_time"),
                    "end_time": hit.entity.get("end_time"),
                    "meeting_type": hit.entity.get("meeting_type"),
                    "title": hit.entity.get("title"),
                    "created_at": hit.entity.get("created_at"),
                }
            }
            for hit in results[0]
        ]


# ─── Factory ────────────────────────────────────────────────────────────────

def get_vector_db() -> VectorDB:
    """Фабрика: возвращает нужную реализацию в зависимости от VECTOR_DB."""
    db_type = os.getenv("VECTOR_DB", "qdrant").lower()
    if db_type == "milvus":
        print("🔌 Используется Milvus (dense only)")
        return MilvusVectorDB()
    elif db_type == "qdrant":
        print("🔌 Используется Qdrant (dense + sparse hybrid)")
        return QdrantVectorDB()
    else:
        raise ValueError(f"Неизвестный тип векторной БД: {db_type}. Допустимые значения: qdrant, milvus")
