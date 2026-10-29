"""导入全部 ORM 模型，供 Alembic 和 metadata 使用。"""

from app.crm.models.audit import AuditLog
from app.crm.models.competitor import Competitor
from app.crm.models.customer import Activity, Contact, Customer, Followup
from app.crm.models.finance import Approval, Attachment, Expense
from app.crm.models.integration import Integration
from app.crm.models.job import JobRun, ScheduledJob
from app.crm.models.knowledge import AgentThread, KbChunk
from app.crm.models.org import ConfigOverride, ProductLine, Team, User
from app.crm.models.report import DailyReport
from app.crm.models.sales import (
    Commission,
    Contract,
    Opportunity,
    PaymentPlan,
    Quote,
    QuoteItem,
)
from app.crm.models.usage import AiUsage
from app.crm.models.workflow import Notification, Task

__all__ = [
    "Activity",
    "AgentThread",
    "AiUsage",
    "Approval",
    "Attachment",
    "AuditLog",
    "Commission",
    "Competitor",
    "ConfigOverride",
    "Contact",
    "Contract",
    "Customer",
    "DailyReport",
    "Expense",
    "Followup",
    "Integration",
    "JobRun",
    "KbChunk",
    "Notification",
    "Opportunity",
    "PaymentPlan",
    "ProductLine",
    "Quote",
    "QuoteItem",
    "ScheduledJob",
    "Task",
    "Team",
    "User",
]
