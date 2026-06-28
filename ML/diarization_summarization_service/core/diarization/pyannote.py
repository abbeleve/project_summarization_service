"""
Реализация диаризации с помощью pyannote.audio.

Поддерживает настройку гиперпараметров:
  - VAD/segmentation: threshold, min_duration_on, min_duration_off
  - Clustering: threshold
  - min/max speakers
  - Overlap-aware сегментация
  - RMS-нормализация аудио перед диаризацией
  - Медианный фильтр для сглаживания переключений спикеров
"""
import logging
import torch
import torchaudio
import torchaudio.functional as F
from typing import Optional
from config import settings
from core.diarization.base import DiarizationBase, DiarizationSegment

logger = logging.getLogger(__name__)


class PyannoteDiarization(DiarizationBase):
    """
    Диаризация с использованием pyannote.audio.

    Использует предобученную модель для определения спикеров в аудио.
    Модель загружается лениво при первом вызове.
    """

    def __init__(
        self,
        model_path: str = None,
        sample_rate: int = None,
        min_segment_duration: float = None,
        segmentation_threshold: float = None,
        min_duration_on: float = None,
        min_duration_off: float = None,
        clustering_threshold: float = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        overlap: bool = None,
        normalize_audio: bool = None,
        median_filter_window: int = None,
    ):
        """
        Инициализация диаризации.

        Args:
            model_path: Путь к модели pyannote
            sample_rate: Частота дискретизации
            min_segment_duration: Минимальная длительность сегмента (сек)
            segmentation_threshold: Порог VAD/сегментации (0-1)
            min_duration_on: Мин. длительность speech-сегмента VAD
            min_duration_off: Мин. пауза для разрыва VAD-сегментов
            clustering_threshold: Порог кластеризации спикеров (0-1)
            min_speakers: Мин. число спикеров (None = авто)
            max_speakers: Макс. число спикеров (None = авто)
            overlap: Использовать overlap-aware сегментацию
            normalize_audio: RMS-нормализация перед диаризацией
            median_filter_window: Размер окна медианного фильтра (0 = откл)
        """
        self.model_path = model_path or settings.pyannote_model_path
        self.sample_rate = sample_rate or settings.sample_rate
        self.min_segment_duration = min_segment_duration or settings.min_segment_duration_sec
        self.segmentation_threshold = segmentation_threshold if segmentation_threshold is not None else settings.pyannote_segmentation_threshold
        self.min_duration_on = min_duration_on if min_duration_on is not None else settings.pyannote_min_duration_on
        self.min_duration_off = min_duration_off if min_duration_off is not None else settings.pyannote_min_duration_off
        self.clustering_threshold = clustering_threshold if clustering_threshold is not None else settings.pyannote_clustering_threshold
        self.min_speakers = min_speakers if min_speakers is not None else settings.pyannote_min_speakers
        self.max_speakers = max_speakers if max_speakers is not None else settings.pyannote_max_speakers
        self.overlap = overlap if overlap is not None else settings.pyannote_overlap
        self.normalize_audio = normalize_audio if normalize_audio is not None else settings.pyannote_normalize_audio
        self.median_filter_window = median_filter_window if median_filter_window is not None else settings.pyannote_median_filter_window
        self._pipeline: Optional[any] = None

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------

    def _load_pipeline(self):
        """Ленивая загрузка и настройка модели."""
        if self._pipeline is not None:
            return

        logger.info(
            f"Загрузка модели pyannote из {self.model_path} "
            f"(seg_threshold={self.segmentation_threshold}, "
            f"clustering_threshold={self.clustering_threshold}, "
            f"min_duration_on={self.min_duration_on}, "
            f"min_duration_off={self.min_duration_off}, "
            f"overlap={self.overlap})"
        )
        from pyannote.audio import Pipeline

        # Пробуем передать гиперпараметры через from_pretrained
        # (hydra instantiate: component={"param": value})
        pipeline_kwargs = {}
        try:
            pipeline_kwargs["sample_rate"] = self.sample_rate
            if self.segmentation_threshold is not None:
                pipeline_kwargs.setdefault("segmentation", {})["threshold"] = self.segmentation_threshold
            if self.min_duration_on is not None:
                pipeline_kwargs.setdefault("segmentation", {})["min_duration_on"] = self.min_duration_on
            if self.min_duration_off is not None:
                pipeline_kwargs.setdefault("segmentation", {})["min_duration_off"] = self.min_duration_off
            if self.clustering_threshold is not None:
                pipeline_kwargs.setdefault("clustering", {})["threshold"] = self.clustering_threshold

            self._pipeline = Pipeline.from_pretrained(
                self.model_path, **pipeline_kwargs
            ).to(torch.device("cuda"))
        except Exception as exc:
            logger.warning(
                "Не удалось передать гиперпараметры в from_pretrained "
                "(fallback к загрузке без параметров): %s", exc
            )
            self._pipeline = Pipeline.from_pretrained(self.model_path).to(torch.device("cuda"))

        # Fallback: пробуем установить параметры напрямую через атрибуты
        # (pyannote.audio 3.x хранит компоненты с суффиксом _)
        if self._pipeline is not None:
            self._apply_params_direct()

        logger.info("Модель pyannote загружена")

    def _apply_params_direct(self):
        """Пробует установить параметры напрямую на компоненты pipeline."""
        # --- Segmentation ---
        if hasattr(self._pipeline, "segmentation_"):
            seg = self._pipeline.segmentation_
            for attr, value in [
                ("threshold", self.segmentation_threshold),
                ("min_duration_on", self.min_duration_on),
                ("min_duration_off", self.min_duration_off),
            ]:
                if value is not None and hasattr(seg, attr):
                    try:
                        setattr(seg, attr, value)
                        logger.debug("segmentation_.%s = %s", attr, value)
                    except Exception as e:
                        logger.warning("Не удалось установить segmentation_.%s: %s", attr, e)
        elif hasattr(self._pipeline, "segmentation"):
            seg = self._pipeline.segmentation
            if isinstance(seg, dict):
                logger.warning("segmentation — dict, атрибуты не применимы")
            else:
                for attr, value in [
                    ("threshold", self.segmentation_threshold),
                    ("min_duration_on", self.min_duration_on),
                    ("min_duration_off", self.min_duration_off),
                ]:
                    if value is not None and hasattr(seg, attr):
                        try:
                            setattr(seg, attr, value)
                            logger.debug("segmentation.%s = %s", attr, value)
                        except Exception as e:
                            logger.warning("Не удалось установить segmentation.%s: %s", attr, e)

        # --- Clustering ---
        if hasattr(self._pipeline, "clustering_"):
            cl = self._pipeline.clustering_
            if self.clustering_threshold is not None and hasattr(cl, "threshold"):
                try:
                    setattr(cl, "threshold", self.clustering_threshold)
                    logger.debug("clustering_.threshold = %s", self.clustering_threshold)
                except Exception as e:
                    logger.warning("Не удалось установить clustering_.threshold: %s", e)
        elif hasattr(self._pipeline, "clustering"):
            cl = self._pipeline.clustering
            if not isinstance(cl, dict):
                if self.clustering_threshold is not None and hasattr(cl, "threshold"):
                    try:
                        setattr(cl, "threshold", self.clustering_threshold)
                        logger.debug("clustering.threshold = %s", self.clustering_threshold)
                    except Exception as e:
                        logger.warning("Не удалось установить clustering.threshold: %s", e)

    # ------------------------------------------------------------------
    # Audio preprocessing
    # ------------------------------------------------------------------

    @staticmethod
    def _rms_normalize(waveform: torch.Tensor, target_db: float = -23.0) -> torch.Tensor:
        """
        RMS-нормализация: приводит среднюю громкость к target_db (LUFS).

        Стабилизирует VAD: на тихих записях порог не будет «пропускать» речь,
        на громких — не будет схлопывать паузы в речь.
        """
        if waveform.numel() == 0:
            return waveform

        rms = torch.sqrt(torch.mean(waveform ** 2))
        if rms < 1e-10:
            return waveform  # тишина — не тянем

        target_amplitude = 10.0 ** (target_db / 20.0)
        gain = target_amplitude / rms
        return waveform * gain

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    def diarize(self, audio_path: str) -> list[DiarizationSegment]:
        """
        Выполняет диаризацию аудиофайла.

        Args:
            audio_path: Путь к аудиофайлу

        Returns:
            Список сегментов диаризации
        """
        try:
            self._load_pipeline()

            logger.info(f"Начало диаризации: {audio_path}")

            # 1. Загрузка аудио
            waveform, sample_rate = torchaudio.load(audio_path)

            # 2. RMS-нормализация (если включена)
            if self.normalize_audio:
                waveform = self._rms_normalize(waveform)
                logger.debug("RMS-нормализация применена")

            # 3. Выполнение диаризации с учётом min/max speakers
            pipeline_input = {"waveform": waveform, "sample_rate": sample_rate}
            pipeline_kwargs = {}
            if self.min_speakers is not None:
                pipeline_kwargs["min_speakers"] = self.min_speakers
            if self.max_speakers is not None:
                pipeline_kwargs["max_speakers"] = self.max_speakers

            output = self._pipeline(pipeline_input, **pipeline_kwargs)

            # 4. Парсинг результатов
            segments = []
            for turn, speaker in output.speaker_diarization:
                duration = turn.end - turn.start
                if duration > self.min_segment_duration:
                    segments.append(DiarizationSegment(
                        speaker=speaker,
                        start=turn.start,
                        stop=turn.end,
                    ))

            logger.info(
                "Диаризация завершена: %d сырых сегментов "
                "(min_speakers=%s, max_speakers=%s)",
                len(segments), self.min_speakers, self.max_speakers,
            )

            # 5. Объединение последовательных сегментов одного спикера
            segments = self.merge_consecutive_speakers(segments)

            # 6. Медианный фильтр для сглаживания переключений спикеров
            if self.median_filter_window > 0:
                segments = self.median_filter_speakers(
                    segments, window=self.median_filter_window
                )
                segments = self.merge_consecutive_speakers(segments)

            logger.info("Итоговых сегментов: %d", len(segments))
            return segments

        except FileNotFoundError:
            logger.error(f"Файл не найден: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        except Exception as e:
            logger.error(f"Ошибка диаризации: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Diarization failed: {str(e)}") from e
