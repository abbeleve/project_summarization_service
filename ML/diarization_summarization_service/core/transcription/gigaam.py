"""
Реализация транскрибации с помощью GigaAM.

Поддерживает два типа моделей:
  - Официальные модели GigaAM (v3_ctc и др.) через библиотеку gigaam
  - ONNX-модели (v3_e2e_rnnt, v3_e2e_ctc) через gigaam.onnx_utils (load_onnx / infer_onnx)
"""
import logging
from typing import Dict, List, Optional

import numpy as np
import librosa
import torch
import torchaudio
from tqdm import tqdm

from config import settings
from core.transcription.base import TranscriptionBase
from core.diarization.base import DiarizationSegment

logger = logging.getLogger(__name__)

RNNT_MAX_SAMPLES = 3_000_000
RNNT_OVERLAP = 16_000


class GigaamRnntOnnxModel:
    """
    Inference-обёртка для GigaAM v3_e2e_rnnt через ONNX Runtime.

    Использует gigaam.onnx_utils.load_onnx / infer_onnx.
    """

    def __init__(self, model_dir: str, model_version: str = "v3_e2e_rnnt", device: str = "cuda"):
        from gigaam.onnx_utils import load_onnx

        provider = "CUDAExecutionProvider" if device == "cuda" else "CPUExecutionProvider"
        logger.info(f"Загрузка ONNX модели {model_version} из {model_dir} (provider={provider})")

        self._sessions, self._model_cfg = load_onnx(model_dir, model_version, provider=provider)

        logger.info("ONNX сессии загружены")

    def transcribe(self, audio: np.ndarray) -> str:
        """Транскрибация одного аудио-массива (16kHz, моно)."""
        from gigaam.onnx_utils import infer_onnx

        result = infer_onnx([audio], self._model_cfg, self._sessions,
                            batch_size=1, progress=False)
        return result[0]

    def _infer_batch(self, chunks: list[np.ndarray]) -> list[str]:
        """Пакетная транскрибация нескольких numpy-массивов."""
        from gigaam.onnx_utils import infer_onnx

        return infer_onnx(chunks, self._model_cfg, self._sessions,
                          batch_size=len(chunks), progress=False)

    def transcribe_chunked(self, audio_path: str) -> str:
        from gigaam.onnx_utils import infer_onnx

        waveform, _ = librosa.load(audio_path, sr=16000, mono=True)

        chunks = []
        start = 0
        while start < len(waveform):
            end = min(start + RNNT_MAX_SAMPLES, len(waveform))
            chunks.append(waveform[start:end])
            if end == len(waveform):
                break
            start += RNNT_MAX_SAMPLES - RNNT_OVERLAP

        logger.info(
            f"Аудио разделено на {len(chunks)} чанк(ов) "
            f"(max {RNNT_MAX_SAMPLES / 16000:.1f}с, overlap {RNNT_OVERLAP / 16000:.1f}с)"
        )

        # Передаём numpy-массивы напрямую — AudioDataset не будет вызывать torchaudio.load
        results = infer_onnx(chunks, self._model_cfg, self._sessions,
                            batch_size=len(chunks), progress=False)

        return " ".join(results).strip()


class GigaamTranscription(TranscriptionBase):
    """
    Транскрибация с использованием GigaAM.

    Поддерживает:
      - Стандартные модели GigaAM (v3_ctc и др.) через библиотеку gigaam
      - ONNX-модели (v3_e2e_rnnt) через gigaam.onnx_utils
    """

    def __init__(self, sample_rate: int = None, chunk_duration: int = None):
        self.sample_rate = sample_rate or settings.sample_rate
        self.chunk_duration = chunk_duration or settings.chunk_duration_sec
        self._models_cache: Dict[str, any] = {}

    def _is_onnx_model(self, model_name: str) -> bool:
        """Проверяет, является ли модель ONNX-моделью (поддерживает .onnx файлы)."""
        return model_name in ("v3_e2e_rnnt", "v3_e2e_ctc")

    def _get_model(self, model_name: str) -> any:
        """Получение модели из кэша или загрузка новой."""
        if model_name not in self._models_cache:
            if self._is_onnx_model(model_name):
                logger.info(f"Загрузка ONNX модели GigaAM: {model_name}")
                # Определяем путь к модели по имени
                if model_name == "v3_e2e_ctc":
                    model_dir = settings.gigaam_ctc_model_path
                else:
                    model_dir = settings.gigaam_model_path
                model = GigaamRnntOnnxModel(
                    model_dir=model_dir,
                    model_version=model_name,
                    device="cuda",
                )
                self._models_cache[model_name] = model
                logger.info(f"ONNX модель {model_name} загружена из {model_dir}")
            else:
                logger.info(f"Загрузка библиотечной модели GigaAM: {model_name}")
                import gigaam
                self._models_cache[model_name] = gigaam.load_model(model_name, device="cuda")
                logger.info(f"Модель GigaAM {model_name} загружена в память")
        else:
            logger.debug(f"Модель GigaAM {model_name} уже в памяти (переиспользование)")
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
            logger.info(f"Начало транскрибации с помощью GigaAM ({model_name})")

            waveform, sr = torchaudio.load(audio_path)
            model = self._get_model(model_name)

            if self._is_onnx_model(model_name):
                self._transcribe_segments_onnx(model, waveform, sr, segments)
            else:
                for segment in tqdm(segments, desc="Транскрибация"):
                    segment.text = self._transcribe_segment(model, waveform, segment)

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

    def _transcribe_segments_onnx(
        self,
        model: GigaamRnntOnnxModel,
        waveform: torch.Tensor,
        sr: int,
        segments: list[DiarizationSegment],
    ):
        """Транскрибация сегментов ONNX моделью (numpy, без torchaudio.load)."""
        if sr != self.sample_rate:
            resampler = torchaudio.transforms.Resample(sr, self.sample_rate)
            waveform = resampler(waveform)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # Конвертируем в numpy один раз
        audio_np = waveform[0].numpy().astype(np.float32)

        for segment in tqdm(segments, desc="Транскрибация (ONNX)"):
            start = int(segment.start * self.sample_rate)
            end = int(segment.stop * self.sample_rate)

            if end - start == 0:
                segment.text = ""
                continue

            chunk = audio_np[start:end]

            if len(chunk) > RNNT_MAX_SAMPLES:
                # Для длинных сегментов — разбиваем на чанки вручную
                sub_chunks = []
                s = 0
                while s < len(chunk):
                    e = min(s + RNNT_MAX_SAMPLES, len(chunk))
                    sub_chunks.append(chunk[s:e])
                    if e == len(chunk):
                        break
                    s += RNNT_MAX_SAMPLES - RNNT_OVERLAP

                results = model._infer_batch(sub_chunks)
                segment.text = " ".join(results).strip()
            else:
                segment.text = model.transcribe(chunk)

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
