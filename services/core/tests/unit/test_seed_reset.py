"""演示重置：每张表要么清空要么明确保留，新加的表不会被漏掉。"""

import app.crm.models  # noqa: F401  注册全部模型
from app.common.db import Base
from seed.__main__ import KEEP_TABLES, RESET_TABLES


def test_every_table_is_reset_or_kept() -> None:
    tables = set(Base.metadata.tables)
    assert "audit_logs" in RESET_TABLES
    assert not set(RESET_TABLES) & set(KEEP_TABLES)
    assert tables == set(RESET_TABLES) | set(KEEP_TABLES)


def test_reset_also_clears_langgraph_checkpoints() -> None:
    """回归：重置只清了会话表，对话内容留在 checkpoint 表里，重新登录还能看到旧对话。"""
    from unittest.mock import MagicMock

    from seed.__main__ import CHECKPOINT_TABLES, reset_business_data

    db = MagicMock()
    db.execute.return_value.scalar.return_value = "checkpoints"
    reset_business_data(db)
    sql = [str(call.args[0]) for call in db.execute.call_args_list]
    assert any(s.startswith("TRUNCATE " + ", ".join(CHECKPOINT_TABLES)) for s in sql)
