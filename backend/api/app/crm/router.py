"""
Роутер для CRM интеграций.
Управление API токенами, проектами Weeek и отправка задач.
"""
import logging
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import httpx

from app.db_service.database import DataBaseManager, encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["CRM"])

WEEEK_API_BASE = "https://api.weeek.net/public/v1"


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
    description: Optional[str] = Field(None, description="Описание задачи")
    assignee: Optional[str] = Field(None, description="Ответственный")
    deadline: Optional[str] = Field(None, description="Дедлайн")


class SendTaskRequest(BaseModel):
    """Тело запроса на отправку задачи в CRM."""
    project_id: Optional[int] = Field(None, description="ID проекта Weeek для привязки задачи")
    board_column_id: Optional[int] = Field(None, description="ID колонки доски Weeek (boardColumnId)")
    user_id: Optional[str] = Field(None, description="ID пользователя Weeek для назначения задачи (делегирование)")
    deadline: Optional[str] = Field(None, description="Дата дедлайна (локальный выбор пользователя, не сохраняется в БД)")


class SendTaskResponse(BaseModel):
    """Ответ на отправку задачи в CRM."""
    status: str = Field(..., description="ok / error / already_sent")
    message: str = Field(..., description="Описание результата")
    crm_task_id: Optional[str] = Field(None, description="ID задачи в Weeek")


class WeeekProjectOut(BaseModel):
    """Проект Weeek для фронтенда."""
    id: int
    name: str
    color: Optional[str] = None
    is_private: Optional[bool] = None


class ProjectsListResponse(BaseModel):
    """Ответ со списком проектов."""
    projects: List[WeeekProjectOut]


class WeeekBoardOut(BaseModel):
    """Доска Weeek для фронтенда."""
    id: int
    name: str
    project_id: int
    is_private: Optional[bool] = None


class BoardsListResponse(BaseModel):
    """Ответ со списком досок."""
    boards: List[WeeekBoardOut]


class WeeekBoardColumnOut(BaseModel):
    """Колонка доски Weeek для фронтенда."""
    id: int
    name: str
    board_id: int


class BoardColumnsListResponse(BaseModel):
    """Ответ со списком колонок."""
    board_columns: List[WeeekBoardColumnOut]


class WeeekMemberOut(BaseModel):
    """Участник проекта Weeek для фронтенда."""
    id: str
    name: str
    email: Optional[str] = None


class MembersListResponse(BaseModel):
    """Ответ со списком участников проекта."""
    members: List[WeeekMemberOut]


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


def _get_weeek_token(db: DataBaseManager, user_id: UUID) -> str:
    """
    Достаёт зашифрованный токен Weeek из БД, расшифровывает и возвращает.
    """
    with db.session_scope() as session:
        from sqlalchemy import text as sa_text
        encrypted = session.execute(
            sa_text("SELECT weeek_api_token FROM \"Staff\" WHERE id = :uid"),
            {"uid": user_id}
        ).scalar()

    if not encrypted:
        raise HTTPException(status_code=400, detail="CRM not connected. Save API token first.")

    try:
        return decrypt_token(encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt CRM token for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to decrypt CRM token")


async def _weeek_post(path: str, token: str, json_body: dict) -> dict:
    """
    Делает POST-запрос к Weeek API, возвращает JSON-ответ.
    При HTTP-ошибке выбрасывает HTTPException.
    """
    url = f"{WEEEK_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=json_body)

    if resp.status_code >= 400:
        detail = f"Weeek API error {resp.status_code}: {resp.text[:300]}"
        logger.error(detail)
        raise HTTPException(status_code=502, detail=detail)

    return resp.json()


async def _weeek_get(path: str, token: str, params: Optional[dict] = None) -> dict:
    """
    Делает GET-запрос к Weeek API, возвращает JSON-ответ.
    При HTTP-ошибке выбрасывает HTTPException.
    """
    url = f"{WEEEK_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)

    if resp.status_code >= 400:
        detail = f"Weeek API error {resp.status_code}: {resp.text[:300]}"
        logger.error(detail)
        raise HTTPException(status_code=502, detail=detail)

    return resp.json()


async def _weeek_put(path: str, token: str, json_body: dict) -> dict:
    """
    Делает PUT-запрос к Weeek API, возвращает JSON-ответ.
    При HTTP-ошибке выбрасывает HTTPException (кроме 404).
    """
    url = f"{WEEEK_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=headers, json=json_body)

    if resp.status_code >= 400:
        detail = f"Weeek API error {resp.status_code}: {resp.text[:300]}"
        logger.error(detail)
        raise HTTPException(status_code=502, detail=detail)

    return resp.json()


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


# ===== Эндпоинты для проектов Weeek =====

@router.get("/projects", response_model=ProjectsListResponse)
async def list_weeek_projects(request: Request):
    """
    Получение списка проектов пользователя из Weeek.
    Требует подключённого CRM токена.
    """
    user_id = _get_current_user_id(request)
    db = _get_db()
    token = _get_weeek_token(db, user_id)

    data = await _weeek_get("/tm/projects", token)
    projects_raw = data.get("projects", [])

    projects = [
        WeeekProjectOut(
            id=p["id"],
            name=p.get("name", f"Project #{p['id']}"),
            color=p.get("color"),
            is_private=p.get("isPrivate"),
        )
        for p in projects_raw
    ]

    return ProjectsListResponse(projects=projects)


# ===== Эндпоинты для участников workspace =====

@router.get("/workspace/members", response_model=MembersListResponse)
async def list_workspace_members(request: Request):
    """
    Получение списка участников workspace из Weeek.
    Вызывает GET /public/v1/ws/members.
    """
    user_id = _get_current_user_id(request)
    db = _get_db()
    token = _get_weeek_token(db, user_id)

    data = await _weeek_get("/ws/members", token)

    # /ws/members может вернуть как массив напрямую, так и {members: [...]}
    members_raw: list = []
    if isinstance(data, list):
        members_raw = data
    elif isinstance(data, dict):
        members_raw = data.get("members") or data.get("data") or []

    if not isinstance(members_raw, list):
        members_raw = []

    members = []
    for m in members_raw:
        mid = m.get("id") or m.get("userId")
        if not mid:
            continue
        first = m.get("firstName", "") or ""
        last = m.get("lastName", "") or ""
        full_name = f"{first} {last}".strip() or m.get("name", "") or f"User #{mid}"
        members.append(WeeekMemberOut(
            id=str(mid),
            name=full_name,
            email=m.get("email"),
        ))

    return MembersListResponse(members=members)


# ===== Эндпоинты для досок и колонок Weeek =====

@router.get("/projects/{project_id}/boards", response_model=BoardsListResponse)
async def list_project_boards(project_id: int, request: Request):
    """
    Получение списка досок проекта из Weeek.
    """
    user_id = _get_current_user_id(request)
    db = _get_db()
    token = _get_weeek_token(db, user_id)

    data = await _weeek_get(f"/tm/boards", token, params={"projectId": project_id})
    boards_raw = data.get("boards", [])

    boards = [
        WeeekBoardOut(
            id=b["id"],
            name=b.get("name", f"Board #{b['id']}"),
            project_id=b.get("projectId", project_id),
            is_private=b.get("isPrivate"),
        )
        for b in boards_raw
    ]

    return BoardsListResponse(boards=boards)


@router.get("/boards/{board_id}/columns", response_model=BoardColumnsListResponse)
async def list_board_columns(board_id: int, request: Request):
    """
    Получение списка колонок доски из Weeek.
    """
    user_id = _get_current_user_id(request)
    db = _get_db()
    token = _get_weeek_token(db, user_id)

    data = await _weeek_get("/tm/board-columns", token, params={"boardId": board_id})
    columns_raw = data.get("boardColumns", [])

    # Фильтруем колонки, принадлежащие этой доске
    columns = [
        WeeekBoardColumnOut(
            id=c["id"],
            name=c.get("name", f"Column #{c['id']}"),
            board_id=c.get("boardId", board_id),
        )
        for c in columns_raw
        if c.get("boardId") == board_id
    ]

    return BoardColumnsListResponse(board_columns=columns)


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
        description=body.description,
        assignee=body.assignee,
        deadline=body.deadline,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")

    task = db.select_meeting_task_by_id(tid)
    return MeetingTaskOut(**task)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, request: Request):
    """
    Удаление задачи. Работает как для отправленных, так и для неотправленных.
    """
    _get_current_user_id(request)
    db = _get_db()

    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    success = db.delete_meeting_task(tid)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")

    return None


@router.post("/tasks/{task_id}/send", response_model=SendTaskResponse)
async def send_task_to_crm(task_id: str, body: Optional[SendTaskRequest] = None, request: Request = None):
    """
    Отправка одной задачи в Weeek CRM.

    - Расшифровывает API токен пользователя
    - Вызывает Weeek POST /tm/tasks
    - Помечает задачу как отправленную
    """
    user_id = _get_current_user_id(request)
    db = _get_db()

    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    # Получаем задачу из БД
    task = db.select_meeting_task_by_id(tid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["sent_to_crm"]:
        return SendTaskResponse(
            status="already_sent",
            message="Task has already been sent to CRM",
            crm_task_id=task.get("crm_task_id"),
        )

    token = _get_weeek_token(db, user_id)
    project_id = body.project_id if body else None
    board_column_id = body.board_column_id if body else None
    assignee_user_id = body.user_id if body else None
    # deadline из локального выбора пользователя (не сохраняется в БД)
    override_deadline = body.deadline if body else None

    # Формируем тело запроса к Weeek API
    weeek_body: dict[str, object] = {
        "title": task["description"][:255],  # Weeek ограничение
        "userId": assignee_user_id,
        "locations": [
            {"projectId": project_id, "boardColumnId": board_column_id}
        ],
        "type": "action",
    }

    # Реальный вызов Weeek API
    data = await _weeek_post("/tm/tasks", token, weeek_body)

    if not data.get("success"):
        logger.error(f"Weeek API returned success=false: {data}")
        raise HTTPException(status_code=502, detail="Weeek API rejected the request")

    weeek_task = data.get("task", {})
    crm_task_id = str(weeek_task.get("id", ""))

    # Дедлайн: приоритет у переданного с фронта (локальный выбор пользователя),
    # иначе из БД (LLM-назначенный)
    deadline_to_use = override_deadline or task.get("deadline")
    if crm_task_id and deadline_to_use:
        try:
            await _weeek_put(
                f"/tm/tasks/{crm_task_id}",
                token,
                {"dueDate": deadline_to_use},
            )
        except HTTPException as e:
            logger.warning(f"Failed to set deadline on Weeek task {crm_task_id}: {e.detail}")

    # Помечаем как отправленное
    success = db.mark_meeting_task_sent(task_id=tid, crm_task_id=crm_task_id)
    if not success:
        logger.error(f"Failed to mark task {task_id} as sent after Weeek API call")
        # Не фатально — задача уже создана в Weeek, но наш флаг не проставлен
        return SendTaskResponse(
            status="error",
            message="Task created in Weeek but failed to update local status",
            crm_task_id=crm_task_id,
        )

    return SendTaskResponse(
        status="ok",
        message="Task sent to Weeek CRM",
        crm_task_id=crm_task_id,
    )


@router.post("/tasks/{summary_id}/send-all", response_model=dict)
async def send_all_tasks(summary_id: str, body: Optional[SendTaskRequest] = None, request: Request = None):
    """
    Отправляет все неотправленные задачи суммаризации в CRM.
    """
    user_id = _get_current_user_id(request)
    db = _get_db()

    try:
        sid = UUID(summary_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid summary_id")

    token = _get_weeek_token(db, user_id)
    project_id = body.project_id if body else None
    board_column_id = body.board_column_id if body else None
    assignee_user_id = body.user_id if body else None
    override_deadline = body.deadline if body else None
    unsent = db.select_unsent_meeting_tasks(sid)

    sent_count = 0
    errors = []

    for task in unsent:
        try:
            task_id = UUID(task["id"])

            weeek_body: dict[str, object] = {
                "title": task["description"][:255],
                "userId": assignee_user_id,
                "locations": [
                    {"projectId": project_id, "boardColumnId": board_column_id}
                ],
                "type": "action",
            }

            data = await _weeek_post("/tm/tasks", token, weeek_body)

            if not data.get("success"):
                errors.append({"task_id": task["id"], "error": "Weeek API rejected"})
                continue

            weeek_task = data.get("task", {})
            crm_task_id = str(weeek_task.get("id", ""))

            # Дедлайн: приоритет у переданного с фронта (локальный выбор), иначе из БД
            deadline_to_use = override_deadline or task.get("deadline")
            if crm_task_id and deadline_to_use:
                try:
                    await _weeek_put(
                        f"/tm/tasks/{crm_task_id}",
                        token,
                        {"dueDate": deadline_to_use},
                    )
                except HTTPException as e:
                    logger.warning(f"Failed to set deadline on Weeek task {crm_task_id}: {e.detail}")

            db.mark_meeting_task_sent(task_id=task_id, crm_task_id=crm_task_id)
            sent_count += 1
        except HTTPException as e:
            errors.append({"task_id": task["id"], "error": e.detail})
        except Exception as e:
            errors.append({"task_id": task["id"], "error": str(e)})

    return {
        "status": "ok" if not errors else "partial",
        "sent": sent_count,
        "total": len(unsent),
        "errors": errors,
    }
