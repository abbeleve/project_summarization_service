"""Shared fixtures and mocks for transcribe tests."""
from unittest.mock import MagicMock, patch
import pytest
from uuid import UUID


# Замоканный UUID для тестов
TEST_TASK_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_TRANSCRIPT_ID = UUID("770e8400-e29b-41d4-a716-446655440002")


@pytest.fixture(autouse=True)
def mock_db_env():
    """Подменяем переменные БД, чтобы database.py не падал при импорте."""
    import os
    with patch.dict(os.environ, {
        "DB_NAME": "test_db",
        "DB_USER": "test_user",
        "DB_PASSWORD": "test_pass",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "REDIS_URL": "redis://localhost:6379/0",
    }, clear=False):
        yield


@pytest.fixture
def mock_db_manager():
    """Создаём замоканный DataBaseManager."""
    with patch("app.tasks.transcribe.DataBaseManager") as mock:
        instance = mock.return_value
        instance.update_celery_task_status = MagicMock()
        instance.select_parts_transcription_by_transcript_id = MagicMock(return_value=[])
        instance.update_parts_transcription = MagicMock()
        yield instance
