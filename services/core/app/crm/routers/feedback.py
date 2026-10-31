"""AI 回复的点赞 / 点踩：本人评价、读回本会话的评价；主管 / 管理员复盘「没帮助」的回复。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import feedback_service
from app.crm.services.feedback_service import FeedbackIn, FeedbackItem, MyRating, Rating

router = APIRouter(prefix="/api/ai-feedback", tags=["ai-feedback"])


@router.post("", response_model=ApiResponse[MyRating | None])
def rate(body: FeedbackIn, user: CurrentUserDep, db: DbDep) -> ApiResponse[MyRating | None]:
    return ok(feedback_service.rate(db, user, body))


@router.get("/thread/{thread_id}", response_model=ApiResponse[list[MyRating]])
def my_ratings(thread_id: str, user: CurrentUserDep, db: DbDep) -> ApiResponse[list[MyRating]]:
    return ok(feedback_service.mine(db, user, thread_id))


@router.get("", response_model=ApiResponse[list[FeedbackItem]])
def review(
    user: CurrentUserDep,
    db: DbDep,
    rating: Annotated[Rating, Query()] = "down",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ApiResponse[list[FeedbackItem]]:
    return ok(feedback_service.review(db, user, rating, limit))
