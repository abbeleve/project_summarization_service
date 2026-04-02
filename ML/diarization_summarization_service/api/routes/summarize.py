"""
API роуты для суммаризации, классификации и Q&A.
"""
import logging
from fastapi import APIRouter, Form, HTTPException, Request
from api.schemas.summarize import (
    SummarizeRequest,
    SummarizeResponse,
    ClassifyRequest,
    ClassifyResponse,
    AskRequest,
    AskResponse,
    LLMPipelineRequest,
    LLMPipelineResponse
)
from services.llm_client import LLMClient
from services.summarization import SummarizationService
from services.classification import ClassificationService
from services.qa import QAService
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["LLM"])


# ===== Суммаризация =====

@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    input_text: str = Form(..., description="Текст для суммаризации"),
    llm_model: str = Form("gemini-2.5-flash", description="Модель LLM")
):
    """
    Суммаризация текста совещания.
    
    Возвращает заголовок, краткое содержание и ключевые пункты.
    """
    try:
        llm_client = LLMClient()
        service = SummarizationService(llm_client)
        
        result = service.summarize(text=input_text, model=llm_model)
        
        return SummarizeResponse(
            title=result.get("title", ""),
            summary=result.get("summary", ""),
            key_points=result.get("key_points", []),
            meeting_type=None
        )
        
    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        logger.error(f"Ошибка суммаризации: {e}")
        raise HTTPException(500, str(e))


# ===== Классификация =====

@router.post("/classify_meeting_type", response_model=ClassifyResponse)
async def classify_meeting_type(
    input_text: str = Form(..., description="Текст совещания"),
    llm_model: str = Form("gemini-2.5-flash", description="Модель LLM")
):
    """
    Классификация типа совещания.
    
    Возвращает тип совещания из разрешённого списка.
    """
    try:
        llm_client = LLMClient()
        service = ClassificationService(llm_client)
        
        meeting_type = service.classify(text=input_text, model=llm_model)
        
        return ClassifyResponse(meeting_type=meeting_type)
        
    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Ошибка классификации: {e}")
        raise HTTPException(500, str(e))


# ===== LLM Pipeline (суммаризация + классификация) =====

@router.post("/llm_pipeline", response_model=LLMPipelineResponse)
async def llm_pipeline(
    input_text: str = Form(..., description="Текст совещания"),
    llm_model: str = Form("gemini-2.5-flash", description="Модель LLM"),
    summarization_usage: bool = Form(True, description="Использовать суммаризацию"),
    classification_usage: bool = Form(True, description="Использовать классификацию")
):
    """
    Полный пайплайн LLM: суммаризация + классификация типа совещания.
    """
    try:
        llm_client = LLMClient()
        summary_service = SummarizationService(llm_client)
        classification_service = ClassificationService(llm_client)
        
        result = {}
        meeting_type = None
        
        if summarization_usage:
            summary_result = summary_service.summarize(text=input_text, model=llm_model)
            result = summary_result
        
        if classification_usage:
            meeting_type = classification_service.classify(text=input_text, model=llm_model)
        
        # Добавляем тип совещания к результату суммаризации
        if result:
            result["meeting_type"] = meeting_type
        
        return LLMPipelineResponse(
            summary=result if result else None,
            meeting_type=meeting_type
        )
        
    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        logger.error(f"Ошибка пайплайна: {e}")
        raise HTTPException(500, str(e))


# ===== Q&A =====

@router.post("/ask", response_model=AskResponse)
async def ask(
    request: Request
):
    """
    Ответ на вопрос по тексту совещания.
    
    Принимает JSON с полями: text, question, llm_model
    """
    try:
        body = await request.json()
        
        text = body.get("text")
        question = body.get("question")
        llm_model = body.get("llm_model", settings.default_llm_model)
        
        if not text:
            raise HTTPException(400, "'text' must be provided and non-empty")
        if not question or not question.strip():
            raise HTTPException(400, "'question' must be provided and non-empty")
        
        llm_client = LLMClient()
        service = QAService(llm_client)
        
        result = service.answer(text=text, question=question, model=llm_model)
        
        return AskResponse(answer=result["answer"])
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        logger.error(f"Ошибка генерации ответа: {e}")
        raise HTTPException(500, str(e))
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Invalid request: {str(e)}")
