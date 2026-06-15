"""
Реализация транскрибации с помощью GigaAM.

Все модели обрабатываются через отдельный микросервис onnx-gigaam,
чтобы изолировать CUDA-контекст ONNX Runtime от PyTorch (pyannote).
"""
import json
import logging
from typing import List

import requests

from config import settings
from core.transcription.base import TranscriptionBase
from core.diarization.base import DiarizationSegment

logger = logging.getLogger(__name__)


class GigaamOnnxHttpClient:
    """
    HTTP-клиент для GigaAM ONNX микросервиса.
    """

    def __init__(self, service_url: str = None, timeout: int = None):
        self.service_url = service_url or settings.gigaam_onnx_service_url
        self.timeout = timeout or settings.gigaam_onnx_timeout_sec

    def transcribe(
        self,
        segments: List[DiarizationSegment],
        audio_path: str,
    ) -> List[DiarizationSegment]:
        try:
            logger.info(
                f"Отправка {len(segments)} сегментов в GigaAM ONNX сервис: "
                f"{self.service_url}"
            )

            with open(audio_path, "rb") as f:
                files = {"audio": (audio_path, f, "audio/wav")}
                data = {
                    "request": json.dumps(
                        {"diarization_results": [seg.to_dict() for seg in segments]}
                    )
                }

                response = requests.post(
                    self.service_url,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )

            if response.status_code != 200:
                logger.error(
                    f"GigaAM ONNX service error: "
                    f"{response.status_code} - {response.text}"
                )
                raise RuntimeError(
                    f"GigaAM ONNX service error: "
                    f"{response.status_code} - {response.text}"
                )

            transcribed_segments = response.json()
            logger.info(
                f"Получено сегментов от GigaAM ONNX сервиса: "
                f"{len(transcribed_segments)}"
            )

            for i, segment in enumerate(segments):
                if i < len(transcribed_segments):
                    segment.text = transcribed_segments[i].get("Text", "")

            logger.info(
                f"Транскрибация через GigaAM ONNX сервис завершена: "
                f"{len(segments)} сегментов"
            )
            return segments

        except requests.Timeout:
            logger.error(
                f"Таймаут запроса к GigaAM ONNX сервису ({self.timeout} сек)"
            )
            raise RuntimeError(
                f"GigaAM ONNX service timeout after {self.timeout} seconds"
            )
        except requests.ConnectionError as e:
            logger.error(
                f"Ошибка подключения к GigaAM ONNX сервису "
                f"({self.service_url}): {e}"
            )
            raise RuntimeError(
                f"Failed to connect to GigaAM ONNX service "
                f"at {self.service_url}: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Ошибка транскрибации GigaAM ONNX: {e}")
            import traceback

            traceback.print_exc()
            raise RuntimeError(f"GigaAM ONNX transcription failed: {str(e)}") from e


class GigaamTranscription(TranscriptionBase):
    """
    Транскрибация с использованием GigaAM через микросервис onnx-gigaam.
    """

    _ALLOWED_MODELS = ("v3_e2e_rnnt", "v3_e2e_ctc")

    def __init__(self, sample_rate: int = None, chunk_duration: int = None):
        self.sample_rate = sample_rate or settings.sample_rate
        self.chunk_duration = chunk_duration or settings.chunk_duration_sec
        self._client: GigaamOnnxHttpClient = None

    def _get_client(self) -> GigaamOnnxHttpClient:
        if self._client is None:
            self._client = GigaamOnnxHttpClient()
        return self._client

    def transcribe(
        self,
        segments: list[DiarizationSegment],
        audio_path: str,
        model_name: str = "v3_e2e_rnnt",
    ) -> list[DiarizationSegment]:
        """
        Транскрибация сегментов через GigaAM ONNX микросервис.

        Args:
            segments: список сегментов диаризации
            audio_path: путь к аудиофайлу
            model_name: название модели (v3_e2e_rnnt, v3_e2e_ctc)

        Raises:
            ValueError: если model_name не из списка разрешённых
        """
        if model_name not in self._ALLOWED_MODELS:
            raise ValueError(
                f"Неподдерживаемая модель GigaAM: '{model_name}'. "
                f"Допустимые: {self._ALLOWED_MODELS}"
            )

        try:
            self.validate_audio_path(audio_path)
            logger.info(
                f"Транскрибация GigaAM ({model_name}) "
                f"через {settings.gigaam_onnx_service_url}"
            )

            client = self._get_client()
            client.transcribe(segments, audio_path)

            logger.info(f"Транскрибация завершена: {len(segments)} сегментов")
            return segments

        except FileNotFoundError:
            logger.error(f"Файл не найден: {audio_path}")
            raise
        except Exception as e:
            logger.error(f"Ошибка транскрибации: {e}")
            import traceback

            traceback.print_exc()
            raise RuntimeError(f"Transcription failed: {str(e)}") from e
