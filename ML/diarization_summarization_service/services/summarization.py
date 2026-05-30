"""
Сервис для суммаризации текста совещаний.
Обёртка над LLMClient с дополнительной бизнес-логикой.
"""
import logging
from typing import Dict, Any, Optional, List
from services.llm_client import LLMClient
from config import settings

logger = logging.getLogger(__name__)


class SummarizationService:
    """
    Сервис для суммаризации текста совещаний.
    
    Предоставляет методы для получения краткого содержания,
    ключевых пунктов и заголовка совещания.
    """
    
    def __init__(self, llm_client: LLMClient = None):
        """
        Инициализация сервиса.
        
        Args:
            llm_client: Клиент для работы с LLM
        """
        self.llm = llm_client or LLMClient()
    
    def summarize(
        self,
        text: str,
        model: str = None,
        include_title: bool = True,
        include_key_points: bool = True
    ) -> Dict[str, Any]:
        """
        Суммаризация текста совещания.
        
        Args:
            text: Текст для суммаризации
            model: Модель LLM
            include_title: Включить заголовок
            include_key_points: Включить ключевые пункты
            
        Returns:
            Словарь с полями: title, summary, key_points
            
        Raises:
            ValueError: Если текст пустой
            RuntimeError: Если суммаризация не удалась
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        logger.info(f"Запрос суммаризации текста ({len(text)} символов)")
        
        result = self.llm.summarize(text=text, model=model)
        
        # Пост-обработка результата
        if not include_title and "title" in result:
            del result["title"]
        
        if not include_key_points and "key_points" in result:
            del result["key_points"]
        
        return result
    
    def get_summary_text(
        self,
        text: str,
        model: str = None
    ) -> str:
        """
        Получение только текста суммаризации.
        
        Args:
            text: Текст для суммаризации
            model: Модель LLM
            
        Returns:
            Текст суммаризации
        """
        result = self.summarize(text=text, model=model)
        return result.get("summary", "")
    
    def get_key_points(
        self,
        text: str,
        model: str = None
    ) -> List[str]:
        """
        Получение ключевых пунктов совещания.
        
        Args:
            text: Текст совещания
            model: Модель LLM
            
        Returns:
            Список ключевых пунктов
        """
        result = self.summarize(text=text, model=model)
        return result.get("key_points", [])
    
    def get_title(
        self,
        text: str,
        model: str = None
    ) -> str:
        """
        Получение заголовка совещания.
        
        Args:
            text: Текст совещания
            model: Модель LLM
            
        Returns:
            Заголовок совещания
        """
        result = self.summarize(text=text, model=model)
        return result.get("title", "Без названия")
    
    def summarize_with_meeting_type(
        self,
        text: str,
        model: str = None,
        classify_first: bool = True
    ) -> Dict[str, Any]:
        """
        Суммаризация с определением типа совещания.
        
        Args:
            text: Текст совещания
            model: Модель LLM
            classify_first: Сначала определить тип
            
        Returns:
            Словарь с полями: title, summary, key_points, meeting_type
        """
        result = self.summarize(text=text, model=model)
        
        if classify_first:
            from services.classification import ClassificationService
            classifier = ClassificationService(self.llm)
            meeting_type = classifier.classify(text=text, model=model)
            result["meeting_type"] = meeting_type
        else:
            result["meeting_type"] = "Не определено"
        
        return result
