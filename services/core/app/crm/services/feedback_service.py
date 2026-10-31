"""AI 回复反馈：本人点赞 / 点踩（再点取消），主管看本团队、管理员看全部「没帮助」的回复。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.crm.models import AiFeedback, User

Rating = Literal["up", "down"]
# 存一段就够复盘，不存整段长回复
MAX_TEXT = 4000


class FeedbackIn(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    message_index: int = Field(ge=0, le=10_000)
    # null：取消
    rating: Rating | None
    mode: Literal["work", "learn"] = "work"
    question: str = Field(default="", max_length=20_000)
    answer: str = Field(default="", max_length=100_000)
    comment: str | None = Field(default=None, max_length=500)


class MyRating(BaseModel):
    message_index: int
    rating: Rating
    comment: str | None


class FeedbackItem(BaseModel):
    id: str
    user_name: str
    rating: Rating
    mode: str
    question: str
    answer: str
    comment: str | None
    created_at: datetime


def rate(db: Session, user: CurrentUser, data: FeedbackIn) -> MyRating | None:
    key = (
        AiFeedback.user_id == user.id,
        AiFeedback.thread_id == data.thread_id,
        AiFeedback.message_index == data.message_index,
    )
    if data.rating is None:
        db.execute(delete(AiFeedback).where(*key))
        return None
    comment = (data.comment or "").strip() or None
    values = {
        "user_id": user.id,
        "team_id": user.team_id,
        "thread_id": data.thread_id,
        "message_index": data.message_index,
        "rating": data.rating,
        "mode": data.mode,
        "question": data.question[:MAX_TEXT],
        "answer": data.answer[:MAX_TEXT],
        "comment": comment,
    }
    stmt = insert(AiFeedback).values(**values)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "thread_id", "message_index"],
            set_={
                "rating": stmt.excluded.rating,
                "comment": stmt.excluded.comment,
                "answer": stmt.excluded.answer,
                "updated_at": datetime.now().astimezone(),
            },
        )
    )
    return MyRating(message_index=data.message_index, rating=data.rating, comment=comment)


def mine(db: Session, user: CurrentUser, thread_id: str) -> list[MyRating]:
    rows = db.scalars(
        select(AiFeedback).where(AiFeedback.user_id == user.id, AiFeedback.thread_id == thread_id)
    ).all()
    return [
        MyRating(message_index=r.message_index, rating=r.rating, comment=r.comment) for r in rows
    ]  # type: ignore[arg-type]


def review(
    db: Session, user: CurrentUser, rating: Rating = "down", limit: int = 50
) -> list[FeedbackItem]:
    if user.role == Role.SALES:
        raise BizError(ErrorCode.FORBIDDEN, "AI 回复反馈仅主管和管理员可以查看")
    stmt = (
        select(AiFeedback, User.name)
        .join(User, User.id == AiFeedback.user_id)
        .where(AiFeedback.rating == rating)
        .order_by(AiFeedback.updated_at.desc())
        .limit(limit)
    )
    if user.role == Role.MANAGER:
        stmt = stmt.where(AiFeedback.team_id == user.team_id)
    return [
        FeedbackItem(
            id=str(f.id),
            user_name=name,
            rating=f.rating,  # type: ignore[arg-type]
            mode=f.mode,
            question=f.question,
            answer=f.answer,
            comment=f.comment,
            created_at=f.updated_at,
        )
        for f, name in db.execute(stmt).all()
    ]
