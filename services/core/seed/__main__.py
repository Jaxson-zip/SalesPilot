"""导入演示数据：python -m seed [--with-kb]

使用固定 UUID + merge，可重复执行。--with-kb 会顺带入库知识库（需要网关可用）。
"""

import argparse
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.db import session_scope
from app.crm.models import Customer, Followup, Opportunity, ProductLine, Team, User
from seed import data

logger = logging.getLogger("seed")


def _owned(row: dict[str, Any]) -> dict[str, Any]:
    """把 owner（CurrentUser）展开成 owner_id / team_id。"""
    values = {k: v for k, v in row.items() if k != "owner"}
    owner: CurrentUser | None = row.get("owner")
    if owner is not None:
        values.update(owner_id=owner.id, team_id=owner.team_id)
    return values


def seed_org(db: Session) -> None:
    for line in data.PRODUCT_LINES:
        db.merge(ProductLine(**line))
    db.merge(Team(id=data.TEAM["id"], name=data.TEAM["name"], default_product_line_id=data.PL_LLM))
    db.flush()
    for u in data.USERS:
        db.merge(User(id=u.id, name=u.name, role=u.role.value, team_id=u.team_id))
    db.flush()
    team = db.get(Team, data.TEAM["id"])
    assert team is not None
    team.manager_id = data.MANAGER.id


def seed_crm(db: Session) -> None:
    for row in data.CUSTOMERS:
        db.merge(Customer(**_owned(row)))
    db.flush()
    for row in data.OPPORTUNITIES:
        db.merge(Opportunity(**_owned(row)))
    db.flush()
    owners = {c["id"]: c["owner"] for c in data.CUSTOMERS}
    for row in data.FOLLOWUPS:
        db.merge(Followup(**_owned({**row, "owner": owners[row["customer_id"]]})))


def main() -> None:
    parser = argparse.ArgumentParser(description="导入演示数据")
    parser.add_argument("--with-kb", action="store_true", help="同时入库知识库（需要网关）")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with session_scope() as db:
        seed_org(db)
        seed_crm(db)
    logger.info(
        "seed done: %d customers, %d opportunities", len(data.CUSTOMERS), len(data.OPPORTUNITIES)
    )
    if args.with_kb:
        from app.rag.ingest import ingest

        try:
            logger.info("knowledge base: %s", ingest("all"))
        except Exception:
            logger.exception("knowledge base ingest failed (gateway unavailable?)")


if __name__ == "__main__":
    main()
