"""
Сервис для ответов на вопросы по тексту совещания.
Обёртка над LLMClient с бизнес-логикой Q&A.
"""
import logging
from typing import Optional, List
from services.llm_client import LLMClient
from config import settings

logger = logging.getLogger(__name__)


class QAService:
    """
    Сервис для ответов на вопросы по тексту совещания.
    
    Предоставляет методы для генерации ответов на вопросы
    пользователей на основе транскрипции совещания.
    """
    
    def __init__(self, llm_client: LLMClient = None):
        """
        Инициализация сервиса.
        
        Args:
            llm_client: Клиент для работы с LLM
        """
        self.llm = llm_client or LLMClient()
    
    def answer(
        self,
        text: str,
        question: str,
        model: str = None,
        include_context: bool = False
    ) -> dict:
        """
        Ответ на вопрос по тексту совещания.
        
        Args:
            text: Текст совещания
            question: Вопрос пользователя
            model: Модель LLM
            include_context: Включить контекст в ответ
            
        Returns:
            Словарь с полями: answer, question, model
            
        Raises:
            ValueError: Если текст или вопрос пустые
            RuntimeError: Если генерация ответа не удалась
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        logger.info(f"Вопрос: {question[:50]}...")
        
        try:
            answer = self.llm.answer_question(
                text=text,
                question=question,
                model=model
            )
            
            result = {
                "answer": answer,
                "question": question,
                "model": model or settings.default_llm_model
            }
            
            if include_context:
                result["context_length"] = len(text)
                result["answer_length"] = len(answer)
            
            logger.info(f"Ответ получен: {len(answer)} символов")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            raise RuntimeError(f"Q&A failed: {str(e)}") from e
    
    def answer_with_sources(
        self,
        text: str,
        question: str,
        segments: Optional[List[dict]] = None,
        model: str = None
    ) -> dict:
        """
        Ответ на вопрос с указанием источников (сегментов).
        
        Args:
            text: Текст совещания
            question: Вопрос пользователя
            segments: Сегменты транскрипции для поиска источников
            model: Модель LLM
            
        Returns:
            Словарь с полями: answer, sources, question
        """
        # Получаем ответ
        result = self.answer(text=text, question=question, model=model)
        
        # Пытаемся найти источники (сегменты)
        sources = []
        if segments:
            answer_lower = result["answer"].lower()
            
            for i, segment in enumerate(segments):
                segment_text = segment.get("text", "").lower()
                speaker = segment.get("speaker", "UNKNOWN")
                start = segment.get("start", 0)
                
                # Простая эвристика: если текст сегмента упоминается в ответе
                if segment_text and segment_text[:50] in answer_lower:
                    sources.append({
                        "segment_index": i,
                        "speaker": speaker,
                        "timestamp": f"{int(start // 60)}:{int(start % 60):02d}"
                    })
        
        result["sources"] = sources[:5]  # Максимум 5 источников
        return result
    
    def batch_answer(
        self,
        text: str,
        questions: List[str],
        model: str = None
    ) -> List[dict]:
        """
        Ответы на несколько вопросов.
        
        Args:
            text: Текст совещания
            questions: Список вопросов
            model: Модель LLM
            
        Returns:
            Список ответов
        """
        results = []
        
        for question in questions:
            try:
                result = self.answer(text=text, question=question, model=model)
                results.append(result)
            except Exception as e:
                logger.error(f"Ошибка при ответе на вопрос '{question}': {e}")
                results.append({
                    "question": question,
                    "answer": f"Ошибка: {str(e)}",
                    "error": True
                })
        
        return results
    
    def generate_follow_up_questions(
        self,
        text: str,
        num_questions: int = 3,
        model: str = None
    ) -> List[str]:
        """
        Генерация рекомендуемых дополнительных вопросов.
        
        Args:
            text: Текст совещания
            num_questions: Количество вопросов для генерации
            model: Модель LLM
            
        Returns:
            Список рекомендуемых вопросов
        """
        prompt = (
            f"На основе следующего текста совещания предложи "
            f"{num_questions} рекомендуемых дополнительных вопроса, "
            f"которые могут заинтересовать пользователя:\n\n{text}"
        )
        
        try:
            response = self.llm.client.chat.completions.create(
                model=model or settings.default_llm_model,
                messages=[
                    {"role": "system", "content": (
                        f"Сгенерируй {num_questions} кратких вопроса "
                        "по тексту совещания. Возвращай только вопросы, "
                        "каждый с новой строки."
                    )},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            questions_raw = response.choices[0].message.content.strip()
            questions = [
                q.strip().lstrip("1234567890.-)").strip()
                for q in questions_raw.split("\n")
                if q.strip()
            ]
            
            return questions[:num_questions]
            
        except Exception as e:
            logger.error(f"Ошибка генерации вопросов: {e}")
            return []
