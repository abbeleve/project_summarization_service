"""
Роутер для CRM интеграций.
Управление API токенами и отправка задач в Weeek.
"""
import logging
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db_service.database import DataBaseManager, encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["CRM"])


# ===== Схемы =====

class ConnectCRMRequest(BaseModel):
    """Запрос на подключение CRM (сохранение API токена)."""
    api_token: str = Field(..., min_length=1, description="API токен Weeek для интеграции CRM")


class ConnectCRMResponse(BaseModel):
    """Ответ на подключение CRM."""
    status: str = Field(..., description="ok / error")
    message: str = Field(..., description="Описание результата")


class MeetingTaskOut(BaseModel):
    """Задача для фронтенда."""
    id: str
    summary_id: str
    description: str
    assignee: str
    deadline: str
    sent_to_crm: bool
    sent_at: Optional[str] = None
    crm_task_id: Optional[str] = None
    created_at: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    """Редактирование задачи."""
    assignee: Optional[str] = Field(None, description="Ответственный")
    deadline: Optional[str] = Field(None, description="Дедлайн")


class SendTaskResponse(BaseModel):
    """Ответ на отправку задачи в CRM."""
    status: str = Field(..., description="ok / error / already_sent")
    message: str = Field(..., description="Описание результата")
    crm_task_id: Optional[str] = Field(None, description="ID задачи в Weeek")


# ===== Вспомогательные функции =====

def _get_current_user_id(request: Request) -> UUID:
    """Извлекает user_id из JWT в request.state."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user in token")
    return UUID(user_id)


def _get_db() -> DataBaseManager:
    return DataBaseManager()


# ===== Эндпоинты для токенов =====

@router.post("/connect", response_model=ConnectCRMResponse)
async def connect_crm(body: ConnectCRMRequest, request: Request):
    """
    Сохранение API токена Weeek для текущего пользователя.
    Токен шифруется перед сохранением в БД.
    """
    user_id = _get_current_user_id(request)

    try:
        encrypted = encrypt_token(body.api_token)
    except Exception as e:
        logger.error(f"Failed to encrypt CRM token: {e}")
        raise HTTPException(status_code=500, detail="Failed to secure token")

    db = _get_db()
    success = db.update_staff(user_id, weeek_api_token=encrypted)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save CRM token")

    logger.info(f"CRM token saved for user {user_id}")
    return ConnectCRMResponse(status="ok", message="CRM API token saved successfully")


@router.delete("/connect", response_model=ConnectCRMResponse)
async def disconnect_crm(request: Request):
    """Удаление API токена Weeek (отключение CRM интеграции)."""
    user_id = _get_current_user_id(request)

    db = _get_db()
    success = db.update_staff(user_id, weeek_api_token=None)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to disconnect CRM")

    logger.info(f"CRM disconnected for user {user_id}")
    return ConnectCRMResponse(status="ok", message="CRM integration disconnected")


@router.get("/connect/status", response_model=dict)
async def crm_status(request: Request):
    """
    Проверка, подключена ли CRM интеграция у текущего пользователя.
    Возвращает только булево значение, токен НЕ отдаётся.
    """
    user_id = _get_current_user_id(request)
    db = _get_db()

    with db.session_scope() as session:
        from sqlalchemy import text
        result = session.execute(
            text("SELECT weeek_api_token IS NOT NULL AND weeek_api_token != '' AS has_token FROM \"Staff\" WHERE id = :uid"),
            {"uid": user_id}
        ).scalar()

    return {"connected": bool(result)}


# ===== Эндпоинты для задач (MeetingTasks) =====

@router.get("/tasks/{summary_id}", response_model=List[MeetingTaskOut])
async def get_tasks(summary_id: str, request: Request):
    """
    Получение списка задач для суммаризации.
    Каждая задача содержит флаг sent_to_crm.
    """
    _get_current_user_id(request)  # только проверка аутентификации
    db = _get_db()

    try:
        sid = UUID(summary_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid summary_id")

    tasks = db.select_meeting_tasks_by_summary_id(sid)
    return [MeetingTaskOut(**t) for t in tasks]


@router.patch("/tasks/{task_id}", response_model=MeetingTaskOut)
async def update_task(task_id: str, body: UpdateTaskRequest, request: Request):
    """
    Редактирование assignee и/или deadline задачи.
    Не влияет на sent_to_crm.
    """
    _get_current_user_id(request)
    db = _get_db()

    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    success = db.update_meeting_task(
        task_id=tid,
        assignee=body.assignee,
        deadline=body.deadline,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")

    task = db.select_meeting_task_by_id(tid)
    return MeetingTaskOut(**task)


@router.post("/tasks/{task_id}/send", response_model=SendTaskResponse)
async def send_task_to_crm(task_id: str, request: Request):
    """
    Отправка одной задачи в Weeek CRM.
    - Расшифровывает API токен пользователя
    - Вызывает Weeek API (POST /v1/tasks)
    - Помечает задачу как отправленную
    """
    user_id = _get_current_user_id(request)
    db = _get_db()

    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    # Получаем задачу
    task = db.select_meeting_task_by_id(tid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["sent_to_crm"]:
        return SendTaskResponse(
            status="already_sent",
            message="Task has already been sent to CRM",
            crm_task_id=task.get("crm_task_id"),
        )

    # Получаем токен пользователя
    staff = db.select_staff_by_id(user_id)
    if not staff:
        raise HTTPException(status_code=404, detail="User not found")

    # Достаём зашифрованный токен напрямую
    with db.session_scope() as session:
        from sqlalchemy import text as sa_text
        encrypted_token = session.execute(
            sa_text("SELECT weeek_api_token FROM \"Staff\" WHERE id = :uid"),
            {"uid": user_id}
        ).scalar()

    if not encrypted_token:
        raise HTTPException(status_code=400, detail="CRM not connected. Save API token first.")

    # Расшифровываем
    try:
        api_token = decrypt_token(encrypted_token)
    except Exception as e:
        logger.error(f"Failed to decrypt CRM token: {e}")
        raise HTTPException(status_code=500, detail="Failed to decrypt CRM token")

    # === ЗДЕСЬ БУДЕТ ВЫЗОВ WEEEK API ===
    # Пока заглушка: отмечаем задачу как отправленную без реального вызова
    crm_task_id = f"weeek-placeholder-{task_id[:8]}"
    logger.info(
        f"[CRM SEND] task={task_id}, user={user_id}, "
        f"desc={task['description'][:50]}, "
        f"token={api_token[:8]}..."
    )
    # TODO: POST https://api.weeek.net/public/v1/tasks
    #   headers: Authorization: Bearer {api_token}
    #   body: {name: task['description'], ...}

    success = db.mark_meeting_task_sent(task_id=tid, crm_task_id=crm_task_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to mark task as sent")

    return SendTaskResponse(
        status="ok",
        message="Task sent to Weeek CRM",
        crm_task_id=crm_task_id,
    )


@router.post("/tasks/{summary_id}/send-all", response_model=dict)
async def send_all_tasks(summary_id: str, request: Request):
    """
    Отправляет все неотправленные задачи суммаризации в CRM.
    """
    user_id = _get_current_user_id(request)
    db = _get_db()

    try:
        sid = UUID(summary_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid summary_id")

    # Проверяем, есть ли токен
    with db.session_scope() as session:
        from sqlalchemy import text as sa_text
        encrypted_token = session.execute(
            sa_text("SELECT weeek_api_token FROM \"Staff\" WHERE id = :uid"),
            {"uid": user_id}
        ).scalar()

    if not encrypted_token:
        raise HTTPException(status_code=400, detail="CRM not connected. Save API token first.")

    unsent = db.select_unsent_meeting_tasks(sid)

    sent_count = 0
    errors = []

    for task in unsent:
        try:
            task_id = UUID(task["id"])
            # Аналогично send_task_to_crm — пока заглушка
            crm_task_id = f"weeek-placeholder-{task['id'][:8]}"
            db.mark_meeting_task_sent(task_id=task_id, crm_task_id=crm_task_id)
            sent_count += 1
        except Exception as e:
            errors.append({"task_id": task["id"], "error": str(e)})

    return {
        "status": "ok" if not errors else "partial",
        "sent": sent_count,
        "total": len(unsent),
        "errors": errors,
    }
