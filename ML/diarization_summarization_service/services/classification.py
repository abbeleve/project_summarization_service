"""
Сервис для классификации типа совещания.
Обёртка над LLMClient с бизнес-логикой классификации.
"""
import logging
from typing import Optional
from services.llm_client import LLMClient
from config import settings

logger = logging.getLogger(__name__)


class ClassificationService:
    """
    Сервис для классификации типа совещания.
    
    Определяет тип совещания на основе текста транскрипции.
    Использует LLM с fallback на классификацию по ключевым словам.
    """
    
    def __init__(self, llm_client: LLMClient = None):
        """
        Инициализация сервиса.
        
        Args:
            llm_client: Клиент для работы с LLM
        """
        self.llm = llm_client or LLMClient()
    
    def classify(
        self,
        text: str,
        model: str = None,
        use_fallback: bool = True
    ) -> str:
        """
        Классификация типа совещания.
        
        Args:
            text: Текст совещания
            model: Модель LLM
            use_fallback: Использовать fallback при ошибке
            
        Returns:
            Тип совещания из разрешённого списка
            
        Raises:
            ValueError: Если текст пустой
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        logger.info(f"Классификация типа совещания ({len(text)} символов)")
        
        try:
            meeting_type = self.llm.classify_meeting_type(text=text, model=model)
            logger.info(f"Тип совещания определён: {meeting_type}")
            return meeting_type
            
        except Exception as e:
            logger.warning(f"LLM классификация не удалась: {e}")
            
            if use_fallback:
                logger.info("Используем fallback классификацию")
                return self._fallback_classification(text)
            else:
                raise
    
    def _fallback_classification(self, text: str) -> str:
        """
        Резервная классификация по ключевым словам.
        
        Args:
            text: Текст совещания
            
        Returns:
            Тип совещания
        """
        text_lower = text.lower()
        
        keywords_map = {
            "Оперативное совещание": [
                "статус", "задача", "срок", "блокер", "назначить",
                "отчёт", "план", "текущ", "еженедельн"
            ],
            "Стратегическое совещание": [
                "стратегия", "рынок", "цель", "план", "перспектива",
                "развитие", "долгосрочн", "видение", "миссия"
            ],
            "Финансовое совещание": [
                "бюджет", "расход", "доход", "квартал", "финансы",
                "q1", "q2", "q3", "q4", "прибыль", "убыток", "инвест"
            ],
            "HR-совещание": [
                "сотрудник", "зарплата", "собеседование", "мотивация",
                "увольнение", "hr", "кадры", "найм", "обучение"
            ],
            "Обзор проекта": [
                "проект", "этап", "риск", "клиент", "сдача", "одобрить",
                "демо", "презентация", "результат", "веха"
            ],
            "Экстренное совещание": [
                "авария", "ошибка", "срочно", "исправить", "падение",
                "критично", "инцидент", "проблем", "сбой"
            ]
        }
        
        scores = {}
        for meeting_type, keywords in keywords_map.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[meeting_type] = score
        
        if scores:
            result = max(scores, key=scores.get)
            logger.info(f"Fallback классификация: {result} (score={scores[result]})")
            return result
        
        logger.info("Fallback классификация: не определено")
        return "Не определено"
    
    def classify_with_confidence(
        self,
        text: str,
        model: str = None
    ) -> dict:
        """
        Классификация с оценкой уверенности.
        
        Args:
            text: Текст совещания
            model: Модель LLM
            
        Returns:
            Словарь с полями: meeting_type, confidence, method
        """
        # Попытка LLM классификации
        try:
            meeting_type = self.llm.classify_meeting_type(text=text, model=model)
            if meeting_type in self.llm.allowed_meeting_types:
                return {
                    "meeting_type": meeting_type,
                    "confidence": 0.9,  # Высокая уверенность для LLM
                    "method": "llm"
                }
        except Exception as e:
            logger.debug(f"LLM классификация не удалась: {e}")
        
        # Fallback
        meeting_type = self._fallback_classification(text)
        
        # Оценка уверенности fallback
        text_lower = text.lower()
        keywords_count = sum(
            1 for kw in [
                "статус", "задача", "срок", "бюджет", "проект",
                "сотрудник", "авария", "стратегия"
            ]
            if kw in text_lower
        )
        
        confidence = min(0.5 + (keywords_count * 0.1), 0.8)
        
        return {
            "meeting_type": meeting_type,
            "confidence": confidence,
            "method": "fallback"
        }
