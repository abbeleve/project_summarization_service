"""
Модуль с задачами Celery.
"""
from app.tasks.transcribe import transcribe_and_summarize_task

__all__ = ["transcribe_and_summarize_task"]
