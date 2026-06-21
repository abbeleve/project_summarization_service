"""
Роутер для CRM интеграций.
Временное хранение API токенов внешних CRM-систем.
"""
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.db_service.database import DataBaseManager, encrypt_token

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


# ===== Эндпоинты =====

@router.post("/connect", response_model=ConnectCRMResponse)
async def connect_crm(
    body: ConnectCRMRequest,
    request: Request,
):
    """
    Сохранение API токена Weeek для текущего пользователя.
    Токен шифруется перед сохранением в БД.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user in token")

    # Шифруем токен перед сохранением
    try:
        encrypted = encrypt_token(body.api_token)
    except Exception as e:
        logger.error(f"Failed to encrypt CRM token: {e}")
        raise HTTPException(status_code=500, detail="Failed to secure token")

    # Сохраняем в БД
    db = DataBaseManager()
    success = db.update_staff(
        UUID(user_id),
        weeek_api_token=encrypted,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to save CRM token")

    logger.info(f"CRM token saved for user {user_id}")
    return ConnectCRMResponse(
        status="ok",
        message="CRM API token saved successfully"
    )


@router.delete("/connect", response_model=ConnectCRMResponse)
async def disconnect_crm(
    request: Request,
):
    """
    Удаление API токена Weeek (отключение CRM интеграции).
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user in token")

    db = DataBaseManager()
    success = db.update_staff(
        UUID(user_id),
        weeek_api_token=None,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to disconnect CRM")

    logger.info(f"CRM disconnected for user {user_id}")
    return ConnectCRMResponse(
        status="ok",
        message="CRM integration disconnected"
    )


@router.get("/connect/status", response_model=dict)
async def crm_status(
    request: Request,
):
    """
    Проверка, подключена ли CRM интеграция у текущего пользователя.
    Возвращает только булево значение, токен НЕ отдаётся.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user in token")

    db = DataBaseManager()
    staff = db.select_staff_by_id(UUID(user_id))

    if not staff:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверяем наличие токена в RAW-запросе (to_dict не включает токен)
    # Используем прямой запрос к БД для проверки
    from app.db_service.database import Staff as StaffModel
    from sqlalchemy import text

    with db.session_scope() as session:
        result = session.execute(
            text("SELECT weeek_api_token IS NOT NULL AND weeek_api_token != '' AS has_token FROM \"Staff\" WHERE id = :uid"),
            {"uid": UUID(user_id)}
        ).scalar()

    return {"connected": bool(result)}
