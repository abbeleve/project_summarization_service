"""
Реализация транскрибации с помощью GigaAM.
"""
import logging
import torch
import torchaudio
from tqdm import tqdm
from pathlib import Path
from typing import Dict, Optional
from config import settings
from core.transcription.base import TranscriptionBase
from core.diarization.base import DiarizationSegment

logger = logging.getLogger(__name__)


class GigaamTranscription(TranscriptionBase):
    """
    Транскрибация с использованием GigaAM.

    Поддерживает различные модели GigaAM для преобразования речи в текст.
    Модели кэшируются для переиспользования между запросами.
    """

    def __init__(
        self,
        sample_rate: int = None,
        chunk_duration: int = None
    ):
        """
        Инициализация транскрибации.

        Args:
            sample_rate: Частота дискретизации
            chunk_duration: Длительность чанка для транскрибации (сек)
        """
        self.sample_rate = sample_rate or settings.sample_rate
        self.chunk_duration = chunk_duration or settings.chunk_duration_sec
        self._models_cache: Dict[str, any] = {}
    
    def _get_model(self, model_name: str) -> any:
        """Получение модели из кэша или загрузка новой."""
        if model_name not in self._models_cache:
            logger.info(f"Загрузка модели GigaAM: {model_name}")
            import gigaam
            self._models_cache[model_name] = gigaam.load_model(model_name, device='cuda')
            logger.info(f"Модель GigaAM {model_name} загружена в память")
        else:
            logger.debug(f"Модель GigaAM {model_name} уже в памяти (переиспользование)")
        return self._models_cache[model_name]

    def transcribe(
        self,
        segments: list[DiarizationSegment],
        audio_path: str,
        model_name: str = "v3_ctc"
    ) -> list[DiarizationSegment]:
        """
        Выполняет транскрибацию сегментов аудио.

        Args:
            segments: Список сегментов диаризации
            audio_path: Путь к аудиофайлу
            model_name: Название модели GigaAM

        Returns:
            Список сегментов с заполненным текстом

        Raises:
            FileNotFoundError: Если файл не найден
            RuntimeError: Если транскрибация не удалась
        """
        try:
            self.validate_audio_path(audio_path)

            logger.info(f"Начало транскрибации с помощью GigaAM ({model_name})")

            # Загрузка аудио
            waveform, _ = torchaudio.load(audio_path)

            # Получение модели из кэша
            model = self._get_model(model_name)

            # Транскрибация каждого сегмента
            for index, segment in enumerate(tqdm(segments, desc="Транскрибация")):
                text = self._transcribe_segment(
                    model=model,
                    waveform=waveform,
                    segment=segment
                )
                segment.text = text

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
    
    def _transcribe_segment(
        self, 
        model, 
        waveform: torch.Tensor, 
        segment: DiarizationSegment
    ) -> str:
        """
        Транскрибация одного сегмента.
        
        Args:
            model: Модель GigaAM
            waveform: Аудиоволна
            segment: Сегмент для транскрибации
            
        Returns:
            Распознанный текст
        """
        # Извлечение чанка из волны
        start_sample = int(segment.start * self.sample_rate)
        end_sample = int(segment.stop * self.sample_rate)
        audio_chunk = waveform[:, start_sample:end_sample]
        
        if audio_chunk.shape[1] == 0:
            return ""
        
        resulted_transcription = ""
        
        # Транскрибация чанками по chunk_duration секунд
        chunk_samples = self.chunk_duration * self.sample_rate
        for chunk_start in range(0, audio_chunk.shape[1], chunk_samples):
            chunk = audio_chunk[:, chunk_start:chunk_start + chunk_samples]
            
            if chunk.shape[1] == 0:
                continue
            
            # Сохранение чанка во временный файл
            temp_chunk = Path("chunk.wav")
            torchaudio.save(uri=str(temp_chunk), src=chunk, sample_rate=self.sample_rate)
            
            # Транскрибация
            transcription = model.transcribe(str(temp_chunk))
            resulted_transcription += transcription
            
            # Очистка
            temp_chunk.unlink(missing_ok=True)
        
        return resulted_transcription
