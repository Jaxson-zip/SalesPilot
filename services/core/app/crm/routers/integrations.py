"""外部集成：企业微信群机器人（管理员配置、发送测试；所有人可查开关状态）、模型接入（管理员）。"""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.common.auth import CurrentUserDep
from app.common.response import ApiResponse, ok
from app.crm.routers.deps import DbDep
from app.crm.services import model_config_service as models
from app.crm.services import wecom_service
from app.crm.services.model_config_service import (
    BuiltinIn,
    BuiltinTestIn,
    CustomIn,
    CustomTestIn,
    EmbeddingIn,
    GroupsIn,
    ModelConfigOut,
    TestOut,
)
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


@router.get("/models", response_model=ApiResponse[ModelConfigOut])
async def get_models(user: CurrentUserDep, db: DbDep) -> ApiResponse[ModelConfigOut]:
    return ok(await run_in_threadpool(models.get_status, db, user))


@router.put("/models/builtin", response_model=ApiResponse[ModelConfigOut])
async def save_builtin(
    body: BuiltinIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ModelConfigOut]:
    return ok(await run_in_threadpool(models.save_builtin, db, user, body))


@router.post("/models/builtin/test", response_model=ApiResponse[TestOut])
async def test_builtin(
    body: BuiltinTestIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[TestOut]:
    return ok(await run_in_threadpool(models.test_builtin, db, user, body))


@router.put("/models/custom/{provider_id}", response_model=ApiResponse[ModelConfigOut])
async def save_custom(
    provider_id: str, body: CustomIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ModelConfigOut]:
    return ok(await run_in_threadpool(models.save_custom, db, user, provider_id, body))


@router.delete("/models/custom/{provider_id}", response_model=ApiResponse[ModelConfigOut])
async def delete_custom(
    provider_id: str, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ModelConfigOut]:
    return ok(await run_in_threadpool(models.delete_custom, db, user, provider_id))


@router.post("/models/custom/{provider_id}/test", response_model=ApiResponse[TestOut])
async def test_custom(
    provider_id: str, body: CustomTestIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[TestOut]:
    return ok(await run_in_threadpool(models.test_custom, db, user, provider_id, body))


@router.put("/models/groups", response_model=ApiResponse[ModelConfigOut])
async def save_groups(
    body: GroupsIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ModelConfigOut]:
    return ok(await run_in_threadpool(models.save_groups, db, user, body))


@router.post("/models/embedding", response_model=ApiResponse[ModelConfigOut])
async def switch_embedding(
    body: EmbeddingIn, user: CurrentUserDep, db: DbDep
) -> ApiResponse[ModelConfigOut]:
    """切换知识库向量模型：后台重建全部向量，完成后自动切换；进度在 GET /models 的 reindex 里。"""
    return ok(await run_in_threadpool(models.switch_embedding, db, user, body))
