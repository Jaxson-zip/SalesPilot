"""Agent 会话列表（agent_threads 表）：新会话登记、更新时间、按用户列出、校验归属。"""

import logging
import re
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.runs import registry
from app.common.auth import CurrentUser
from app.common.errors import BizError, ErrorCode
from app.crm.models import AgentThread, Opportunity

logger = logging.getLogger("core.agent")
TITLE_MAX_CHARS = 30
DEFAULT_TITLE = "新对话"
SessionFactory = Callable[[], AbstractContextManager[Any]]


class ThreadItem(BaseModel):
    thread_id: str
    title: str
    updated_at: datetime
    opportunity_id: uuid.UUID | None = None
    running: bool = False  # 还在后台生成


class ThreadPage(BaseModel):
    items: list[ThreadItem]
    total: int


def make_title(message: str) -> str:
    """取第一条用户消息的前 30 个字（空白折叠为一个空格）。"""
    text = re.sub(r"\s+", " ", message).strip()
    return text[:TITLE_MAX_CHARS] or DEFAULT_TITLE


def find_thread(db: Session, thread_id: str) -> AgentThread | None:
    return db.scalars(select(AgentThread).where(AgentThread.thread_id == thread_id)).first()


def ensure_owner(row: AgentThread | None, user: CurrentUser) -> None:
    """别人的会话一律 40401（不暴露存在性）。"""
    if row is not None and row.user_id != user.id:
        raise BizError(ErrorCode.NOT_FOUND, "会话不存在")


def _valid_opportunity(db: Session, opportunity_id: uuid.UUID | None) -> uuid.UUID | None:
    if opportunity_id is None or db.get(Opportunity, opportunity_id) is None:
        return None
    return opportunity_id


def upsert_thread(
    db: Session,
    user: CurrentUser,
    thread_id: str,
    message: str,
    opportunity_id: uuid.UUID | None = None,
) -> AgentThread:
    """新会话写入（标题取首条消息）；已有会话只刷新 updated_at，并补上关联商机。"""
    row = find_thread(db, thread_id)
    ensure_owner(row, user)
    opp = _valid_opportunity(db, opportunity_id)
    if row is None:
        row = AgentThread(
            thread_id=thread_id, user_id=user.id, title=make_title(message), opportunity_id=opp
        )
        db.add(row)
    else:
        row.updated_at = func.now()  # type: ignore[assignment]
        if opp is not None:
            row.opportunity_id = opp
    db.flush()
    return row


def touch_thread(
    session: SessionFactory,
    user: CurrentUser,
    thread_id: str,
    message: str,
    opportunity_id: uuid.UUID | None,
) -> None:
    """chat 入口调用：登记会话。数据库不可用时只记日志，不影响对话本身。"""
    try:
        with session() as db:
            if db is None:  # 单元测试的空会话
                return
            upsert_thread(db, user, thread_id, message, opportunity_id)
    except BizError:
        raise
    except Exception:
        logger.warning("agent_threads: upsert failed thread_id=%s", thread_id, exc_info=True)


def list_threads(db: Session, user: CurrentUser, limit: int) -> ThreadPage:
    """只返回当前用户自己的会话（任何角色都一样），按 updated_at 倒序。"""
    cond = AgentThread.user_id == user.id
    total = db.scalar(select(func.count()).select_from(AgentThread).where(cond)) or 0
    stmt = (
        select(AgentThread)
        .where(cond)
        .order_by(AgentThread.updated_at.desc(), AgentThread.created_at.desc())
        .limit(limit)
    )
    running = registry.active_threads(str(user.id))
    items = [
        ThreadItem(
            thread_id=r.thread_id,
            title=r.title,
            updated_at=r.updated_at,
            opportunity_id=r.opportunity_id,
            running=r.thread_id in running,
        )
        for r in db.scalars(stmt).all()
    ]
    return ThreadPage(items=items, total=int(total))


def _owned(db: Session, user: CurrentUser, thread_id: str) -> AgentThread:
    row = find_thread(db, thread_id)
    ensure_owner(row, user)
    if row is None:
        raise BizError(ErrorCode.NOT_FOUND, "会话不存在")
    return row


def rename_thread(db: Session, user: CurrentUser, thread_id: str, title: str) -> ThreadItem:
    row = _owned(db, user, thread_id)
    row.title = make_title(title)
    db.flush()
    return ThreadItem(
        thread_id=row.thread_id,
        title=row.title,
        updated_at=row.updated_at,
        opportunity_id=row.opportunity_id,
    )


def delete_thread(db: Session, user: CurrentUser, thread_id: str, saver: Any) -> None:
    """删除会话记录和对话检查点（检查点删除失败只记日志，列表里已经看不到）。"""
    row = _owned(db, user, thread_id)
    db.delete(row)
    db.flush()
    try:
        saver.delete_thread(thread_id)
    except Exception:
        logger.warning(
            "agent_threads: checkpoint delete failed thread_id=%s", thread_id, exc_info=True
        )


class ThreadRename(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_CHARS)
