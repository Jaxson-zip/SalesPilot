"""操作权限（业务模块接口契约 §0）：看得到 ≠ 改得了。

数据范围（能看什么）由 app.common.scope 负责；这里决定能做什么，所有 service 复用：
- 业务数据只有负责人本人能修改；管理员对业务数据只读（40301 rule=role_forbidden）
- 主管只做审批和回款，且只能处理本团队的记录
- 看不到的记录仍然返回 40401（不泄露存在性）
"""

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError, ErrorCode
from app.common.scope import ScopedModel, ensure_visible
from app.rules.loader import solo_mode

RULE_ROLE_FORBIDDEN = "role_forbidden"
RULE_NOT_OWNER = "not_owner"
RULE_NOT_TEAM = "not_team"


def forbidden(message: str, rule: str) -> BizError:
    return BizError(ErrorCode.FORBIDDEN, message, {"rule": rule})


def ensure_business_writer(user: CurrentUser) -> None:
    """新建 / 修改业务数据的前置条件：管理员只读。"""
    if user.role is Role.ADMIN:
        raise forbidden("管理员对业务数据只读，不能新建或修改", RULE_ROLE_FORBIDDEN)


def ensure_owner(obj: ScopedModel | None, user: CurrentUser) -> None:
    """修改单条业务记录：看不到 → 40401；管理员 → role_forbidden；不是负责人 → not_owner。"""
    ensure_visible(obj, user)
    ensure_business_writer(user)
    assert obj is not None
    if obj.owner_id != user.id:
        raise forbidden("只有负责人本人可以操作这条记录", RULE_NOT_OWNER)


def ensure_role(user: CurrentUser, role: Role, message: str) -> None:
    """限定单一角色（审批、回款仅 manager）。"""
    if user.role is not role:
        raise forbidden(message, RULE_ROLE_FORBIDDEN)


def can_configure(user: CurrentUser) -> bool:
    """系统配置（模型、行业包、业务规则、定时任务、战卡、消息推送）：管理员；
    个人模式下主管也可以（一个人既做业务也管配置）。成员与团队管理始终只有管理员。"""
    if user.role is Role.ADMIN:
        return True
    return user.role is Role.MANAGER and solo_mode()


def ensure_configurer(user: CurrentUser, message: str) -> None:
    if not can_configure(user):
        raise forbidden(message, RULE_ROLE_FORBIDDEN)


def ensure_same_team(obj: ScopedModel | None, user: CurrentUser) -> None:
    """主管处理的记录必须属于本团队：看不到 → 40401；可见但不是本团队 → 40301 not_team。"""
    ensure_visible(obj, user)
    assert obj is not None
    if user.team_id is None or obj.team_id != user.team_id:
        raise forbidden("只能处理本团队的记录", RULE_NOT_TEAM)
