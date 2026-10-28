"""外部集成：企业微信群机器人（管理员配置、发送测试；所有人可查开关状态）。"""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import wecom_service
from app.crm.services.wecom_service import PushOut, WecomConfigIn, WecomConfigOut

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/wecom", response_model=ApiResponse[WecomConfigOut])
def get_wecom(user: CurrentUserDep, db: DbDep) -> ApiResponse[WecomConfigOut]:
    return ok(wecom_service.get_config(db, user))


@router.put("/wecom", response_model=ApiResponse[WecomConfigOut])
def save_wecom(body: WecomConfigIn, user: CurrentUserDep, db: DbDep) -> ApiResponse[WecomConfigOut]:
    return ok(wecom_service.save_config(db, user, body))


@router.post("/wecom/test", response_model=ApiResponse[PushOut])
async def test_wecom(user: CurrentUserDep, db: DbDep) -> ApiResponse[PushOut]:
    return ok(await run_in_threadpool(wecom_service.send_test, db, user))


@router.get("/flags", response_model=ApiResponse[dict[str, bool]])
def flags(user: CurrentUserDep, db: DbDep) -> ApiResponse[dict[str, bool]]:
    """各推送事件是否可用（决定前端是否显示「推送到群」），不含地址。"""
    return ok(wecom_service.config_flags(db))
