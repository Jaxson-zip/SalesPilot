"""演示重置：每张表要么清空要么明确保留，新加的表不会被漏掉。"""

import app.crm.models  # noqa: F401  注册全部模型
from app.common.db import Base
from seed.__main__ import KEEP_TABLES, RESET_TABLES


def test_every_table_is_reset_or_kept() -> None:
    tables = set(Base.metadata.tables)
    assert "audit_logs" in RESET_TABLES
    assert not set(RESET_TABLES) & set(KEEP_TABLES)
    assert tables == set(RESET_TABLES) | set(KEEP_TABLES)
