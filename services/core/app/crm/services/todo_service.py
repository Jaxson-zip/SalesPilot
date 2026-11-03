"""工作台待办里除任务以外的事项：回款逾期 / 今天到期、今天的日报、待审批。

原来待办只读任务表，回款逾期和日报催交只发站内通知，待办里看不到。
这里按当前数据实时算（不读通知），处理完（登记回款、提交日报、审批完）就自动消失。
数据范围与工作台其他卡片一致：按 view 和角色过滤。
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.scope import View, apply_scope, resolve_view
from app.crm.models import Contract, Customer, DailyReport
from app.crm.schemas.todo import TodoItem
from app.crm.services import approval_service
from app.crm.services.codes import local_today
from app.crm.services.contract_service import due_soon_condition, overdue_condition, plan_states


def _yuan(fen: int) -> str:
    return f"¥{fen / 100:,.2f}"


def payment_items(db: Session, user: CurrentUser, view: View | None) -> list[TodoItem]:
    """逾期和今天到期、还没收齐的回款期次。"""
    stmt = select(Contract).where(
        Contract.status == "active", or_(overdue_condition(), due_soon_condition(0))
    )
    contracts = list(db.scalars(apply_scope(stmt, Contract, user, view)))
    ids = {c.customer_id for c in contracts}
    names = dict(db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(ids))).all())
    states = plan_states(db, contracts)
    today = local_today()
    items: list[TodoItem] = []
    for c in contracts:
        for plan, state in states[c.id]:
            overdue = state.status == "overdue"
            due_today = state.status in ("pending", "partial") and state.due_date == today
            if not overdue and not due_today:
                continue
            when = f"已逾期 {state.overdue_days} 天" if overdue else "今天到期"
            items.append(
                TodoItem(
                    kind="payment_overdue" if overdue else "payment_due",
                    title=f"催回款：{c.code} {plan.name}",
                    subject=names.get(c.customer_id, ""),
                    detail=f"应收 {_yuan(state.amount - state.paid)}，{when}",
                    due_date=state.due_date,
                    overdue=overdue,
                    link=f"/contracts?plan={c.id}",
                )
            )
    return sorted(items, key=lambda t: t.due_date or today)


def report_item(db: Session, user: CurrentUser, view: View | None) -> TodoItem | None:
    """销售本人工作日还没提交当天日报（与日报催交同一口径：只催销售、只在工作日）。"""
    today = local_today()
    if user.role is not Role.SALES or resolve_view(user, view) is not View.MINE:
        return None
    if today.weekday() >= 5:
        return None
    submitted = db.scalar(
        select(DailyReport.id).where(
            DailyReport.user_id == user.id,
            DailyReport.report_date == today,
            DailyReport.status == "submitted",
        )
    )
    if submitted:
        return None
    return TodoItem(
        kind="report",
        title="提交今天的日报",
        detail="AI 会按今天的跟进和操作生成草稿，确认后提交",
        due_date=today,
        link="/reports",
    )


def approval_item(db: Session, user: CurrentUser) -> TodoItem | None:
    """主管：待本团队审批的报价和报销（与工作台「待审批」同一口径，不随视图切换）。"""
    if user.role is not Role.MANAGER:
        return None
    pending = approval_service.count_pending_by_type(db, user, View.TEAM)
    total = sum(pending.values())
    if not total:
        return None
    parts = [f"报价 {pending['quote']} 条" if pending["quote"] else ""]
    parts.append(f"报销 {pending['expense']} 条" if pending["expense"] else "")
    return TodoItem(
        kind="approval",
        title=f"处理待审批（{total} 条）",
        detail="、".join(p for p in parts if p),
        link="/approvals",
    )


def list_todos(db: Session, user: CurrentUser, view: View | None = None) -> list[TodoItem]:
    """顺序：待审批、日报、回款（逾期在前）；任务由前端另取后合并。"""
    head = [approval_item(db, user), report_item(db, user, view)]
    return [t for t in head if t] + payment_items(db, user, view)
