"""
FastAPI приложение для транскрибации и суммаризации аудио.
Новая архитектура с разделением на модули.
"""
import logging
import sys
import torch
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes.transcribe import router as transcribe_router
from api.routes.transcribe_v2 import router as transcribe_v2_router
from api.routes.summarize import router as summarize_router
from dependencies import (
    get_diarization_singleton,
    get_transcription_singleton,
    get_audio_converter_singleton
)

# Настройка логирования
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | "
    "%(filename)s:%(lineno)d | %(funcName)s() | %(message)s"
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events для инициализации и очистки ресурсов.
    """
    # ===== Startup =====
    logger.info("=" * 50)
    logger.info("🚀 Запуск сервиса транскрибации и суммаризации")
    logger.info("=" * 50)
    logger.info(f"📍 Pyannote model path: {settings.pyannote_model_path}")
    logger.info(f"📍 Whisper model path: {settings.whisper_model_path}")
    logger.info(f"📍 OpenAI base URL: {settings.openai_base_url}")
    logger.info(f"📍 Allowed LLM models: {settings.allowed_llm_models}")
    logger.info(f"📍 Sample rate: {settings.sample_rate} Hz")
    logger.info(f"📍 Log level: {settings.log_level}")
    logger.info("=" * 50)

    # Предзагрузка singleton экземпляров
    logger.info("📦 Инициализация singleton экземпляров...")
    
    app.state.audio_converter = get_audio_converter_singleton()
    logger.info("✅ AudioConverter инициализирован")
    
    app.state.diarizer = get_diarization_singleton()
    logger.info("✅ PyannoteDiarization инициализирован")
    
    app.state.transcriber = get_transcription_singleton()
    logger.info("✅ GigaamTranscription инициализирован")

    logger.info("=" * 50)
    logger.info("✅ Сервис готов к работе")
    logger.info("=" * 50)

    yield

    # ===== Shutdown =====
    logger.info("🛑 Остановка сервиса...")

    # Очистка памяти GPU
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("🧹 GPU память очищена")

    logger.info("✅ Сервис остановлен")


# Создание приложения
app = FastAPI(
    title="Audio Transcription & Diarization Service",
    description="Сервис для транскрибации, диаризации и суммаризации аудио",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутов
app.include_router(transcribe_router)
app.include_router(transcribe_v2_router)
app.include_router(summarize_router)


# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    """Проверка здоровья сервиса."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "cuda_available": torch.cuda.is_available(),
        "device": "cuda" if torch.cuda.is_available() else "cpu"
    }


# Главная страница
@app.get("/", tags=["Root"])
async def root():
    """Информация о сервисе."""
    return {
        "name": "Audio Transcription & Diarization Service",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8053,
        reload=False,
        log_level=settings.log_level.lower()
    )
