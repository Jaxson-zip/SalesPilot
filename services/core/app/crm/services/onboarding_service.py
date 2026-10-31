"""新手上手清单（接口契约 §36）：工作台顶部的几步，按库里的真实数据判断做没做完，不靠前端记。

步骤按角色给：能改系统配置的人（管理员；个人模式下的主管）先接模型、调报价参数；
能做业务的人（销售、主管）录客户 → 记跟进 → AI 出方案 → 把报价链接发给客户。
管理员对业务数据只读，所以只有配置两步。
"""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.permissions import can_configure
from app.crm.models import AiUsage, ConfigOverride, Customer, Followup, Quote, QuoteShare

StepKey = Literal["model", "pricing", "customer", "followup", "solution", "share"]


class OnboardingStep(BaseModel):
    key: StepKey
    title: str
    detail: str
    href: str
    done: bool


class Onboarding(BaseModel):
    steps: list[OnboardingStep]
    done: int
    total: int


Check = Callable[[Session, CurrentUser], bool]


def _any(db: Session, stmt: object) -> bool:
    return bool(db.scalar(select(exists(stmt))))  # type: ignore[arg-type]


STEPS: list[tuple[StepKey, str, str, str, Check]] = [
    (
        "model",
        "接入大模型",
        "填一个模型厂商的 Key，AI 出方案、写跟进才能用",
        "/settings/models",
        lambda db, u: _any(db, select(AiUsage.id)),
    ),
    (
        "pricing",
        "按你的报价习惯调好参数",
        "人天单价、毛利底线、折扣上限在行业包参数里改，报价都按它算",
        "/settings/packs",
        lambda db, u: _any(db, select(ConfigOverride.id).where(ConfigOverride.scope != "global")),
    ),
    (
        "customer",
        "录入第一个客户",
        "客户页右上角新建，或者直接在 AI 工作台说「新建客户…」",
        "/customers",
        lambda db, u: _any(db, select(Customer.id).where(Customer.owner_id == u.id)),
    ),
    (
        "followup",
        "记一条跟进",
        "把聊天记录或会议纪要贴给 AI，它会整理成跟进并安排下一步",
        "/ai?mode=work",
        lambda db, u: _any(db, select(Followup.id).where(Followup.owner_id == u.id)),
    ),
    (
        "solution",
        "让 AI 出第一份方案和报价",
        "说清楚客户要做什么，AI 拆需求、给三档方案，价格按规则算",
        "/ai?mode=work",
        lambda db, u: _any(
            db, select(Quote.id).where(Quote.owner_id == u.id, Quote.source == "agent")
        ),
    ),
    (
        "share",
        "把报价链接发给客户",
        "报价审批通过后点「分享给客户」，客户手机上直接看，打开时会提醒你",
        "/quotes",
        lambda db, u: _any(db, select(QuoteShare.id).where(QuoteShare.created_by == u.id)),
    ),
]
CONFIG_STEPS: frozenset[StepKey] = frozenset({"model", "pricing"})


def _wanted(user: CurrentUser, key: StepKey) -> bool:
    if key in CONFIG_STEPS:
        return can_configure(user)
    return user.role is not Role.ADMIN


def get_onboarding(db: Session, user: CurrentUser) -> Onboarding:
    steps = [
        OnboardingStep(key=key, title=title, detail=detail, href=href, done=check(db, user))
        for key, title, detail, href, check in STEPS
        if _wanted(user, key)
    ]
    return Onboarding(steps=steps, done=sum(s.done for s in steps), total=len(steps))
