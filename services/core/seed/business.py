"""导入业务模块演示数据。固定 UUID + merge，可重复执行（重复执行会把演示单据恢复到初始状态）。

毛利、提成、制度校验结果全部调用 app.rules / service 中的规则函数计算，不在种子里写死。
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.common import storage
from app.crm.models import (
    Activity,
    Approval,
    Attachment,
    Commission,
    Contact,
    Contract,
    Expense,
    Opportunity,
    Payment,
    PaymentPlan,
    Quote,
    QuoteItem,
)
from app.crm.services import contract_service
from app.crm.services.codes import local_today, month_start, next_code
from app.crm.services.demo import demo_id
from app.crm.services.expense_service import policy_check
from app.crm.services.quote_service import approval_reasons, commission_lines
from app.packs.registry import get_pack
from app.rules import calc_commission, check_expense_policy, check_margin, load_rules
from app.rules.crm_calc import headcount_of
from app.rules.loader import RuleSet
from seed import business_data as bd
from seed.data import MANAGER, SALES
from seed.files import invoice_pdf, receipt_png
from seed.workflow import seed_workflow

OWNER = {"owner_id": SALES.id, "team_id": SALES.team_id}


def _code(
    db: Session, model: Any, row_id: uuid.UUID, column: InstrumentedAttribute[Any], prefix: str
) -> str:
    existing = db.get(model, row_id)
    return existing.code if existing is not None else next_code(db, column, prefix)


def seed_contacts(db: Session) -> None:
    for row in bd.CONTACTS:
        values = {k: v for k, v in row.items() if k != "key"}
        db.merge(Contact(id=demo_id(f"contact:{row['key']}"), **values, **OWNER))


def closed_at() -> datetime:
    """演示用成交时间：3 天前，但不早于本月 1 日。"""
    return max(month_start(), datetime.now(UTC) - timedelta(days=3))


def _close_won_opportunities(db: Session) -> None:
    """赢单商机的成交时间放在本月内，工作台「本月赢单」有数据。"""
    closed = closed_at()
    for opp_id in (demo_id("opp:yuehai"), demo_id("opp:nanshan")):
        opp = db.get(Opportunity, opp_id)
        if opp is not None:
            opp.closed_at = closed


def _seed_quote_items(
    db: Session, quote_id: uuid.UUID, items: list[dict[str, Any]]
) -> list[QuoteItem]:
    db.execute(delete(QuoteItem).where(QuoteItem.quote_id == quote_id))
    rows = [
        QuoteItem(id=demo_id(f"quote-item:{quote_id}:{i}"), quote_id=quote_id, **item)
        for i, item in enumerate(items)
    ]
    db.add_all(rows)
    db.flush()
    return rows


def _seed_quote(db: Session, row: dict[str, Any]) -> tuple[Quote, list[QuoteItem]]:
    rules = load_rules(get_pack(row["pack"]).rules_file)
    total_cost = sum(i["unit_cost"] * i["qty"] for i in row["items"])
    total_price = sum(i["unit_price"] * i["qty"] for i in row["items"])
    margin = check_margin(total_cost, total_price, rules)
    keys = ("id", "opportunity_id", "customer_id", "pack", "tier", "status", "source")
    quote = db.merge(
        Quote(
            **{k: row[k] for k in keys},
            code=_code(db, Quote, row["id"], Quote.code, "Q"),
            total_cost=total_cost,
            total_price=total_price,
            margin_rate=margin.margin_rate,
            idempotency_key=None,
            **OWNER,
        )
    )
    db.flush()
    return quote, _seed_quote_items(db, quote.id, row["items"])


def _seed_contract(
    db: Session, quote: Quote, items: list[QuoteItem], ratio: float, key: str
) -> None:
    contract_id = demo_id(f"contract:{key}")
    paid = round(quote.total_price * ratio)
    db.merge(
        Contract(
            id=contract_id,
            code=_code(db, Contract, contract_id, Contract.code, "C"),
            quote_id=quote.id,
            customer_id=quote.customer_id,
            amount=quote.total_price,
            paid_amount=paid,
            status="paid" if paid >= quote.total_price else "active",
            created_at=closed_at(),
            **OWNER,
        )
    )
    db.flush()
    # 已回款的合同带一条到账记录；迁移已补过历史记录的不再重复
    has_payment = db.scalar(select(Payment.id).where(Payment.contract_id == contract_id))
    if paid and not has_payment:
        db.add(
            Payment(
                id=demo_id(f"payment:{key}"),
                contract_id=contract_id,
                amount=paid,
                received_on=local_today() - timedelta(days=7),
                reference_no=f"DEMO-{key.upper()}-01",
                note="演示数据：首付款到账",
                created_by=MANAGER.id,
            )
        )
    db.flush()
    rules = load_rules(get_pack(quote.pack).rules_file)
    _seed_payment_plan(db, db.get(Contract, contract_id), rules, key)
    result = calc_commission(
        commission_lines(items, quote.total_price), quote.margin_rate, ratio, rules
    )
    db.merge(
        Commission(
            id=demo_id(f"commission:{key}"),
            contract_id=contract_id,
            user_id=SALES.id,
            estimated=result.estimated,
            confirmed=result.confirmed,
            **OWNER,
        )
    )


# 演示逾期回款：悦海合同的到货验收款改为 5 天前到期（已回款 40%，这一期只收了一部分）
OVERDUE_DEMO = {"yuehai": (2, 5)}
# 演示开票跟踪：期次 → (状态, 几天前开票)。悦海第 2 期已开票未回款，第 3 期销售已申请等主管开票
INVOICE_DEMO: dict[str, dict[int, tuple[str, int]]] = {
    "yuehai": {1: ("issued", 40), 2: ("issued", 12), 3: ("requested", 0)},
}


def _seed_payment_plan(db: Session, contract: Contract | None, rules: RuleSet, key: str) -> None:
    assert contract is not None
    db.execute(delete(PaymentPlan).where(PaymentPlan.contract_id == contract.id))
    contract_service.create_default_plan(db, contract, rules)
    if key in OVERDUE_DEMO:
        seq, days_ago = OVERDUE_DEMO[key]
        plan = db.scalar(
            select(PaymentPlan).where(
                PaymentPlan.contract_id == contract.id, PaymentPlan.seq == seq
            )
        )
        assert plan is not None
        plan.due_date = local_today() - timedelta(days=days_ago)
    for seq, (status, days_ago) in INVOICE_DEMO.get(key, {}).items():
        plan = db.scalar(
            select(PaymentPlan).where(
                PaymentPlan.contract_id == contract.id, PaymentPlan.seq == seq
            )
        )
        assert plan is not None
        plan.invoice_status = status
        plan.invoice_type = "special"
        if status == "issued":
            plan.invoice_no = f"4403{contract.code[-3:]}{seq:04d}"
            plan.invoiced_on = local_today() - timedelta(days=days_ago)
        else:
            plan.invoice_requested_at = datetime.now(UTC)
            plan.invoice_note = "抬头：粤海物流集团有限公司"


def _seed_approval(
    db: Session,
    key: str,
    target_type: str,
    target: Quote | Expense,
    reason: str,
    suggestion: str | None,
) -> None:
    db.merge(
        Approval(
            id=demo_id(f"approval:{key}"),
            target_type=target_type,
            target_id=target.id,
            reason=reason,
            ai_suggestion=suggestion,
            status="pending",
            approver_id=None,
            comment=None,
            decided_at=None,
            **OWNER,
        )
    )


def seed_quotes(db: Session) -> None:
    for row in bd.QUOTES:
        quote, items = _seed_quote(db, row)
        key = f"quote:{quote.id}"
        if row["status"] == "pending_approval":
            reasons = approval_reasons(quote, items, load_rules(get_pack(quote.pack).rules_file))
            _seed_approval(db, key, "quote", quote, "；".join(reasons), row.get("suggestion"))
        if row.get("paid_ratio") is not None:
            contract_key = "yuehai" if quote.id == bd.Q_YUEHAI else "nanshan"
            _seed_contract(db, quote, items, row["paid_ratio"], contract_key)
    _close_won_opportunities(db)


def _seed_attachments(db: Session, expense: Expense, files: list[tuple[str, str]]) -> None:
    db.execute(
        delete(Attachment).where(
            Attachment.owner_type == "expense", Attachment.owner_ref_id == expense.id
        )
    )
    for i, (kind, name) in enumerate(files):
        att_id = demo_id(f"attachment:{expense.id}:{i}")
        is_pdf = name.endswith(".pdf")
        content = (
            invoice_pdf("Invoice " + expense.code, f"{expense.amount / 100:.2f}")
            if is_pdf
            else receipt_png()
        )
        key = f"expense/{expense.id}/{att_id}{'.pdf' if is_pdf else '.png'}"
        storage.save(key, content)
        db.add(
            Attachment(
                id=att_id,
                owner_type="expense",
                owner_ref_id=expense.id,
                kind=kind,
                file_name=name,
                mime="application/pdf" if is_pdf else "image/png",
                size=len(content),
                storage_key=key,
                **OWNER,
            )
        )


def seed_expenses(db: Session) -> None:
    rules = load_rules()
    skip = {"suggestion", "attachments"}
    for row in bd.EXPENSES:
        # 人数由结构化参与人计算（契约 v3 §17），不使用种子里写的数字
        row = {**row, "headcount": headcount_of(
            len(row["contact_ids"]), len(row["colleague_ids"]), row["extra_guests"]
        )}  # fmt: skip
        check = policy_check(row["type"], row["amount"], row["headcount"], rules)
        expense = db.merge(
            Expense(
                **{k: v for k, v in row.items() if k not in skip},
                code=_code(db, Expense, row["id"], Expense.code, "E"),
                policy_check=check.model_dump(),
                idempotency_key=None,
                **OWNER,
            )
        )
        db.flush()
        _seed_attachments(db, expense, row["attachments"])
        if row["status"] == "pending_approval":
            reason = check_expense_policy(
                row["amount"], row["headcount"], row["type"], rules
            ).reason
            _seed_approval(
                db, f"expense:{expense.id}", "expense", expense, reason, row.get("suggestion")
            )


def seed_activities(db: Session) -> None:
    now = datetime.now(UTC)
    for row in bd.ACTIVITIES:
        actor = row["actor"]
        db.merge(
            Activity(
                id=demo_id(f"activity:{row['key']}"),
                subject_type=row["subject_type"],
                subject_id=row["subject_id"],
                actor_id=actor.id if actor else None,
                source="manual" if actor else "agent",
                action=row["action"],
                content=row["content"],
                created_at=now - timedelta(hours=row["hours_ago"]),
                **OWNER,
            )
        )


def seed_business(db: Session) -> None:
    seed_contacts(db)
    seed_quotes(db)
    db.flush()
    seed_expenses(db)
    seed_activities(db)
    db.flush()
    seed_workflow(db)
