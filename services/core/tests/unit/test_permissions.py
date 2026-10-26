"""操作权限纯函数（接口契约 §0）：不依赖数据库。"""

import uuid
from dataclasses import dataclass

import pytest

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError
from app.common.permissions import (
    ensure_business_writer,
    ensure_owner,
    ensure_role,
    ensure_same_team,
)

TEAM = uuid.uuid4()
OTHER_TEAM = uuid.uuid4()
SALES = CurrentUser(id=uuid.uuid4(), name="销售", role=Role.SALES, team_id=TEAM)
MANAGER = CurrentUser(id=uuid.uuid4(), name="主管", role=Role.MANAGER, team_id=TEAM)
ADMIN = CurrentUser(id=uuid.uuid4(), name="管理员", role=Role.ADMIN)


@dataclass
class Record:
    owner_id: uuid.UUID | None
    team_id: uuid.UUID | None


def _raises(code: int, rule: str | None = None) -> pytest.RaisesExc[BizError]:
    return pytest.raises(BizError, check=lambda e: e.code == code and _rule(e) == rule)


def _rule(e: BizError) -> str | None:
    return e.data.get("rule") if isinstance(e.data, dict) else None


def test_business_writer() -> None:
    ensure_business_writer(SALES)
    ensure_business_writer(MANAGER)
    with _raises(40301, "role_forbidden"):
        ensure_business_writer(ADMIN)


def test_owner_can_modify() -> None:
    ensure_owner(Record(SALES.id, TEAM), SALES)
    ensure_owner(Record(MANAGER.id, TEAM), MANAGER)


def test_manager_cannot_modify_sales_record() -> None:
    with _raises(40301, "not_owner"):
        ensure_owner(Record(SALES.id, TEAM), MANAGER)


def test_admin_is_read_only_even_when_visible() -> None:
    with _raises(40301, "role_forbidden"):
        ensure_owner(Record(SALES.id, TEAM), ADMIN)


def test_invisible_record_is_not_found() -> None:
    with _raises(40401):
        ensure_owner(Record(uuid.uuid4(), OTHER_TEAM), SALES)
    with _raises(40401):
        ensure_owner(None, MANAGER)


def test_role_and_team() -> None:
    ensure_role(MANAGER, Role.MANAGER, "x")
    for user in (SALES, ADMIN):
        with _raises(40301, "role_forbidden"):
            ensure_role(user, Role.MANAGER, "x")
    ensure_same_team(Record(SALES.id, TEAM), MANAGER)
    with _raises(40301, "not_team"):
        ensure_same_team(Record(MANAGER.id, OTHER_TEAM), MANAGER)  # 可见（本人）但不属于本团队
    with _raises(40401):
        ensure_same_team(Record(uuid.uuid4(), OTHER_TEAM), MANAGER)
