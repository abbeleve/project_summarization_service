"""
Реализация транскрибации с помощью Whisper сервиса.
Отправляет запрос к внешнему сервису whisper_transcription_service.
"""
import json
import logging
import requests
from typing import List
from config import settings
from core.transcription.base import TranscriptionBase
from core.diarization.base import DiarizationSegment

logger = logging.getLogger(__name__)


class WhisperTranscription(TranscriptionBase):
    """
    Транскрибация с использованием Whisper сервиса.
    
    Использует внешний сервис для транскрибации через HTTP API.
    """
    
    def __init__(
        self,
        service_url: str = None,
        timeout: int = None
    ):
        """
        Инициализация транскрибации.

        Args:
            service_url: URL Whisper сервиса
            timeout: Таймаут запроса (сек). По умолчанию 1800 (30 мин).
        """
        self.service_url = service_url or settings.whisper_service_url
        self.timeout = timeout or settings.whisper_timeout_sec
    
    def transcribe(
        self,
        segments: List[DiarizationSegment],
        audio_path: str
    ) -> List[DiarizationSegment]:
        """
        Выполняет транскрибацию через внешний Whisper сервис.

        Args:
            segments: Список сегментов диаризации
            audio_path: Путь к аудиофайлу

        Returns:
            Список сегментов с заполненным текстом

        Raises:
            FileNotFoundError: Если файл не найден
            RuntimeError: Если транскрибация не удалась
        """
        try:
            self.validate_audio_path(audio_path)

            logger.info(f"Начало транскрибации через Whisper сервис: {audio_path}")
            logger.info(f"Whisper сервис URL: {self.service_url}")
            logger.info(f"Количество сегментов: {len(segments)}")

            # Отправка запроса к сервису
            with open(audio_path, "rb") as f:
                files = {"audio": (audio_path, f, "audio/wav")}
                data = {
                    "request": json.dumps({"diarization_results": [seg.to_dict() for seg in segments]})
                }

                logger.info(f"Отправка запроса к {self.service_url}")
                response = requests.post(
                    self.service_url,
                    files=files,
                    data=data,
                    timeout=self.timeout
                )

            logger.info(f"Статус ответа: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Whisper service error: {response.status_code} - {response.text}")
                raise RuntimeError(f"Whisper service error: {response.status_code} - {response.text}")

            # Парсинг ответа (Whisper сервис возвращает список сегментов)
            transcribed_segments = response.json()
            logger.info(f"Получено сегментов в ответе: {len(transcribed_segments)}")

            # Обновление сегментов текстом из ответа
            for i, segment in enumerate(segments):
                if i < len(transcribed_segments):
                    segment.text = transcribed_segments[i].get("Text", "")
                    logger.debug(f"Сегмент {i}: {segment.speaker} [{segment.start:.2f}-{segment.stop:.2f}] - {segment.text[:50]}...")

            logger.info(f"Транскрибация завершена: {len(segments)} сегментов")
            return segments

        except FileNotFoundError:
            logger.error(f"Файл не найден: {audio_path}")
            raise
        except requests.Timeout:
            logger.error(f"Таймаут запроса к Whisper сервису ({self.timeout} сек)")
            raise RuntimeError(f"Whisper service timeout after {self.timeout} seconds")
        except requests.ConnectionError as e:
            logger.error(f"Ошибка подключения к Whisper сервису ({self.service_url}): {e}")
            raise RuntimeError(f"Failed to connect to Whisper service at {self.service_url}: {str(e)}")
        except Exception as e:
            logger.error(f"Ошибка транскрибации: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Transcription failed: {str(e)}") from e
