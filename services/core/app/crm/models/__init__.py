"""导入全部 ORM 模型，供 Alembic 和 metadata 使用。"""

from app.crm.models.customer import Activity, Contact, Customer, Followup
from app.crm.models.finance import Approval, Attachment, Expense
from app.crm.models.knowledge import AgentThread, KbChunk
from app.crm.models.org import ProductLine, Team, User
from app.crm.models.sales import Commission, Contract, Opportunity, Quote, QuoteItem

__all__ = [
    "Activity",
    "AgentThread",
    "Approval",
    "Attachment",
    "Commission",
    "Contact",
    "Contract",
    "Customer",
    "Expense",
    "Followup",
    "KbChunk",
    "Opportunity",
    "ProductLine",
    "Quote",
    "QuoteItem",
    "Team",
    "User",
]
