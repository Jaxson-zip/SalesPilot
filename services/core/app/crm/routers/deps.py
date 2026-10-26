"""路由公共依赖：数据库会话、分页参数。"""

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.crm.schemas.common import PageParams

DbDep = Annotated[Session, Depends(get_db)]


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


PageDep = Annotated[PageParams, Depends(page_params)]
