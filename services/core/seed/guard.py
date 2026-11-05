"""seed --reset 的确认：清库前列出要删的数据，必须明确确认。

线上曾有人照着文档跑了 --reset，试用账号录入的报销全部消失。现在：
- 交互终端里要输入 RESET 才继续；
- 非交互（docker compose exec -T、CI）必须带 --yes，否则直接退出、什么都不删。
"""

import sys
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

# 给人看的摘要：只列最常被试用者录入的几类
SUMMARY_TABLES = (
    ("customers", "客户"),
    ("opportunities", "商机"),
    ("quotes", "报价单"),
    ("expenses", "报销单"),
    ("contracts", "合同"),
    ("payments", "回款"),
)


def reset_summary(db: Session) -> str:
    parts = []
    for table, label in SUMMARY_TABLES:
        count = db.execute(text(f"select count(*) from {table}")).scalar_one()
        parts.append(f"{label} {count}")
    return "、".join(parts)


def confirm_reset(
    db: Session,
    assume_yes: bool,
    ask: Callable[[str], str] = input,
    interactive: bool | None = None,
) -> bool:
    """返回 True 才允许清库。"""
    summary = reset_summary(db)
    print(f"--reset 会清空全部业务数据（{summary}），包括试用者录入的，无法恢复。")
    if assume_yes:
        return True
    tty = sys.stdin.isatty() if interactive is None else interactive
    if not tty:
        print("非交互运行：确认无误后加 --yes 再执行。本次什么都没有删除。")
        return False
    if ask("确认清空请输入 RESET：").strip() != "RESET":
        print("已取消，什么都没有删除。")
        return False
    return True
