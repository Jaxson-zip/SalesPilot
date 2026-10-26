"""路由公共依赖：数据库会话、分页参数。"""

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.crm.schemas.common import PageParams

# scope="function"：在返回响应之前提交事务。默认的 request 作用域会在响应发出后才 commit，
# 前端「写完立刻读」（上传票据后马上刷新详情）可能读到提交前的旧数据。
# 回归：浏览器测试偶发看不到刚上传的票据（tests/unit/test_db_dep.py）
DbDep = Annotated[Session, Depends(get_db, scope="function")]


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


PageDep = Annotated[PageParams, Depends(page_params)]
