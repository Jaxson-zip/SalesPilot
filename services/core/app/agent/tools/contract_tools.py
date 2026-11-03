"""合同、提成、回款查询工具（只读）：薄包装 contract_service.list_contracts，按当前用户的数据范围。

回归：问「我这个月提成多少」「哪些合同回款逾期」，模型没有工具可查，只能让销售自己报合同明细。
"""

from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolContext, ToolResult, ToolSpec
from app.crm.schemas.common import PageParams
from app.crm.schemas.finance import ContractItem
from app.crm.services import contract_service, target_service, user_service
from app.crm.services.contract_service import ContractFilter


class ListContractsArgs(BaseModel):
    owner_name: str | None = Field(
        default=None, max_length=50, description="只看某位同事负责的合同（主管 / 管理员用）"
    )
    overdue_only: bool = Field(default=False, description="只看回款逾期的合同")


def _row(c: ContractItem) -> dict[str, Any]:
    nxt = c.next_payment
    return {
        "code": c.code,
        "customer": c.customer.name if c.customer else None,
        "owner": c.owner.name if c.owner else None,
        "status": "已收齐" if c.status == "paid" else "回款中",
        "amount": c.amount,
        "paid_amount": c.paid_amount,
        "overdue_amount": c.overdue_amount,
        "estimated": c.commission.estimated,
        "confirmed": c.commission.confirmed,
        "next_payment": (
            {
                "name": nxt.name,
                "remaining": nxt.amount,  # 本期还差的金额
                "plan_amount": nxt.plan_amount,  # 本期总额
                "due_date": str(nxt.due_date),
                "overdue_days": nxt.overdue_days,
            }
            if nxt
            else None
        ),
    }


def _filtered_summary(rows: list[dict[str, Any]]) -> str:
    """筛选后只按筛出的合同合计。

    回归：按负责人筛选时原来照搬全部合同的合计，
    张晨名下显示「本月新签 ¥92,000」（其实是李薇签的）。
    """

    def total(key: str) -> int:
        return sum(int(r[key] or 0) for r in rows)

    unpaid = total("amount") - total("paid_amount")
    return (
        f"筛出 {len(rows)} 份合同；预估提成 ¥{total('estimated') / 100:,.0f}，"
        f"已按回款确认 ¥{total('confirmed') / 100:,.0f}；待回款 ¥{unpaid / 100:,.0f}，"
        f"其中逾期 ¥{total('overdue_amount') / 100:,.0f}"
    )


def list_contracts(ctx: ToolContext, args: ListContractsArgs) -> ToolResult:
    with ctx.session() as db:
        owners = []
        if args.owner_name:
            users = user_service.list_users(db, ctx.user).items
            owners = [u.id for u in users if args.owner_name.strip() in u.name]
            if not owners:
                return ToolResult(ok=True, summary=f"可见范围内没有叫「{args.owner_name}」的同事")
        f = ContractFilter(owner_id=owners, overdue=["overdue"] if args.overdue_only else [])
        page = contract_service.list_contracts(
            db, ctx.user, None, PageParams(page=1, page_size=50), f=f
        )
    rows = [_row(c) for c in page.items]
    if args.owner_name or args.overdue_only:
        summary = _filtered_summary(rows)
        data: dict[str, Any] = {"contracts": rows}
    else:
        s = page.summary
        summary = (
            f"{page.total} 份合同；本月新签 ¥{s.month_amount / 100:,.0f}；"
            f"全部合同预估提成 ¥{s.estimated_commission / 100:,.0f}，"
            f"已按回款确认 ¥{s.confirmed_commission / 100:,.0f}；"
            f"待回款 ¥{s.unpaid_amount / 100:,.0f}"
        )
        data = {"summary": s.model_dump(), "contracts": rows}
    return ToolResult(ok=True, summary=summary, data=data)


CONTRACT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "list_contracts",
        "查合同、提成和回款：每份合同的金额、已回款、逾期金额、下一期回款、预估 / 已确认提成。"
        "用户问提成多少、回款情况、哪些合同逾期、某位同事签了多少时使用；提成按合同里的数，"
        "不要让用户自己报合同明细，也不要用 calc_commission 重新估算已签的合同",
        ListContractsArgs,
        list_contracts,
    ),
]


class TargetBoardArgs(BaseModel):
    month: str | None = Field(default=None, description="YYYY-MM，不填为本月")


def team_targets(ctx: ToolContext, args: TargetBoardArgs) -> ToolResult:
    """本月（或指定月）每个人的业绩目标、已签、完成率、预测（数据范围同业绩目标页）。"""
    with ctx.session() as db:
        board = target_service.board(db, ctx.user, args.month)
    rows = [
        {
            "name": r.user.name,
            "team": r.team_name,
            "target": r.target,
            "achieved": r.achieved,
            "contracts": r.contracts,
            "forecast": r.forecast,
            "rate": r.rate,
        }
        for r in board.rows
        if r.active
    ]
    summary = (
        f"{board.month} 共 {len(rows)} 人；时间进度 {board.time_progress:.0%}，"
        f"已签 ¥{board.total.achieved / 100:,.0f}"
    )
    data = {"month": board.month, "time_progress": board.time_progress, "rows": rows}
    return ToolResult(ok=True, summary=summary, data=data)


CONTRACT_TOOLS.append(
    ToolSpec(
        "team_targets",
        "查某个月（默认本月）每个人的业绩目标、当月新签合同金额、完成率、预测成交和所属团队。"
        "用户问本月业绩、谁完成得好或差、哪个团队落后、谁最需要关注时使用；"
        "pipeline_summary 是累计漏斗，不分月份也不分人",
        TargetBoardArgs,
        team_targets,
    )
)
