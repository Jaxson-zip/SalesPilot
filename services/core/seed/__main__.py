"""导入演示数据：python -m seed [--with-kb]

使用固定 UUID + merge，可重复执行。--with-kb 会顺带入库知识库（需要网关可用）。
"""

import argparse
import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, forget_user
from app.common.config import get_settings
from app.common.db import session_scope
from app.common.errors import BizError
from app.common.passwords import hash_password, verify_password
from app.crm.models import Customer, Followup, Opportunity, ProductLine, SalesTarget, Team, User
from app.crm.services.demo import DEMO_LOGINS
from app.crm.services.target_service import parse_month
from seed import data
from seed.business import seed_business
from seed.guard import confirm_reset

logger = logging.getLogger("seed")

# --reset 清空的业务表，录演示视频前用它去掉测试和试用产生的数据。
RESET_TABLES = (
    "notifications",
    "tasks",
    "activities",
    "approvals",
    "attachments",
    "commissions",
    "payments",
    "payment_plans",
    "invoice_events",
    "contracts",
    "quote_shares",  # 发给客户的报价链接跟着报价一起清
    "quote_items",
    "quotes",
    "expenses",
    "followups",
    "opportunities",
    "contacts",
    "customers",
    "agent_threads",
    "daily_reports",
    "ai_usage",
    "code_counters",  # 单号从头编
    "ai_feedback",
    "sales_targets",
    "job_runs",  # 运行记录清掉后，当天的定时任务会按新数据重新跑一次
    "audit_logs",  # 日报草稿按今天的操作日志汇总，不清会把测试时的操作算进演示数据
)
# 重置时保留：组织、行业包配置、竞品战卡、知识库、外部集成、定时任务配置
KEEP_TABLES = (
    "users",
    "teams",
    "product_lines",
    "config_overrides",
    "competitors",
    "kb_chunks",
    "integrations",
    "scheduled_jobs",
)


# LangGraph 的会话存储（不在 ORM 里，由 PostgresSaver 建表）：会话表清空时一起清，
# 否则旧对话内容还在、只是没有登记（回归：重置后 AI 工作台仍显示旧对话）
CHECKPOINT_TABLES = ("checkpoints", "checkpoint_writes", "checkpoint_blobs")


def reset_business_data(db: Session) -> None:
    db.execute(text(f"TRUNCATE {', '.join(RESET_TABLES)} RESTART IDENTITY CASCADE"))
    present = [
        t for t in CHECKPOINT_TABLES if db.execute(text(f"select to_regclass('{t}')")).scalar()
    ]
    if present:
        db.execute(text(f"TRUNCATE {', '.join(present)}"))
    logger.info(
        "reset: truncated %d business tables, %d checkpoint tables", len(RESET_TABLES), len(present)
    )


def _owned(row: dict[str, Any]) -> dict[str, Any]:
    """把 owner（CurrentUser）展开成 owner_id / team_id。"""
    values = {k: v for k, v in row.items() if k != "owner"}
    owner: CurrentUser | None = row.get("owner")
    if owner is not None:
        values.update(owner_id=owner.id, team_id=owner.team_id)
    return values


def seed_org(db: Session, reset_passwords: bool = False) -> None:
    for line in data.PRODUCT_LINES:
        db.merge(ProductLine(**line))
    db.merge(Team(id=data.TEAM["id"], name=data.TEAM["name"], default_product_line_id=data.PL_LLM))
    east = data.TEAM_EAST
    db.merge(Team(id=east["id"], name=east["name"], default_product_line_id=data.PL_SOFTWARE))
    db.flush()
    demo_password = get_settings().demo_password
    password = hash_password(demo_password)
    for u in data.USERS:
        user = db.merge(User(id=u.id, name=u.name, role=u.role.value, team_id=u.team_id))
        # 账号：已有登录名和密码的不覆盖（管理员可能改过）
        user.username = user.username or DEMO_LOGINS[u.id]
        user.password_hash = user.password_hash or password
        if reset_passwords:  # 分享演示环境前：演示账号统一回到 DEMO_PASSWORD，不要求首次改密码
            changed = not verify_password(demo_password, user.password_hash)
            user.password_hash, user.must_change_password = password, False
            if (
                changed
            ):  # 密码真的变了：之前签发的登录全部作废（回归：重置后旧 token 仍能以原身份访问）
                user.token_version = (user.token_version or 0) + 1
                forget_user(user.id)
    db.flush()
    team = db.get(Team, data.TEAM["id"])
    assert team is not None
    team.manager_id = data.MANAGER.id
    east_team = db.get(Team, data.TEAM_EAST["id"])
    assert east_team is not None
    east_team.manager_id = data.EAST_MANAGER.id


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
    seed_targets(db)


def seed_targets(db: Session) -> None:
    """本月业绩目标（主管改过的不覆盖）：工作台和「业绩目标」页有完成进度可看。"""
    month = parse_month(None)
    for user, amount in data.TARGETS:
        exists = db.scalar(
            select(SalesTarget.id).where(
                SalesTarget.owner_id == user.id, SalesTarget.month == month
            )
        )
        if exists is None:
            db.add(SalesTarget(owner_id=user.id, team_id=user.team_id, month=month, amount=amount))


def main() -> None:
    parser = argparse.ArgumentParser(description="导入演示数据")
    parser.add_argument("--with-kb", action="store_true", help="同时入库知识库（需要网关）")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先清空客户、商机、报价、报销等业务数据，再导入演示数据",
    )
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="把演示账号的密码统一重置为 DEMO_PASSWORD（分享演示环境前用），已登录的会被踢下线",
    )
    parser.add_argument("--yes", action="store_true", help="--reset 不再询问（非交互运行时必须带）")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with session_scope() as db:
        if args.reset:
            if not confirm_reset(db, args.yes):
                raise SystemExit(1)
            reset_business_data(db)
        seed_org(db, reset_passwords=args.reset_passwords)
        seed_crm(db)
        db.flush()
        seed_business(db)
    logger.info(
        "seed done: %d customers, %d opportunities, quotes / contracts / expenses / approvals",
        len(data.CUSTOMERS),
        len(data.OPPORTUNITIES),
    )
    if args.with_kb:
        from app.rag.ingest import ingest

        try:
            logger.info("knowledge base: %s", ingest("all"))
        except BizError as exc:
            # 没配 Embedding Key 或网关没启动时属于预期情况：业务数据已导入，知识库稍后再补
            logger.warning(
                "knowledge base skipped: %s (configure an embedding model, then run "
                "`python -m app.rag.ingest --scope all`)",
                exc.message,
            )
        except Exception:
            logger.exception("knowledge base ingest failed")


if __name__ == "__main__":
    main()
