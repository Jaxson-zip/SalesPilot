"""报价分享链接 schema（接口契约 §35）。金额单位：分。公开视图不含成本、毛利、提成。"""

from datetime import date, datetime

from pydantic import BaseModel

from app.crm.schemas.quote import QuoteStatus
from app.packs.base import ClientCost


class QuoteShareOut(BaseModel):
    """负责人看到的分享状态：链接路径、有效期、甲方打开次数。"""

    token: str
    path: str  # 前端路由 /share/q/{token}，由前端拼上当前域名
    expires_at: datetime
    view_count: int
    last_viewed_at: datetime | None
    created_at: datetime


class PublicQuoteLine(BaseModel):
    name: str
    unit: str
    qty: int
    unit_price: int
    subtotal_price: int
    category: str


class PublicScope(BaseModel):
    """这一档报价的项目范围：交付端、功能模块名、交付方式，以及需求里有但这次不含的
    （经济版砍掉的二期功能、没报价的端）。只有软件外包这类行业包有。"""

    platforms: list[str] = []
    modules: list[str] = []
    team_size: int | None = None
    excluded_platforms: list[str] = []
    excluded_modules: list[str] = []


class PublicQuote(BaseModel):
    code: str
    status: QuoteStatus
    customer_name: str | None
    opportunity_name: str | None
    tier_name: str
    owner_name: str | None
    created_at: datetime
    valid_until: date
    items: list[PublicQuoteLine]
    list_price: int
    discount_rate: float
    total_price: int
    client_costs: list[ClientCost] = []
    scope: PublicScope | None = None
    terms: list[str] = []  # 条款与说明（templates.yaml，和打印版一样）
