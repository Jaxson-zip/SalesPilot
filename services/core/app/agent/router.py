"""Agent 接口：chat / resume（SSE）与会话历史（只读）。只做参数和响应。"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.agent import models, service, threads
from app.agent.checkpoint import get_checkpointer
from app.agent.history import ThreadMessages, read_thread_messages
from app.agent.sse import sse_stream
from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatIn(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    opportunity_id: uuid.UUID | None = None
    model: str | None = Field(default=None, max_length=100)


class ResumeIn(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    decision: Literal["approve", "reject"]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


@router.post("/chat")
async def chat(body: ChatIn, user: CurrentUserDep, request: Request) -> EventSourceResponse:
    deps = service.build_deps(user, body.thread_id, _request_id(request), body.model)
    run = await run_in_threadpool(service.prepare_chat, deps, body.message, body.opportunity_id)
    return EventSourceResponse(sse_stream(run.graph, run.payload, run.config, run.thread_id))


@router.post("/resume")
async def resume(body: ResumeIn, user: CurrentUserDep, request: Request) -> EventSourceResponse:
    deps = service.build_deps(user, body.thread_id, _request_id(request), None)
    run = await run_in_threadpool(service.prepare_resume, deps, body.decision)
    return EventSourceResponse(sse_stream(run.graph, run.payload, run.config, run.thread_id))


@router.get("/models", response_model=ApiResponse[models.ChatModels])
def chat_models(user: CurrentUserDep, request: Request) -> ApiResponse[models.ChatModels]:
    return ok(models.chat_models(_request_id(request)))


@router.get("/threads", response_model=ApiResponse[threads.ThreadPage])
def list_threads(
    user: CurrentUserDep, db: DbDep, limit: Annotated[int, Query(ge=1, le=100)] = 30
) -> ApiResponse[threads.ThreadPage]:
    return ok(threads.list_threads(db, user, limit))


@router.get("/threads/{thread_id}/messages", response_model=ApiResponse[ThreadMessages])
def thread_messages(
    user: CurrentUserDep, db: DbDep, thread_id: Annotated[str, Path(max_length=100)]
) -> ApiResponse[ThreadMessages]:
    return ok(read_thread_messages(db, user, thread_id, get_checkpointer()))
