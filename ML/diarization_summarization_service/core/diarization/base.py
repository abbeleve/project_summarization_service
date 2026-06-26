"""
Базовый класс для диаризации аудио.
Определяет интерфейс для всех реализаций диаризации.
"""
from abc import ABC, abstractmethod
from typing import List, Dict
from collections import Counter
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

    def median_filter_speakers(
        self,
        segments: List[DiarizationSegment],
        window: int = 3,
    ) -> List[DiarizationSegment]:
        """
        Сглаживает переключения спикеров медианным (majority-vote) фильтром.

        Для каждого сегмента берётся окно соседних сегментов размера ``window``,
        и метка спикера заменяется на наиболее частую в этом окне.
        Убирает «дребезг» — одиночные SPEAKER_00 посреди SPEAKER_01.

        Args:
            segments: Входные сегменты (должны быть отсортированы по времени)
            window: Размер окна (нечётное, >= 3). Если чётное, увеличивается на 1.

        Returns:
            Сглаженные сегменты (количество не меняется, только метки)
        """
        if len(segments) < 3 or window < 3:
            return segments

        # Приводим к нечётному
        if window % 2 == 0:
            window += 1

        half = window // 2
        n = len(segments)
        labels = [seg.speaker for seg in segments]

        smoothed = list(labels)
        for i in range(n):
            left = max(0, i - half)
            right = min(n, i + half + 1)
            window_labels = labels[left:right]
            most_common = Counter(window_labels).most_common(1)[0][0]
            smoothed[i] = most_common

        result = []
        for seg, new_speaker in zip(segments, smoothed):
            result.append(DiarizationSegment(
                speaker=new_speaker,
                start=seg.start,
                stop=seg.stop,
            ))

        return result
