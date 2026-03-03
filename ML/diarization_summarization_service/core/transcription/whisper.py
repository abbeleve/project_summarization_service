"""
Реализация транскрибации с помощью Whisper сервиса.
Отправляет запрос к внешнему сервису whisper_transcription_service.
"""
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
        timeout: int = 300
    ):
        """
        Инициализация транскрибации.
        
        Args:
            service_url: URL Whisper сервиса
            timeout: Таймаут запроса (сек)
        """
        self.service_url = service_url or settings.whisper_service_url
        self.timeout = timeout
    
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
            
            # Отправка запроса к сервису
            with open(audio_path, "rb") as f:
                files = {"file": (audio_path, f, "audio/wav")}
                data = {
                    "diarization_results": [seg.to_dict() for seg in segments]
                }
                
                response = requests.post(
                    self.service_url,
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
            
            if response.status_code != 200:
                raise RuntimeError(f"Whisper service error: {response.status_code} - {response.text}")
            
            # Парсинг ответа
            result = response.json()
            transcribed_segments = result.get("transcript", [])
            
            # Обновление сегментов
            for i, segment in enumerate(segments):
                if i < len(transcribed_segments):
                    segment.text = transcribed_segments[i].get("Text", "")
            
            logger.info(f"Транскрибация завершена: {len(segments)} сегментов")
            return segments
            
        except FileNotFoundError:
            logger.error(f"Файл не найден: {audio_path}")
            raise
        except requests.Timeout:
            logger.error(f"Таймаут запроса к Whisper сервису ({self.timeout} сек)")
            raise RuntimeError(f"Whisper service timeout after {self.timeout} seconds")
        except Exception as e:
            logger.error(f"Ошибка транскрибации: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Transcription failed: {str(e)}") from e
