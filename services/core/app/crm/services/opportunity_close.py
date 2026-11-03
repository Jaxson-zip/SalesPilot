"""商机进入终态后的收尾：赢单推喜报、关闭同商机的其他报价；输单关闭未成交的报价、待审批和未完成的待办。

输单后不应再有「报价已审批，还没发给客户」「跟进报价」这类推进提醒：
- 草稿 / 待审批 / 已审批 / 已发送的报价改为「已关闭」，待审批的审批单一并驳回；
- 商机下未完成的待办（含发送报价时自动建的跟进任务）自动完成，备注写明原因。
"""

from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.crm.models import Customer, Opportunity, Quote, Task, User
from app.crm.services import quote_closing, wecom_service

LOST_NOTE = "商机已输单，自动关闭"
WON_NOTE = "商机已按其他报价赢单，自动关闭"


def push_won(db: Session, opp: Opportunity) -> None:
    customer = db.get(Customer, opp.customer_id)
    owner = db.get(User, opp.owner_id) if opp.owner_id else None
    wecom_service.queue(
        db,
        "deal_won",
        f"赢单：{opp.name}",
        f"**🎉 赢单喜报**\n"
        f"> 客户：{customer.name if customer else '—'}\n"
        f"> 商机：{opp.name}\n"
        f'> 金额：<font color="info">¥{opp.amount / 100:,.0f}</font>\n'
        f"> 负责人：{owner.name if owner else '—'}",
    )


def close_lost(db: Session, user: CurrentUser, opp: Opportunity) -> str:
    """关闭输单商机下未成交的报价和未完成的待办，返回追加到阶段动态里的说明。"""
    quotes = quote_closing.close_open_quotes(
        db, user, Quote.opportunity_id == opp.id, LOST_NOTE, "商机已输单"
    )
    tasks = quote_closing.complete_tasks(
        db, (Task.subject_type == "opportunity") & (Task.subject_id == opp.id), LOST_NOTE
    )
    return quote_closing.summary(quotes, tasks)


def close_won_siblings(db: Session, user: CurrentUser, opp: Opportunity) -> str:
    """赢单后同一商机下其他还没成交的报价（别的版本 / 档位）关闭，客户手里只剩成交的那一份。

    商机下的其他待办不动：赢单后还有签合同、交付对接等事要做。
    """
    quotes = quote_closing.close_open_quotes(
        db, user, Quote.opportunity_id == opp.id, WON_NOTE, "商机已赢单"
    )
    return quote_closing.summary(quotes, 0)
