"""AI 工作台示例问题按当前用户的数据填写。

原来示例写死「把星河设计的商机推进到商务谈判」，商机删了、输单了还在推荐。
templates.yaml 的 ai_prompts 可以带占位符，按本人负责的数据填：
- {customer} {contact}：最近更新的、有联系人的客户和它的一位联系人；
- {opp_customer} {opp_name} {next_stage}：最近更新的进行中商机（线索～方案报价）和它的下一阶段。
  商务谈判的下一步是赢单，属于不可逆操作，不拿来当示例。
数据不够时用这条示例的 fallback；没有 fallback 就不显示这张卡片。
"""

import uuid
from string import Formatter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crm.models import Contact, Customer, Opportunity
from app.crm.schemas.opportunity import STAGE_LABELS, STAGES

ADVANCEABLE = ("lead", "qualified", "proposal")


def _customer_values(db: Session, owner_id: uuid.UUID) -> dict[str, str]:
    stmt = (
        select(Customer.name, Contact.name)
        .join(Contact, Contact.customer_id == Customer.id)
        .where(Customer.owner_id == owner_id)
        .order_by(Customer.updated_at.desc(), Contact.created_at)
        .limit(1)
    )
    row = db.execute(stmt).first()
    return {"customer": row[0], "contact": row[1]} if row else {}


def _opportunity_values(db: Session, owner_id: uuid.UUID) -> dict[str, str]:
    stmt = (
        select(Opportunity.name, Opportunity.stage, Customer.name)
        .join(Customer, Customer.id == Opportunity.customer_id)
        .where(Opportunity.owner_id == owner_id, Opportunity.stage.in_(ADVANCEABLE))
        .order_by(Opportunity.updated_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).first()
    if row is None:
        return {}
    name, stage, customer = row
    following = STAGES[STAGES.index(stage) + 1]
    return {"opp_name": name, "opp_customer": customer, "next_stage": STAGE_LABELS[following]}


def user_values(db: Session, owner_id: uuid.UUID) -> dict[str, str]:
    return _customer_values(db, owner_id) | _opportunity_values(db, owner_id)


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name}


def fill(prompts: list[dict[str, Any]], values: dict[str, str]) -> list[dict[str, Any]]:
    """填好占位符的示例（去掉 fallback 字段）；缺数据又没有 fallback 的示例不返回。"""
    out: list[dict[str, Any]] = []
    for p in prompts:
        text = str(p["prompt"])
        if _fields(text) <= values.keys():
            text = text.format(**values)
        elif p.get("fallback"):
            text = str(p["fallback"])
        else:
            continue
        out.append({k: v for k, v in p.items() if k != "fallback"} | {"prompt": text})
    return out
