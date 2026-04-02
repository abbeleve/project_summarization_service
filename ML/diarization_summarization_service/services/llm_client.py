"""
Клиент для работы с LLM через OpenAI-compatible API.
Обёртка над OpenAI SDK с валидацией и обработкой ошибок.
"""
import logging
import json
from typing import Optional, Dict, Any, List
from openai import OpenAI
from config import settings
from prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Клиент для работы с LLM моделями.

    Поддерживает Gemini API и OpenAI-совместимые API
    для суммаризации, классификации и ответов на вопросы.
    """
    
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        prompts_path: str = "prompts/llm_prompts.yaml"
    ):
        """
        Инициализация клиента.
        
        Args:
            api_key: API ключ для LLM сервиса
            base_url: Базовый URL API
            prompts_path: Путь к файлу с промптами
        """
        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url
        self._client: Optional[OpenAI] = None
        self.prompts = PromptLoader(prompts_path)
        
        # Загрузка системных промптов
        self.system_summarization_prompt = self.prompts.get("summarization.system")
        self.summarization_prompt = self.prompts.get("summarization.user")
        self.system_keypoints_prompt = self.prompts.get("keypoints.system")
        self.keypoints_prompt = self.prompts.get("keypoints.user")
        self.system_questions_prompt = self.prompts.get("questions.system")
        self.questions_prompt = self.prompts.get("questions.user")
        self.system_summarization_json_prompt = self.prompts.get("summarization_json.system")
        self.classification_system_template = self.prompts.get("classification.system_template")
        
        # Загрузка онтологии
        with open("ontology.txt", "r", encoding="utf-8") as f:
            self.ontology_text = f.read()
        
        # Разрешённые типы совещаний
        self.allowed_meeting_types = {
            "Оперативное совещание",
            "Стратегическое совещание",
            "Финансовое совещание",
            "HR-совещание",
            "Обзор проекта",
            "Экстренное совещание"
        }
    
    @property
    def client(self) -> OpenAI:
        """Ленивая инициализация OpenAI клиента."""
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client
    
    def validate_model(self, model: str) -> bool:
        """
        Проверка разрешённости модели.
        
        Args:
            model: Название модели
            
        Returns:
            True если модель разрешена
        """
        return model in settings.allowed_llm_models
    
    def _parse_json_response(self, response: Any) -> Dict:
        """
        Парсинг JSON ответа от LLM.
        
        Args:
            response: Ответ от OpenAI API
            
        Returns:
            Распарсенный JSON
            
        Raises:
            RuntimeError: Если ответ не валидный JSON
        """
        raw = response.choices[0].message.content.strip()
        
        try:
            result = json.loads(raw)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Модель вернула невалидный JSON:\n{raw}")
            logger.error(f"Ошибка парсинга: {e}")
            raise RuntimeError(f"Model returned invalid JSON:\n{raw}") from e
    
    def summarize(
        self, 
        text: str, 
        model: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> Dict[str, Any]:
        """
        Суммаризация текста совещания.
        
        Args:
            text: Текст для суммаризации
            model: Модель LLM
            temperature: Температура генерации
            max_tokens: Максимум токенов
            
        Returns:
            Словарь с полями: title, summary, key_points
            
        Raises:
            ValueError: Если модель не разрешена
            RuntimeError: Если суммаризация не удалась
        """
        model = model or settings.default_llm_model
        temperature = temperature or settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_tokens
        
        if not self.validate_model(model):
            raise ValueError(f"Model {model} not allowed. Allowed: {settings.allowed_llm_models}")
        
        logger.info(f"Суммаризация текста ({len(text)} символов), модель: {model}")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.system_summarization_json_prompt},
                    {"role": "user", "content": f"Анализируй следующий текст совещания:\n\n{text}"}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "meeting_analysis",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "summary": {"type": "string"},
                                "key_points": {
                                    "type": "array", 
                                    "items": {"type": "string"}
                                },
                            },
                            "required": ["title", "summary", "key_points"]
                        }
                    },
                    # "plugins": [{"id": "response-healing"}]
                },
            )
            
            result = self._parse_json_response(response)
            
            # Валидация результата
            for key in ["title", "summary", "key_points"]:
                if key not in result:
                    raise ValueError(f"Отсутствует поле: {key}")
            
            if not isinstance(result["key_points"], list):
                raise ValueError("key_points должен быть списком")
            
            logger.info(f"Суммаризация завершена: {result.get('title', 'no title')}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка суммаризации: {e}")
            raise RuntimeError(f"Summarization failed: {str(e)}") from e
    
    def classify_meeting_type(
        self, 
        text: str, 
        model: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """
        Классификация типа совещания.
        
        Args:
            text: Текст совещания
            model: Модель LLM
            temperature: Температура генерации
            max_tokens: Максимум токенов
            
        Returns:
            Тип совещания из разрешённого списка
            
        Raises:
            RuntimeError: Если классификация не удалась
        """
        model = model or settings.default_llm_model
        temperature = temperature or settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_tokens
        
        logger.info(f"Классификация типа совещания, модель: {model}")
        
        # Форматирование промпта с онтологией
        system_prompt = self.prompts.format(
            "classification.system_template",
            ontology=self.ontology_text
        )
        
        if not system_prompt:
            raise RuntimeError("Prompt 'classification.system_template' not found")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Текст совещания:\n{text}"}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            raw = response.choices[0].message.content.strip()
            
            # Проверка на допустимый тип
            if raw in self.allowed_meeting_types:
                logger.info(f"Классификация завершена: {raw}")
                return raw
            else:
                # Fallback на ключевые слова
                logger.warning(f"Модель вернула недопустимый тип: {raw}. Используем fallback.")
                return self._fallback_classification(text)
            
        except Exception as e:
            logger.error(f"Ошибка классификации: {e}")
            # Fallback на ключевые слова
            return self._fallback_classification(text)
    
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
                "статус", "задача", "срок", "блокер", "назначить"
            ],
            "Стратегическое совещание": [
                "стратегия", "рынок", "цель", "план", "перспектива"
            ],
            "Финансовое совещание": [
                "бюджет", "расход", "доход", "квартал", "финансы", 
                "q1", "q2", "q3", "q4"
            ],
            "HR-совещание": [
                "сотрудник", "зарплата", "собеседование", "мотивация", 
                "увольнение", "hr"
            ],
            "Обзор проекта": [
                "проект", "этап", "риск", "клиент", "сдача", "одобрить"
            ],
            "Экстренное совещание": [
                "авария", "ошибка", "срочно", "исправить", "падение", "критично"
            ]
        }
        
        scores = {}
        for meeting_type, keywords in keywords_map.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[meeting_type] = score
        
        if scores:
            result = max(scores, key=scores.get)
            logger.info(f"Fallback классификация: {result}")
            return result
        
        logger.info("Fallback классификация: не определено")
        return "Не определено"
    
    def answer_question(
        self, 
        text: str, 
        question: str, 
        model: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """
        Ответ на вопрос по тексту совещания.
        
        Args:
            text: Текст совещания
            question: Вопрос пользователя
            model: Модель LLM
            temperature: Температура генерации
            max_tokens: Максимум токенов
            
        Returns:
            Ответ на вопрос
            
        Raises:
            ValueError: Если текст или вопрос пустые
            RuntimeError: Если генерация ответа не удалась
        """
        if not text:
            raise ValueError("Text cannot be empty")
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        model = model or settings.default_llm_model
        temperature = temperature or settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_tokens
        
        logger.info(f"Ответ на вопрос (модель: {model}): {question[:50]}...")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.system_questions_prompt},
                    {"role": "user", "content": (
                        f"{self.questions_prompt}\n\n"
                        f"Текст совещания:\n{text}\n\n"
                        f"Вопрос от пользователя:\n{question}"
                    )}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            answer = response.choices[0].message.content.strip()
            logger.info(f"Ответ получен: {len(answer)} символов")
            return answer
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            raise RuntimeError(f"Q&A failed: {str(e)}") from e
