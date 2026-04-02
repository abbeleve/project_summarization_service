"""
Универсальный клиент для работы с векторными БД.
Поддерживает Qdrant и Milvus через переменную окружения VECTOR_DB.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import os
import uuid
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility
from qdrant_client import QdrantClient
from qdrant_client.models import Distance
from qdrant_client.models import VectorParams
from qdrant_client.models import PointStruct
from qdrant_client.models import Filter, FieldCondition, MatchValue
from pymilvus import connections
import time

class VectorDB(ABC):
    """Абстрактный интерфейс векторной БД"""
    @abstractmethod
    def init_collection(self, collection_name: str, vector_dim: int):
        pass
    
    @abstractmethod
    def index_chunks(self, chunks: List[Dict], embeddings: List[List[float]]):
        pass
    
    @abstractmethod
    def search(self, query_vector: List[float], limit: int, employee_id: str, exclude_transcript_id: Optional[str] = None):
        pass

class QdrantVectorDB(VectorDB):
    """Реализация для Qdrant"""
    
    def __init__(self):
        self.client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "qdrant"),
            port=int(os.getenv("QDRANT_PORT", 6333))
        )
        self.collection_name = None
        self.distance = Distance.COSINE
    
    def init_collection(self, collection_name: str, vector_dim: int):
        
        
        self.collection_name = collection_name
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_dim, distance=self.distance)
            )
        print(f"✅ Qdrant коллекция '{collection_name}' готова")
    
    def index_chunks(self, chunks: List[Dict], embeddings: List[List[float]]):
        
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings[i],
                payload=chunk
            )
            for i, chunk in enumerate(chunks)
        ]
        self.client.upsert(collection_name=self.collection_name, wait=True, points=points)
        return len(points)
    
    def search(self, query_vector: List[float], limit: int, employee_id: str, exclude_transcript_id: Optional[str] = None):
        """Поиск с фильтрацией по employee_id"""
        # Фильтр: только чанки пользователя + исключение transcript_id
        must_conditions = [
            FieldCondition(key="employee_id", match=MatchValue(value=employee_id))
        ]
        
        if exclude_transcript_id:
            must_conditions.append(
                FieldCondition(key="transcript_id", match=MatchValue(value=exclude_transcript_id))
            )
        
        query_filter = Filter(must=must_conditions) if must_conditions else None

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True
        )
        return [{"score": p.score, "payload": p.payload} for p in results.points]


class MilvusVectorDB(VectorDB):
    """Реализация для Milvus с ленивым подключением"""
    
    def __init__(self):
        self.host = os.getenv("MILVUS_HOST", "milvus-standalone")
        self.port = int(os.getenv("MILVUS_PORT", "19530"))
        self.collection = None
        self.collection_name = None
        # ← НЕ подключаемся здесь! Только сохраняем параметры
    
    def _ensure_connection(self):
        """Ленивая инициализация подключения к Milvus"""
        from pymilvus import connections, utility
        
        # Проверяем, есть ли уже активное подключение
        try:
            if utility.get_server_version():
                return  # Уже подключены
        except:
            pass
        
        # Подключаемся с повторными попытками
        max_retries = 10
        retry_delay = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                print(f"   🔌 Попытка подключения к Milvus ({attempt}/{max_retries})...")
                connections.connect(
                    alias="default",
                    host=self.host,
                    port=self.port,
                    timeout=5  # Таймаут на подключение
                )
                # Проверяем версию сервера как признак готовности
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
        """Инициализация коллекции с ленивым подключением"""
        self._ensure_connection()  # ← Подключаемся ЗДЕСЬ с повторными попытками
        
        from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility
        
        self.collection_name = collection_name
        
        if not utility.has_collection(collection_name):
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=36),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=vector_dim),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4000),
                FieldSchema(name="transcript_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(name="speaker", dtype=DataType.VARCHAR, max_length=100, default_value="UNKNOWN"),
                FieldSchema(name="start_time", dtype=DataType.FLOAT),
                FieldSchema(name="end_time", dtype=DataType.FLOAT),
                FieldSchema(name="meeting_type", dtype=DataType.VARCHAR, max_length=200, default_value=""),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500, default_value=""),
            ]
            schema = CollectionSchema(fields, description="Чанки совещаний")
            self.collection = Collection(name=collection_name, schema=schema)
            
            # Создаём индекс
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
        """Индексация чанков"""
        if self.collection is None:
            raise RuntimeError("Коллекция не инициализирована. Вызовите init_collection() сначала.")
        
        import uuid
        
        entities = {
            "id": [str(uuid.uuid4()) for _ in chunks],
            "vector": embeddings,
            "text": [c["text"] for c in chunks],
            "transcript_id": [c["transcript_id"] for c in chunks],
            "speaker": [c.get("speaker") or "UNKNOWN" for c in chunks],
            "start_time": [c["start_time"] for c in chunks],
            "end_time": [c["end_time"] for c in chunks],
            "meeting_type": [c.get("meeting_type") or "" for c in chunks],
            "title": [c.get("title") or "" for c in chunks],
        }
        self.collection.insert(entities)
        self.collection.flush()
        return len(chunks)
    
    def search(self, query_vector: List[float], limit: int, employee_id: str, exclude_transcript_id: Optional[str] = None):
        """Поиск с фильтрацией по employee_id"""
        if self.collection is None:
            raise RuntimeError("Коллекция не инициализирована. Вызовите init_collection() сначала.")

        # Фильтр: только чанки пользователя + исключение transcript_id
        expr = f'employee_id == "{employee_id}"'
        if exclude_transcript_id:
            expr += f' and transcript_id != "{exclude_transcript_id}"'

        results = self.collection.search(
            data=[query_vector],
            anns_field="vector",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=limit,
            expr=expr,
            output_fields=["text", "transcript_id", "employee_id", "speaker", "start_time", "end_time", "meeting_type", "title"]
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
                    "title": hit.entity.get("title")
                }
            }
            for hit in results[0]
        ]


def get_vector_db() -> VectorDB:
    """Фабрика: возвращает нужную реализацию в зависимости от VECTOR_DB"""
    db_type = os.getenv("VECTOR_DB", "qdrant").lower()
    
    if db_type == "milvus":
        print("🔌 Используется Milvus")
        return MilvusVectorDB()
    elif db_type == "qdrant":
        print("🔌 Используется Qdrant")
        return QdrantVectorDB()
    else:
        raise ValueError(f"Неизвестный тип векторной БД: {db_type}. Допустимые значения: qdrant, milvus")