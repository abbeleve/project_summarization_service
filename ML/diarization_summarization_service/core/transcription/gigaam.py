"""
Реализация транскрибации с помощью GigaAM.

Поддерживает два типа моделей:
  - Официальные модели GigaAM (v3_ctc и др.) через библиотеку gigaam
  - ONNX-модели (v3_e2e_rnnt, v3_e2e_ctc) через HTTP-клиент к отдельному микросервису
    (onnx-gigaam), чтобы изолировать CUDA-контекст ONNX Runtime от PyTorch (pyannote).
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import requests
import torch
import torchaudio
from tqdm import tqdm

from config import settings
from core.transcription.base import TranscriptionBase
from core.diarization.base import DiarizationSegment

logger = logging.getLogger(__name__)


class GigaamOnnxHttpClient:
    """
    HTTP-клиент для GigaAM ONNX микросервиса.

    Отправляет аудиофайл + сегменты на onnx-gigaam:8056/transcribe,
    получает сегменты с заполненным текстом.
    """

    def __init__(self, service_url: str = None, timeout: int = None):
        self.service_url = service_url or settings.gigaam_onnx_service_url
        self.timeout = timeout or settings.gigaam_onnx_timeout_sec

    def transcribe(
        self,
        segments: List[DiarizationSegment],
        audio_path: str,
    ) -> List[DiarizationSegment]:
        """
        Транскрибация сегментов через GigaAM ONNX микросервис.

        Args:
            segments: Список сегментов диаризации
            audio_path: Путь к аудиофайлу

        Returns:
            Список сегментов с заполненным текстом
        """
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
    Транскрибация с использованием GigaAM.

    Поддерживает:
      - Стандартные модели GigaAM (v3_ctc и др.) через библиотеку gigaam
      - ONNX-модели (v3_e2e_rnnt, v3_e2e_ctc) через HTTP-клиент к микросервису
    """

    def __init__(self, sample_rate: int = None, chunk_duration: int = None):
        self.sample_rate = sample_rate or settings.sample_rate
        self.chunk_duration = chunk_duration or settings.chunk_duration_sec
        self._models_cache: Dict[str, any] = {}

    def _is_onnx_model(self, model_name: str) -> bool:
        """Проверяет, является ли модель ONNX-моделью (требует микросервис)."""
        return model_name in ("v3_e2e_rnnt", "v3_e2e_ctc")

    def _get_model(self, model_name: str) -> any:
        """Получение модели из кэша или загрузка новой."""
        if model_name not in self._models_cache:
            if self._is_onnx_model(model_name):
                logger.info(
                    f"Создание HTTP-клиента для ONNX модели GigaAM: {model_name}"
                )
                model = GigaamOnnxHttpClient()
                self._models_cache[model_name] = model
                logger.info(
                    f"HTTP-клиент для {model_name} создан "
                    f"(URL: {settings.gigaam_onnx_service_url})"
                )
            else:
                logger.info(
                    f"Загрузка библиотечной модели GigaAM: {model_name}"
                )
                import gigaam

                self._models_cache[model_name] = gigaam.load_model(
                    model_name, device="cuda"
                )
                logger.info(
                    f"Модель GigaAM {model_name} загружена в память"
                )
        else:
            logger.debug(
                f"Модель GigaAM {model_name} уже в памяти (переиспользование)"
            )
        return self._models_cache[model_name]

    def transcribe(
        self,
        segments: list[DiarizationSegment],
        audio_path: str,
        model_name: str = "v3_e2e_rnnt",
    ) -> list[DiarizationSegment]:
        """
        Выполняет транскрибацию сегментов аудио.

        Args:
            segments: список сегментов диаризации
            audio_path: путь к аудиофайлу
            model_name: название модели GigaAM

        Returns:
            список сегментов с заполненным текстом
        """
        try:
            self.validate_audio_path(audio_path)
            logger.info(
                f"Начало транскрибации с помощью GigaAM ({model_name})"
            )

            model = self._get_model(model_name)

            if self._is_onnx_model(model_name):
                # ONNX модели — через HTTP к микросервису (без локального ORT)
                model.transcribe(segments, audio_path)
            else:
                # Библиотечные модели GigaAM — локально
                waveform, sr = torchaudio.load(audio_path)
                for segment in tqdm(segments, desc="Транскрибация"):
                    segment.text = self._transcribe_segment(
                        model, waveform, segment
                    )

            logger.info(
                f"Транскрибация завершена: {len(segments)} сегментов"
            )
            return segments

        except FileNotFoundError:
            logger.error(f"Файл не найден: {audio_path}")
            raise
        except Exception as e:
            logger.error(f"Ошибка транскрибации: {e}")
            import traceback

            traceback.print_exc()
            raise RuntimeError(f"Transcription failed: {str(e)}") from e

    def _transcribe_segment(
        self,
        model,
        waveform: torch.Tensor,
        segment: DiarizationSegment,
    ) -> str:
        """
        Транскрибация одного сегмента (для библиотечной модели GigaAM).
        """
        start = int(segment.start * self.sample_rate)
        end = int(segment.stop * self.sample_rate)
        chunk = waveform[:, start:end]

        if chunk.shape[1] == 0:
            return ""

        result = ""
        chunk_samples = self.chunk_duration * self.sample_rate

        for offset in range(0, chunk.shape[1], chunk_samples):
            sub = chunk[:, offset : offset + chunk_samples]
            if sub.shape[1] == 0:
                continue

            tmp = Path("chunk.wav")
            torchaudio.save(uri=str(tmp), src=sub, sample_rate=self.sample_rate)
            result += model.transcribe(str(tmp))
            tmp.unlink(missing_ok=True)

        return result
