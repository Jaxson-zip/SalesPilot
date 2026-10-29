"""工作台 service（接口契约 §1）：指标卡 + 漏斗。「本月」按北京时间自然月。"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser, Role
from app.common.scope import View, apply_scope
from app.crm.models import Commission, Contract, Opportunity
from app.crm.schemas.dashboard import Dashboard
from app.crm.schemas.opportunity import FINAL_STAGES
from app.crm.services import approval_service, opportunity_service, target_service, task_service
from app.crm.services.codes import month_start


def _sum_count(db: Session, stmt: Any) -> tuple[int, int]:
    count, amount = db.execute(stmt).one()
    return int(count or 0), int(amount or 0)


def _opportunity_kpis(db: Session, user: CurrentUser, view: View | None) -> dict[str, int]:
    agg = select(func.count(), func.coalesce(func.sum(Opportunity.amount), 0))
    opened = agg.where(Opportunity.stage.not_in(FINAL_STAGES))
    # 「本月成交」按本月新签合同金额算，与合同页同一口径（不走商机直接成交的报价也算进来）
    signed = select(func.count(), func.coalesce(func.sum(Contract.amount), 0)).where(
        Contract.created_at >= month_start()
    )
    _, won_amount = _sum_count(db, apply_scope(signed, Contract, user, view))
    open_count, open_amount = _sum_count(db, apply_scope(opened, Opportunity, user, view))
    return {
        "won_amount_month": won_amount,
        "open_opportunities": open_count,
        "open_amount": open_amount,
    }


def _commission_kpis(db: Session, user: CurrentUser, view: View | None) -> dict[str, int]:
    """本月新签合同对应的提成：预估合计与已按回款确认的合计。"""
    stmt = (
        select(
            func.coalesce(func.sum(Commission.estimated), 0),
            func.coalesce(func.sum(Commission.confirmed), 0),
        )
        .join(Contract, Contract.id == Commission.contract_id)
        .where(Contract.created_at >= month_start())
    )
    estimated, confirmed = db.execute(apply_scope(stmt, Commission, user, view)).one()
    return {
        "estimated_commission_month": int(estimated),
        "confirmed_commission_month": int(confirmed),
    }


def get_dashboard(db: Session, user: CurrentUser, view: View | None = None) -> Dashboard:
    # 主管的「待审批」始终是待本团队审批的数量，不随视图切换
    approval_view = View.TEAM if user.role is Role.MANAGER else view
    return Dashboard(
        **_opportunity_kpis(db, user, view),
        **_commission_kpis(db, user, view),
        pending_approvals=approval_service.count_pending(db, user, approval_view),
        **task_service.count_due(db, user, view),
        funnel=opportunity_service.funnel(db, user, view),
        target_month=target_service.month_target(db, user, view),
    )
