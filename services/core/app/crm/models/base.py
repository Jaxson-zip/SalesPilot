"""ORM 公共字段：uuid 主键、created_at / updated_at、owner_id / team_id（数据范围过滤用）。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TimestampMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OwnedMixin(TimestampMixin):
    """业务数据：owner_id 为负责人（为空表示公海），team_id 冗余存储负责人所在团队。"""

    @declared_attr
    def owner_id(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(ForeignKey("users.id"), index=True, nullable=True)

    @declared_attr
    def team_id(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(ForeignKey("teams.id"), index=True, nullable=True)
