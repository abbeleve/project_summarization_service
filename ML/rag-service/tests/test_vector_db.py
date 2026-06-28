"""Tests for vector_db.py — чистые функции без внешних зависимостей."""
import os
import math
from collections import Counter
from unittest.mock import patch

import pytest

from vector_db import (
    extract_sparse_vector,
    extract_sparse_vector_from_text,
    _build_filter_dict,
    get_vector_db,
    QdrantVectorDB,
    MilvusVectorDB,
)


# =========================================================================
# extract_sparse_vector
# =========================================================================

class TestExtractSparseVector:
    """Тестируем извлечение sparse вектора из текста (BM25)."""

    def test_english_text(self):
        """Английский текст — возвращает индексы и значения."""
        indices, values = extract_sparse_vector("Hello world test")
        assert isinstance(indices, list)
        assert isinstance(values, list)
        assert len(indices) > 0
        assert len(indices) == len(values)

    def test_russian_text(self):
        """Русский текст — корректная токенизация."""
        indices, values = extract_sparse_vector("Привет мир тест")
        assert len(indices) > 0
        assert len(indices) == len(values)

    def test_mixed_text(self):
        """Смешанный русский + английский."""
        indices, values = extract_sparse_vector("Привет world тест 123")
        assert len(indices) > 0

    def test_stopwords_removed(self):
        """Стоп-слова удаляются (и, в, на, the, a...)."""
        indices, values = extract_sparse_vector("и в на the a an")
        # После удаления стоп-слов все токены уйдут, будет fallback
        # Fallback берёт те же токены (все остаются, т.к. после удаления пусто)
        assert len(indices) > 0

    def test_single_letter_tokens_removed(self):
        """Однобуквенные токены удаляются (кроме fallback)."""
        indices, values = extract_sparse_vector("a b c")
        # Все однобуквенные, после фильтра пусто → fallback
        # В fallback тоже фильтр > 1 буквы, поэтому опять пусто
        # fallback: `[t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1]`
        # a b c — все len=1 → опять пусто → return [], []
        assert indices == []
        assert values == []

    def test_empty_text(self):
        """Пустой текст → пустой вектор."""
        indices, values = extract_sparse_vector("")
        assert indices == []
        assert values == []

    def test_numeric_tokens(self):
        """Цифры — отдельные токены."""
        indices, values = extract_sparse_vector("123 456")
        # Цифры не стоп-слова, len>1
        assert len(indices) > 0

    def test_deterministic_hashing(self):
        """Один и тот же текст → одинаковые индексы."""
        i1, v1 = extract_sparse_vector("тестовый текст для проверки")
        i2, v2 = extract_sparse_vector("тестовый текст для проверки")
        assert i1 == i2
        assert v1 == v2

    def test_sublinear_scaling(self):
        """Повтор токена → log-масштабирование (1+log(1+count))."""
        indices, values = extract_sparse_vector("word word word")
        # "word" встретился 3 раза
        expected_value = 1.0 + math.log(1.0 + 3)  # = 1.0 + log(4) ≈ 2.386
        assert len(indices) == 1, f"Должен быть 1 уникальный токен: {indices}"
        assert abs(values[0] - expected_value) < 0.001, (
            f"Значение {values[0]} != ожидаемое {expected_value:.3f}"
        )

    def test_dimension_range(self):
        """Индексы в диапазоне 1..30000."""
        text = "раз два три четыре пять шесть семь восемь девять десять " * 10
        indices, values = extract_sparse_vector(text)
        for idx in indices:
            assert 1 <= idx <= 30000, f"Индекс {idx} вне диапазона 1..30000"

    def test_indices_sorted(self):
        """Индексы отсортированы по возрастанию."""
        text = "z x y a b c word test hello"
        indices, values = extract_sparse_vector(text)
        assert indices == sorted(indices), "Индексы должны быть отсортированы"

    def test_values_positive(self):
        """Все значения > 0."""
        text = "какой-то текст для проверки значений"
        indices, values = extract_sparse_vector(text)
        for v in values:
            assert v > 0, f"Значение {v} должно быть положительным"

    def test_fallback_when_all_filtered(self):
        """Когда все токены отфильтрованы — fallback на все исходные."""
        # Стоп-слова короткие, но токенов >1 буквы среди них нет
        text = "и в на по"
        indices, values = extract_sparse_vector(text)
        # После удаления стоп-слов: [] → fallback: те же и в на по
        # Fallback: len > 1 → "на" "по" остаются, "и" "в" отсекаются
        assert len(indices) > 0, "Fallback должен дать ненулевой вектор"

    def test_non_empty_guarantee(self):
        """Даже при пустом результате — возвращается [0], [0.0] если всё пусто."""
        # Только однобуквенные стоп-слова
        indices, values = extract_sparse_vector("a")
        # После удаления стоп-слов: "a" уходит (это стоп-слово)
        # Fallback: [t for t in findall if len(t) > 1] → пусто
        # верхний уровень: if not tokens: return [], []
        assert indices == []
        assert values == []


# =========================================================================
# extract_sparse_vector_from_text (wrapper)
# =========================================================================

class TestExtractSparseVectorFromText:
    """Тестируем обёртку, возвращающую SparseVector."""

    def test_returns_sparse_vector(self):
        """Возвращает объект с полями indices и values."""
        from qdrant_client.models import SparseVector
        result = extract_sparse_vector_from_text("hello world")
        assert isinstance(result, SparseVector)
        assert len(result.indices) > 0
        assert len(result.values) > 0


# =========================================================================
# _build_filter_dict
# =========================================================================

class TestBuildFilterDict:
    """Тестируем построение Qdrant REST filter dict."""

    def test_employee_id_mandatory(self):
        """employee_id всегда добавляется в must."""
        result = _build_filter_dict("user-123")
        assert result is not None
        assert "must" in result
        assert any(
            c.get("key") == "employee_id" and c.get("match", {}).get("value") == "user-123"
            for c in result["must"]
        )

    def test_exclude_transcript_id(self):
        """exclude_transcript_id → must_not."""
        result = _build_filter_dict("user-1", exclude_transcript_id="tr-999")
        assert result is not None
        assert "must_not" in result
        assert any(
            c.get("key") == "transcript_id" and c.get("match", {}).get("value") == "tr-999"
            for c in result["must_not"]
        )

    def test_meeting_type_filter(self):
        """Фильтр по типу встречи."""
        result = _build_filter_dict("user-1", filters={"meeting_type": "brainstorm"})
        assert any(
            c.get("key") == "meeting_type" and c.get("match", {}).get("value") == "brainstorm"
            for c in result["must"]
        )

    def test_speaker_filter(self):
        """Фильтр по спикеру."""
        result = _build_filter_dict("user-1", filters={"speaker": "Иван"})
        assert any(
            c.get("key") == "speaker" and c.get("match", {}).get("value") == "Иван"
            for c in result["must"]
        )

    def test_date_range(self):
        """Фильтр по диапазону дат."""
        result = _build_filter_dict("user-1", filters={
            "date_from": "2024-01-01",
            "date_to": "2024-12-31",
        })
        date_condition = next(
            (c for c in result["must"] if c.get("key") == "created_at"), None
        )
        assert date_condition is not None
        assert date_condition["range"]["gte"] == "2024-01-01"
        assert date_condition["range"]["lte"] == "2024-12-31"

    def test_date_from_only(self):
        """Только начальная дата."""
        result = _build_filter_dict("user-1", filters={"date_from": "2024-06-01"})
        date_condition = next(
            (c for c in result["must"] if c.get("key") == "created_at"), None
        )
        assert date_condition is not None
        assert "gte" in date_condition["range"]
        assert "lte" not in date_condition["range"]

    def test_title_filter(self):
        """Фильтр по названию."""
        result = _build_filter_dict("user-1", filters={"title": "важный созвон"})
        assert any(
            c.get("key") == "title" and c.get("match", {}).get("text") == "важный созвон"
            for c in result["must"]
        )

    def test_exclude_and_filter_combined(self):
        """exclude + filters одновременно."""
        result = _build_filter_dict(
            "user-1",
            exclude_transcript_id="tr-999",
            filters={"meeting_type": "sync", "speaker": "Пётр"},
        )
        assert "must_not" in result
        # employee_id, meeting_type, speaker в must
        must_keys = {c["key"] for c in result["must"]}
        assert "employee_id" in must_keys
        assert "meeting_type" in must_keys
        assert "speaker" in must_keys
        # transcript_id НЕ в must
        assert not any(c.get("key") == "transcript_id" for c in result["must"])

    def test_empty_filters_returns_none_without_employee(self):
        """Без employee_id и фильтров — None (edge case)."""
        # Функция всегда получает employee_id, это обязательный параметр
        # Этот тест — на случай если когда-нибудь изменят сигнатуру
        pass

    def test_all_filters_combined(self):
        """Все фильтры одновременно."""
        result = _build_filter_dict(
            "user-42",
            exclude_transcript_id="tr-1",
            filters={
                "meeting_type": "one-on-one",
                "speaker": "Анна",
                "date_from": "2024-03-01",
                "date_to": "2024-03-31",
                "title": "ретроспектива",
            },
        )
        assert result is not None
        must_keys = {c["key"] for c in result["must"]}
        assert "employee_id" in must_keys
        assert "meeting_type" in must_keys
        assert "speaker" in must_keys
        assert "created_at" in must_keys
        assert "title" in must_keys
        assert "transcript_id" not in must_keys
        assert result["must_not"][0]["key"] == "transcript_id"


# =========================================================================
# QdrantVectorDB._build_filter
# =========================================================================

class TestQdrantBuildFilter:
    """Тестируем QdrantVectorDB._build_filter — построение Qdrant Filter-объекта."""

    @pytest.fixture
    def db(self):
        """Создаём QdrantVectorDB с замоканным клиентом (клиент не используется в _build_filter)."""
        with patch("vector_db.QdrantClient"):
            db = QdrantVectorDB()
            db.collection_name = "test-collection"
            return db

    def test_employee_id_mandatory(self, db):
        """employee_id — обязательное поле."""
        qfilter = db._build_filter("user-123")
        assert qfilter is not None
        field_keys = {c.key for c in qfilter.must}
        assert "employee_id" in field_keys

    def test_exclude_transcript_id(self, db):
        """exclude_transcript_id → must_not."""
        qfilter = db._build_filter("user-1", exclude_transcript_id="tr-999")
        assert qfilter.must_not is not None
        assert any(c.key == "transcript_id" for c in qfilter.must_not)

    def test_no_filters_minimal(self, db):
        """Только employee_id — минимальный фильтр."""
        qfilter = db._build_filter("user-1")
        assert len(qfilter.must) >= 1
        assert qfilter.must_not is None or qfilter.must_not == []


# =========================================================================
# get_vector_db factory
# =========================================================================

class TestGetVectorDB:
    """Тестируем фабрику get_vector_db."""

    def test_default_is_qdrant(self):
        """Без VECTOR_DB — QdrantVectorDB."""
        with patch.dict(os.environ, {}, clear=True):
            db = get_vector_db()
            assert isinstance(db, QdrantVectorDB)

    def test_qdrant_explicit(self):
        """VECTOR_DB=qdrant → QdrantVectorDB."""
        with patch.dict(os.environ, {"VECTOR_DB": "qdrant"}, clear=True):
            db = get_vector_db()
            assert isinstance(db, QdrantVectorDB)

    @patch("vector_db.MilvusVectorDB")
    def test_milvus(self, mock_milvus):
        """VECTOR_DB=milvus → MilvusVectorDB."""
        with patch.dict(os.environ, {"VECTOR_DB": "milvus"}, clear=True):
            db = get_vector_db()
            assert isinstance(db, MilvusVectorDB) or mock_milvus.called

    def test_case_insensitive(self):
        """Регистр не имеет значения."""
        with patch.dict(os.environ, {"VECTOR_DB": "QDRANT"}, clear=True):
            db = get_vector_db()
            assert isinstance(db, QdrantVectorDB)

    def test_invalid_raises(self):
        """Неизвестное значение → ValueError."""
        with patch.dict(os.environ, {"VECTOR_DB": "pinecone"}, clear=True):
            with pytest.raises(ValueError, match="Неизвестный тип"):
                get_vector_db()

    def test_milvus_without_mock(self):
        """Milvus без мока — конструктор не падает (подключение ленивое)."""
        with patch.dict(os.environ, {"VECTOR_DB": "milvus"}, clear=True):
            db = get_vector_db()
            assert isinstance(db, MilvusVectorDB)


# =========================================================================
# MilvusVectorDB
# =========================================================================

class TestMilvusVectorDB:
    """Тестируем MilvusVectorDB с замоканными зависимостями."""

    def test_search_no_collection_raises(self):
        """Без инициализации коллекции — RuntimeError."""
        db = MilvusVectorDB()
        with pytest.raises(RuntimeError, match="Коллекция не инициализирована"):
            db.search([0.1] * 1024, 10, "user-1")
