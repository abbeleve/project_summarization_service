"""
Базовый класс для диаризации аудио.
Определяет интерфейс для всех реализаций диаризации.
"""
from abc import ABC, abstractmethod
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class DiarizationSegment:
    """
    Сегмент диаризации.
    
    Attributes:
        speaker: Идентификатор спикера (например, "SPEAKER_00")
        start: Время начала сегмента (секунды)
        stop: Время окончания сегмента (секунды)
        text: Текст сегмента (заполняется после транскрибации)
    """
    speaker: str
    start: float
    stop: float
    text: str = ""
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "Speaker": self.speaker,
            "start": self.start,
            "stop": self.stop,
            "Text": self.text
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "DiarizationSegment":
        """Создание из словаря."""
        return cls(
            speaker=data.get("Speaker", "UNKNOWN"),
            start=data.get("start", 0.0),
            stop=data.get("stop", 0.0),
            text=data.get("Text", "")
        )


class DiarizationBase(ABC):
    """
    Базовый класс для диаризации аудио.
    
    Все реализации диаризации должны наследовать этот класс
    и реализовать метод diarize().
    """
    
    @abstractmethod
    def diarize(self, audio_path: str) -> List[DiarizationSegment]:
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
        pass
    
    def merge_consecutive_speakers(
        self, 
        segments: List[DiarizationSegment],
        min_gap_sec: float = 0.1
    ) -> List[DiarizationSegment]:
        """
        Объединяет последовательные сегменты одного спикера.
        
        Args:
            segments: Список сегментов
            min_gap_sec: Минимальный разрыв между сегментами для объединения
            
        Returns:
            Список с объединёнными сегментами
        """
        if not segments:
            return []
        
        merged = []
        current = segments[0]
        
        for next_seg in segments[1:]:
            if (current.speaker == next_seg.speaker and 
                next_seg.start - current.stop < min_gap_sec):
                # Объединяем сегменты
                current = DiarizationSegment(
                    speaker=current.speaker,
                    start=current.start,
                    stop=next_seg.stop
                )
            else:
                merged.append(current)
                current = next_seg
        
        merged.append(current)
        return merged
