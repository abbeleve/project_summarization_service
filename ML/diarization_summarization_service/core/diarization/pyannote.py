"""
Реализация диаризации с помощью pyannote.audio.
"""
import logging
import torch
import torchaudio
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
        min_segment_duration: float = None
    ):
        """
        Инициализация диаризации.

        Args:
            model_path: Путь к модели pyannote
            sample_rate: Частота дискретизации
            min_segment_duration: Минимальная длительность сегмента (сек)
        """
        self.model_path = model_path or settings.pyannote_model_path
        self.sample_rate = sample_rate or settings.sample_rate
        self.min_segment_duration = min_segment_duration or settings.min_segment_duration_sec
        self._pipeline: Optional[any] = None

    def _load_pipeline(self):
        """Ленивая загрузка модели."""
        if self._pipeline is None:
            logger.info(f"Загрузка модели pyannote из {self.model_path}")
            from pyannote.audio import Pipeline
            self._pipeline = Pipeline.from_pretrained(self.model_path).to(torch.device("cuda"))
            logger.info("Модель pyannote загружена")

    def diarize(self, audio_path: str) -> list[DiarizationSegment]:
        """
        Выполняет диаризацию аудиофайла.

        Args:
            audio_path: Путь к аудиофайлу

        Returns:
            Список сегментов диаризации

        Raises:
            FileNotFoundError: Если файл не найден
            RuntimeError: Если диаризация не удалась
        """
        try:
            self._load_pipeline()

            logger.info(f"Начало диаризации: {audio_path}")

            # Загрузка аудио
            waveform, sample_rate = torchaudio.load(audio_path)

            # Выполнение диаризации
            output = self._pipeline({
                "waveform": waveform,
                "sample_rate": sample_rate
            })

            # Парсинг результатов
            segments = []
            for turn, speaker in output.speaker_diarization:
                duration = turn.end - turn.start

                # Фильтрация коротких артефактов
                if duration > self.min_segment_duration:
                    segment = DiarizationSegment(
                        speaker=speaker,
                        start=turn.start,
                        stop=turn.end
                    )
                    segments.append(segment)

            logger.info(f"Диаризация завершена: {len(segments)} сегментов")

            # Объединение последовательных сегментов одного спикера
            segments = self.merge_consecutive_speakers(segments)
            logger.info(f"После объединения: {len(segments)} сегментов")

            return segments

        except FileNotFoundError:
            logger.error(f"Файл не найден: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        except Exception as e:
            logger.error(f"Ошибка диаризации: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Diarization failed: {str(e)}") from e
