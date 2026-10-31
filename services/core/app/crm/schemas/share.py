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
    """需求清单里给甲方看的部分：交付端、功能模块名、交付方式（只有软件外包这类行业包有）。"""

    platforms: list[str] = []
    modules: list[str] = []
    team_size: int | None = None


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
