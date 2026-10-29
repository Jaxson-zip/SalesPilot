"""Agent 接口：chat / resume（SSE）与会话历史（只读）。只做参数和响应。"""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Path, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.agent import materials, models, service, threads
from app.agent import samples as sample_lib
from app.agent.checkpoint import get_checkpointer
from app.agent.history import ThreadMessages, read_thread_messages
from app.agent.runs import registry
from app.agent.sse import follow_run
from app.common.auth import CurrentUserDep
from app.common.errors import BizError, ErrorCode
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import usage_service

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatIn(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    opportunity_id: uuid.UUID | None = None
    # 需求卡片上确认后的需求（交付端、功能模块…）：本轮直接按它出正式报价
    requirement: dict[str, Any] | None = None
    model: str | None = Field(default=None, max_length=100)
    # 上传的一手材料（先调 /materials 取文字）；有材料时 AI 直接整理成跟进 / 联系人 / 下一步
    material: materials.MaterialIn | None = None
    # 客户样例图片的逐张识别结果（先调 /samples）；有样例时直接走出方案
    samples: sample_lib.SamplesIn | None = None


class ResumeIn(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    decision: Literal["approve", "reject"]
    # 生成报价单时销售在三档里另选的档位（tier 键，如 economy）；不传按推荐档
    tier: str | None = Field(default=None, max_length=30)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


@router.post("/chat")
async def chat(body: ChatIn, user: CurrentUserDep, request: Request) -> EventSourceResponse:
    await run_in_threadpool(usage_service.ensure_daily_quota, user)
    deps = service.build_deps(user, body.thread_id, _request_id(request), body.model)
    run = await run_in_threadpool(
        service.prepare_chat,
        deps,
        body.message,
        body.opportunity_id,
        body.material,
        requirement=body.requirement,
        samples=body.samples,
    )
    return EventSourceResponse(follow_run(service.start_run(run, user)))


@router.post("/resume")
async def resume(body: ResumeIn, user: CurrentUserDep, request: Request) -> EventSourceResponse:
    deps = service.build_deps(user, body.thread_id, _request_id(request), None)
    run = await run_in_threadpool(service.prepare_resume, deps, body.decision, None, body.tier)
    return EventSourceResponse(follow_run(service.start_run(run, user)))


@router.post("/materials", response_model=ApiResponse[materials.MaterialOut])
def extract_material(
    user: CurrentUserDep, request: Request, file: Annotated[UploadFile, File()]
) -> ApiResponse[materials.MaterialOut]:
    """一手材料 → 文字（不入库）：文本 / Word / PDF 本地解析，图片走视觉模型识别。"""
    usage_service.ensure_daily_quota(user)
    content = file.file.read(materials.MAX_BYTES + 1)
    return ok(materials.extract(file.filename or "", content, _request_id(request)))


@router.post("/samples", response_model=ApiResponse[sample_lib.SampleItem])
def analyze_sample(
    user: CurrentUserDep, request: Request, file: Annotated[UploadFile, File()]
) -> ApiResponse[sample_lib.SampleItem]:
    """客户样例图片 → 单据类型、字段名、清晰度（一次一张，不入库）。"""
    usage_service.ensure_daily_quota(user)
    content = file.file.read(materials.MAX_BYTES + 1)
    return ok(sample_lib.analyze(file.filename or "", content, _request_id(request)))


@router.get("/models", response_model=ApiResponse[models.ChatModels])
def chat_models(user: CurrentUserDep, request: Request) -> ApiResponse[models.ChatModels]:
    return ok(models.chat_models(_request_id(request)))


@router.get("/threads", response_model=ApiResponse[threads.ThreadPage])
def list_threads(
    user: CurrentUserDep, db: DbDep, limit: Annotated[int, Query(ge=1, le=100)] = 30
) -> ApiResponse[threads.ThreadPage]:
    return ok(threads.list_threads(db, user, limit))


@router.patch("/threads/{thread_id}", response_model=ApiResponse[threads.ThreadItem])
def rename_thread(
    user: CurrentUserDep,
    db: DbDep,
    thread_id: Annotated[str, Path(max_length=100)],
    body: threads.ThreadRename,
) -> ApiResponse[threads.ThreadItem]:
    return ok(threads.rename_thread(db, user, thread_id, body.title))


@router.delete("/threads/{thread_id}", response_model=ApiResponse[None])
def delete_thread(
    user: CurrentUserDep, db: DbDep, thread_id: Annotated[str, Path(max_length=100)]
) -> ApiResponse[None]:
    threads.delete_thread(db, user, thread_id, get_checkpointer())
    return ok(None)


@router.get("/threads/{thread_id}/messages", response_model=ApiResponse[ThreadMessages])
def thread_messages(
    user: CurrentUserDep, db: DbDep, thread_id: Annotated[str, Path(max_length=100)]
) -> ApiResponse[ThreadMessages]:
    return ok(read_thread_messages(db, user, thread_id, get_checkpointer()))


def _own_run(db: DbDep, user: CurrentUserDep, thread_id: str) -> Any:
    threads.ensure_owner(threads.find_thread(db, thread_id), user)
    run = registry.get(thread_id)
    if run is None or run.user_id != str(user.id):
        raise BizError(ErrorCode.NOT_FOUND, "这个会话没有正在生成的回复")
    return run


@router.get("/threads/{thread_id}/stream")
def follow_thread(
    user: CurrentUserDep, db: DbDep, thread_id: Annotated[str, Path(max_length=100)]
) -> EventSourceResponse:
    """回到正在生成的会话：从本轮第一条事件重放，接着实时推送（SSE，与 chat 相同的事件）。"""
    return EventSourceResponse(follow_run(_own_run(db, user, thread_id)))


@router.post("/threads/{thread_id}/stop", response_model=ApiResponse[None])
def stop_thread(
    user: CurrentUserDep, db: DbDep, thread_id: Annotated[str, Path(max_length=100)]
) -> ApiResponse[None]:
    """停止正在生成的回复（后台在当前步骤结束后停下）；已经结束的不报错。"""
    _own_run(db, user, thread_id)
    registry.stop(thread_id)
    return ok(None)
