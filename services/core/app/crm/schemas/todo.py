"""工作台待办里除任务以外的事项（todo_service）。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

TodoKind = Literal["payment_overdue", "payment_due", "report", "approval"]


class TodoItem(BaseModel):
    kind: TodoKind
    title: str
    subject: str = ""  # 客户名等，显示在标题下
    detail: str = ""
    due_date: date | None = None
    overdue: bool = False
    link: str  # 站内路由，点击跳转去处理
