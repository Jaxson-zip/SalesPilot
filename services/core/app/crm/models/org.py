"""组织：团队、用户、产品线（产品线 → 行业包映射由管理员维护）。"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import Base
from app.crm.models.base import TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(100))
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", use_alter=True, name="fk_teams_manager_id"), nullable=True
    )
    default_product_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_lines.id"), nullable=True
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), index=True)  # sales / manager / admin
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    # 账号（迁移 0019）：登录名唯一；停用后不能登录，已签发的 token 也立即失效
    username: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # 改密码、重置密码、停用时 +1，旧 token 作废
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductLine(TimestampMixin, Base):
    __tablename__ = "product_lines"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    pack: Mapped[str] = mapped_column(String(50))  # 行业包 id，如 llm_deploy
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ConfigOverride(TimestampMixin, Base):
    """管理员在网页上改过的配置（业务规则、行业包参数、产品价格）。

    文件（rules.yaml / catalog.json）是默认值，这里只存改动；删掉一行即恢复默认。
    scope：global（通用规则）或行业包 id；key：点分路径，如 margin.floor_rate、catalog.SRV-L20-4。
    """

    __tablename__ = "config_overrides"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_config_overrides_scope_key"),)

    scope: Mapped[str] = mapped_column(String(50))
    key: Mapped[str] = mapped_column(String(200))
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
