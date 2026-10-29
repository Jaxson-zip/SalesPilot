"""业绩目标：每人每月一个签约额目标（分）。团队目标 = 成员目标之和。"""

import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import OwnedMixin


class SalesTarget(OwnedMixin, Base):
    """owner_id 是目标所属的人，team_id 是设置时所在团队（数据范围按它过滤）。"""

    __tablename__ = "sales_targets"
    __table_args__ = (UniqueConstraint("owner_id", "month", name="uq_sales_targets_owner_month"),)

    month: Mapped[date] = mapped_column(Date)  # 当月 1 日
    amount: Mapped[int] = mapped_column(BigInteger)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
