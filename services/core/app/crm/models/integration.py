"""外部集成配置（目前只有企业微信群机器人）：每种集成一行，由管理员在网页上维护。"""

from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import TimestampMixin


class Integration(TimestampMixin, Base):
    __tablename__ = "integrations"

    kind: Mapped[str] = mapped_column(String(20), unique=True)  # wecom
    # wecom：{"webhook_url": str, "events": [..], "enabled": bool}
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # 最近 20 次推送结果：[{"at", "event", "ok", "error", "title"}]
    recent: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    updated_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
