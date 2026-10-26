"""任务接口（接口契约 v3 §12）：只做参数和响应，业务逻辑在 task_service。"""

import uuid

from fastapi import APIRouter

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.common.scope import View
from app.crm.routers.deps import DbDep, PageDep
from app.crm.schemas.common import Page
from app.crm.schemas.task import TaskCreate, TaskDue, TaskItem, TaskStatus, TaskSubject, TaskUpdate
from app.crm.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=ApiResponse[Page[TaskItem]])
def list_tasks(
    user: CurrentUserDep,
    db: DbDep,
    page: PageDep,
    view: View | None = None,
    status: TaskStatus | None = None,
    due: TaskDue | None = None,
    subject_type: TaskSubject | None = None,
    subject_id: uuid.UUID | None = None,
) -> ApiResponse[Page[TaskItem]]:
    filters = {"status": status, "due": due, "subject_type": subject_type, "subject_id": subject_id}
    return ok(task_service.list_tasks(db, user, view, page, filters))


@router.post("", response_model=ApiResponse[TaskItem])
def create_task(body: TaskCreate, user: CurrentUserDep, db: DbDep) -> ApiResponse[TaskItem]:
    return ok(task_service.create_task(db, user, body))


@router.patch("/{task_id}", response_model=ApiResponse[TaskItem])
def update_task(
    task_id: uuid.UUID, body: TaskUpdate, user: CurrentUserDep, db: DbDep
) -> ApiResponse[TaskItem]:
    return ok(task_service.update_task(db, user, task_id, body))


@router.delete("/{task_id}", response_model=ApiResponse[None])
def delete_task(task_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> ApiResponse[None]:
    task_service.delete_task(db, user, task_id)
    return ok(None)
