"""Tests for transcribe.py — чистая функция split_into_chunks + вспомогательные."""
from uuid import UUID
from unittest.mock import patch, MagicMock, call
import subprocess
import pytest

from app.tasks.transcribe import (
    split_into_chunks,
    update_task_status,
    _get_enrolled_speakers,
)


# =========================================================================
# split_into_chunks
# =========================================================================

class TestSplitIntoChunks:
    """Тестируем разбиение транскрипции на чанки для RAG."""

    def make_part(self, text: str, speaker: str = "SPEAKER_00",
                  start_ms: int = 0, end_ms: int = 5000, part_id=1) -> dict:
        return {
            "id": part_id,
            "text": f"{speaker}: {text}",
            "speaker": speaker,
            "start_time": start_ms,
            "end_time": end_ms,
        }

    @pytest.fixture
    def meta(self):
        return {
            "id": UUID("770e8400-e29b-41d4-a716-446655440002"),
            "title": "Тестовое совещание",
            "meeting_type": "brainstorm",
            "employee_id": UUID("660e8400-e29b-41d4-a716-446655440001"),
            "created_at": "2024-06-28T10:00:00",
        }

    def test_single_part(self, meta):
        """Одна часть → один чанк."""
        parts = [self.make_part("Привет всем.")]
        chunks = split_into_chunks(parts, meta)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "SPEAKER_00: Привет всем."
        assert chunks[0]["transcript_id"] == str(meta["id"])
        assert chunks[0]["employee_id"] == str(meta["employee_id"])
        assert chunks[0]["speaker"] == "SPEAKER_00"
        assert chunks[0]["start_time"] == 0.0
        assert chunks[0]["end_time"] == 5.0
        assert chunks[0]["meeting_type"] == "brainstorm"
        assert chunks[0]["title"] == "Тестовое совещание"
        assert chunks[0]["created_at"] == "2024-06-28T10:00:00"

    def test_multiple_parts(self, meta):
        """Несколько частей → несколько чанков."""
        parts = [
            self.make_part("Первое слово.", "SPEAKER_00", 0, 5000, 1),
            self.make_part("Второе слово.", "SPEAKER_01", 5000, 10000, 2),
            self.make_part("Третье слово.", "SPEAKER_00", 10000, 15000, 3),
        ]
        chunks = split_into_chunks(parts, meta)
        assert len(chunks) == 3
        assert chunks[0]["speaker"] == "SPEAKER_00"
        assert chunks[1]["speaker"] == "SPEAKER_01"
        assert chunks[2]["speaker"] == "SPEAKER_00"

    def test_empty_parts(self, meta):
        """Пустой список → пустой список чанков."""
        assert split_into_chunks([], meta) == []

    def test_part_with_empty_text_after_speaker_prefix(self, meta):
        """SPEAKER_00: без текста — чанк создаётся (текст = префикс)."""
        parts = [
            {"id": 1, "text": "SPEAKER_00: ", "speaker": "SPEAKER_00",
             "start_time": 0, "end_time": 5000},
        ]
        chunks = split_into_chunks(parts, meta)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "SPEAKER_00:"

    def test_time_conversion_ms_to_sec(self, meta):
        """start_time/end_time конвертируются из миллисекунд в секунды."""
        parts = [self.make_part("Текст.", "SPEAKER_00", 15000, 30000)]
        chunks = split_into_chunks(parts, meta)
        assert chunks[0]["start_time"] == 15.0
        assert chunks[0]["end_time"] == 30.0

    def test_missing_meta_fields(self, meta):
        """Отсутствующие поля meta — не падает."""
        meta_incomplete = {
            "id": meta["id"],
            "employee_id": meta["employee_id"],
        }
        parts = [self.make_part("Текст.")]
        chunks = split_into_chunks(parts, meta_incomplete)
        assert len(chunks) == 1
        assert chunks[0]["title"] == meta_incomplete.get("title", "")
        assert chunks[0]["meeting_type"] == meta_incomplete.get("meeting_type", "")
        assert chunks[0]["created_at"] == meta_incomplete.get("created_at", "")

    def test_employee_id_as_uuid(self, meta):
        """employee_id конвертируется в строку."""
        chunks = split_into_chunks([self.make_part("Текст.")], meta)
        assert isinstance(chunks[0]["employee_id"], str)

    def test_transcript_id_as_uuid(self, meta):
        """transcript_id конвертируется в строку."""
        chunks = split_into_chunks([self.make_part("Текст.")], meta)
        assert isinstance(chunks[0]["transcript_id"], str)

    def test_all_chunk_keys_present(self, meta):
        """Каждый чанк содержит все ожидаемые ключи."""
        required_keys = {
            "text", "transcript_id", "employee_id", "speaker",
            "start_time", "end_time", "meeting_type", "title", "created_at",
        }
        chunks = split_into_chunks(
            [self.make_part("Текст.", "SPEAKER_02", 1000, 2000)],
            meta,
        )
        assert required_keys == set(chunks[0].keys()), (
            f"Отсутствуют ключи: {required_keys - set(chunks[0].keys())}"
        )

    def test_speaker_field_used(self, meta):
        """speaker из part['speaker'] используется явно."""
        parts = [{
            "id": 1,
            "text": "Привет.",
            "speaker": "СПИКЕР_1",
            "start_time": 0,
            "end_time": 1000,
        }]
        chunks = split_into_chunks(parts, meta)
        assert chunks[0]["speaker"] == "СПИКЕР_1"


# =========================================================================
# update_task_status
# =========================================================================

class TestUpdateTaskStatus:
    """Тестируем обновление статуса задачи через БД."""

    def test_update_with_progress(self, mock_db_manager):
        """Обновление с прогрессом."""
        update_task_status("task-1", "processing", {"step": "transcription", "percent": 50})
        mock_db_manager.update_celery_task_status.assert_called_once_with(
            "task-1", "processing", {"step": "transcription", "percent": 50}
        )

    def test_update_without_progress(self, mock_db_manager):
        """Обновление без прогресса."""
        update_task_status("task-2", "completed")
        mock_db_manager.update_celery_task_status.assert_called_once_with(
            "task-2", "completed", None
        )

    def test_update_failed_status(self, mock_db_manager):
        """Обновление статуса failed."""
        update_task_status("task-3", "failed", {"error": "timeout"})
        mock_db_manager.update_celery_task_status.assert_called_once_with(
            "task-3", "failed", {"error": "timeout"}
        )


# =========================================================================
# _get_enrolled_speakers
# =========================================================================

class TestGetEnrolledSpeakers:
    """Тестируем получение списка зарегистрированных спикеров."""

    def test_returns_empty_when_import_error(self):
        """ImportError voice-модуля → пустой список."""
        with patch("app.voice.qdrant_profiles.list_all_profiles",
                   side_effect=ImportError("no voice module")):
            result = _get_enrolled_speakers()
            assert result == []

    def test_returns_empty_when_exception(self):
        """Любое исключение → пустой список."""
        with patch("app.voice.qdrant_profiles.list_all_profiles",
                   side_effect=RuntimeError("Qdrant down")):
            result = _get_enrolled_speakers()
            assert result == []

    def test_returns_profiles_when_available(self):
        """Нормальный ответ → список профилей."""
        expected = [
            {"full_name": "Иван Иванов", "user_id": "u1"},
            {"full_name": "Пётр Петров", "user_id": "u2"},
        ]
        with patch("app.voice.qdrant_profiles.list_all_profiles",
                   return_value=expected):
            result = _get_enrolled_speakers()
            assert result == expected

    def test_returns_empty_list(self):
        """Пустой список профилей."""
        with patch("app.voice.qdrant_profiles.list_all_profiles",
                   return_value=[]):
            result = _get_enrolled_speakers()
            assert result == []


# =========================================================================
# _apply_speaker_labels_to_parts
# =========================================================================

class TestApplySpeakerLabels:
    """Тестируем применение имён спикеров к частям транскрипции."""

    @pytest.fixture
    def mock_enrolled(self):
        """Подменяем _get_enrolled_speakers внутри модуля transcribe."""
        with patch("app.tasks.transcribe._get_enrolled_speakers") as mock:
            mock.return_value = [
                {"full_name": "Иван Иванов", "user_id": "u-ivan"},
                {"full_name": "Мария Петрова", "user_id": "u-maria"},
            ]
            yield mock

    def test_updates_parts_with_matched_speakers(
        self, mock_db_manager, mock_enrolled
    ):
        """SPEAKER_00 → Иван Иванов, employee_id проставляется."""
        from app.tasks.transcribe import _apply_speaker_labels_to_parts

        mock_db_manager.select_parts_transcription_by_transcript_id.return_value = [
            {"id": 1, "text": "SPEAKER_00: Привет всем."},
            {"id": 2, "text": "SPEAKER_01: Добрый день."},
        ]

        label_map = {"SPEAKER_00": "Иван Иванов", "SPEAKER_01": "Мария Петрова"}

        tid = UUID("770e8400-e29b-41d4-a716-446655440002")
        _apply_speaker_labels_to_parts(mock_db_manager, tid, label_map)

        # Проверяем что для SPEAKER_00 проставили имя + employee_id
        mock_db_manager.update_parts_transcription.assert_any_call(
            1, text="Иван Иванов: Привет всем.", employee_id="u-ivan"
        )
        mock_db_manager.update_parts_transcription.assert_any_call(
            2, text="Мария Петрова: Добрый день.", employee_id="u-maria"
        )

    def test_skips_unmatched_speakers(
        self, mock_db_manager, mock_enrolled
    ):
        """Неизвестный спикер — текст не меняется."""
        from app.tasks.transcribe import _apply_speaker_labels_to_parts

        mock_db_manager.select_parts_transcription_by_transcript_id.return_value = [
            {"id": 1, "text": "SPEAKER_XX: Какой-то текст."},
        ]

        _apply_speaker_labels_to_parts(
            mock_db_manager,
            UUID("770e8400-e29b-41d4-a716-446655440002"),
            {"SPEAKER_00": "Иван Иванов"},
        )

        # SPEAKER_XX нет в label_map — апдейта быть не должно
        mock_db_manager.update_parts_transcription.assert_not_called()

    def test_skips_part_without_colon(
        self, mock_db_manager, mock_enrolled
    ):
        """Часть без ':' в тексте — пропускается."""
        from app.tasks.transcribe import _apply_speaker_labels_to_parts

        mock_db_manager.select_parts_transcription_by_transcript_id.return_value = [
            {"id": 1, "text": "Какой-то текст без спикера"},
        ]

        _apply_speaker_labels_to_parts(
            mock_db_manager,
            UUID("770e8400-e29b-41d4-a716-446655440002"),
            {"SPEAKER_00": "Иван Иванов"},
        )

        mock_db_manager.update_parts_transcription.assert_not_called()


# =========================================================================
# _identify_speakers_by_embedding
# =========================================================================

class TestIdentifySpeakersByEmbedding:
    """Тестируем идентификацию спикеров по голосовым эмбеддингам."""

    TID = UUID("770e8400-e29b-41d4-a716-446655440002")

    @pytest.fixture
    def segments(self):
        return [{"Speaker": "SPEAKER_00", "start": 0, "stop": 10}]

    @pytest.fixture
    def enrolled(self):
        return [{"full_name": "Иван Иванов", "user_id": "u-ivan"}]

    @pytest.fixture
    def mock_voice_modules(self, mocker):
        """Мокаем voice-модули (эмбеддинги + Qdrant поиск)."""
        mock_extract = mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
            return_value=[0.1] * 192,
        )
        mock_search = mocker.patch(
            "app.voice.qdrant_profiles.search_speaker",
            return_value=("u-ivan", "Иван Иванов", 0.85),
        )
        return mock_extract, mock_search

    @pytest.fixture
    def mock_subprocess_success(self, mocker):
        """Мокаем subprocess.run — успешный ffmpeg, возвращает WAV."""
        mock_proc = MagicMock()
        mock_proc.stdout = b"\x00" * 32000  # 2 секунды 16kHz 16-bit
        mock_proc.check_returncode = MagicMock()
        return mocker.patch("subprocess.run", return_value=mock_proc)

    @pytest.fixture
    def mock_os_cleanup(self, mocker):
        """Мокаем os.unlink для очистки temp-файлов."""
        return mocker.patch("os.unlink")

    # --- Основные сценарии ---

    def test_empty_segments(self, mocker):
        """Пустые сегменты → пустой маппинг."""
        from app.tasks.transcribe import _identify_speakers_by_embedding

        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/audio.wav", [], [], dry_run=True
        )
        assert result == {}

    def test_voice_modules_not_available(self, mocker):
        """Voice-модули не импортируются → пустой маппинг."""
        from app.tasks.transcribe import _identify_speakers_by_embedding

        # Мокаем ImportError на уровне app.voice.speaker_identification
        mocker.patch("app.voice.speaker_identification.extract_embedding_from_wav_bytes",
                      side_effect=ImportError("no torch"))

        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/audio.wav",
            [{"Speaker": "SPK_00", "start": 0, "stop": 5}],
            [],
            dry_run=True,
        )
        assert result == {}

    def test_dry_run_with_match(
        self, mocker, segments, enrolled, mock_voice_modules, mock_subprocess_success
    ):
        """dry_run=True, спикер найден → маппинг без апдейта БД."""
        from app.tasks.transcribe import _identify_speakers_by_embedding

        db_mock = MagicMock()
        result = _identify_speakers_by_embedding(
            db_mock, self.TID, "/audio.wav", segments, enrolled, dry_run=True
        )
        assert result == {"SPEAKER_00": "Иван Иванов"}
        # БД не трогаем
        db_mock.select_parts_transcription_by_transcript_id.assert_not_called()

    def test_dry_run_no_match(
        self, mocker, segments, enrolled, mock_subprocess_success
    ):
        """dry_run=True, Qdrant ничего не нашёл → пустой маппинг."""
        mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
            return_value=[0.1] * 192,
        )
        mocker.patch(
            "app.voice.qdrant_profiles.search_speaker",
            return_value=None,  # не нашли
        )

        from app.tasks.transcribe import _identify_speakers_by_embedding
        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/audio.wav", segments, enrolled, dry_run=True
        )
        assert result == {}

    # --- Обработка ошибок ffmpeg ---

    def test_ffmpeg_called_process_error(
        self, mocker, segments, enrolled
    ):
        """Ошибка ffmpeg → логируется, спикер пропускается."""
        mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
            return_value=[0.1] * 192,
        )
        mocker.patch("app.voice.qdrant_profiles.search_speaker")

        mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(
            1, ["ffmpeg"], stderr=b"ffmpeg error"
        ))

        from app.tasks.transcribe import _identify_speakers_by_embedding
        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/bad.wav", segments, enrolled, dry_run=True
        )
        assert result == {}

    def test_ffmpeg_timeout(
        self, mocker, segments, enrolled
    ):
        """Таймаут ffmpeg → логируется, спикер пропускается."""
        mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
            return_value=[0.1] * 192,
        )
        mocker.patch("app.voice.qdrant_profiles.search_speaker")
        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(
            cmd=["ffmpeg"], timeout=120,
        ))

        from app.tasks.transcribe import _identify_speakers_by_embedding
        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/audio.wav", segments, enrolled, dry_run=True
        )
        assert result == {}

    # --- Обработка короткого/некачественного аудио ---

    def test_audio_too_short(
        self, mocker, segments, enrolled
    ):
        """WAV < 16000 байт (< 1 сек) → пропускается."""
        mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
        )
        mocker.patch("app.voice.qdrant_profiles.search_speaker")

        mock_proc = MagicMock()
        mock_proc.stdout = b"\x00" * 8000  # меньше секунды
        mock_proc.check_returncode = MagicMock()
        mocker.patch("subprocess.run", return_value=mock_proc)

        from app.tasks.transcribe import _identify_speakers_by_embedding
        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/audio.wav", segments, enrolled, dry_run=True
        )
        # Аудио слишком короткое — экстракция не вызывается
        assert result == {}

    def test_embedding_extraction_fails(
        self, mocker, segments, enrolled, mock_subprocess_success
    ):
        """Экстракция эмбеддинга вернула None → пропускается."""
        mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
            return_value=None,
        )
        mocker.patch("app.voice.qdrant_profiles.search_speaker")

        from app.tasks.transcribe import _identify_speakers_by_embedding
        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/audio.wav", segments, enrolled, dry_run=True
        )
        assert result == {}

    # --- Non-dry-run: обновление БД ---

    def test_non_dry_run_updates_db(
        self, mocker, enrolled, mock_voice_modules, mock_subprocess_success
    ):
        """dry_run=False, спикер найден → БД обновляется."""
        from app.tasks.transcribe import _identify_speakers_by_embedding

        db_mock = MagicMock()
        db_mock.select_parts_transcription_by_transcript_id.return_value = [
            {"id": 1, "text": "SPEAKER_00: Привет всем."},
            {"id": 2, "text": "SPEAKER_01: Добрый день."},
        ]

        segments = [
            {"Speaker": "SPEAKER_00", "start": 0, "stop": 10},
            {"Speaker": "SPEAKER_01", "start": 10, "stop": 20},
        ]

        result = _identify_speakers_by_embedding(
            db_mock, self.TID, "/audio.wav", segments, enrolled, dry_run=False
        )

        assert result == {"SPEAKER_00": "Иван Иванов", "SPEAKER_01": "Иван Иванов"}
        # SPEAKER_00 обновлён
        db_mock.update_parts_transcription.assert_any_call(
            1, text="Иван Иванов: Привет всем.", employee_id="u-ivan"
        )
        # SPEAKER_01 обновлён
        db_mock.update_parts_transcription.assert_any_call(
            2, text="Иван Иванов: Добрый день.", employee_id="u-ivan"
        )

    def test_non_dry_run_no_match_skips_db(
        self, mocker, enrolled, mock_subprocess_success
    ):
        """dry_run=False, совпадений нет → БД не трогается."""
        mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
            return_value=[0.1] * 192,
        )
        mocker.patch(
            "app.voice.qdrant_profiles.search_speaker",
            return_value=None,
        )

        from app.tasks.transcribe import _identify_speakers_by_embedding

        db_mock = MagicMock()
        result = _identify_speakers_by_embedding(
            db_mock, self.TID, "/audio.wav",
            [{"Speaker": "SPEAKER_00", "start": 0, "stop": 10}],
            enrolled, dry_run=False
        )
        assert result == {}
        db_mock.select_parts_transcription_by_transcript_id.assert_not_called()
        db_mock.update_parts_transcription.assert_not_called()

    # --- Несколько сегментов одного спикера ---

    def test_multiple_segments_merged(
        self, mocker, enrolled
    ):
        """Несколько сегментов одного спикера → склейка через concat."""
        mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
            return_value=[0.1] * 192,
        )
        mocker.patch(
            "app.voice.qdrant_profiles.search_speaker",
            return_value=("u-ivan", "Иван Иванов", 0.85),
        )
        mocker.patch("os.urandom", return_value=b"\xaa\xbb")
        mocker.patch("os.unlink")

        # Мокаем subprocess.run для concat path (multi-segment)
        # Первые вызовы — вырезаем части, последний — concat
        mock_proc = MagicMock()
        mock_proc.stdout = b"\x00" * 32000
        mock_proc.check_returncode = MagicMock()
        mocker.patch("subprocess.run", return_value=mock_proc)

        # Мокаем open для чтения merged.wav
        mock_wav_data = b"\x00" * 64000
        mock_open = mocker.mock_open(read_data=mock_wav_data)
        mocker.patch("builtins.open", mock_open)

        from app.tasks.transcribe import _identify_speakers_by_embedding

        segments = [
            {"Speaker": "SPEAKER_00", "start": 0, "stop": 30},
            {"Speaker": "SPEAKER_00", "start": 60, "stop": 90},
        ]

        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/audio.wav", segments, enrolled, dry_run=True
        )
        assert result == {"SPEAKER_00": "Иван Иванов"}

    def test_speaker_60_seconds_limit(
        self, mocker, enrolled
    ):
        """Не более 60 секунд аудио на спикера (MAX_SECONDS)."""
        mocker.patch(
            "app.voice.speaker_identification.extract_embedding_from_wav_bytes",
            return_value=[0.1] * 192,
        )
        mocker.patch(
            "app.voice.qdrant_profiles.search_speaker",
            return_value=("u-ivan", "Иван Иванов", 0.85),
        )

        mock_proc = MagicMock()
        mock_proc.stdout = b"\x00" * 32000
        mock_proc.check_returncode = MagicMock()
        run_mock = mocker.patch("subprocess.run", return_value=mock_proc)

        from app.tasks.transcribe import _identify_speakers_by_embedding

        # Один сегмент на 300 секунд — должно обрезаться до 60
        segments = [
            {"Speaker": "SPEAKER_00", "start": 0, "stop": 300},
        ]
        result = _identify_speakers_by_embedding(
            MagicMock(), self.TID, "/audio.wav", segments, enrolled, dry_run=True
        )
        assert result == {"SPEAKER_00": "Иван Иванов"}
        # ffmpeg должен быть вызван с -t 60, а не -t 300
        # Ищем вызов subprocess.run с аргументом "-t" и значением "60"
        found_60s = False
        for c in run_mock.call_args_list:
            if c.args and isinstance(c.args[0], list) and "-t" in c.args[0]:
                t_idx = c.args[0].index("-t")
                if t_idx + 1 < len(c.args[0]) and float(c.args[0][t_idx + 1]) == 60.0:
                    found_60s = True
                    break
        assert found_60s, "ffmpeg должен вызываться с -t 60 (MAX_SECONDS)"
