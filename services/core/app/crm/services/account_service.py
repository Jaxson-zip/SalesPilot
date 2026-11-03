"""成员与团队管理（仅管理员）：新建成员、改角色 / 团队、重置密码、停用 / 启用，新建 / 改名团队。

- 新建和重置密码都生成临时密码，只在响应里出现一次，成员首次登录必须修改。
- 销售和主管必须属于某个团队；管理员不属于团队。
- 不能停用或降级自己，也不能让系统里没有启用的管理员。
- 停用、重置密码会让该成员已登录的会话立即失效；停用时名下还有客户，通知本团队主管去交接。
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role, forget_user
from app.common.errors import BizError, ErrorCode
from app.common.passwords import hash_password, temp_password
from app.common.permissions import ensure_role
from app.crm.models import Customer, ProductLine, Team, User
from app.crm.schemas.account import (
    AccountCreate,
    AccountItem,
    AccountUpdate,
    TeamIn,
    TeamItem,
    TempPassword,
)
from app.crm.services import notification_service, transfer_service

RULE_SELF = "account_self"
RULE_LAST_ADMIN = "last_admin"
ROLE_ORDER = {Role.ADMIN.value: 0, Role.MANAGER.value: 1, Role.SALES.value: 2}


def ensure_admin(user: CurrentUser) -> None:
    ensure_role(user, Role.ADMIN, "仅管理员可以管理成员和团队")


def _customers(db: Session) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(Customer.owner_id, func.count()).where(Customer.owner_id.is_not(None))
        .group_by(Customer.owner_id)
    ).all()  # fmt: skip
    return {owner: n for owner, n in rows}


def _item(user: User, teams: dict[uuid.UUID, str], customers: dict[uuid.UUID, int]) -> AccountItem:
    return AccountItem(
        id=user.id,
        username=user.username,
        name=user.name,
        role=Role(user.role),
        team_id=user.team_id,
        team_name=teams.get(user.team_id) if user.team_id else None,
        active=user.active,
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at,
        customers=customers.get(user.id, 0),
    )


def _team_names(db: Session) -> dict[uuid.UUID, str]:
    return {t.id: t.name for t in db.scalars(select(Team)).all()}


def _one(db: Session, user: User) -> AccountItem:
    return _item(user, _team_names(db), _customers(db))


def list_accounts(db: Session, admin: CurrentUser) -> list[AccountItem]:
    ensure_admin(admin)
    teams, customers = _team_names(db), _customers(db)
    users = sorted(
        db.scalars(select(User)).all(),
        key=lambda u: (not u.active, ROLE_ORDER.get(u.role, 9), u.name),
    )
    return [_item(u, teams, customers) for u in users]


def _team_for(db: Session, role: Role, team_id: uuid.UUID | None) -> uuid.UUID | None:
    if role is Role.ADMIN:
        return None
    if team_id is None:
        raise BizError(
            ErrorCode.VALIDATION, "销售和主管必须选择所属团队", {"rule": "team_required"}
        )
    if db.get(Team, team_id) is None:
        raise BizError(ErrorCode.NOT_FOUND, "团队不存在")
    return team_id


def _ensure_username_free(db: Session, username: str) -> None:
    taken = db.scalar(select(User.id).where(func.lower(User.username) == username.lower()))
    if taken is not None:
        raise BizError(ErrorCode.DUPLICATE, f"登录名「{username}」已被使用")


def create_account(db: Session, admin: CurrentUser, data: AccountCreate) -> TempPassword:
    ensure_admin(admin)
    _ensure_username_free(db, data.username)
    password = temp_password()
    user = User(
        username=data.username.lower(),
        name=data.name.strip(),
        role=data.role.value,
        team_id=_team_for(db, data.role, data.team_id),
        password_hash=hash_password(password),
        must_change_password=True,
        active=True,
        token_version=0,
    )
    db.add(user)
    db.flush()
    return TempPassword(account=_one(db, user), temp_password=password)


def _active_admins(db: Session) -> int:
    stmt = select(func.count()).select_from(User)
    return db.scalar(stmt.where(User.role == Role.ADMIN.value, User.active.is_(True))) or 0


def _get(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id, with_for_update=True)
    if user is None:
        raise BizError(ErrorCode.NOT_FOUND, "成员不存在")
    return user


def _guard_admins(db: Session, admin: CurrentUser, user: User, data: AccountUpdate) -> None:
    demote = data.role is not None and data.role is not Role.ADMIN
    deactivate = data.active is False
    if user.id == admin.id and (demote or deactivate):
        raise BizError(ErrorCode.RULE_VIOLATION, "不能停用或降级自己的账号", {"rule": RULE_SELF})
    last_admin = user.role == Role.ADMIN.value and user.active and _active_admins(db) <= 1
    if last_admin and (demote or deactivate):
        raise BizError(
            ErrorCode.RULE_VIOLATION, "至少要保留一名启用的管理员", {"rule": RULE_LAST_ADMIN}
        )


def _notify_handover(db: Session, user: User, customers: int) -> None:
    if not customers or user.team_id is None:
        return
    managers = db.scalars(
        select(User.id).where(
            User.team_id == user.team_id,
            User.role == Role.MANAGER.value,
            User.active.is_(True),
            User.id != user.id,
        )
    ).all()
    notification_service.notify(
        db,
        managers,
        "account_deactivated",
        f"{user.name} 的账号已停用，请交接客户",
        f"名下还有 {customers} 个客户，可在客户页「按人交接」转给其他成员",
        f"/customers?handover={user.id}",
    )


def update_account(
    db: Session, admin: CurrentUser, user_id: uuid.UUID, data: AccountUpdate
) -> AccountItem:
    ensure_admin(admin)
    user = _get(db, user_id)
    _guard_admins(db, admin, user, data)
    role = data.role or Role(user.role)
    team_id = data.team_id if "team_id" in data.model_fields_set else user.team_id
    if data.role is not None or "team_id" in data.model_fields_set:
        old_team = user.team_id
        user.team_id = _team_for(db, role, team_id)
        user.role = role.value
        if user.team_id is not None and user.team_id != old_team:
            # 名下客户和进行中的业务跟人走，否则新主管看不到、审批还找原主管
            transfer_service.move_member_team(db, user.id, user.team_id)
    if data.name is not None:
        user.name = data.name.strip()
    if data.active is not None and data.active != user.active:
        user.active = data.active
        user.token_version += 1  # 停用立即下线；重新启用也要重新登录
        if not data.active:
            _notify_handover(db, user, _customers(db).get(user.id, 0))
    db.flush()
    forget_user(user.id)
    return _one(db, user)


def reset_password(db: Session, admin: CurrentUser, user_id: uuid.UUID) -> TempPassword:
    ensure_admin(admin)
    user = _get(db, user_id)
    password = temp_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.token_version += 1
    db.flush()
    forget_user(user.id)
    return TempPassword(account=_one(db, user), temp_password=password)


# ---------- 团队 ----------


def list_teams(db: Session, admin: CurrentUser) -> list[TeamItem]:
    ensure_admin(admin)
    users = db.scalars(select(User).where(User.active.is_(True))).all()
    lines = {line.id: line for line in db.scalars(select(ProductLine)).all()}
    out = []
    for team in db.scalars(select(Team).order_by(Team.created_at)).all():
        members = [u for u in users if u.team_id == team.id]
        managers = [u.name for u in members if u.role == Role.MANAGER.value]
        line = lines.get(team.default_product_line_id) if team.default_product_line_id else None
        out.append(
            TeamItem(
                id=team.id,
                name=team.name,
                members=len(members),
                managers=managers,
                default_product_line_id=line.id if line else None,
                default_product_line=line.name if line else None,
                pack=line.pack if line else None,
            )
        )
    return out


def _set_default_line(db: Session, team: Team, data: TeamIn) -> None:
    """请求里带了 default_product_line_id 才改；null 表示改回系统默认行业包。"""
    if "default_product_line_id" not in data.model_fields_set:
        return
    line_id = data.default_product_line_id
    if line_id is not None:
        line = db.get(ProductLine, line_id)
        if line is None:
            raise BizError(ErrorCode.NOT_FOUND, "产品线不存在")
        if not line.enabled:
            raise BizError(ErrorCode.VALIDATION, f"产品线「{line.name}」已停用", {"rule": "pack"})
    team.default_product_line_id = line_id


def _team_item(db: Session, admin: CurrentUser, team_id: uuid.UUID) -> TeamItem:
    return next(t for t in list_teams(db, admin) if t.id == team_id)


def create_team(db: Session, admin: CurrentUser, data: TeamIn) -> TeamItem:
    ensure_admin(admin)
    name = data.name.strip()
    if db.scalar(select(Team.id).where(Team.name == name)) is not None:
        raise BizError(ErrorCode.DUPLICATE, f"团队「{name}」已存在")
    team = Team(name=name)
    _set_default_line(db, team, data)
    db.add(team)
    db.flush()
    return _team_item(db, admin, team.id)


def rename_team(db: Session, admin: CurrentUser, team_id: uuid.UUID, data: TeamIn) -> TeamItem:
    ensure_admin(admin)
    team = db.get(Team, team_id)
    if team is None:
        raise BizError(ErrorCode.NOT_FOUND, "团队不存在")
    name = data.name.strip()
    clash = db.scalar(select(Team.id).where(Team.name == name, Team.id != team_id))
    if clash is not None:
        raise BizError(ErrorCode.DUPLICATE, f"团队「{name}」已存在")
    team.name = name
    _set_default_line(db, team, data)
    db.flush()
    forget_user()
    return _team_item(db, admin, team.id)
