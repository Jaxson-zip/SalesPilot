"""Agent 接口：POST /api/agent/chat、POST /api/agent/resume（SSE）。只做参数和响应。"""

import uuid
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.agent import service
from app.agent.sse import sse_stream
from app.common.auth import CurrentUserDep

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
