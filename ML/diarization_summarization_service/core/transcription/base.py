"""
Базовый класс для транскрибации аудио.
Определяет интерфейс для всех реализаций транскрибации.
"""
from abc import ABC, abstractmethod
from typing import List
from core.diarization.base import DiarizationSegment


class TranscriptionBase(ABC):
    """
    Базовый класс для транскрибации аудио.
    
    Все реализации транскрибации должны наследовать этот класс
    и реализовать метод transcribe().
    """
    
    @abstractmethod
    def transcribe(
        self, 
        segments: List[DiarizationSegment], 
        audio_path: str
    ) -> List[DiarizationSegment]:
        """
        Выполняет транскрибацию сегментов аудио.
        
        Args:
            segments: Список сегментов диаризации
            audio_path: Путь к аудиофайлу
            
        Returns:
            Список сегментов с заполненным текстом
            
        Raises:
            FileNotFoundError: Если файл не найден
            RuntimeError: Если транскрибация не удалась
        """
        pass
    
    def validate_audio_path(self, audio_path: str):
        """
        Валидация пути к аудиофайлу.
        
        Args:
            audio_path: Путь к файлу
            
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если файл пустой
        """
        import os
        
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        if os.path.getsize(audio_path) == 0:
            raise ValueError(f"Audio file is empty: {audio_path}")
