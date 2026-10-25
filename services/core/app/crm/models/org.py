"""组织：团队、用户、产品线（产品线 → 行业包映射由管理员维护）。"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
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


class ProductLine(TimestampMixin, Base):
    __tablename__ = "product_lines"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    pack: Mapped[str] = mapped_column(String(50))  # 行业包 id，如 llm_deploy
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
